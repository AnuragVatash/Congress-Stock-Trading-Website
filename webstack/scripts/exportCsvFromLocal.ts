/*
  Export OHLCV from local CSV/TXT files into a single CSV suitable for Supabase import.

  Inputs under ./us/** with rows like:
  <TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>

  Output columns (match your StockPrices table):
  asset_id,ticker,price_date,open,high,low,close,volume,adj_open,adj_high,adj_low,adj_close,adj_volume,split_factor,dividend,created_at,updated_at

  Defaults:
  - limit 50 tickers from Assets
  - last 1825 days (5 years)
  - PER = 'D'
  - output to ./exports/stock_prices_export.csv
*/

import { PrismaClient } from '@prisma/client';
import fg from 'fast-glob';
import fs from 'node:fs/promises';
import path from 'node:path';

type CliOptions = {
  rootDir: string;
  days: number;
  per: string;
  limit: number;
  outFile: string;
  restrictToAssets: boolean;
  concurrency: number;
};

const prisma = new PrismaClient();

function parseArgs(argv: string[]): CliOptions {
  const opts: CliOptions = {
    rootDir: path.resolve(process.cwd(), 'us'),
    days: 1825,
    per: 'D',
    limit: 50,
    outFile: path.resolve(process.cwd(), 'exports', 'stock_prices_export.csv'),
    restrictToAssets: true,
    concurrency: 4,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--root' || a === '--rootDir') opts.rootDir = path.resolve(argv[++i] ?? opts.rootDir);
    else if (a === '--days') opts.days = Number(argv[++i] ?? opts.days);
    else if (a === '--per') opts.per = String(argv[++i] ?? opts.per);
    else if (a === '--limit') opts.limit = Number(argv[++i] ?? opts.limit);
    else if (a === '--out' || a === '--outFile') opts.outFile = path.resolve(argv[++i] ?? opts.outFile);
    else if (a === '--concurrency') opts.concurrency = Number(argv[++i] ?? opts.concurrency);
    else if (a === '--no-restrict-to-assets') opts.restrictToAssets = false;
  }
  return opts;
}

function normalizeTicker(raw: string | null | undefined): string {
  const t = (raw ?? '').trim().toUpperCase();
  return t.endsWith('.US') ? t.slice(0, -3) : t;
}

function parseDate(dateStr: string): string | null {
  if (!dateStr) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return dateStr;
  if (/^\d{8}$/.test(dateStr)) {
    const y = dateStr.slice(0, 4);
    const m = dateStr.slice(4, 6);
    const d = dateStr.slice(6, 8);
    return `${y}-${m}-${d}`;
  }
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return null;
  return d.toISOString().slice(0, 10);
}

function csvEscape(val: string | number | null | undefined): string {
  if (val === null || val === undefined) return '';
  const s = String(val);
  if (s.includes(',') || s.includes('"') || s.includes('\n')) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

async function ensureOutDir(p: string): Promise<void> {
  const dir = path.dirname(p);
  await fs.mkdir(dir, { recursive: true });
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - opts.days);
  const cutoffKey = cutoff.toISOString().slice(0, 10);

  console.log('Export starting with options:', opts);
  await ensureOutDir(opts.outFile);

  // Build ticker -> asset_id map
  let assets: Array<{ asset_id: number; ticker: string | null; ticker_clean: string | null }> = await (prisma as any).assets.findMany({
    select: { asset_id: true, ticker: true, ticker_clean: true },
    orderBy: { asset_id: 'asc' },
    take: 10000,
  });
  // Filter to limit tickers
  const seen = new Set<string>();
  const selected: Array<{ key: string; asset_id: number }> = [];
  for (const a of assets) {
    const candidates = [a.ticker, a.ticker_clean].map(t => normalizeTicker(t ?? ''));
    for (const c of candidates) {
      if (!c) continue;
      if (!seen.has(c)) {
        seen.add(c);
        selected.push({ key: c, asset_id: (a as any).asset_id });
        break; // prefer first available
      }
    }
    if (selected.length >= opts.limit) break;
  }
  const allowed = new Set(selected.map(s => s.key));
  const tickerToAssetId = new Map(selected.map(s => [s.key, s.asset_id] as [string, number]));
  console.log(`Selected ${selected.length} tickers`);

  // Discover files then process only those matching selected tickers
  const pattern = path.join(opts.rootDir, '**/*.{csv,txt}').replace(/\\/g, '/');
  const files = await fg(pattern, { dot: false, onlyFiles: true });

  // Write header
  const header = [
    'asset_id','ticker','price_date','open','high','low','close','volume',
    'adj_open','adj_high','adj_low','adj_close','adj_volume','split_factor','dividend','created_at','updated_at'
  ].join(',') + '\n';
  await fs.writeFile(opts.outFile, header, 'utf8');

  let processed = 0;
  for (const file of files) {
    const base = path.basename(file).toUpperCase();
    const baseTicker = normalizeTicker(base.split('.')[0]);
    if (!allowed.has(baseTicker)) continue;

    const assetId = tickerToAssetId.get(baseTicker);
    if (!assetId) continue;

    const content = await fs.readFile(file, 'utf8');
    const lines = content.split(/\r?\n/);
    if (lines.length <= 1) continue;
    // skip header
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      const parts = line.split(',');
      if (parts.length < 9) continue;
      const [tkr, per, dateStr, _time, openStr, highStr, lowStr, closeStr, volStr] = parts;
      if (opts.per && String(per).toUpperCase() !== opts.per.toUpperCase()) continue;

      const dateKey = parseDate(dateStr);
      if (!dateKey) continue;
      if (dateKey < cutoffKey) continue;

      const outTicker = normalizeTicker(tkr);
      if (outTicker !== baseTicker) continue;

      const open = Number(openStr);
      const high = Number(highStr);
      const low = Number(lowStr);
      const close = Number(closeStr);
      const volume = Math.round(Number(volStr) || 0);
      if (!isFinite(open) || !isFinite(high) || !isFinite(low) || !isFinite(close)) continue;

      const row = [
        csvEscape(assetId),
        csvEscape(outTicker),
        csvEscape(dateKey),
        csvEscape(open),
        csvEscape(high),
        csvEscape(low),
        csvEscape(close),
        csvEscape(volume),
        '', '', '', '', '', '', '', '', '' // adjusted + split/div + timestamps left empty for defaults/nulls
      ].join(',') + '\n';
      await fs.appendFile(opts.outFile, row, 'utf8');
    }
    processed++;
    if (processed % 50 === 0) console.log(`Processed files: ${processed}`);
  }

  console.log(`Export complete. CSV at: ${opts.outFile}`);
}

main().catch(async (err) => {
  console.error('Export failed:', err);
  await prisma.$disconnect();
  process.exit(1);
}).then(async () => {
  await prisma.$disconnect();
});



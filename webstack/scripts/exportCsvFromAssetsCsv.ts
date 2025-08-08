/*
  Export OHLCV from local files for all assets listed in a CSV (snapshot of your Assets table),
  appending to an existing export file while avoiding duplicate tickers already exported.

  Inputs:
  - Assets CSV (e.g., exports/Assets_rows.csv) with columns including at least: asset_id, ticker, ticker_clean
  - Local OHLCV files under ./us/** named like <ticker>.us.txt with rows:
    <TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>

  Output:
  - Single CSV suitable for Supabase import: same header as previous export script

  Default filters:
  - PER=D (daily)
  - last 1095 days (3 years)
  - append to ./exports/stock_prices_export.csv, skipping tickers already present in that file
*/

import fg from 'fast-glob';
import fs from 'node:fs/promises';
import path from 'node:path';
import { parse as parseCsv } from 'csv-parse/sync';

type CliOptions = {
  assetsCsv: string;
  rootDir: string;
  days: number;
  per: string;
  outFile: string;
  append: boolean;
  concurrency: number;
};

function parseArgs(argv: string[]): CliOptions {
  const opts: CliOptions = {
    assetsCsv: path.resolve(process.cwd(), 'exports', 'Assets_rows.csv'),
    rootDir: path.resolve(process.cwd(), 'us'),
    days: 1095,
    per: 'D',
    outFile: path.resolve(process.cwd(), 'exports', 'stock_prices_export.csv'),
    append: true,
    concurrency: 4,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--assets' || a === '--assetsCsv') opts.assetsCsv = path.resolve(argv[++i] ?? opts.assetsCsv);
    else if (a === '--root' || a === '--rootDir') opts.rootDir = path.resolve(argv[++i] ?? opts.rootDir);
    else if (a === '--days') opts.days = Number(argv[++i] ?? opts.days);
    else if (a === '--per') opts.per = String(argv[++i] ?? opts.per);
    else if (a === '--out' || a === '--outFile') opts.outFile = path.resolve(argv[++i] ?? opts.outFile);
    else if (a === '--no-append') opts.append = false;
    else if (a === '--concurrency') opts.concurrency = Number(argv[++i] ?? opts.concurrency);
  }
  return opts;
}

function normalizeTicker(raw: string | null | undefined): string {
  const t = (raw ?? '').trim().toUpperCase();
  return t.endsWith('.US') ? t.slice(0, -3) : t;
}

function parseDateKey(dateStr: string): string | null {
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

async function fileExists(p: string): Promise<boolean> {
  try { await fs.access(p); return true; } catch { return false; }
}

async function ensureDirFor(p: string): Promise<void> {
  await fs.mkdir(path.dirname(p), { recursive: true });
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - opts.days);
  const cutoffKey = cutoff.toISOString().slice(0, 10);

  console.log('Export-from-assets starting with options:', opts);

  // 1) Read assets CSV
  const assetsRaw = await fs.readFile(opts.assetsCsv, 'utf8');
  const rows: any[] = parseCsv(assetsRaw, { columns: true, skip_empty_lines: true });

  // Build mapping: tickerNormalized -> asset_id (first occurrence wins), skip rows with no ticker/ticker_clean
  const tickerToAssetId = new Map<string, number>();
  for (const r of rows) {
    const assetId = Number(r.asset_id ?? r.ASSET_ID ?? r.id);
    const t1 = normalizeTicker(r.ticker ?? r.TICKER);
    const t2 = normalizeTicker(r.ticker_clean ?? r.TICKER_CLEAN);
    const candidate = t1 || t2;
    if (!assetId || !candidate) continue;
    if (!tickerToAssetId.has(candidate)) tickerToAssetId.set(candidate, assetId);
  }
  console.log(`Assets CSV tickers mapped: ${tickerToAssetId.size}`);

  // 2) Discover local files and index by ticker
  const pattern = path.join(opts.rootDir, '**/*.{csv,txt}').replace(/\\/g, '/');
  const files = await fg(pattern, { dot: false, onlyFiles: true });
  const tickerToFile = new Map<string, string>();
  // Prefer stocks over etfs if duplicates appear
  for (const file of files) {
    const base = path.basename(file).toUpperCase();
    const baseTicker = normalizeTicker(base.split('.')[0]);
    if (!baseTicker) continue;
    const lower = file.toLowerCase();
    const isStock = lower.includes('stocks');
    if (!tickerToFile.has(baseTicker) || isStock) tickerToFile.set(baseTicker, file);
  }
  console.log(`Local file index built: ${tickerToFile.size} tickers`);

  // 3) If appending, skip tickers already present in outFile
  await ensureDirFor(opts.outFile);
  const outExists = await fileExists(opts.outFile);
  const alreadyExported = new Set<string>();
  if (opts.append && outExists) {
    const existing = await fs.readFile(opts.outFile, 'utf8');
    const lines = existing.split(/\r?\n/);
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      const cols = [] as string[];
      let cur = '';
      let inQ = false;
      for (let c of line) {
        if (c === '"') { inQ = !inQ; continue; }
        if (c === ',' && !inQ) { cols.push(cur); cur = ''; } else { cur += c; }
      }
      cols.push(cur);
      const ticker = (cols[1] || '').toUpperCase();
      if (ticker) alreadyExported.add(ticker);
    }
    console.log(`Detected ${alreadyExported.size} tickers already in export`);
  }

  // 4) Write header if not appending or file not existing
  if (!opts.append || !outExists) {
    const header = [
      'asset_id','ticker','price_date','open','high','low','close','volume',
      'adj_open','adj_high','adj_low','adj_close','adj_volume','split_factor','dividend','created_at','updated_at'
    ].join(',') + '\n';
    await fs.writeFile(opts.outFile, header, 'utf8');
  }

  // 5) Process each asset ticker and append rows
  let writtenTickers = 0;
  let missingFiles = 0;
  for (const [ticker, assetId] of tickerToAssetId) {
    if (alreadyExported.has(ticker)) continue;
    const file = tickerToFile.get(ticker);
    if (!file) { missingFiles++; continue; }

    const content = await fs.readFile(file, 'utf8');
    const lines = content.split(/\r?\n/);
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      const parts = line.split(',');
      if (parts.length < 9) continue;
      const [tkr, per, dateStr, _time, openStr, highStr, lowStr, closeStr, volStr] = parts;
      if (opts.per && String(per).toUpperCase() !== opts.per.toUpperCase()) continue;
      const dateKey = parseDateKey(dateStr);
      if (!dateKey) continue;
      if (dateKey < cutoffKey) continue;
      if (normalizeTicker(tkr) !== ticker) continue;

      const open = Number(openStr);
      const high = Number(highStr);
      const low = Number(lowStr);
      const close = Number(closeStr);
      const volume = Math.round(Number(volStr) || 0);
      if (!isFinite(open) || !isFinite(high) || !isFinite(low) || !isFinite(close)) continue;

      const row = [
        csvEscape(assetId),
        csvEscape(ticker),
        csvEscape(dateKey),
        csvEscape(open),
        csvEscape(high),
        csvEscape(low),
        csvEscape(close),
        csvEscape(volume),
        '', '', '', '', '', '', '', '', ''
      ].join(',') + '\n';
      await fs.appendFile(opts.outFile, row, 'utf8');
    }
    writtenTickers++;
    if (writtenTickers % 25 === 0) console.log(`Appended data for ${writtenTickers} tickers so far...`);
  }

  console.log(`Done. Wrote new data for ${writtenTickers} tickers. Missing files for ${missingFiles} tickers.`);
}

main().catch(err => {
  console.error('Export-from-assets failed:', err);
  process.exit(1);
});



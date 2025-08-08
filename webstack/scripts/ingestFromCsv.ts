/*
  Ingest OHLCV CSV/TXT files into Postgres StockPrices.

  Expected columns per row:
  <TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>

  Notes:
  - Only daily rows (PER=D) are ingested by default.
  - Last 5 years by default (configurable via --days).
  - Duplicates are skipped by DB constraint (ticker+date unique).
  - Tickers are uppercased.
  - DATE can be YYYY-MM-DD or YYYYMMDD. TIME optional.
*/

import { PrismaClient } from '@prisma/client';
import fg from 'fast-glob';
import { parse } from 'csv-parse/sync';
import fs from 'node:fs/promises';
import path from 'node:path';

const prisma = new PrismaClient();

type CliOptions = {
  rootDir: string;
  days: number; // lookback window (e.g., 1825 for 5 years)
  per: string; // expected period flag in PER column (default 'D')
  concurrency: number;
  dryRun: boolean;
  restrictToAssets: boolean;
};

function parseArgs(argv: string[]): CliOptions {
  const opts: CliOptions = {
    rootDir: path.resolve(process.cwd(), 'us'),
    days: 1825,
    per: 'D',
    concurrency: 4,
    dryRun: false,
    restrictToAssets: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--root' || a === '--rootDir') opts.rootDir = path.resolve(argv[++i] ?? opts.rootDir);
    else if (a === '--days') opts.days = Number(argv[++i] ?? opts.days);
    else if (a === '--per') opts.per = String(argv[++i] ?? opts.per);
    else if (a === '--concurrency') opts.concurrency = Number(argv[++i] ?? opts.concurrency);
    else if (a === '--dry-run' || a === '--dryRun') opts.dryRun = true;
    else if (a === '--restrict-to-assets' || a === '--restrictToAssets') opts.restrictToAssets = true;
  }
  return opts;
}

function parseDate(dateStr: string, timeStr?: string): Date | null {
  if (!dateStr) return null;
  let yyyy = 0, mm = 0, dd = 0;
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    const [y, m, d] = dateStr.split('-').map(Number);
    yyyy = y; mm = m; dd = d;
  } else if (/^\d{8}$/.test(dateStr)) {
    yyyy = Number(dateStr.slice(0, 4));
    mm = Number(dateStr.slice(4, 6));
    dd = Number(dateStr.slice(6, 8));
  } else {
    // Fallback: try Date constructor
    const dt = new Date(dateStr);
    return isNaN(dt.getTime()) ? null : dt;
  }

  let hh = 0, mi = 0, ss = 0;
  if (timeStr && timeStr.trim() !== '' && timeStr !== '0') {
    if (/^\d{6}$/.test(timeStr)) {
      hh = Number(timeStr.slice(0, 2));
      mi = Number(timeStr.slice(2, 4));
      ss = Number(timeStr.slice(4, 6));
    } else if (/^\d{2}:\d{2}(:\d{2})?$/.test(timeStr)) {
      const parts = timeStr.split(':').map(Number);
      hh = parts[0] ?? 0; mi = parts[1] ?? 0; ss = parts[2] ?? 0;
    }
  }
  // Construct as UTC to avoid TZ drift
  const dt = new Date(Date.UTC(yyyy, mm - 1, dd, hh, mi, ss, 0));
  return isNaN(dt.getTime()) ? null : dt;
}

function normalizeTicker(raw: string): string {
  const t = (raw || '').trim().toUpperCase();
  // Strip common suffixes like .US from file/row
  return t.endsWith('.US') ? t.slice(0, -3) : t;
}

async function ingestFile(filePath: string, cutoffDate: Date, perWanted: string, dryRun: boolean, allowedTickers?: Set<string>, tickerToAssetId?: Map<string, number>): Promise<{ inserted: number; skipped: number }> {
  // Fast pre-filter by filename ticker when restricting
  if (allowedTickers && allowedTickers.size > 0) {
    const base = path.basename(filePath).toUpperCase();
    const maybeTicker = normalizeTicker(base.split('.')[0]);
    if (!allowedTickers.has(maybeTicker)) {
      return { inserted: 0, skipped: 0 };
    }
  }

  const buf = await fs.readFile(filePath, 'utf8');
  // Robust parse: allow both CSV and TXT with commas
  const records: string[][] = parse(buf, {
    relaxQuotes: true,
    relaxColumnCount: true,
    skipEmptyLines: true,
  });

  const toInsert: Array<{
    ticker: string;
    date: Date;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: bigint;
    asset_id?: number;
  }> = [];

  for (const rec of records) {
    if (rec.length < 9) continue; // require at least up to VOL
    const first = String(rec[0] ?? '').toUpperCase();
    // Skip header rows
    if (first === 'TICKER' || first === '<TICKER>') continue;

    const [tickerRaw, per, dateStr, timeStr, openStr, highStr, lowStr, closeStr, volStr] = rec as string[];
    if (perWanted && String(per).toUpperCase() !== perWanted.toUpperCase()) continue;

    const ticker = normalizeTicker(tickerRaw);
    if (allowedTickers && allowedTickers.size > 0 && !allowedTickers.has(ticker)) continue;
    const date = parseDate(String(dateStr), String(timeStr));
    if (!ticker || !date) continue;
    if (date < cutoffDate) continue;

    const open = Number(openStr);
    const high = Number(highStr);
    const low = Number(lowStr);
    const close = Number(closeStr);
    const vol = BigInt(Math.max(0, Math.floor(Number(volStr) || 0)));

    if (!isFinite(open) || !isFinite(high) || !isFinite(low) || !isFinite(close)) continue;

    const assetId = tickerToAssetId?.get(ticker);
    toInsert.push({
      ticker,
      date,
      open,
      high,
      low,
      close,
      volume: vol,
      asset_id: assetId,
    });
  }

  if (toInsert.length === 0) return { inserted: 0, skipped: 0 };

  if (dryRun) return { inserted: toInsert.length, skipped: 0 };

  // Batch insert with skipDuplicates
  const batchSize = 1000;
  let inserted = 0;
  for (let i = 0; i < toInsert.length; i += batchSize) {
    const chunk = toInsert.slice(i, i + batchSize);
    try {
      const res = await prisma.stockPrices.createMany({ data: chunk, skipDuplicates: true });
      inserted += res.count;
    } catch (err) {
      console.error(`Failed inserting batch for ${filePath}:`, err);
    }
  }
  return { inserted, skipped: toInsert.length - inserted };
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - opts.days);

  console.log('CSV ingest starting with options:', opts);

  // Discover files under rootDir (csv/txt)
  const pattern = path.join(opts.rootDir, '**/*.{csv,txt}').replace(/\\/g, '/');
  const files = await fg(pattern, { dot: false, onlyFiles: true });
  console.log(`Discovered ${files.length} files`);

  // Optionally restrict to tickers present in Assets table
  let allowed: Set<string> | undefined;
  let tickerToAssetId: Map<string, number> | undefined;
  if (opts.restrictToAssets) {
    console.log('Restricting to tickers present in Assets table...');
    const assets = await prisma.assets.findMany({ select: { ticker: true, asset_id: true, ticker_clean: true } as any });
    allowed = new Set(
      assets
        .flatMap((a: any) => [a.ticker, a.ticker_clean])
        .map((t: string | null) => (t ?? '').toUpperCase())
        .map((t: string) => (t.endsWith('.US') ? t.slice(0, -3) : t))
        .filter((t: string) => !!t)
    );
    tickerToAssetId = new Map(
      assets.flatMap((a: any) => {
        const keys: string[] = [];
        if (a.ticker) keys.push(normalizeTicker(a.ticker));
        if (a.ticker_clean) keys.push(normalizeTicker(a.ticker_clean));
        return keys.map(k => [k, a.asset_id] as [string, number]);
      })
    );
    console.log(`Allowlist contains ${allowed.size} tickers`);
  }

  // Simple concurrency control
  const workers = Math.max(1, Math.min(opts.concurrency, 16));
  let index = 0;
  let totalInserted = 0;
  let totalSkipped = 0;

  async function worker(id: number) {
    while (true) {
      const i = index++;
      if (i >= files.length) break;
      const file = files[i];
      try {
        const { inserted, skipped } = await ingestFile(file, cutoff, opts.per, opts.dryRun, allowed, tickerToAssetId);
        totalInserted += inserted;
        totalSkipped += skipped;
        if ((i + 1) % 100 === 0) {
          console.log(`[${i + 1}/${files.length}] Inserted: ${totalInserted}, Skipped: ${totalSkipped}`);
        }
      } catch (e) {
        console.error(`Error processing ${file}:`, e);
      }
    }
  }

  const start = Date.now();
  await Promise.all(Array.from({ length: workers }, (_, i) => worker(i)));
  const ms = Date.now() - start;
  console.log(`CSV ingest done in ${(ms / 1000).toFixed(1)}s. Inserted: ${totalInserted}, Skipped: ${totalSkipped}`);
}

main()
  .catch(err => {
    console.error('Fatal error during CSV ingest:', err);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });



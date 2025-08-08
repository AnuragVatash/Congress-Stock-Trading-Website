/*
  Split a combined CSV (exported for Supabase) into per-ticker JSON files
  under public/price-data/<TICKER>.json for static serving on Vercel.

  Input CSV columns:
  asset_id,ticker,price_date,open,high,low,close,volume,adj_open,adj_high,adj_low,adj_close,adj_volume,split_factor,dividend,created_at,updated_at

  Output JSON (per ticker):
  [ { date: 'YYYY-MM-DD', open: number, high: number, low: number, close: number, volume: number } ]
*/

import fs from 'node:fs/promises';
import path from 'node:path';

type CliOptions = { inFile: string; outDir: string; };

function parseArgs(argv: string[]): CliOptions {
  const opts: CliOptions = {
    inFile: path.resolve(process.cwd(), 'exports', 'stock_prices_export.csv'),
    outDir: path.resolve(process.cwd(), 'public', 'price-data'),
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--in' || a === '--inFile') opts.inFile = path.resolve(argv[++i] ?? opts.inFile);
    else if (a === '--out' || a === '--outDir') opts.outDir = path.resolve(argv[++i] ?? opts.outDir);
  }
  return opts;
}

async function ensureDir(p: string): Promise<void> {
  await fs.mkdir(p, { recursive: true });
}

function parseCsvLine(line: string): string[] {
  const cols: string[] = [];
  let cur = '';
  let inQ = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') {
      // toggle quote, handle escaped quotes by doubling
      if (inQ && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else {
        inQ = !inQ;
      }
      continue;
    }
    if (c === ',' && !inQ) {
      cols.push(cur);
      cur = '';
    } else {
      cur += c;
    }
  }
  cols.push(cur);
  return cols;
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  console.log('Splitting CSV to per-ticker JSON:', opts);
  await ensureDir(opts.outDir);

  const content = await fs.readFile(opts.inFile, 'utf8');
  const lines = content.split(/\r?\n/);
  if (lines.length <= 1) {
    console.log('No data lines found.');
    return;
  }

  // header
  const header = parseCsvLine(lines[0]);
  const idxTicker = header.indexOf('ticker');
  const idxDate = header.indexOf('price_date');
  const idxOpen = header.indexOf('open');
  const idxHigh = header.indexOf('high');
  const idxLow = header.indexOf('low');
  const idxClose = header.indexOf('close');
  const idxVolume = header.indexOf('volume');
  if ([idxTicker, idxDate, idxOpen, idxHigh, idxLow, idxClose, idxVolume].some(i => i < 0)) {
    throw new Error('Missing required columns in CSV header');
  }

  const map = new Map<string, { date: string; open: number; high: number; low: number; close: number; volume: number; }[]>();

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const cols = parseCsvLine(line);
    const tkr = (cols[idxTicker] || '').toUpperCase();
    const date = (cols[idxDate] || '').slice(0, 10);
    const open = Number(cols[idxOpen]);
    const high = Number(cols[idxHigh]);
    const low = Number(cols[idxLow]);
    const close = Number(cols[idxClose]);
    const volume = Math.round(Number(cols[idxVolume]) || 0);
    if (!tkr || !date || !isFinite(open) || !isFinite(high) || !isFinite(low) || !isFinite(close)) continue;
    const arr = map.get(tkr) ?? [];
    arr.push({ date, open, high, low, close, volume });
    map.set(tkr, arr);
  }

  // Write each ticker JSON sorted by date
  let written = 0;
  for (const [tkr, arr] of map) {
    arr.sort((a, b) => a.date.localeCompare(b.date));
    const outPath = path.join(opts.outDir, `${tkr}.json`);
    await fs.writeFile(outPath, JSON.stringify(arr), 'utf8');
    written++;
    if (written % 200 === 0) console.log(`Wrote ${written} JSON files...`);
  }
  console.log(`Done. Wrote ${written} JSON files to ${opts.outDir}`);
}

main().catch(err => {
  console.error('Split export failed:', err);
  process.exit(1);
});



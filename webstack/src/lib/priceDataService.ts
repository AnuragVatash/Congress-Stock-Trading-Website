// webstack/src/lib/priceDataService.ts

import { prisma } from './prisma';

export interface PriceDataPoint {
  date: Date;
  price: number;
  volume: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface TradeDataPoint {
  date: Date;
  price: number;
  type: 'buy' | 'sell';
  amount: number;
  memberName: string;
  memberId: number;
}

export interface DateRange {
  start: Date;
  end: Date;
}

export function getDateRangeFromTransactions(transactions: any[]): DateRange {
  if (transactions.length === 0) {
    const end = new Date();
    const start = new Date();
    start.setFullYear(start.getFullYear() - 1);
    return { start, end };
  }

  const dates = transactions
    .map(t => t.transaction_date)
    .filter(date => date)
    .map(date => new Date(date))
    .sort((a, b) => a.getTime() - b.getTime());

  if (dates.length === 0) {
    const end = new Date();
    const start = new Date();
    start.setFullYear(start.getFullYear() - 1);
    return { start, end };
  }

  // Add some padding around the date range
  const start = new Date(dates[0]);
  start.setDate(start.getDate() - 30); // 30 days before first trade

  const end = new Date(dates[dates.length - 1]);
  end.setDate(end.getDate() + 30); // 30 days after last trade

  return { start, end };
}

export async function getRealPriceData(
  ticker: string, 
  startDate: Date, 
  endDate: Date
): Promise<PriceDataPoint[]> {
  // Skip DB entirely if disabled or not configured
  const dbDisabled = (process.env.PRICE_DATA_DISABLE_DB || '').toLowerCase() === 'true' || process.env.PRICE_DATA_DISABLE_DB === '1';
  if (dbDisabled || !process.env.DATABASE_URL) {
    return [];
  }
  try {
    // Using any to bypass the Prisma client type issue until it's regenerated
    const priceRecords = await (prisma as any).stockPrices.findMany({
      where: {
        ticker: ticker.toUpperCase(),
        date: {
          gte: startDate,
          lte: endDate
        }
      },
      orderBy: {
        date: 'asc'
      }
    });

    return priceRecords.map((record: any) => ({
      date: record.date,
      price: record.adj_close || record.close,
      volume: Number(record.volume),
      open: record.adj_open || record.open,
      high: record.adj_high || record.high,
      low: record.adj_low || record.low,
      close: record.adj_close || record.close
    }));

  } catch (error) {
    // Suppress noisy DB errors when the table doesn't exist in this env
    if (process.env.NODE_ENV !== 'production') {
      console.warn(`DB price fetch failed for ${ticker}. Falling back to static JSON.`);
    }
    return [];
  }
}

async function getPriceDataFromYFinanceService(
  ticker: string,
  startDate: Date,
  endDate: Date
): Promise<PriceDataPoint[]> {
  try {
    const start = startDate.toISOString().slice(0, 10);
    const end = endDate.toISOString().slice(0, 10);

    const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';
    const url = new URL(`/api/stock-prices/${encodeURIComponent(ticker)}`, baseUrl);
    url.searchParams.set('start', start);
    url.searchParams.set('end', end);
    url.searchParams.set('interval', '1d');

    const res = await fetch(url.toString(), { next: { revalidate: 300 } });
    if (!res.ok) {
      console.warn(`YFinance service returned status ${res.status}`);
      return [];
    }
    const json = await res.json();
    const prices = Array.isArray(json?.prices) ? json.prices : [];
    return prices.map((p: any) => ({
      date: new Date(p.date),
      price: typeof p.adj_close === 'number' && p.adj_close > 0 ? p.adj_close : p.close,
      volume: Number(p.volume) || 0,
      open: typeof p.adj_open === 'number' && p.adj_open > 0 ? p.adj_open : p.open,
      high: typeof p.adj_high === 'number' && p.adj_high > 0 ? p.adj_high : p.high,
      low: typeof p.adj_low === 'number' && p.adj_low > 0 ? p.adj_low : p.low,
      close: typeof p.adj_close === 'number' && p.adj_close > 0 ? p.adj_close : p.close,
    }));
  } catch (error) {
    console.error(`Error fetching price data from yfinance service for ${ticker}:`, error);
    return [];
  }
}

async function getPriceDataFromStaticJson(
  ticker: string,
  startDate: Date,
  endDate: Date
): Promise<PriceDataPoint[]> {
  try {
    const upper = ticker.toUpperCase();
    const explicitBase = process.env.PRICE_DATA_BASE_URL;
    const bucket = process.env.PRICE_DATA_BUCKET || 'price-data';
    const supabaseUrl = process.env.PRICE_DATA_SUPABASE_URL || process.env.PRICE_DATA_NEXT_PUBLIC_SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;

    let finalUrl: string;
    if (explicitBase && explicitBase.length > 0) {
      const base = explicitBase.replace(/\/$/, '');
      finalUrl = `${base}/${encodeURIComponent(upper)}.json`;
    } else if (supabaseUrl && supabaseUrl.length > 0) {
      const sb = supabaseUrl.replace(/\/$/, '');
      finalUrl = `${sb}/storage/v1/object/public/${encodeURIComponent(bucket)}/${encodeURIComponent(upper)}.json`;
    } else {
      const site = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';
      finalUrl = new URL(`/price-data/${encodeURIComponent(upper)}.json`, site).toString();
    }

    let res = await fetch(finalUrl, { next: { revalidate: 3600 } });
    if (!res.ok && (res.status === 400 || res.status === 404)) {
      // Retry with ?download in case storage expects it
      const retryUrl = finalUrl.includes('?') ? `${finalUrl}&download=1` : `${finalUrl}?download=1`;
      res = await fetch(retryUrl, { next: { revalidate: 3600 } });
      if (!res.ok) {
        if (process.env.NODE_ENV !== 'production') {
          console.warn(`Static price JSON fetch failed for ${ticker}:`, res.status, finalUrl);
        }
        return [];
      }
    }
    const arr = await res.json();
    if (!Array.isArray(arr)) return [];
    const startMs = startDate.getTime();
    const endMs = endDate.getTime();
    return arr
      .map((p: any) => ({
        date: new Date(p.date),
        price: typeof p.adj_close === 'number' ? p.adj_close : (p.close as number),
        volume: Number(p.volume) || 0,
        open: typeof p.adj_open === 'number' ? p.adj_open : (p.open as number),
        high: typeof p.adj_high === 'number' ? p.adj_high : (p.high as number),
        low: typeof p.adj_low === 'number' ? p.adj_low : (p.low as number),
        close: typeof p.adj_close === 'number' ? p.adj_close : (p.close as number),
      }))
      .filter(p => {
        const t = p.date.getTime();
        return t >= startMs && t <= endMs;
      })
      .sort((a, b) => a.date.getTime() - b.date.getTime());
  } catch {
    return [];
  }
}

export async function hasStoredPriceData(ticker: string): Promise<boolean> {
  try {
    const count = await (prisma as any).stockPrices.count({
      where: {
        ticker: ticker.toUpperCase()
      }
    });
    return count > 0;
  } catch (error) {
    console.error(`Error checking stored price data for ${ticker}:`, error);
    return false;
  }
}

// Fallback to generate mock data if no real data is available
export function generateMockPriceData(
  ticker: string, 
  startDate: Date, 
  endDate: Date
): PriceDataPoint[] {
  const data: PriceDataPoint[] = [];
  const currentDate = new Date(startDate);
  
  // Base price varies by ticker
  const basePrices: Record<string, number> = {
    'AAPL': 150,
    'TSLA': 200,
    'MSFT': 300,
    'GOOGL': 2500,
    'AMZN': 3000,
    'NVDA': 400,
    'META': 250,
  };
  
  let currentPrice = basePrices[ticker.toUpperCase()] || 100;
  
  while (currentDate <= endDate) {
    // Skip weekends
    if (currentDate.getDay() !== 0 && currentDate.getDay() !== 6) {
      // Random daily change between -5% and +5%
      const changePercent = (Math.random() - 0.5) * 0.1;
      const priceChange = currentPrice * changePercent;
      currentPrice = Math.max(1, currentPrice + priceChange);
      
      const open = currentPrice * (0.99 + Math.random() * 0.02);
      const close = currentPrice;
      const high = Math.max(open, close) * (1 + Math.random() * 0.03);
      const low = Math.min(open, close) * (0.97 + Math.random() * 0.03);
      const volume = Math.floor(Math.random() * 10000000) + 1000000;
      
      data.push({
        date: new Date(currentDate),
        price: close,
        volume,
        open,
        high,
        low,
        close
      });
    }
    
    currentDate.setDate(currentDate.getDate() + 1);
  }
  
  return data;
}

export async function getPriceDataForDateRange(
  ticker: string, 
  startDate: Date, 
  endDate: Date
): Promise<PriceDataPoint[]> {
  // Prefer static JSON from public/price-data first
  const staticData = await getPriceDataFromStaticJson(ticker, startDate, endDate);
  if (staticData.length > 0) return staticData;

  // Then try DB if available
  const realData = await getRealPriceData(ticker, startDate, endDate);
  if (realData.length > 0) return realData;

  // No data
  return [];
}

export function generateTradeDataPoints(
  transactions: any[], 
  priceData: PriceDataPoint[]
): TradeDataPoint[] {
  if (!transactions || transactions.length === 0 || priceData.length === 0) {
    return [];
  }

  const tradeData: TradeDataPoint[] = [];
  
  transactions.forEach(transaction => {
    if (!transaction.transaction_date) return;
    
    const tradeDate = new Date(transaction.transaction_date);
    
    // Find the closest price data point
    const closestPriceData = priceData.reduce((closest, current) => {
      const currentDiff = Math.abs(current.date.getTime() - tradeDate.getTime());
      const closestDiff = Math.abs(closest.date.getTime() - tradeDate.getTime());
      return currentDiff < closestDiff ? current : closest;
    });
    
    if (closestPriceData) {
      const isLikelyBuy = transaction.transaction_type?.toLowerCase().includes('purchase') || 
                         transaction.transaction_type?.toLowerCase().includes('buy');
      
      const memberName = transaction.Filings?.Members?.name || 'Unknown Member';
      const memberId = transaction.Filings?.Members?.member_id || 0;
      
      const avgAmount = ((transaction.amount_range_low || 0) + (transaction.amount_range_high || 0)) / 2;
      
      tradeData.push({
        date: tradeDate,
        price: closestPriceData.price,
        type: isLikelyBuy ? 'buy' : 'sell',
        amount: avgAmount,
        memberName,
        memberId
      });
    }
  });
  
  return tradeData.sort((a, b) => a.date.getTime() - b.date.getTime());
}

// Keep backward compatibility with the old mock data service
export const getMockPriceDataForDateRange = getPriceDataForDateRange; 
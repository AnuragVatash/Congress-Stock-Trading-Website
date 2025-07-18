// webstack/scripts/ingestPrices.ts

import { PrismaClient } from '@prisma/client';
import TiingoService, { TiingoPriceData } from '../src/lib/tiingoService';

const prisma = new PrismaClient();
const tiingo = new TiingoService();

interface IngestOptions {
  ticker?: string;
  startDate?: string;
  endDate?: string;
  limit?: number;
  recentOnly?: boolean;
}

async function getDistinctTickers(limit?: number): Promise<string[]> {
  const assets = await prisma.assets.findMany({
    where: {
      ticker: {
        not: null
      },
      Transactions: {
        some: {}
      }
    },
    select: {
      ticker: true,
      _count: {
        select: {
          Transactions: true
        }
      }
    },
    orderBy: {
      Transactions: {
        _count: 'desc'
      }
    },
    take: limit
  });

  return assets
    .map(asset => asset.ticker)
    .filter((ticker): ticker is string => ticker !== null);
}

async function getRecentlyTradedTickers(dayLimit = 90): Promise<string[]> {
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - dayLimit);

  const assets = await prisma.assets.findMany({
    where: {
      ticker: {
        not: null
      },
      Transactions: {
        some: {
          transaction_date: {
            gte: cutoffDate
          }
        }
      }
    },
    select: {
      ticker: true
    }
  });

  return assets
    .map(asset => asset.ticker)
    .filter((ticker): ticker is string => ticker !== null);
}

async function storePriceData(ticker: string, priceData: TiingoPriceData[]): Promise<number> {
  if (priceData.length === 0) {
    console.log(`No price data to store for ${ticker}`);
    return 0;
  }

  let stored = 0;
  
  for (const price of priceData) {
    try {
      await prisma.stockPrices.upsert({
        where: {
          ticker_date: {
            ticker: ticker.toUpperCase(),
            date: new Date(price.date)
          }
        },
        update: {
          open: price.open,
          high: price.high,
          low: price.low,
          close: price.close,
          volume: BigInt(price.volume),
          adj_open: price.adjOpen,
          adj_high: price.adjHigh,
          adj_low: price.adjLow,
          adj_close: price.adjClose,
          adj_volume: BigInt(price.adjVolume),
          split_factor: price.splitFactor,
          dividend: price.divCash,
          updated_at: new Date()
        },
        create: {
          ticker: ticker.toUpperCase(),
          date: new Date(price.date),
          open: price.open,
          high: price.high,
          low: price.low,
          close: price.close,
          volume: BigInt(price.volume),
          adj_open: price.adjOpen,
          adj_high: price.adjHigh,
          adj_low: price.adjLow,
          adj_close: price.adjClose,
          adj_volume: BigInt(price.adjVolume),
          split_factor: price.splitFactor,
          dividend: price.divCash
        }
      });
      stored++;
    } catch (error) {
      console.error(`Error storing price data for ${ticker} on ${price.date}:`, error);
    }
  }

  console.log(`Stored ${stored} price records for ${ticker}`);
  return stored;
}

async function ingestPricesForTicker(
  ticker: string, 
  startDate?: string, 
  endDate?: string
): Promise<void> {
  try {
    console.log(`\n=== Processing ${ticker} ===`);
    
    // Check if we already have recent data
    const latestPrice = await prisma.stockPrices.findFirst({
      where: { ticker: ticker.toUpperCase() },
      orderBy: { date: 'desc' }
    });

    let fetchStartDate = startDate;
    if (!fetchStartDate && latestPrice) {
      // Start from the day after our latest data
      const nextDay = new Date(latestPrice.date);
      nextDay.setDate(nextDay.getDate() + 1);
      fetchStartDate = nextDay.toISOString().split('T')[0];
      
      console.log(`Latest data: ${latestPrice.date.toISOString().split('T')[0]}, fetching from: ${fetchStartDate}`);
    } else if (!fetchStartDate) {
      // Default to 2 years of history for new tickers
      const twoYearsAgo = new Date();
      twoYearsAgo.setFullYear(twoYearsAgo.getFullYear() - 2);
      fetchStartDate = twoYearsAgo.toISOString().split('T')[0];
      
      console.log(`New ticker, fetching from: ${fetchStartDate}`);
    }

    // Skip if we're already up to date
    if (fetchStartDate && endDate && fetchStartDate > endDate) {
      console.log(`${ticker} is already up to date`);
      return;
    }

    const priceData = await tiingo.getHistoricalPrices(ticker, fetchStartDate, endDate);
    
    if (priceData.length > 0) {
      await storePriceData(ticker, priceData);
      console.log(`✓ Successfully processed ${ticker}`);
    } else {
      console.log(`⚠ No new price data for ${ticker}`);
    }

  } catch (error) {
    console.error(`✗ Error processing ${ticker}:`, error);
  }
}

async function main() {
  const args = process.argv.slice(2);
  const options: IngestOptions = {};

  // Parse command line arguments
  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--ticker':
        options.ticker = args[++i];
        break;
      case '--start-date':
        options.startDate = args[++i];
        break;
      case '--end-date':
        options.endDate = args[++i];
        break;
      case '--limit':
        options.limit = parseInt(args[++i]);
        break;
      case '--recent-only':
        options.recentOnly = true;
        break;
      case '--help':
        console.log(`
Usage: npm run ingest-prices [options]

Options:
  --ticker <symbol>     Ingest prices for a specific ticker
  --start-date <date>   Start date (YYYY-MM-DD)
  --end-date <date>     End date (YYYY-MM-DD)
  --limit <number>      Limit number of tickers to process
  --recent-only         Only process recently traded tickers (last 90 days)
  --help               Show this help message

Examples:
  npm run ingest-prices --ticker AAPL
  npm run ingest-prices --recent-only --limit 10
  npm run ingest-prices --start-date 2024-01-01 --end-date 2024-12-31
        `);
        process.exit(0);
    }
  }

  console.log('🚀 Starting price data ingestion...');
  console.log('Configuration:', options);

  try {
    let tickers: string[];

    if (options.ticker) {
      tickers = [options.ticker];
    } else if (options.recentOnly) {
      console.log('Getting recently traded tickers...');
      tickers = await getRecentlyTradedTickers();
    } else {
      console.log('Getting all distinct tickers...');
      tickers = await getDistinctTickers(options.limit);
    }

    console.log(`Found ${tickers.length} tickers to process`);
    
    if (tickers.length === 0) {
      console.log('No tickers found to process');
      return;
    }

    let processed = 0;
    for (const ticker of tickers) {
      await ingestPricesForTicker(ticker, options.startDate, options.endDate);
      processed++;
      
      console.log(`Progress: ${processed}/${tickers.length} (${((processed/tickers.length)*100).toFixed(1)}%)`);
      
      // Add a small delay between tickers to be respectful
      if (processed < tickers.length) {
        console.log('Waiting before next ticker...');
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
    }

    console.log('\n✅ Price ingestion completed successfully!');
    
    // Summary stats
    const totalPriceRecords = await prisma.stockPrices.count();
    const uniqueTickers = await prisma.stockPrices.groupBy({
      by: ['ticker']
    });
    
    console.log(`\n📊 Summary:`);
    console.log(`- Total price records: ${totalPriceRecords.toLocaleString()}`);
    console.log(`- Unique tickers with price data: ${uniqueTickers.length}`);

  } catch (error) {
    console.error('❌ Error during price ingestion:', error);
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

// Handle graceful shutdown
process.on('SIGINT', async () => {
  console.log('\n⏹ Received SIGINT, shutting down gracefully...');
  await prisma.$disconnect();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('\n⏹ Received SIGTERM, shutting down gracefully...');
  await prisma.$disconnect();
  process.exit(0);
});

if (require.main === module) {
  main().catch(console.error);
}

export { ingestPricesForTicker, getDistinctTickers, getRecentlyTradedTickers }; 
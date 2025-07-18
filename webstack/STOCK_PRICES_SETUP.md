# Stock Price Data Implementation Setup

This guide explains how to set up and use the stock price data system that integrates with Tiingo API for real stock price data.

## Overview

The system can:

- Fetch and store historical stock prices from Tiingo API
- Use real data when available, fallback to mock data otherwise
- Display price charts with congressional trade overlays
- Respect API rate limits (50 requests/hour for free tier)

## Setup Steps

### 1. Environment Configuration

Create a `.env.local` file in the `webstack` directory with:

```env
# Database
DATABASE_URL="file:../../db/combined_trades.db"

# Tiingo API Configuration
# Get your free API key from https://api.tiingo.com/
TIINGO_API_KEY=your_tiingo_api_key_here
TIINGO_BASE_URL=https://api.tiingo.com

# App Configuration
NODE_ENV=development
```

### 2. Get Tiingo API Key

1. Go to https://api.tiingo.com/
2. Sign up for a free account
3. Get your API token from the dashboard
4. Add it to your `.env.local` file

**Free Tier Limits:**

- 1,000 API calls per day
- 50 calls per hour
- Historical data back to 2004+ for most tickers

### 3. Database Migration

The database schema has already been updated with the `StockPrices` table. If you need to apply the migration:

```bash
npm run db:migrate
```

### 4. Generate Prisma Client

```bash
npm run db:generate
```

## Usage

### Ingesting Price Data

The system provides several options for fetching and storing price data:

#### Ingest specific ticker

```bash
npm run ingest-prices -- --ticker AAPL
```

#### Ingest recently traded stocks (last 90 days)

```bash
npm run ingest-prices -- --recent-only --limit 10
```

#### Ingest all stocks with congressional trades

```bash
npm run ingest-prices -- --limit 50
```

#### Ingest with date range

```bash
npm run ingest-prices -- --start-date 2024-01-01 --end-date 2024-12-31 --recent-only
```

#### Get help

```bash
npm run ingest-prices -- --help
```

### Rate Limiting

The system automatically handles Tiingo's rate limits:

- Waits 75 seconds between requests to stay under 50/hour
- Tracks request count and resets hourly
- Graceful error handling for rate limit exceeded

### Data Flow

1. **Real Data**: System first tries to fetch from local database
2. **Fallback**: If no real data exists, generates mock data for visualization
3. **Updates**: Only fetches new data since last stored date
4. **Storage**: Uses upsert to handle existing records

### Chart Integration

The charts automatically use real data when available:

```typescript
// In components, the price service handles the data source
import { getPriceDataForDateRange } from "@/src/lib/priceDataService";

// This will use real data if available, mock data otherwise
const priceData = await getPriceDataForDateRange(ticker, startDate, endDate);
```

## Production Recommendations

### Nightly Updates

Set up a cron job or GitHub Action to run:

```bash
npm run ingest-prices -- --recent-only --limit 40
```

This stays within the 1,000 daily limit while keeping recently traded stocks up to date.

### Caching Strategy

- Price data is stored locally and served from database
- Charts only query the database, not the API
- Consider adding Redis cache for frequently accessed price data

### Scaling Considerations

If you exceed free tier limits:

1. **Tiingo Power ($99/mo)**: 50,000 requests/day, real-time data
2. **Polygon.io**: Good for recent data (2+ years), competitive pricing
3. **Alpha Vantage**: 500 requests/day free tier
4. **Bulk Data**: Tiingo offers bulk historical files for one-time backfill

## File Structure

```
webstack/
├── src/lib/
│   ├── tiingoService.ts        # Tiingo API client
│   ├── priceDataService.ts     # Price data service (real + mock)
│   └── mockPriceData.ts        # Old mock data (deprecated)
├── scripts/
│   └── ingestPrices.ts         # Price ingestion script
├── prisma/
│   └── schema.prisma           # Updated with StockPrices model
└── STOCK_PRICES_SETUP.md       # This file
```

## Troubleshooting

### "TIINGO_API_KEY environment variable is required"

- Make sure `.env.local` exists and has the correct API key
- Restart the development server after adding environment variables

### "Property 'stockPrices' does not exist"

- Run `npm run db:generate` to regenerate Prisma client
- Restart TypeScript service in your editor

### Rate limit errors

- The system should handle this automatically with delays
- Check if your API key is valid
- Consider upgrading to paid tier for higher limits

### No price data returned

- Some tickers might not be available on Tiingo
- Check ticker symbol spelling (should be uppercase)
- Verify the ticker exists in your transactions data

## API Rate Monitoring

Monitor your API usage:

- Free tier: 1,000 calls/day, 50/hour
- Check usage in Tiingo dashboard
- The script logs API calls and progress

## Performance Tips

1. **Start Small**: Test with `--limit 5` first
2. **Recent Only**: Use `--recent-only` for maintenance updates
3. **Incremental**: The system only fetches missing date ranges
4. **Batch Processing**: The script processes tickers sequentially with delays

// webstack/src/lib/tiingoService.ts

export interface TiingoPriceData {
  date: string;
  close: number;
  high: number;
  low: number;
  open: number;
  volume: number;
  adjClose: number;
  adjHigh: number;
  adjLow: number;
  adjOpen: number;
  adjVolume: number;
  divCash: number;
  splitFactor: number;
}

export interface TiingoMetaData {
  ticker: string;
  name: string;
  description: string;
  startDate: string;
  endDate: string;
}

class TiingoService {
  private apiKey: string;
  private baseUrl: string;
  private requestCount = 0;
  private lastRequestTime = 0;
  private readonly MAX_REQUESTS_PER_HOUR = 50;
  private readonly HOUR_IN_MS = 60 * 60 * 1000;

  constructor() {
    this.apiKey = process.env.TIINGO_API_KEY || '';
    this.baseUrl = process.env.TIINGO_BASE_URL || 'https://api.tiingo.com';
    
    if (!this.apiKey) {
      throw new Error('TIINGO_API_KEY environment variable is required');
    }
  }

  private async rateLimitCheck(): Promise<void> {
    const now = Date.now();
    
    // Reset counter if an hour has passed
    if (now - this.lastRequestTime > this.HOUR_IN_MS) {
      this.requestCount = 0;
    }
    
    // If we're at the limit, wait until we can make another request
    if (this.requestCount >= this.MAX_REQUESTS_PER_HOUR) {
      const waitTime = this.HOUR_IN_MS - (now - this.lastRequestTime);
      console.log(`Rate limit reached. Waiting ${Math.ceil(waitTime / 1000)} seconds...`);
      await new Promise(resolve => setTimeout(resolve, waitTime));
      this.requestCount = 0;
    }
    
    // Add delay between requests to stay under 50/hour comfortably
    if (this.requestCount > 0) {
      await new Promise(resolve => setTimeout(resolve, 75000)); // 75 seconds between requests
    }
    
    this.requestCount++;
    this.lastRequestTime = now;
  }

  async getHistoricalPrices(
    ticker: string, 
    startDate?: string, 
    endDate?: string
  ): Promise<TiingoPriceData[]> {
    await this.rateLimitCheck();
    
    const params = new URLSearchParams({
      token: this.apiKey,
      format: 'json',
      resampleFreq: 'daily'
    });
    
    if (startDate) params.append('startDate', startDate);
    if (endDate) params.append('endDate', endDate);
    
    const url = `${this.baseUrl}/tiingo/daily/${ticker}/prices?${params}`;
    
    try {
      console.log(`Fetching prices for ${ticker}...`);
      const response = await fetch(url);
      
      if (!response.ok) {
        if (response.status === 404) {
          console.warn(`Ticker ${ticker} not found on Tiingo`);
          return [];
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (!Array.isArray(data)) {
        console.warn(`No price data returned for ${ticker}`);
        return [];
      }
      
      return data.map((item: any) => ({
        date: item.date,
        close: item.close,
        high: item.high,
        low: item.low,
        open: item.open,
        volume: item.volume,
        adjClose: item.adjClose,
        adjHigh: item.adjHigh,
        adjLow: item.adjLow,
        adjOpen: item.adjOpen,
        adjVolume: item.adjVolume,
        divCash: item.divCash || 0,
        splitFactor: item.splitFactor || 1
      }));
      
    } catch (error) {
      console.error(`Error fetching prices for ${ticker}:`, error);
      throw error;
    }
  }

  async getTickerMetadata(ticker: string): Promise<TiingoMetaData | null> {
    await this.rateLimitCheck();
    
    const url = `${this.baseUrl}/tiingo/daily/${ticker}?token=${this.apiKey}`;
    
    try {
      const response = await fetch(url);
      
      if (!response.ok) {
        if (response.status === 404) {
          console.warn(`Ticker ${ticker} metadata not found`);
          return null;
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      return {
        ticker: data.ticker,
        name: data.name,
        description: data.description,
        startDate: data.startDate,
        endDate: data.endDate
      };
      
    } catch (error) {
      console.error(`Error fetching metadata for ${ticker}:`, error);
      return null;
    }
  }

  // Get recently active tickers from our database
  async getRecentlyTradedTickers(dayLimit = 90): Promise<string[]> {
    // This will be implemented to query our database
    // For now, return empty array - will be filled by the ingestion script
    return [];
  }
}

export default TiingoService; 
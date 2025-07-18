// webstack/src/lib/mockPriceData.ts

export type PriceDataPoint = {
  date: Date;
  price: number;
  volume: number;
};

export type TradeDataPoint = {
  date: Date;
  price: number;
  type: 'buy' | 'sell';
  amount: number;
  memberName: string;
  memberId: number;
};

// Generate mock stock price data
export function generateMockPriceData(
  ticker: string, 
  startDate: Date, 
  endDate: Date,
  startPrice: number = 100
): PriceDataPoint[] {
  const data: PriceDataPoint[] = [];
  const daysDiff = Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));
  
  let currentPrice = startPrice;
  let currentDate = new Date(startDate);
  
  // Different volatility for different stocks
  const volatility = getVolatilityForTicker(ticker);
  
  for (let i = 0; i <= daysDiff; i++) {
    if (currentDate.getDay() !== 0 && currentDate.getDay() !== 6) { // Skip weekends
      // Generate price movement with some randomness
      const priceChange = (Math.random() - 0.5) * volatility * currentPrice * 0.02;
      currentPrice = Math.max(currentPrice + priceChange, 0.01);
      
      // Generate volume (higher volume on bigger price movements)
      const baseVolume = 1000000;
      const volumeMultiplier = 1 + Math.abs(priceChange / currentPrice) * 5;
      const volume = Math.floor(baseVolume * volumeMultiplier * (0.5 + Math.random()));
      
      data.push({
        date: new Date(currentDate),
        price: Number(currentPrice.toFixed(2)),
        volume
      });
    }
    
    currentDate.setDate(currentDate.getDate() + 1);
  }
  
  return data;
}

// Generate trade data based on actual transactions
export function generateTradeDataPoints(
  transactions: any[],
  priceData: PriceDataPoint[]
): TradeDataPoint[] {
  const tradePoints: TradeDataPoint[] = [];
  
  transactions.forEach(transaction => {
    if (!transaction.transaction_date) return;
    
    const tradeDate = new Date(transaction.transaction_date);
    
    // Find the closest price point
    const closestPricePoint = priceData.reduce((closest, point) => {
      const currentDiff = Math.abs(point.date.getTime() - tradeDate.getTime());
      const closestDiff = Math.abs(closest.date.getTime() - tradeDate.getTime());
      return currentDiff < closestDiff ? point : closest;
    });
    
    if (closestPricePoint) {
      const avgAmount = ((transaction.amount_range_low || 0) + (transaction.amount_range_high || 0)) / 2;
      
      tradePoints.push({
        date: tradeDate,
        price: closestPricePoint.price,
        type: transaction.transaction_type.toLowerCase().includes('purchase') ? 'buy' : 'sell',
        amount: avgAmount,
        memberName: transaction.Filings?.Members?.name || 'Unknown',
        memberId: transaction.Filings?.Members?.member_id || 0
      });
    }
  });
  
  return tradePoints.sort((a, b) => a.date.getTime() - b.date.getTime());
}

function getVolatilityForTicker(ticker: string): number {
  const highVolatility = ['TSLA', 'GME', 'AMC', 'NVDA'];
  const mediumVolatility = ['AAPL', 'GOOGL', 'MSFT', 'AMZN'];
  
  if (highVolatility.includes(ticker)) return 2.0;
  if (mediumVolatility.includes(ticker)) return 1.0;
  return 0.8; // Default low volatility
}

// Get mock price data for a specific date range
export function getMockPriceDataForDateRange(
  ticker: string,
  startDate: Date,
  endDate: Date
): PriceDataPoint[] {
  // In a real app, this would fetch from an API
  // For now, generate consistent mock data based on ticker
  let basePrice = 100;
  
  // Set different base prices for different tickers
  switch (ticker) {
    case 'TSLA': basePrice = 200; break;
    case 'AAPL': basePrice = 150; break;
    case 'GOOGL': basePrice = 2500; break;
    case 'MSFT': basePrice = 300; break;
    case 'AMZN': basePrice = 3000; break;
    default: basePrice = 100;
  }
  
  return generateMockPriceData(ticker, startDate, endDate, basePrice);
}

// Calculate date range based on transactions
export function getDateRangeFromTransactions(transactions: any[]): { start: Date; end: Date } {
  if (transactions.length === 0) {
    const end = new Date();
    const start = new Date();
    start.setFullYear(start.getFullYear() - 1);
    return { start, end };
  }
  
  const dates = transactions
    .filter(t => t.transaction_date)
    .map(t => new Date(t.transaction_date));
  
  const start = new Date(Math.min(...dates.map(d => d.getTime())));
  const end = new Date(Math.max(...dates.map(d => d.getTime())));
  
  // Add some padding
  start.setMonth(start.getMonth() - 1);
  end.setMonth(end.getMonth() + 1);
  
  return { start, end };
} 
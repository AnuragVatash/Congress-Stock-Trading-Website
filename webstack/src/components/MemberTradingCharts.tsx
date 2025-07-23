// webstack/src/components/MemberTradingCharts.tsx
"use client";

import { useState } from 'react';
import StockPriceChart from './StockPriceChart';
import VolumeChart from './VolumeChart';
import { 
  getDateRangeFromTransactions, 
  generateTradeDataPoints 
} from '@/src/lib/priceDataService';

type Transaction = {
  transaction_id: number;
  transaction_date: Date | string | null;
  transaction_type: string;
  amount_range_low: number | null;
  amount_range_high: number | null;
  Assets: {
    asset_id: number;
    company_name: string;
    ticker: string | null;
  } | null;
  Filings?: {
    Members?: {
      member_id: number;
      name: string;
    };
  };
};

type Props = {
  trades: Transaction[];
  memberName: string;
};

type StockSummary = {
  ticker: string;
  company_name: string;
  asset_id: number;
  trades: Transaction[];
  totalVolume: number;
  tradeCount: number;
};

export default function MemberTradingCharts({ trades, memberName }: Props) {
  const [selectedStock, setSelectedStock] = useState<string | null>(null);
  const [chartType, setChartType] = useState<'trades' | 'volume'>('trades');

  // Group trades by stock
  const stockSummaries: StockSummary[] = [];
  const stockMap = new Map<string, StockSummary>();

  trades.forEach(trade => {
    if (!trade.Assets?.ticker) return;
    
    const ticker = trade.Assets.ticker;
    const totalVolume = ((trade.amount_range_low || 0) + (trade.amount_range_high || 0)) / 2;
    
    if (!stockMap.has(ticker)) {
      stockMap.set(ticker, {
        ticker,
        company_name: trade.Assets.company_name,
        asset_id: trade.Assets.asset_id,
        trades: [],
        totalVolume: 0,
        tradeCount: 0
      });
    }
    
    const summary = stockMap.get(ticker)!;
    summary.trades.push(trade);
    summary.totalVolume += totalVolume;
    summary.tradeCount++;
  });

  stockSummaries.push(...Array.from(stockMap.values()));
  stockSummaries.sort((a, b) => b.totalVolume - a.totalVolume);

  const topStocks = stockSummaries.slice(0, 5);
  const currentStock = selectedStock ? 
    stockSummaries.find(s => s.ticker === selectedStock) : 
    topStocks[0];

  if (topStocks.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-xl font-bold text-white mb-4">Trading Charts</h3>
        <p className="text-gray-400 text-center py-8">No trading data available for charts.</p>
      </div>
    );
  }

  // Note: For now we'll use mock data since this component needs to be converted to async
  // or moved to server-side rendering to use the real price data
  let priceData, tradeData;
  if (currentStock) {
    const dateRange = getDateRangeFromTransactions(currentStock.trades);
    // Generate mock data synchronously for now
    const mockData = [];
    const currentDate = new Date(dateRange.start);
    let currentPrice = 100;
    
    while (currentDate <= dateRange.end) {
      if (currentDate.getDay() !== 0 && currentDate.getDay() !== 6) {
        const changePercent = (Math.random() - 0.5) * 0.1;
        currentPrice = Math.max(1, currentPrice + (currentPrice * changePercent));
        
        mockData.push({
          date: new Date(currentDate),
          price: currentPrice,
          volume: Math.floor(Math.random() * 10000000) + 1000000,
          open: currentPrice * 0.99,
          high: currentPrice * 1.03,
          low: currentPrice * 0.97,
          close: currentPrice
        });
      }
      currentDate.setDate(currentDate.getDate() + 1);
    }
    
    priceData = mockData;
    tradeData = generateTradeDataPoints(currentStock.trades, priceData);
  }

  return (
    <div className="space-y-6">
      {/* Stock Selector */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-xl font-bold text-white mb-4">
          {memberName}&apos;s Trading Activity
        </h3>
        
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Select Stock to View:
          </label>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {topStocks.map(stock => (
              <button
                key={stock.ticker}
                onClick={() => setSelectedStock(stock.ticker)}
                className={`p-3 rounded-lg border transition-colors text-left ${
                  (selectedStock || topStocks[0].ticker) === stock.ticker
                    ? 'border-blue-400 bg-blue-900/20' 
                    : 'border-gray-600 bg-gray-700 hover:bg-gray-600'
                }`}
              >
                <div className="font-semibold text-white">{stock.ticker}</div>
                <div className="text-sm text-gray-400 truncate">{stock.company_name}</div>
                <div className="text-sm text-gray-300">
                  {stock.tradeCount} trades • ${(stock.totalVolume / 1000).toFixed(0)}K
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="flex gap-4">
          <button
            onClick={() => setChartType('trades')}
            className={`px-4 py-2 rounded-lg transition-colors ${
              chartType === 'trades'
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            Price with Trade Pins
          </button>
          <button
            onClick={() => setChartType('volume')}
            className={`px-4 py-2 rounded-lg transition-colors ${
              chartType === 'volume'
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            Price and Volume
          </button>
        </div>
      </div>

      {/* Chart Display */}
      {currentStock && priceData && tradeData && (
        <div>
          {chartType === 'trades' ? (
            <StockPriceChart 
              priceData={priceData}
              tradeData={tradeData}
              ticker={currentStock.ticker}
              height={400}
            />
          ) : (
            <VolumeChart 
              priceData={priceData}
              ticker={currentStock.ticker}
              height={400}
            />
          )}
          
          {/* Additional Info */}
          <div className="mt-4 bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h4 className="text-lg font-semibold text-white mb-2">
              {memberName}&apos;s {currentStock.ticker} Trading Summary
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-gray-400">Total Trades</div>
                <div className="text-white font-semibold">{currentStock.tradeCount}</div>
              </div>
              <div>
                <div className="text-gray-400">Total Volume</div>
                <div className="text-white font-semibold">${currentStock.totalVolume.toLocaleString()}</div>
              </div>
              <div>
                <div className="text-gray-400">Buys</div>
                <div className="text-green-400 font-semibold">
                  {currentStock.trades.filter(t => t.transaction_type.toLowerCase().includes('purchase')).length}
                </div>
              </div>
              <div>
                <div className="text-gray-400">Sells</div>
                <div className="text-red-400 font-semibold">
                  {currentStock.trades.filter(t => t.transaction_type.toLowerCase().includes('sale')).length}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 
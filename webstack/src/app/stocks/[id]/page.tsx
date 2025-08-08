// webstack/src/app/stocks/[id]/page.tsx
// OPTIMIZED - Uses SQL aggregation for statistics instead of JavaScript processing

import { prisma } from '@/src/lib/prisma';
import { notFound } from 'next/navigation';
import Link from 'next/link';
import { format } from 'date-fns';
import StockPriceChart from '@/src/components/StockPriceChart';
import VolumeChart from '@/src/components/VolumeChart';
import { 
  getPriceDataForDateRange, 
  getDateRangeFromTransactions, 
  generateTradeDataPoints 
} from '@/src/lib/priceDataService';
import type { PriceDataPoint, TradeDataPoint } from '@/src/lib/priceDataService';

// Force dynamic rendering to avoid build-time database queries
export const dynamic = 'force-dynamic';

// Performance monitoring functions
async function measureTimeAsync<T>(operationName: string, fn: () => Promise<T>): Promise<T> {
  const start = performance.now();
  const result = await fn();
  const end = performance.now();
  const duration = end - start;
  
  console.log(`🚀 STOCK: ${operationName} took ${duration.toFixed(2)}ms`);
  return result;
}

function formatCurrency(value: number | null): string {
  if (value === null) return 'N/A';
  if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `$${(value / 1000).toFixed(1)}K`;
  return `$${value}`;
}

// OPTIMIZED: Get stock statistics using SQL aggregation instead of JavaScript processing
async function getStockStatistics(assetId: number) {
  return measureTimeAsync('Stock Statistics SQL Query', async () => {
    const [stockInfo, stockStats, buyStats, sellStats, topTraders] = await Promise.all([
      // Basic stock info
      prisma.assets.findUnique({
        where: { asset_id: assetId }
      }),
      
      // Overall statistics
      prisma.$queryRaw<Array<{
        total_volume: number;
        trade_count: bigint;
        total_transactions: bigint;
      }>>`
        SELECT 
          COALESCE(SUM((t.amount_range_low + t.amount_range_high) / 2.0), 0) as total_volume,
          COUNT(DISTINCT t.transaction_id) as trade_count,
          COUNT(t.transaction_id) as total_transactions
        FROM "Transactions" t
        WHERE t.asset_id = ${assetId}
      `,
      
      // Buy transactions count
      prisma.$queryRaw<Array<{ buy_count: bigint }>>`
        SELECT COUNT(t.transaction_id) as buy_count
        FROM "Transactions" t
        WHERE t.asset_id = ${assetId} 
        AND LOWER(t.transaction_type) LIKE '%purchase%'
      `,
      
      // Sell transactions count  
      prisma.$queryRaw<Array<{ sell_count: bigint }>>`
        SELECT COUNT(t.transaction_id) as sell_count
        FROM "Transactions" t
        WHERE t.asset_id = ${assetId}
        AND LOWER(t.transaction_type) LIKE '%sale%'
      `,
      
      // Top traders using SQL aggregation
      prisma.$queryRaw<Array<{
        member_id: number;
        name: string;
        party: string | null;
        chamber: string | null;
        trade_count: bigint;
        total_volume: number;
      }>>`
        SELECT 
          m.member_id,
          m.name,
          m.party,
          m.chamber,
          COUNT(t.transaction_id) as trade_count,
          COALESCE(SUM((t.amount_range_low + t.amount_range_high) / 2.0), 0) as total_volume
        FROM "Transactions" t
        JOIN "Filings" f ON t.filing_id = f.filing_id
        JOIN "Members" m ON f.member_id = m.member_id
        WHERE t.asset_id = ${assetId}
        GROUP BY m.member_id, m.name, m.party, m.chamber
        ORDER BY trade_count DESC
        LIMIT 5
      `
    ]);

    if (!stockInfo) return null;

    return {
      stock: stockInfo,
      totalVolume: Number(stockStats[0]?.total_volume || 0),
      totalTrades: Number(stockStats[0]?.trade_count || 0),
      buyTransactions: Number(buyStats[0]?.buy_count || 0),
      sellTransactions: Number(sellStats[0]?.sell_count || 0),
      topTraders: topTraders.map(trader => ({
        member_id: trader.member_id,
        name: trader.name,
        party: trader.party,
        chamber: trader.chamber,
        tradeCount: Number(trader.trade_count),
        totalVolume: trader.total_volume
      }))
    };
  });
}

export default async function StockDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const pageStart = performance.now();
  const { id } = await params;
  const assetId = Number(id);

  if (isNaN(assetId)) {
    notFound();
  }

  console.log(`🔍 STOCK: Starting stock ${assetId} detail page render`);

  // Get optimized statistics and recent transactions in parallel
  const [stockData, recentTransactions] = await Promise.all([
    getStockStatistics(assetId),
    measureTimeAsync('Recent Transactions Query', () =>
      prisma.transactions.findMany({
        where: { asset_id: assetId },
        include: {
          Filings: {
            include: {
              Members: true
            }
          }
        },
        orderBy: {
          transaction_date: 'desc'
        },
        take: 100 // Limit for performance - show most recent 100 transactions
      })
    )
  ]);

  if (!stockData) {
    notFound();
  }

  const { stock, totalVolume, totalTrades, buyTransactions, sellTransactions, topTraders } = stockData;

  // Generate chart data using static JSON or DB; show unavailable if none
  let priceData: PriceDataPoint[] = [];
  let tradeData: TradeDataPoint[] = [];
  if (recentTransactions.length > 0) {
    const dateRange = getDateRangeFromTransactions(recentTransactions);
    priceData = await getPriceDataForDateRange(stock.ticker || 'UNKNOWN', dateRange.start, dateRange.end);
    if (priceData.length > 0) {
      tradeData = generateTradeDataPoints(recentTransactions, priceData);
    }
  }

  const pageEnd = performance.now();
  console.log(`🚀 STOCK: TOTAL PAGE TIME: ${(pageEnd - pageStart).toFixed(2)}ms`);
  console.log(`📊 STOCK: Loaded stats for ${stock.company_name} with ${totalTrades} total trades`);

  return (
    <div className="min-h-screen" style={{ background: 'var(--c-navy)' }}>
      <div className="max-w-7xl mx-auto p-4 md:p-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center mb-4">
            <Link href="/" className="text-blue-400 hover:text-blue-300 mr-4">
              ← Back to Home
            </Link>
          </div>
          <div className="card" style={{ background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))' }}>
            <div className="flex items-center space-x-4 mb-6">
              <div className="w-16 h-16 rounded-lg flex items-center justify-center" style={{ background: 'var(--c-navy-600)' }}>
                <span className="text-white font-bold text-lg">{stock.ticker}</span>
              </div>
              <div>
                <h1 className="text-3xl font-bold text-white" style={{ color: 'var(--c-jade)' }}>{stock.company_name}</h1>
                <p className="text-lg text-white">{stock.ticker}</p>
              </div>
            </div>
            {/* Stock Statistics */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div className="card" style={{ background: 'var(--c-neutral-50)' }}>
                <div className="text-2xl font-bold text-[#0d1b2a]">{totalTrades}</div>
                <div className="text-sm" style={{ color: 'var(--c-secondary-text)' }}>Total Trades</div>
              </div>
              <div className="card" style={{ background: 'var(--c-neutral-50)' }}>
                <div className="text-2xl font-bold" style={{ color: 'var(--c-success)' }}>{buyTransactions}</div>
                <div className="text-sm" style={{ color: 'var(--c-secondary-text)' }}>Buy Orders</div>
              </div>
              <div className="card" style={{ background: 'var(--c-neutral-50)' }}>
                <div className="text-2xl font-bold" style={{ color: 'var(--c-error)' }}>{sellTransactions}</div>
                <div className="text-sm" style={{ color: 'var(--c-secondary-text)' }}>Sell Orders</div>
              </div>
              <div className="card" style={{ background: 'var(--c-neutral-50)' }}>
                <div className="text-2xl font-bold" style={{ color: 'var(--c-warning)' }}>{formatCurrency(totalVolume)}</div>
                <div className="text-sm" style={{ color: 'var(--c-secondary-text)' }}>Total Volume</div>
              </div>
            </div>
          </div>
        </div>

        {/* Charts Section */}
        {priceData && priceData.length > 0 ? (
          <div className="mb-8 space-y-8">
            <StockPriceChart 
              priceData={priceData}
              tradeData={tradeData}
              ticker={stock.ticker || 'UNKNOWN'}
              height={400}
            />
            <VolumeChart 
              priceData={priceData}
              ticker={stock.ticker || 'UNKNOWN'}
              height={300}
            />
          </div>
        ) : (
          <div className="mb-8">
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 text-gray-300">
              Price/volume data unavailable for {stock.ticker}. Check back later.
            </div>
          </div>
        )}

        <div className="grid lg:grid-cols-3 gap-8">
          {/* Top Traders */}
          <div className="lg:col-span-1">
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <h2 className="text-2xl font-bold text-white mb-6">Top Traders</h2>
              <div className="space-y-4">
                {topTraders.map((member) => (
                  <Link
                    key={member.member_id}
                    href={`/members/${member.member_id}`}
                    className="block bg-gray-700 rounded-lg p-4 hover:bg-gray-600 transition-colors"
                  >
                    <div className="flex justify-between items-center">
                      <div>
                        <div className="text-white font-semibold">{member.name}</div>
                        <div className="text-sm text-gray-400">
                          {member.party} • {member.chamber}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-white font-semibold">{member.tradeCount} trades</div>
                        <div className="text-sm text-gray-400">{formatCurrency(member.totalVolume)}</div>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          </div>

          {/* Recent Transactions */}
          <div className="lg:col-span-2">
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <h2 className="text-2xl font-bold text-white mb-6">Recent Transactions</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-xs text-gray-400 uppercase bg-gray-700">
                    <tr>
                      <th className="px-4 py-3 text-left">Date</th>
                      <th className="px-4 py-3 text-left">Member</th>
                      <th className="px-4 py-3 text-left">Type</th>
                      <th className="px-4 py-3 text-left">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {recentTransactions.map((transaction) => (
                      <tr key={transaction.transaction_id} className="hover:bg-gray-700/50 transition-colors">
                        <td className="px-4 py-3 text-gray-300">
                          {transaction.transaction_date ? 
                            format(new Date(transaction.transaction_date), 'MMM dd, yyyy') : 
                            'N/A'
                          }
                        </td>
                        <td className="px-4 py-3">
                          <Link 
                            href={`/members/${transaction.Filings.Members.member_id}`}
                            className="text-blue-400 hover:text-blue-300 font-medium"
                          >
                            {transaction.Filings.Members.name}
                          </Link>
                          <div className="text-xs text-gray-400">
                            {transaction.Filings.Members.party}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                            transaction.transaction_type.toLowerCase().includes('purchase') 
                              ? 'bg-green-900 text-green-300' 
                              : 'bg-red-900 text-red-300'
                          }`}>
                            {transaction.transaction_type}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-white">
                          {formatCurrency(transaction.amount_range_low)} - {formatCurrency(transaction.amount_range_high)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              
              {recentTransactions.length === 0 && (
                <div className="text-center py-12">
                  <p className="text-gray-400">No transactions found for this stock.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 
// webstack/src/app/page.tsx
// OPTIMIZED VERSION - Uses SQL aggregation instead of loading individual transactions

import HeroSection from '@/src/components/HeroSection';
import SearchSection from '@/src/components/SearchSection';
import StatsGrid from '@/src/components/StatsGrid';
import RecentTradesHome from '@/src/components/RecentTradesHome';
import { PrismaClient } from '@prisma/client';
import { formatDistanceToNow } from 'date-fns';
import Link from 'next/link';
import Image from 'next/image';

const prisma = new PrismaClient();

// Performance monitoring functions
function measureTime<T>(operationName: string, fn: () => T): T {
  const start = performance.now();
  const result = fn();
  const end = performance.now();
  const duration = end - start;
  
  console.log(`🚀 HOME: ${operationName} took ${duration.toFixed(2)}ms`);
  return result;
}

async function measureTimeAsync<T>(operationName: string, fn: () => Promise<T>): Promise<T> {
  const start = performance.now();
  const result = await fn();
  const end = performance.now();
  const duration = end - start;
  
  console.log(`🚀 HOME: ${operationName} took ${duration.toFixed(2)}ms`);
  return result;
}

// OPTIMIZED: Get featured politicians using SQL aggregation instead of loading all transactions
const getFeaturedPoliticiansOptimized = async () => {
  return measureTimeAsync('Featured Politicians SQL Query', async () => {
    const result = await prisma.$queryRaw<Array<{
      member_id: number;
      name: string;
      photo_url: string | null;
      party: string | null;
      state: string | null;
      chamber: string | null;
      trade_count: bigint;
      total_volume: number;
    }>>`
      SELECT 
        m.member_id,
        m.name,
        m.photo_url,
        m.party,
        m.state,
        m.chamber,
        COUNT(t.transaction_id) as trade_count,
        COALESCE(SUM((t.amount_range_low + t.amount_range_high) / 2.0), 0) as total_volume
      FROM Members m
      LEFT JOIN Filings f ON m.member_id = f.member_id
      LEFT JOIN Transactions t ON f.filing_id = t.filing_id
      GROUP BY m.member_id, m.name, m.photo_url, m.party, m.state, m.chamber
      HAVING COUNT(t.transaction_id) > 0
      ORDER BY trade_count DESC
      LIMIT 5
    `;

    return result.map(row => ({
      member_id: row.member_id,
      name: row.name,
      photo_url: row.photo_url,
      party: row.party,
      state: row.state,
      chamber: row.chamber,
      tradeCount: Number(row.trade_count),
      totalVolume: row.total_volume
    }));
  });
};

// OPTIMIZED: Get top stocks using SQL aggregation instead of loading all transactions
const getTopStocksOptimized = async () => {
  return measureTimeAsync('Top Stocks SQL Query', async () => {
    const result = await prisma.$queryRaw<Array<{
      ticker: string;
      company_name: string;
      trade_count: bigint;
      total_volume: number;
    }>>`
      SELECT 
        a.ticker,
        a.company_name,
        COUNT(t.transaction_id) as trade_count,
        COALESCE(SUM((t.amount_range_low + t.amount_range_high) / 2.0), 0) as total_volume
      FROM Assets a
      LEFT JOIN Transactions t ON a.asset_id = t.asset_id
      WHERE a.ticker IS NOT NULL
      GROUP BY a.asset_id, a.ticker, a.company_name
      HAVING COUNT(t.transaction_id) > 0
      ORDER BY trade_count DESC
      LIMIT 5
    `;

    return result.map(row => ({
      ticker: row.ticker || 'N/A',
      company_name: row.company_name,
      tradeCount: Number(row.trade_count),
      totalVolume: row.total_volume
    }));
  });
};

// OPTIMIZED: Get platform statistics using SQL aggregation
const getPlatformStatsOptimized = async () => {
  return measureTimeAsync('Platform Statistics SQL Queries', async () => {
    const [totalTradesResult, totalMembersResult, totalVolumeResult] = await Promise.all([
      prisma.transactions.count(),
      prisma.members.count(),
      prisma.$queryRaw<Array<{ total_volume: number }>>`
        SELECT COALESCE(SUM((amount_range_low + amount_range_high) / 2.0), 0) as total_volume
        FROM Transactions
      `
    ]);

    return {
      totalTrades: totalTradesResult,
      totalMembers: totalMembersResult,
      totalVolume: Number(totalVolumeResult[0]?.total_volume || 0)
    };
  });
};

export default async function Home() {
  const pageStart = performance.now();
  console.log('🔍 HOME: Starting Home page render with SQL optimization');

  // Run all optimized queries in parallel
  const [featuredPoliticians, topStocks, platformStats, recentTrades, latestApiRequest] = await Promise.all([
    getFeaturedPoliticiansOptimized(),
    getTopStocksOptimized(),
    getPlatformStatsOptimized(),
    // Recent trades still need individual records since they're displayed
    measureTimeAsync('Recent Trades Query', () => 
      prisma.transactions.findMany({
        include: {
          Assets: true,
          Filings: {
            include: {
              Members: true
            }
          }
        },
        orderBy: {
          transaction_date: 'desc'
        },
        take: 20
      })
    ),
    // Get the latest API request to determine last update time
    measureTimeAsync('Latest API Request Query', () =>
      prisma.aPI_Requests.findFirst({
        orderBy: {
          created_at: 'desc'
        },
        select: {
          created_at: true
        }
      })
    )
  ]);

  // Format the last update time
  const lastUpdate = latestApiRequest?.created_at 
    ? formatDistanceToNow(new Date(latestApiRequest.created_at), { addSuffix: true })
    : 'Unknown';

  const pageEnd = performance.now();
  console.log(`🚀 HOME: TOTAL PAGE TIME: ${(pageEnd - pageStart).toFixed(2)}ms`);

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Hero Section with Sidebars */}
      <div className="relative py-16 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-12 gap-6">
            {/* Left Sidebar - Featured Members */}
            <div className="lg:col-span-3 hidden lg:block">
              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 h-full">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-xl font-bold text-white">Featured Members</h2>
                  <Link href="/members" className="text-blue-400 hover:text-blue-300 text-sm font-medium">
                    View All →
                  </Link>
                </div>
                <div className="space-y-2 overflow-hidden" style={{ height: '408px' }}>
                  {featuredPoliticians.slice(0, 5).map((politician, index) => (
                    <Link
                      key={politician.member_id}
                      href={`/members/${politician.member_id}`}
                      className="block bg-gray-700 rounded-lg p-3 hover:bg-gray-600 transition-colors"
                      style={{ height: '76px' }}
                    >
                      <div className="flex items-center justify-between h-full">
                        <div className="flex items-center space-x-3 flex-1 min-w-0">
                          <div className="relative w-10 h-10 rounded-full overflow-hidden bg-gray-600 flex-shrink-0">
                            {politician.photo_url ? (
                              <Image
                                src={politician.photo_url}
                                alt={politician.name}
                                fill
                                className="object-cover"
                              />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm font-semibold">
                                {politician.name.charAt(0)}
                              </div>
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <h3 className="text-white font-semibold text-sm truncate">{politician.name}</h3>
                            <p className="text-xs text-gray-400">
                              {politician.party} • {politician.chamber}
                            </p>
                          </div>
                        </div>
                        <div className="text-right flex-shrink-0 ml-2">
                          <div className="text-white font-semibold text-sm">{politician.tradeCount} trades</div>
                          <div className="text-xs text-gray-400">${((politician.totalVolume / 1000000) | 0)}M</div>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            </div>

            {/* Center - Hero Section */}
            <div className="lg:col-span-6">
              <HeroSection lastUpdate={lastUpdate} />
            </div>

            {/* Right Sidebar - Top Traded Stocks */}
            <div className="lg:col-span-3 hidden lg:block">
              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 h-full">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-xl font-bold text-white">Top Traded Stocks</h2>
                  <Link href="/trades" className="text-blue-400 hover:text-blue-300 text-sm font-medium">
                    View All →
                  </Link>
                </div>
                <div className="space-y-2 overflow-hidden" style={{ height: '408px' }}>
                  {topStocks.slice(0, 5).map((stock, index) => (
                    <div
                      key={stock.ticker}
                      className="block bg-gray-700 rounded-lg p-3 hover:bg-gray-600 transition-colors cursor-pointer"
                      style={{ height: '76px' }}
                    >
                      <div className="flex items-center justify-between h-full">
                        <div className="flex items-center space-x-3 flex-1 min-w-0">
                          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center flex-shrink-0">
                            <span className="text-white font-bold text-xs">{stock.ticker}</span>
                          </div>
                          <div className="min-w-0 flex-1">
                            <h3 className="text-white font-semibold text-sm truncate">{stock.company_name}</h3>
                            <p className="text-xs text-gray-400">{stock.tradeCount} trades</p>
                          </div>
                        </div>
                        <div className="text-right flex-shrink-0 ml-2">
                          <div className="text-white font-semibold text-sm">${((stock.totalVolume / 1000000) | 0)}M</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <RecentTradesHome trades={recentTrades} />
      <SearchSection />
      
      {/* Platform Statistics moved to bottom */}
      <StatsGrid 
        totalTrades={platformStats.totalTrades}
        totalMembers={platformStats.totalMembers}
        totalVolume={platformStats.totalVolume}
      />
      
      {/* Newsletter Section */}
      <div className="py-12 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg p-8 text-center">
            <h3 className="text-2xl font-bold text-white mb-4">
              Stay Updated on Congressional Trading
            </h3>
            <p className="text-blue-100 mb-6 max-w-2xl mx-auto">
              Get weekly insights and alerts about significant trades made by members of Congress. 
              Join thousands of investors and journalists who rely on our data.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 max-w-md mx-auto">
              <input
                type="email"
                placeholder="Enter your email"
                className="flex-1 px-4 py-3 rounded-lg bg-white/10 border border-white/20 text-white placeholder-blue-200 focus:outline-none focus:border-white/40"
              />
              <button className="px-6 py-3 bg-white text-blue-600 rounded-lg font-semibold hover:bg-gray-100 transition-colors">
                Subscribe
              </button>
            </div>
            <p className="text-xs text-blue-200 mt-4">
              Trusted by reporters at The New York Times, Wall Street Journal, and more.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

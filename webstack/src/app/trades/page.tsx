export const dynamic = 'error';
export const revalidate = 0;
// webstack/src/app/trades/page.tsx
// ALREADY OPTIMIZED - Uses SQL aggregation, adding performance monitoring

import { PrismaClient } from '@prisma/client';
import Link from 'next/link';
import IssuersTable from '@/src/components/IssuersTable';

const prisma = new PrismaClient();

// Performance monitoring functions
async function measureTimeAsync<T>(operationName: string, fn: () => Promise<T>): Promise<T> {
  const start = performance.now();
  const result = await fn();
  const end = performance.now();
  const duration = end - start;
  
  console.log(`🚀 TRADES: ${operationName} took ${duration.toFixed(2)}ms`);
  return result;
}

type IssuerData = {
  asset_id: number;
  company_name: string;
  ticker: string | null;
  lastTraded: Date | null;
  totalVolume: number;
  tradeCount: number;
  politicianCount: number;
  sector: string;
  currentPrice: number;
  priceChange: number;
  priceData: number[]; // 30-day price sparkline data
};

function formatCurrency(value: number): string {
  if (value >= 1e9) {
    return `$${(value / 1e9).toFixed(2)}B`;
  }
  if (value >= 1e6) {
    return `$${(value / 1e6).toFixed(1)}M`;
  }
  if (value >= 1e3) {
    return `$${(value / 1e3).toFixed(1)}K`;
  }
  return `$${value}`;
}

// Mock function to generate sector based on company name
function inferSector(companyName: string): string {
  const name = companyName.toLowerCase();
  if (name.includes('bank') || name.includes('financial') || name.includes('capital') || name.includes('credit')) {
    return 'Financial Services';
  }
  if (name.includes('tech') || name.includes('microsoft') || name.includes('apple') || name.includes('google') || name.includes('meta')) {
    return 'Technology';
  }
  if (name.includes('pharma') || name.includes('health') || name.includes('medical') || name.includes('bio')) {
    return 'Healthcare';
  }
  if (name.includes('energy') || name.includes('oil') || name.includes('gas') || name.includes('exxon')) {
    return 'Energy';
  }
  if (name.includes('retail') || name.includes('walmart') || name.includes('target') || name.includes('amazon')) {
    return 'Consumer Discretionary';
  }
  if (name.includes('auto') || name.includes('tesla') || name.includes('ford') || name.includes('general motors')) {
    return 'Automotive';
  }
  return 'Other';
}

// Mock function to generate 30-day price data
function generatePriceData(basePrice: number): number[] {
  const data = [];
  let currentPrice = basePrice;
  
  for (let i = 0; i < 30; i++) {
    const change = (Math.random() - 0.5) * 0.1; // ±5% daily change
    currentPrice = Math.max(1, currentPrice * (1 + change));
    data.push(currentPrice);
  }
  
  return data;
}

async function getTradesData(page: number = 1, pageSize: number = 50) {
  const offset = (page - 1) * pageSize;
  
  // First, get aggregated data using raw SQL for better performance
  const aggregatedAssets = await measureTimeAsync('Issuers SQL Query with Aggregation', async () => {
    return await prisma.$queryRaw<Array<{
      asset_id: number;
      company_name: string;
      ticker: string | null;
      total_volume: number;
      trade_count: number;
      politician_count: number;
      last_traded: string | null;
    }>>`
      SELECT 
        a.asset_id,
        a.company_name,
        a.ticker,
        COALESCE(SUM((t.amount_range_low + t.amount_range_high) / 2), 0) as total_volume,
        COUNT(t.transaction_id) as trade_count,
        COUNT(DISTINCT f.member_id) as politician_count,
        MAX(t.transaction_date) as last_traded
      FROM Assets a
      LEFT JOIN Transactions t ON a.asset_id = t.asset_id
      LEFT JOIN Filings f ON t.filing_id = f.filing_id
      GROUP BY a.asset_id, a.company_name, a.ticker
      HAVING trade_count > 0
      ORDER BY total_volume DESC
      LIMIT ${pageSize} OFFSET ${offset}
    `;
  });

  // Process data for each issuer
  const issuersData: IssuerData[] = aggregatedAssets
    .map(asset => {
      // Mock price data
      const basePrice = Math.random() * 200 + 50; // $50-$250
      const priceData = generatePriceData(basePrice);
      const currentPrice = priceData[priceData.length - 1];
      const previousPrice = priceData[priceData.length - 2];
      const priceChange = ((currentPrice - previousPrice) / previousPrice) * 100;

      return {
        asset_id: asset.asset_id,
        company_name: asset.company_name,
        ticker: asset.ticker,
        lastTraded: asset.last_traded ? new Date(asset.last_traded) : null,
        totalVolume: Number(asset.total_volume),
        tradeCount: Number(asset.trade_count),
        politicianCount: Number(asset.politician_count),
        sector: inferSector(asset.company_name),
        currentPrice,
        priceChange,
        priceData
      };
    });

  return issuersData;
}

async function getSummaryMetrics() {
  // Use raw SQL for better performance
  return measureTimeAsync('Summary Metrics Parallel Queries', async () => {
    const [totalTrades, totalFilings, totalMembers, totalAssets, totalVolume] = await Promise.all([
      prisma.transactions.count(),
      prisma.filings.count(),
      prisma.members.count(),
      prisma.assets.count(),
      prisma.$queryRaw<Array<{ total_volume: number }>>`
        SELECT COALESCE(SUM((amount_range_low + amount_range_high) / 2), 0) as total_volume
        FROM Transactions
      `
    ]);

    return {
      totalTrades,
      totalFilings,
      totalVolume: Number(totalVolume[0]?.total_volume || 0),
      totalMembers,
      totalAssets
    };
  });
}

export default async function TradesPage() {
  const pageStart = performance.now();
  console.log('🔍 TRADES: Starting TradesPage render (already optimized)');

  const [issuersData, summaryMetrics] = await Promise.all([
    getTradesData(1, 50), // Load first 50 items
    getSummaryMetrics()
  ]);

  const pageEnd = performance.now();
  console.log(`🚀 TRADES: TOTAL PAGE TIME: ${(pageEnd - pageStart).toFixed(2)}ms`);

  return (
    <div className="min-h-screen" style={{ background: 'var(--c-navy)', color: 'var(--c-navy)' }}>
      {/* Congress Alpha Brand */}
      <div className="w-full" style={{ background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))' }}>
        <span className="text-3xl font-extrabold" style={{ color: '#fff' }}>Congress Alpha</span>
      </div>
      
      <div className="max-w-7xl mx-auto p-4 md:p-8">
        {/* Header */}
        <div className="card" style={{ background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))' }}>
          <div className="flex items-center mb-4">
            <Link href="/" className="button-secondary">
              ← Back to Home
            </Link>
          </div>
          <h1 className="text-4xl font-bold mb-4 text-white" style={{ color: 'var(--c-jade)' }}>Congressional Trades</h1>
          <p className="text-xl text-white">
            Comprehensive view of all securities traded by members of Congress
          </p>
          <div className="mt-2 card" style={{ background: 'var(--c-jade-100)', border: 'none' }}>
            <p className="text-sm" style={{ color: 'var(--c-jade)' }}>
              💡 <strong>Search Enhancement:</strong> The search now queries ALL traded securities, not just the top 50 shown by default.
            </p>
          </div>
        </div>

        {/* Summary Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="text-2xl font-bold text-blue-400">
              {summaryMetrics.totalTrades.toLocaleString()}
            </div>
            <div className="text-sm text-gray-400 uppercase tracking-wide">Trades</div>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="text-2xl font-bold text-purple-400">
              {summaryMetrics.totalFilings.toLocaleString()}
            </div>
            <div className="text-sm text-gray-400 uppercase tracking-wide">Filings</div>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="text-2xl font-bold text-green-400">
              {formatCurrency(summaryMetrics.totalVolume)}
            </div>
            <div className="text-sm text-gray-400 uppercase tracking-wide">Volume</div>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="text-2xl font-bold text-yellow-400">
              {summaryMetrics.totalMembers}
            </div>
            <div className="text-sm text-gray-400 uppercase tracking-wide">Politicians</div>
          </div>
          
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <div className="text-2xl font-bold text-red-400">
              {summaryMetrics.totalAssets.toLocaleString()}
            </div>
            <div className="text-sm text-gray-400 uppercase tracking-wide">Issuers</div>
          </div>
        </div>

        {/* Trades Table */}
        <IssuersTable issuers={issuersData} />
      </div>
    </div>
  );
} 
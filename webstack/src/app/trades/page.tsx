export const dynamic = 'error';
export const revalidate = 0;
// webstack/src/app/trades/page.tsx
// ALREADY OPTIMIZED - Uses SQL aggregation, adding performance monitoring

import { prisma } from '@/src/lib/prisma';
import Link from 'next/link';
import IssuersTable from '@/src/components/IssuersTable';
import Image from 'next/image';

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
      FROM "Assets" a
      LEFT JOIN "Transactions" t ON a.asset_id = t.asset_id
      LEFT JOIN "Filings" f ON t.filing_id = f.filing_id
      GROUP BY a.asset_id, a.company_name, a.ticker
      HAVING COUNT(t.transaction_id) > 0
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
        FROM "Transactions"
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

  const [issuersData] = await Promise.all([
    getTradesData(1, 50), // Load first 50 items
    getSummaryMetrics()
  ]);

  const pageEnd = performance.now();
  console.log(`🚀 TRADES: TOTAL PAGE TIME: ${(pageEnd - pageStart).toFixed(2)}ms`);

  return (
    <div className="min-h-screen" style={{ background: 'var(--c-navy)', color: 'var(--c-navy)' }}>
      {/* Back button in top left corner */}
      <div style={{ margin: '1.5rem 0 0 1.5rem', position: 'absolute', top: 0, left: 0 }}>
        <Link href="/">
          <Image src="/return.png" alt="Back to Home" width={40} height={40} style={{ cursor: 'pointer' }} />
        </Link>
      </div>
      <div className="max-w-7xl mx-auto p-4 md:p-8">
        {/* Header */}
        <div className="card" style={{ background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))' }}>
          <h1 className="text-4xl font-bold mb-4 text-white text-center" style={{ color: 'var(--c-jade)' }}>Congressional Trades</h1>
          <p className="text-xl text-white text-center">
            Comprehensive view of all securities traded by members of Congress
          </p>
        </div>
        {/* Spacer between header and search/filter */}
        <div style={{ height: '1rem' }} />
        {/* Trades Table */}
        <IssuersTable issuers={issuersData} />
      </div>
    </div>
  );
} 
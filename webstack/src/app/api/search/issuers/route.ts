// webstack/src/app/api/search/issuers/route.ts
// API endpoint for searching issuers with complete data structure for IssuersTable

import { prisma } from '@/src/lib/prisma';
import { NextResponse } from 'next/server';

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

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get('q')?.trim();
  const limit = Number(searchParams.get('limit')) || 20;

  if (!query || query.length < 2) {
    return NextResponse.json({ 
      error: 'Query must be at least 2 characters long' 
    }, { status: 400 });
  }

  try {
    console.log(`🔍 SEARCH: Searching issuers for "${query}"`);
    
    // OPTIMIZED: Use SQL aggregation to search ALL issuers
    const searchResults = await prisma.$queryRaw<Array<{
      asset_id: number;
      company_name: string;
      ticker: string | null;
      total_volume: number;
      trade_count: bigint;
      politician_count: bigint;
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
      WHERE (a.ticker ILIKE '%' || ${query} || '%' OR a.company_name ILIKE '%' || ${query} || '%')
      GROUP BY a.asset_id, a.company_name, a.ticker
      HAVING COUNT(t.transaction_id) > 0
      ORDER BY 
        CASE 
          WHEN a.ticker LIKE ${query} || '%' THEN 1
          WHEN a.company_name LIKE ${query} || '%' THEN 2
          ELSE 3
        END,
        total_volume DESC
      LIMIT ${limit}
    `;

    // Transform to match IssuersTable data structure
    const issuersData = searchResults.map(asset => {
      // Generate mock price data (same as trades page)
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

    console.log(`📊 SEARCH: Found ${issuersData.length} issuers matching "${query}"`);
    return NextResponse.json(issuersData);

  } catch (error) {
    console.error('Failed to search issuers:', error);
    return NextResponse.json({ 
      error: 'An error occurred while searching issuers' 
    }, { status: 500 });
  }
} 
// webstack/src/app/api/search/stocks/route.ts
// OPTIMIZED - Uses SQL aggregation instead of loading all transactions

import { prisma } from '@/src/lib/prisma';
import { NextResponse } from 'next/server';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get('q')?.trim();
  const limit = Number(searchParams.get('limit')) || 10;

  if (!query || query.length < 2) {
    return NextResponse.json({ 
      error: 'Query must be at least 2 characters long' 
    }, { status: 400 });
  }

  try {
    // OPTIMIZED: Use SQL aggregation instead of loading all transactions
    const stocksWithStats = await prisma.$queryRaw<Array<{
      asset_id: number;
      ticker: string | null;
      company_name: string;
      trade_count: bigint;
      total_volume: number;
    }>>`
      SELECT 
        a.asset_id,
        a.ticker,
        a.company_name,
        COUNT(t.transaction_id) as trade_count,
        COALESCE(SUM((t.amount_range_low + t.amount_range_high) / 2.0), 0) as total_volume
      FROM "Assets" a
      JOIN "Transactions" t ON a.asset_id = t.asset_id
      WHERE (a.ticker ILIKE '%' || ${query} || '%' OR a.company_name ILIKE '%' || ${query} || '%')
      GROUP BY a.asset_id, a.ticker, a.company_name
      ORDER BY 
        CASE 
          WHEN a.ticker LIKE ${query} || '%' THEN 1
          WHEN a.company_name LIKE ${query} || '%' THEN 2
          ELSE 3
        END,
        trade_count DESC
      LIMIT ${limit}
    `;

    const result = stocksWithStats.map(stock => ({
      asset_id: stock.asset_id,
      ticker: stock.ticker,
      company_name: stock.company_name,
      tradeCount: Number(stock.trade_count),
      totalVolume: stock.total_volume
    }));

    return NextResponse.json(result);

  } catch (error) {
    console.error('Failed to search stocks:', error);
    return NextResponse.json({ 
      error: 'An error occurred while searching stocks' 
    }, { status: 500 });
  }
} 
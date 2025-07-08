// app/api/trades/recent/route.ts
import { prisma } from '@/lib/prisma';
import { NextResponse } from 'next/server';

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const take = Number(searchParams.get('limit') ?? 300);

  const trades = await prisma.transactions.findMany({
    include: {
      Assets: true,
      Filings: { include: { Members: true } }
    },
    orderBy: { transaction_date: 'desc' },
    take
  });

  /* cache for 30 s so multiple visitors share the same payload */
  return NextResponse.json(trades, { headers: { 'Cache-Control': 's-maxage=30' } });
}

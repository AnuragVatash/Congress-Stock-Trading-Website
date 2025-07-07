// app/api/trades/route.ts
import { prisma } from '@/lib/prisma';
import { NextResponse } from 'next/server';

export async function GET() {
  const trades = await prisma.transactions.findMany({
    include: {
      Assets: true,
      Filings: {include: {members: true}},
    },
    orderBy: { transaction_date: 'desc' },
    take: 100,
  });
  return NextResponse.json(trades);
}

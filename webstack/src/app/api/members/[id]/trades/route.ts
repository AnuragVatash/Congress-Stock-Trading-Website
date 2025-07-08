// File: /app/api/members/[id]/trades/route.ts
// This code is now correct because `npx prisma generate` has been run.

import { PrismaClient, Prisma } from '@prisma/client';
import { NextResponse } from 'next/server';

const prisma = new PrismaClient();

// This type definition will now work correctly because the client is up to date.
type TransactionDateFilter = NonNullable<Prisma.TransactionsWhereInput['transaction_date']>;

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const memberId = Number(params.id);
  if (isNaN(memberId)) {
    return NextResponse.json({ error: 'Invalid member ID.' }, { status: 400 });
  }

  try {
    const { searchParams } = new URL(request.url);
    const fromParam = searchParams.get('from');
    const toParam = searchParams.get('to');

    const where: Prisma.TransactionsWhereInput = {
      Filings: { member_id: memberId },
    };

    const dateFilter: TransactionDateFilter = {};

    if (fromParam) {
      const fromDate = new Date(fromParam);
      if (!isNaN(fromDate.getTime())) {
        dateFilter.gte = fromDate;
      }
    }

    if (toParam) {
      const toDate = new Date(toParam);
      if (!isNaN(toDate.getTime())) {
        toDate.setUTCHours(23, 59, 59, 999);
        dateFilter.lte = toDate;
      }
    }

    if (Object.keys(dateFilter).length > 0) {
      where.transaction_date = dateFilter;
    }

    const trades = await prisma.transactions.findMany({
      where,
      include: {
        Assets: true,
      },
      orderBy: {
        transaction_date: 'desc',
      },
    });

    return NextResponse.json(trades);

  } catch (error) {
    console.error("Failed to fetch trades:", error);
    return NextResponse.json({ error: 'An error occurred while fetching trades.' }, { status: 500 });
  }
}
// /app/api/members/[id]/trades/route.ts

import { PrismaClient } from '@prisma/client';
import { NextResponse } from 'next/server';

const prisma = new PrismaClient();

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const memberId = Number(params.id);
  if (isNaN(memberId)) {
    return NextResponse.json({ error: 'Invalid member ID.' }, { status: 400 });
  }

  try {
    const trades = await prisma.transactions.findMany({
      where: {
        Filings: {
          member_id: memberId
        }
      },
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
      }
    });

    return NextResponse.json(trades);

  } catch (error) {
    console.error("Failed to fetch member trades:", error);
    return NextResponse.json({ error: 'An error occurred while fetching the member trades.' }, { status: 500 });
  }
}
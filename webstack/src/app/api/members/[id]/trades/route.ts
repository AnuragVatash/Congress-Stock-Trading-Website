// /app/api/members/[id]/trades/route.ts
// Handler signature matches Next.js App Router dynamic API route requirements
// GET(request: Request, { params }: { params: Promise<{ id: string }> })

import { PrismaClient } from '@prisma/client';
import { NextResponse } from 'next/server';

const prisma = new PrismaClient();

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const memberId = Number(id);
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
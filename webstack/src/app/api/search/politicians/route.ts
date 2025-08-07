// webstack/src/app/api/search/politicians/route.ts

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
    const politicians = await prisma.members.findMany({
      where: {
        name: {
          contains: query,
          mode: 'insensitive'
        }
      },
      include: {
        Filings: {
          include: {
            Transactions: true
          }
        }
      },
      take: limit,
      orderBy: {
        name: 'asc'
      }
    });

    // Transform the data to include trade count
    const politiciansWithTradeCount = politicians.map(politician => ({
      member_id: politician.member_id,
      name: politician.name,
      photo_url: politician.photo_url,
      party: politician.party,
      state: politician.state,
      chamber: politician.chamber,
      tradeCount: politician.Filings.reduce((count, filing) => count + filing.Transactions.length, 0)
    }));

    return NextResponse.json(politiciansWithTradeCount);

  } catch (error) {
    console.error('Failed to search politicians:', error);
    return NextResponse.json({ 
      error: 'An error occurred while searching politicians' 
    }, { status: 500 });
  }
} 
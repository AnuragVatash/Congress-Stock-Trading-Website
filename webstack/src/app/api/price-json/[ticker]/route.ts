import { NextResponse } from 'next/server';
import { getPriceDataForDateRange } from '@/src/lib/priceDataService';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ ticker: string }> }
) {
  const { ticker } = await params;
  const { searchParams } = new URL(request.url);
  const start = searchParams.get('start');
  const end = searchParams.get('end');

  if (!ticker || !start || !end) {
    return NextResponse.json({ error: 'ticker, start, and end are required' }, { status: 400 });
  }

  try {
    const startDate = new Date(start);
    const endDate = new Date(end);
    const data = await getPriceDataForDateRange(ticker, startDate, endDate);
    return NextResponse.json(data, { headers: { 'Cache-Control': 's-maxage=300' } });
  } catch {
    return NextResponse.json({ error: 'Failed to load price data' }, { status: 500 });
  }
}



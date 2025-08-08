import { NextResponse } from 'next/server';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const ticker = searchParams.get('ticker') ?? '';
  const start = searchParams.get('start') ?? '';
  const end = searchParams.get('end') ?? '';
  const interval = searchParams.get('interval') ?? '1d';

  if (!ticker) {
    return NextResponse.json({ error: 'Ticker is required' }, { status: 400 });
  }

  const baseUrl = process.env.YFINANCE_API_URL || 'http://127.0.0.1:8001';
  const upstreamUrl = `${baseUrl}/prices?ticker=${encodeURIComponent(
    ticker
  )}${start ? `&start=${encodeURIComponent(start)}` : ''}${end ? `&end=${encodeURIComponent(end)}` : ''}&interval=${encodeURIComponent(
    interval
  )}`;

  try {
    const res = await fetch(upstreamUrl, { next: { revalidate: 300 } });
    if (!res.ok) {
      throw new Error(`Upstream yfinance service error: ${res.status}`);
    }
    const data = await res.json();
    return NextResponse.json(data, {
      headers: { 'Cache-Control': 's-maxage=300, stale-while-revalidate=60' }
    });
  } catch (error) {
    console.error('Failed to fetch stock prices via yfinance service:', error);
    return NextResponse.json(
      { error: 'Failed to fetch stock prices' },
      { status: 500 }
    );
  }
}



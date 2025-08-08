"use client";

// webstack/src/components/MemberTradingCharts.tsx

import { useEffect, useMemo, useState } from 'react';
import StockPriceChart from './StockPriceChart';
import VolumeChart from './VolumeChart';
import { generateTradeDataPoints } from '../lib/priceDataService';
import type { PriceDataPoint, TradeDataPoint } from '../lib/priceDataService';

// Transactions coming from profile page (with Assets joined)
type Transaction = {
  transaction_id: number;
  transaction_date: Date | string | null;
  transaction_type: string;
  amount_range_low: number | null;
  amount_range_high: number | null;
  Assets: { asset_id: number; company_name: string; ticker: string | null } | null;
  Filings?: { Members?: { member_id: number; name: string } };
};

type Props = { trades: Transaction[] };

type StockSummary = {
  ticker: string;
  company_name: string;
  asset_id: number;
  trades: Transaction[];
  inRangeTrades: number;
};

type RawPrice = {
  date: string;
  adj_close?: number; close?: number;
  volume?: number;
  adj_open?: number; open?: number;
  adj_high?: number; high?: number;
  adj_low?: number; low?: number;
};

function parsePrices(raw: unknown): PriceDataPoint[] {
  if (!Array.isArray(raw)) return [];
  return (raw as RawPrice[]).map((p) => ({
    date: new Date(p.date),
    price: typeof p.adj_close === 'number' ? p.adj_close : (p.close ?? 0),
    volume: Number(p.volume) || 0,
    open: typeof p.adj_open === 'number' ? p.adj_open : (p.open ?? 0),
    high: typeof p.adj_high === 'number' ? p.adj_high : (p.high ?? 0),
    low: typeof p.adj_low === 'number' ? p.adj_low : (p.low ?? 0),
    close: typeof p.adj_close === 'number' ? p.adj_close : (p.close ?? 0),
  }));
}

export default function MemberTradingCharts({ trades }: Props) {
  // Fixed 3-year window
  const chartEnd = useMemo(() => new Date(), []);
  const chartStart = useMemo(() => {
    const d = new Date();
    d.setFullYear(d.getFullYear() - 3);
    return d;
  }, []);

  // Summaries and top 5 by in-range trades
  const { topStocks, inRangeTradesAll, totalTickers } = useMemo(() => {
    const startMs = chartStart.getTime();
    const endMs = chartEnd.getTime();
    const perTicker = new Map<string, StockSummary>();
    const inRangeTrades: Transaction[] = [];
    for (const t of trades) {
      const asset = t.Assets;
      const ticker = asset?.ticker;
      if (!asset || !ticker) continue;
      const ms = t.transaction_date ? new Date(t.transaction_date as string).getTime() : 0;
      if (ms >= startMs && ms <= endMs) inRangeTrades.push(t);
      if (!perTicker.has(ticker)) {
        perTicker.set(ticker, {
          ticker,
          company_name: asset.company_name,
          asset_id: asset.asset_id,
          trades: [],
          inRangeTrades: 0,
        });
      }
      const s = perTicker.get(ticker)!;
      s.trades.push(t);
      if (ms >= startMs && ms <= endMs) s.inRangeTrades++;
    }
    const list = Array.from(perTicker.values()).sort((a, b) => {
      if (b.inRangeTrades !== a.inRangeTrades) return b.inRangeTrades - a.inRangeTrades;
      return a.ticker.localeCompare(b.ticker);
    });
    return { topStocks: list.slice(0, 5), inRangeTradesAll: inRangeTrades, totalTickers: perTicker.size };
  }, [trades, chartStart, chartEnd]);

  // SPY chart and 50 most recent pins
  const [spyPrice, setSpyPrice] = useState<PriceDataPoint[] | null>(null);
  const [spyTrades, setSpyTrades] = useState<TradeDataPoint[] | null>(null);
  useEffect(() => {
    const loadSpy = async () => {
      const params = new URLSearchParams({
        start: chartStart.toISOString().slice(0, 10),
        end: chartEnd.toISOString().slice(0, 10),
      });
      const res = await fetch(`/api/price-json/SPY?${params.toString()}`, { cache: 'force-cache' });
      if (!res.ok) return;
      const data = parsePrices(await res.json());
      setSpyPrice(data);
      const pins = [...inRangeTradesAll]
        .sort((a, b) => new Date(b.transaction_date as string).getTime() - new Date(a.transaction_date as string).getTime())
        .slice(0, 50);
      setSpyTrades(generateTradeDataPoints(pins, data));
    };
    loadSpy();
  }, [chartStart, chartEnd, inRangeTradesAll]);

  // Per-ticker charts
  const [perTickerPrice, setPerTickerPrice] = useState<Record<string, PriceDataPoint[]>>({});
  const [perTickerTrades, setPerTickerTrades] = useState<Record<string, TradeDataPoint[]>>({});
  useEffect(() => {
    const load = async () => {
      const params = new URLSearchParams({
        start: chartStart.toISOString().slice(0, 10),
        end: chartEnd.toISOString().slice(0, 10),
      });
      await Promise.all(topStocks.map(async (s) => {
        if (perTickerPrice[s.ticker]) return;
        const res = await fetch(`/api/price-json/${encodeURIComponent(s.ticker)}?${params.toString()}`, { cache: 'force-cache' });
        if (!res.ok) return;
        const data = parsePrices(await res.json());
        setPerTickerPrice(prev => ({ ...prev, [s.ticker]: data }));
        setPerTickerTrades(prev => ({ ...prev, [s.ticker]: generateTradeDataPoints(s.trades, data) }));
      }));
    };
    load();
  }, [topStocks, chartStart, chartEnd, perTickerPrice]);

  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-xl font-bold text-white mb-2">Market Benchmark (SPY)</h3>
        <p className="text-sm text-gray-400 mb-4">Price and volume are for SPY (market). Pins show the 50 most recent member transactions within the last 3 years.</p>
        {spyPrice && spyTrades ? (
          <>
            <StockPriceChart priceData={spyPrice} tradeData={spyTrades} ticker={'SPY'} height={400} />
            <div className="mt-2">
              <VolumeChart priceData={spyPrice} ticker={'SPY'} height={300} />
            </div>
          </>
        ) : (
          <div className="text-gray-400">Loading SPY chart…</div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {topStocks.map(stock => {
          const p = perTickerPrice[stock.ticker];
          const t = perTickerTrades[stock.ticker];
          return (
            <div key={stock.ticker} className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <h4 className="text-lg font-semibold text-white mb-2">{stock.ticker} — {stock.company_name}</h4>
              {p && t ? (
                <StockPriceChart priceData={p} tradeData={t} ticker={stock.ticker} height={300} clickTarget="asset" assetId={stock.asset_id} />
              ) : (
                <div className="text-gray-400">Loading chart…</div>
              )}
            </div>
          );
        })}
      </div>

      {totalTickers > 50 && (
        <div className="text-sm text-gray-400">Tickers limited to 50. Use search to view more transactions.</div>
      )}
    </div>
  );
} 
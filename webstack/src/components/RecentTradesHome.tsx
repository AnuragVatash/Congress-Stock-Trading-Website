// webstack/src/components/RecentTradesHome.tsx
"use client";

import Link from 'next/link';
import { format } from 'date-fns';

type Trade = {
  transaction_id: number;
  transaction_date: Date | string | null;
  transaction_type: string;
  amount_range_low: number | null;
  amount_range_high: number | null;
  Assets: {
    company_name: string;
    ticker: string | null;
  } | null;
  Filings: {
    Members: {
      member_id: number;
      name: string;
      party: string | null;
    };
  };
};

type Props = {
  trades: Trade[];
  isLoading?: boolean;
};

function formatCurrency(value: number | null): string {
  if (value === null) return 'N/A';
  if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `$${(value / 1000).toFixed(1)}K`;
  return `$${value}`;
}

function formatDateForDisplay(date: Date | string | null): string {
  if (!date) return 'N/A';
  const dateObj = date instanceof Date ? date : new Date(date);
  return format(dateObj, 'MMM dd');
}

export default function RecentTradesHome({ trades, isLoading = false }: Props) {
  if (isLoading) {
    return (
      <div className="py-12 px-4">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-3xl font-bold text-white mb-8">Recent Trades</h2>
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
            <div className="animate-pulse space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="flex space-x-4">
                  <div className="rounded-full bg-gray-700 h-10 w-10"></div>
                  <div className="flex-1 space-y-2 py-1">
                    <div className="h-4 bg-gray-700 rounded w-3/4"></div>
                    <div className="h-4 bg-gray-700 rounded w-1/2"></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="py-12 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h2 className="text-3xl font-bold text-white">Recent Trades</h2>
          <Link 
            href="/trades"
            className="text-blue-400 hover:text-blue-300 font-medium"
          >
            View All →
          </Link>
        </div>
        
        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-700">
                <tr className="text-left">
                  <th className="px-6 py-4 text-sm font-medium text-gray-300">Member</th>
                  <th className="px-6 py-4 text-sm font-medium text-gray-300">Ticker</th>
                  <th className="px-6 py-4 text-sm font-medium text-gray-300">Company</th>
                  <th className="px-6 py-4 text-sm font-medium text-gray-300">Type</th>
                  <th className="px-6 py-4 text-sm font-medium text-gray-300">Amount</th>
                  <th className="px-6 py-4 text-sm font-medium text-gray-300">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {trades.slice(0, 10).map((trade) => (
                  <tr key={trade.transaction_id} className="hover:bg-gray-700/50 transition-colors">
                    <td className="px-6 py-4">
                      <Link 
                        href={`/members/${trade.Filings.Members.member_id}`}
                        className="text-blue-400 hover:text-blue-300 font-medium"
                      >
                        {trade.Filings.Members.name}
                      </Link>
                      <div className="text-sm text-gray-400">
                        {trade.Filings.Members.party}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="font-mono text-teal-400 font-semibold">
                        {trade.Assets?.ticker || 'N/A'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-white max-w-xs truncate">
                      {trade.Assets?.company_name || 'N/A'}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                        trade.transaction_type.toLowerCase().includes('purchase') 
                          ? 'bg-green-900 text-green-300' 
                          : 'bg-red-900 text-red-300'
                      }`}>
                        {trade.transaction_type}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-white">
                      <div className="text-sm">
                        {formatCurrency(trade.amount_range_low)} - {formatCurrency(trade.amount_range_high)}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-gray-400 text-sm">
                      {formatDateForDisplay(trade.transaction_date)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          {trades.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-400">No recent trades found.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
} 
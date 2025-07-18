// webstack/src/components/TradesTable.tsx
"use client";

import { useState } from 'react';
import { format } from 'date-fns';

type Trade = {
    transaction_id: number;
    transaction_date: Date | string | null;
    owner_code: string | null;
    transaction_type: string;
    amount_range_low: number | null;
    amount_range_high: number | null;
    Assets: {
        company_name: string;
        ticker: string | null;
    } | null;
};

type Props = {
    trades: Trade[];
};

function formatCurrency(value: number | null): string {
    if (value === null) return 'N/A';
    if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
    if (value >= 1000) return `$${(value / 1000).toFixed(1)}K`;
    return `$${value}`;
}

export default function TradesTable({ trades }: Props) {
    const [page, setPage] = useState(0);
    const tradesPerPage = 10;
    const pageCount = Math.ceil(trades.length / tradesPerPage);

    const paginatedTrades = trades.slice(
        page * tradesPerPage,
        (page + 1) * tradesPerPage
    );

    if (trades.length === 0) {
        return (
            <div className="bg-gray-800 text-white p-6 rounded-lg shadow-lg h-full">
                <h2 className="text-2xl font-bold mb-4">Recent Trades</h2>
                <p className="text-center text-gray-500 mt-8">No trades found for this member.</p>
            </div>
        )
    }

    return (
        <div className="bg-gray-800 text-white p-6 rounded-lg shadow-lg">
            <h2 className="text-2xl font-bold mb-4">Recent Trades</h2>
            <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                    <thead className="text-xs text-gray-400 uppercase bg-gray-700">
                        <tr>
                            <th scope="col" className="px-4 py-3">Date</th>
                            <th scope="col" className="px-4 py-3">Ticker</th>
                            <th scope="col" className="px-4 py-3">Asset</th>
                            <th scope="col" className="px-4 py-3">Type</th>
                            <th scope="col" className="px-4 py-3">Amount</th>
                            <th scope="col" className="px-4 py-3">Owner</th>
                        </tr>
                    </thead>
                    <tbody>
                        {paginatedTrades.map((trade) => (
                            <tr key={trade.transaction_id} className="border-b border-gray-700 hover:bg-gray-600">
                                <td className="px-4 py-3">{trade.transaction_date ? format(trade.transaction_date instanceof Date ? trade.transaction_date : new Date(trade.transaction_date), 'MMM dd, yyyy') : 'N/A'}</td>
                                <td className="px-4 py-3 font-mono text-teal-400">{trade.Assets?.ticker || 'N/A'}</td>
                                <td className="px-4 py-3">{trade.Assets?.company_name || 'N/A'}</td>
                                <td className={`px-4 py-3 font-semibold ${trade.transaction_type.includes('purchase') ? 'text-green-400' : 'text-red-400'}`}>
                                    {trade.transaction_type}
                                </td>
                                <td className="px-4 py-3">{formatCurrency(trade.amount_range_low)} - {formatCurrency(trade.amount_range_high)}</td>
                                <td className="px-4 py-3 text-gray-400">{trade.owner_code || 'N/A'}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Pagination Controls */}
            <div className="flex justify-between items-center pt-4">
                <button
                    onClick={() => setPage(p => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="px-4 py-2 bg-gray-700 rounded-md disabled:opacity-50"
                >
                    Previous
                </button>
                <span className="text-sm text-gray-400">
                    Page {page + 1} of {pageCount}
                </span>
                <button
                    onClick={() => setPage(p => Math.min(pageCount - 1, p + 1))}
                    disabled={page === pageCount - 1}
                    className="px-4 py-2 bg-gray-700 rounded-md disabled:opacity-50"
                >
                    Next
                </button>
            </div>
        </div>
    );
} 
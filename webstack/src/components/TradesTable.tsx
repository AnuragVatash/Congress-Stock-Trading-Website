// webstack/src/components/TradesTable.tsx
"use client";

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
    // Fixed height for the component
    const tableHeight = '500px';

    if (trades.length === 0) {
        return (
            <div 
              className="text-white p-6 rounded-lg shadow-lg flex items-center justify-center"
              style={{ background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))', height: tableHeight }}
            >
                <p className="text-center text-gray-500">No trades found for this member.</p>
            </div>
        )
    }

    return (
        <div 
          className="text-white rounded-lg shadow-lg overflow-hidden"
          style={{ background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))' }}
        >
            <div className="overflow-auto" style={{ height: tableHeight }}>
                <table className="w-full text-sm text-left table-fixed">
                    <thead className="text-xs text-gray-400 uppercase bg-gray-700 sticky top-0 z-10">
                        <tr>
                            <th scope="col" className="px-4 py-3 w-28">Date</th>
                            <th scope="col" className="px-4 py-3 w-24">Ticker</th>
                            <th scope="col" className="px-4 py-3">Asset</th>
                            <th scope="col" className="px-4 py-3 w-48">Type</th>
                            <th scope="col" className="px-4 py-3 w-32">Amount</th>
                            <th scope="col" className="px-4 py-3 w-20">Owner</th>
                        </tr>
                    </thead>
                    <tbody>
                        {trades.map((trade) => (
                            <tr key={trade.transaction_id} className="border-b border-gray-700 hover:bg-gray-600">
                                <td className="px-4 py-3 whitespace-nowrap">{trade.transaction_date ? format(trade.transaction_date instanceof Date ? trade.transaction_date : new Date(trade.transaction_date), 'MMM dd, yyyy') : 'N/A'}</td>
                                <td className="px-4 py-3 font-mono text-teal-400">{trade.Assets?.ticker || 'N/A'}</td>
                                <td className="px-4 py-3 truncate" title={trade.Assets?.company_name || ''}>{trade.Assets?.company_name || 'N/A'}</td>
                                <td className={`px-4 py-3 font-semibold truncate ${trade.transaction_type.includes('purchase') ? 'text-green-400' : 'text-red-400'}`} title={trade.transaction_type}>{trade.transaction_type}</td>
                                <td className="px-4 py-3 whitespace-nowrap">{formatCurrency(trade.amount_range_low)} - {formatCurrency(trade.amount_range_high)}</td>
                                <td className="px-4 py-3 text-gray-400">{trade.owner_code || 'N/A'}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
} 
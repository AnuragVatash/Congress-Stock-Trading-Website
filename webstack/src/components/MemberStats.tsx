// webstack/src/components/MemberStats.tsx

type Transaction = {
    amount_range_low: number | null;
    amount_range_high: number | null;
    Assets: {
        ticker: string | null;
    } | null;
};

type Props = {
    trades: Transaction[];
};

function formatCurrency(value: number): string {
    if (value >= 1e6) {
        return `$${(value / 1e6).toFixed(1)}M`;
    }
    if (value >= 1e3) {
        return `$${(value / 1e3).toFixed(1)}K`;
    }
    return `$${value}`;
}

export default function MemberStats({ trades }: Props) {
    const totalTrades = trades.length;

    const totalVolume = trades.reduce((acc, trade) => {
        const avgAmount = ((trade.amount_range_low || 0) + (trade.amount_range_high || 0)) / 2;
        return acc + avgAmount;
    }, 0);

    const stockCounts = trades.reduce((acc, trade) => {
        const ticker = trade.Assets?.ticker || 'Unknown';
        acc[ticker] = (acc[ticker] || 0) + 1;
        return acc;
    }, {} as Record<string, number>);

    const topStocks = Object.entries(stockCounts)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 3);

    return (
        <div className="mt-8">
            <h3 className="text-xl font-bold mb-4 text-gray-300">Trading Snapshot</h3>
            <div className="space-y-3 text-sm">
                <div className="flex justify-between items-center">
                    <span className="text-gray-400">Total Trades:</span>
                    <span className="font-semibold text-white">{totalTrades}</span>
                </div>
                <div className="flex justify-between items-center">
                    <span className="text-gray-400">Est. Volume:</span>
                    <span className="font-semibold text-white">{formatCurrency(totalVolume)}</span>
                </div>
                <div>
                    <span className="text-gray-400">Top Traded Tickers:</span>
                    {topStocks.length > 0 ? (
                        <ul className="list-none mt-2 space-y-1">
                            {topStocks.map(([ticker, count]) => (
                                <li key={ticker} className="font-mono bg-gray-700 rounded-md px-2 py-1 flex justify-between items-center">
                                    <span className="text-teal-400">{ticker}</span>
                                    <span className="text-gray-300">{count} trades</span>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="text-gray-500 mt-1">No trading activity found.</p>
                    )}
                </div>
            </div>
        </div>
    );
} 
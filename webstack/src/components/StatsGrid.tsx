// webstack/src/components/StatsGrid.tsx

type StatsGridProps = {
  totalTrades?: number;
  totalMembers?: number;
  totalVolume?: number;
};

function formatCurrency(value: number): string {
  if (value >= 1e9) {
    return `$${(value / 1e9).toFixed(1)}B`;
  }
  if (value >= 1e6) {
    return `$${(value / 1e6).toFixed(1)}M`;
  }
  if (value >= 1e3) {
    return `$${(value / 1e3).toFixed(1)}K`;
  }
  return `$${value}`;
}

export default function StatsGrid({ totalTrades = 0, totalMembers = 0, totalVolume = 0 }: StatsGridProps) {
  return (
    <div style={{ width: '1500px', maxWidth: '100%', margin: '0 auto', padding: 16 }}>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
        <div className="card" style={{ background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))' }}>
          <div className="text-3xl font-bold text-white" style={{ color: 'var(--c-jade)' }}>{totalTrades.toLocaleString()}</div>
          <div className="text-sm text-white">Congressional trades since 2012</div>
        </div>
        <div className="card" style={{ background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))' }}>
          <div className="text-3xl font-bold text-white" style={{ color: 'var(--c-jade)' }}>{totalMembers}</div>
          <div className="text-sm text-white">Members of Congress</div>
        </div>
        <div className="card" style={{ background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))' }}>
          <div className="text-3xl font-bold text-white" style={{ color: 'var(--c-jade)' }}>{formatCurrency(totalVolume)}</div>
          <div className="text-sm text-white">Total volume disclosed</div>
        </div>
      </div>
    </div>
  );
} 
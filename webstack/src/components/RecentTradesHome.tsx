import TradesTable from "@/src/components/TradesTable";

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

export default function RecentTradesHome({ trades }: Props) {
  return (
    <div 
      style={{ width: '1500px', maxWidth: '100%', margin: '0 auto', padding: 16, background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))', border: '1px solid #fff', borderRadius: 12 }}
      className="rounded-lg shadow-lg"
    >
      <h2 className="text-3xl font-bold text-center mb-4">Recent Trades</h2>
      <TradesTable trades={trades} />
    </div>
  );
} 
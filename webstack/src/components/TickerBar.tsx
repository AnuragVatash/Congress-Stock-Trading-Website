type TickerItem = {
  member: string;
  ticker: string;
  amount: string;
  type: string;
  date: string;
};

export default function TickerBar({ items }: { items: TickerItem[] }) {
  // Cap items to avoid excessive DOM children while keeping the marquee feel
  const capped = items.slice(0, 20);

  return (
    <div style={{ width: '100%', overflow: 'hidden', height: '56px', display: 'flex', alignItems: 'center' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'stretch',
          whiteSpace: 'nowrap',
          fontSize: '1rem',
          gap: 0,
        }}
      >
        {/* Track A */}
        <div
          aria-hidden={false}
          style={{
            display: 'flex',
            animation: 'ticker-scroll-ltr 93s linear infinite',
          }}
        >
          {capped.map((item, i) => (
            <div
              key={`a-${i}`}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minWidth: '180px',
                padding: '0 1.25rem',
                marginRight: 0,
                fontWeight: 500,
                color: item.type === 'Purchase' ? '#4AC088' : '#E74C3C',
                borderLeft: i === 0 ? 'none' : '1px solid rgba(255,255,255,0.18)',
              }}
            >
              <span>{item.member} {item.ticker} {item.amount} {item.type}</span>
              <span style={{ fontSize: '0.8em', color: 'rgba(255,255,255,0.7)', marginTop: 2, textAlign: 'center', fontWeight: 400 }}>
                {item.date}
              </span>
            </div>
          ))}
        </div>

        {/* Track B (clone) */}
        <div
          aria-hidden={true}
          style={{
            display: 'flex',
            animation: 'ticker-scroll-ltr 93s linear infinite',
          }}
        >
          {capped.map((item, i) => (
            <div
              key={`b-${i}`}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minWidth: '180px',
                padding: '0 1.25rem',
                marginRight: 0,
                fontWeight: 500,
                color: item.type === 'Purchase' ? '#4AC088' : '#E74C3C',
                borderLeft: i === 0 ? 'none' : '1px solid rgba(255,255,255,0.18)',
              }}
            >
              <span>{item.member} {item.ticker} {item.amount} {item.type}</span>
              <span style={{ fontSize: '0.8em', color: 'rgba(255,255,255,0.7)', marginTop: 2, textAlign: 'center', fontWeight: 400 }}>
                {item.date}
              </span>
            </div>
          ))}
        </div>
      </div>
      <style>{`
        @keyframes ticker-scroll-ltr {
          0% { transform: translateX(-50%); }
          100% { transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}



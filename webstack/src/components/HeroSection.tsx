'use client';

import { useState, useEffect } from 'react';
import { formatDistanceToNow } from 'date-fns';

// webstack/src/components/HeroSection.tsx

export default function HeroSection({ lastUpdateDate }: { lastUpdateDate: Date | null | undefined }) {
  const [lastUpdate, setLastUpdate] = useState('');

  useEffect(() => {
    if (lastUpdateDate) {
      setLastUpdate(formatDistanceToNow(new Date(lastUpdateDate), { addSuffix: true }));
    } else {
      setLastUpdate('Unknown');
    }
  }, [lastUpdateDate]);

  return (
    <section
      className="rounded-lg shadow-lg mb-8"
      style={{
        background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))',
        color: '#fff',
        boxShadow: '0 2px 6px rgba(13,27,42,0.08)'
      }}
    >
      <div className="px-8 py-12 md:py-20 text-center">
        <h1 className="text-5xl font-extrabold mb-4" style={{ color: 'var(--c-jade)' }}>
          Congress Alpha
        </h1>
        <p className="text-xl mb-6" style={{ color: 'var(--c-gray-50)' }}>
          Track stock trades made by members of Congress in real-time.<br />
          <span style={{ color: 'var(--c-jade)' }}>Transparency</span> in congressional trading through comprehensive data analysis.
        </p>
        <div className="mb-6">
          <span
            className="inline-block px-4 py-2 rounded-full font-semibold"
            style={{ background: 'var(--c-jade-100)', color: 'var(--c-navy)', minWidth: 180, display: 'inline-block', textAlign: 'center' }}
            suppressHydrationWarning
          >
            Last updated: {lastUpdate || '...'}
          </span>
        </div>
        <a href="#search" className="button-primary">
          Search Congressional Trades
        </a>
      </div>
    </section>
  );
} 
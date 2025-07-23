// webstack/src/components/FeaturedCards.tsx
"use client";

import Link from 'next/link';
import Image from 'next/image';

type FeaturedPolitician = {
  member_id: number;
  name: string;
  photo_url: string | null;
  party: string | null;
  state: string | null;
  chamber: string | null;
  tradeCount: number;
  totalVolume: number;
};

type TopStock = {
  ticker: string;
  company_name: string;
  tradeCount: number;
  totalVolume: number;
  recentChange?: number;
};

type Props = {
  featuredPoliticians: FeaturedPolitician[];
  topStocks: TopStock[];
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

export default function FeaturedCards({ featuredPoliticians, topStocks }: Props) {
  return (
    <div style={{ width: '1500px', maxWidth: '100%', margin: '0 auto', padding: 16, border: '1px solid #fff', borderRadius: 12 }}>
      <div className="grid lg:grid-cols-2 gap-12">
          {/* Featured Politicians */}
          <div>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-white">Featured Members</h2>
              <Link href="/members" className="text-blue-400 hover:text-blue-300 text-sm font-medium">
                View All →
              </Link>
            </div>
            <div className="space-y-4">
              {featuredPoliticians.slice(0, 4).map((politician) => (
                <Link
                  key={politician.member_id}
                  href={`/members/${politician.member_id}`}
                  className="block card hover:shadow-lg transition-colors"
                  style={{ background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))' }}
                >
                  <div className="flex items-center space-x-4">
                    <div className="relative w-12 h-12 rounded-full overflow-hidden" style={{ background: 'var(--c-jade-100)' }}>
                      {politician.photo_url ? (
                        <Image
                          src={politician.photo_url}
                          alt={politician.name}
                          fill
                          className="object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-gray-400 text-xl font-semibold">
                          {politician.name.charAt(0)}
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-white font-semibold truncate">{politician.name}</h3>
                      <p className="text-sm text-gray-400">
                        {politician.party} • {politician.chamber} • {politician.state}
                      </p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="text-white font-semibold">{politician.tradeCount} trades</div>
                      <div className="text-sm text-gray-400">{formatCurrency(politician.totalVolume)}</div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>

          {/* Top Traded Stocks */}
          <div>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-white">Top Traded Stocks</h2>
              <Link href="/trades" className="text-blue-400 hover:text-blue-300 text-sm font-medium">
                View All →
              </Link>
            </div>
            <div className="space-y-4">
              {topStocks.slice(0, 4).map((stock) => (
                <div
                  key={stock.ticker}
                  className="bg-gray-800 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors p-4"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center flex-shrink-0">
                        <span className="text-white font-bold text-sm">{stock.ticker}</span>
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className="text-white font-semibold truncate">{stock.company_name}</h3>
                        <p className="text-sm text-gray-400">{stock.tradeCount} congressional trades</p>
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="text-white font-semibold">{formatCurrency(stock.totalVolume)}</div>
                      <div className="text-sm text-gray-400">Total volume</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Newsletter Signup */}
        <div className="mt-16 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg p-8 text-center" style={{ border: '1px solid #fff', borderRadius: 12 }}>
          <h3 className="text-2xl font-bold text-white mb-4">
            Stay Updated on Congressional Trading
          </h3>
          <p className="text-blue-100 mb-6 max-w-2xl mx-auto">
            Get weekly insights and alerts about significant trades made by members of Congress. 
            Join thousands of investors and journalists who rely on our data.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 max-w-md mx-auto">
            <input
              type="email"
              placeholder="Enter your email"
              className="flex-1 px-4 py-3 rounded-lg bg-white/10 border border-white/20 text-white placeholder-blue-200 focus:outline-none focus:border-white/40"
            />
            <button className="px-6 py-3 bg-white text-blue-600 rounded-lg font-semibold hover:bg-gray-100 transition-colors">
              Subscribe
            </button>
          </div>
          <p className="text-xs text-blue-200 mt-4">
            Trusted by reporters at The New York Times, Wall Street Journal, and more.
          </p>
        </div>
    </div>
  );
} 
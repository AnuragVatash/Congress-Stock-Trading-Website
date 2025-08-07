// webstack/src/components/SearchSection.tsx
"use client";

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';

type Politician = {
  member_id: number;
  name: string;
  photo_url: string | null;
  party: string | null;
  state: string | null;
  chamber: string | null;
  tradeCount: number;
};

type Stock = {
  asset_id: number;
  ticker: string | null;
  company_name: string;
  tradeCount: number;
  totalVolume: number;
};

// Enhanced debounce hook that prevents expensive operations on every keystroke
function useDebouncedSearch(delay: number) {
  const [displayValue, setDisplayValue] = useState('');
  const [debouncedValue, setDebouncedValue] = useState('');
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const setValue = useCallback((value: string) => {
    // Update display immediately for UI responsiveness  
    setDisplayValue(value);
    
    // Clear existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    
    // Set new timeout for debounced value - only this triggers searches
    timeoutRef.current = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);
  }, [delay]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return [displayValue, debouncedValue, setValue] as const;
}

export default function SearchSection() {
  // Use proper debounced inputs to prevent expensive operations on every keystroke
  const [politicianSearchDisplay, politicianSearchDebounced, setPoliticianSearch] = useDebouncedSearch(300);
  const [stockSearchDisplay, stockSearchDebounced, setStockSearch] = useDebouncedSearch(300);
  
  const [politicianResults, setPoliticianResults] = useState<Politician[]>([]);
  const [stockResults, setStockResults] = useState<Stock[]>([]);
  const [showPoliticianDropdown, setShowPoliticianDropdown] = useState(false);
  const [showStockDropdown, setShowStockDropdown] = useState(false);
  const [loadingPoliticians, setLoadingPoliticians] = useState(false);
  const [loadingStocks, setLoadingStocks] = useState(false);
  
  const politicianDropdownRef = useRef<HTMLDivElement>(null);
  const stockDropdownRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (politicianDropdownRef.current && !politicianDropdownRef.current.contains(event.target as Node)) {
        setShowPoliticianDropdown(false);
      }
      if (stockDropdownRef.current && !stockDropdownRef.current.contains(event.target as Node)) {
        setShowStockDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Search politicians ONLY when debounced value changes - prevents delays
  useEffect(() => {
    const searchPoliticians = async () => {
      if (politicianSearchDebounced.length < 2) {
        setPoliticianResults([]);
        setShowPoliticianDropdown(false);
        return;
      }

      setLoadingPoliticians(true);
      try {
        const response = await fetch(`/api/search/politicians?q=${encodeURIComponent(politicianSearchDebounced)}&limit=5`);
        if (response.ok) {
          const results = await response.json();
          setPoliticianResults(results);
          setShowPoliticianDropdown(true);
        }
      } catch (error) {
        console.error('Error searching politicians:', error);
      } finally {
        setLoadingPoliticians(false);
      }
    };

    // No additional timeout needed - the debounced value already handles this
    searchPoliticians();
  }, [politicianSearchDebounced]); // Only trigger on debounced changes

  // Search stocks ONLY when debounced value changes - prevents 952ms delays  
  useEffect(() => {
    const searchStocks = async () => {
      if (stockSearchDebounced.length < 2) {
        setStockResults([]);
        setShowStockDropdown(false);
        return;
      }

      setLoadingStocks(true);
      try {
        const response = await fetch(`/api/search/stocks?q=${encodeURIComponent(stockSearchDebounced)}&limit=5`);
        if (response.ok) {
          const results = await response.json();
          setStockResults(results);
          setShowStockDropdown(true);
        }
      } catch (error) {
        console.error('Error searching stocks:', error);
      } finally {
        setLoadingStocks(false);
      }
    };

    // No additional timeout needed - the debounced value already handles this
    searchStocks();
  }, [stockSearchDebounced]); // Only trigger on debounced changes

  const handlePoliticianSelect = useCallback((politician: Politician) => {
    router.push(`/members/${politician.member_id}`);
    setPoliticianSearch('');
    setShowPoliticianDropdown(false);
  }, [router, setPoliticianSearch]);

  const handleStockSelect = useCallback((stock: Stock) => {
    router.push(`/stocks/${stock.asset_id}`);
    setStockSearch('');
    setShowStockDropdown(false);
  }, [router, setStockSearch]);

  const handlePoliticianSearch = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (politicianSearchDisplay.trim() && politicianResults.length > 0) {
      handlePoliticianSelect(politicianResults[0]);
    }
  }, [politicianSearchDisplay, politicianResults, handlePoliticianSelect]);

  const handleStockSearch = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (stockSearchDisplay.trim() && stockResults.length > 0) {
      handleStockSelect(stockResults[0]);
    }
  }, [stockSearchDisplay, stockResults, handleStockSelect]);

  const formatCurrency = useCallback((value: number): string => {
    if (value >= 1e6) {
      return `$${(value / 1e6).toFixed(1)}M`;
    }
    if (value >= 1e3) {
      return `$${(value / 1e3).toFixed(1)}K`;
    }
    return `$${value}`;
  }, []);

  // Optimized input handlers that only update display values immediately
  const handlePoliticianInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setPoliticianSearch(e.target.value);
  }, [setPoliticianSearch]);

  const handleStockInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setStockSearch(e.target.value);
  }, [setStockSearch]);

  return (
    <div id="search" style={{ width: '1500px', maxWidth: '100%', margin: '0 auto', padding: 16, scrollMarginTop: 72 }}>
      <section 
        className="rounded-lg card" 
        style={{ background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))' }}
      >
        <h2 className="text-3xl font-bold text-white text-center mb-8">
          Search Congressional Trades
        </h2>
        <div className="grid md:grid-cols-2 gap-8">
            {/* Politician Search */}
            <div 
              className="rounded-lg p-6 border" 
              style={{ background: 'linear-gradient(10deg, var(--c-navy-700), var(--c-navy-800))', borderColor: 'var(--c-navy-600)' }}
              ref={politicianDropdownRef}
            >
              <h3 className="text-xl font-semibold text-white mb-4 flex items-center">
                <svg className="w-6 h-6 mr-2 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
                Politician Search
              </h3>
              <p className="text-gray-400 mb-4">
                Find trades by a specific member of Congress
              </p>
              <form onSubmit={handlePoliticianSearch}>
                <div className="relative">
                  <div className="flex gap-2">
                    <div className="flex-1 relative">
                      <input
                        type="text"
                        placeholder="Enter politician name (2+ chars)..."
                        value={politicianSearchDisplay}
                        onChange={handlePoliticianInputChange}
                        className="w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-400"
                      />
                      {loadingPoliticians && (
                        <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-400"></div>
                        </div>
                      )}
                    </div>
                    <button
                      type="submit"
                      className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
                    >
                      Search
                    </button>
                  </div>
                  
                  {/* Politician Dropdown */}
                  {showPoliticianDropdown && politicianResults.length > 0 && (
                    <div className="absolute top-full left-0 right-14 mt-1 bg-gray-900 border border-gray-600 rounded-lg shadow-lg z-10 max-h-60 overflow-y-auto">
                      {politicianResults.map((politician) => (
                        <button
                          key={politician.member_id}
                          type="button"
                          onClick={() => handlePoliticianSelect(politician)}
                          className="w-full px-4 py-3 text-left hover:bg-gray-700 transition-colors border-b border-gray-700 last:border-b-0"
                        >
                          <div className="flex items-center space-x-3">
                            <div className="relative w-8 h-8 rounded-full overflow-hidden bg-gray-700 flex-shrink-0">
                              {politician.photo_url ? (
                                <Image
                                  src={politician.photo_url}
                                  alt={politician.name}
                                  fill
                                  className="object-cover"
                                />
                              ) : (
                                <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm font-semibold">
                                  {politician.name.charAt(0)}
                                </div>
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="text-white font-medium truncate">{politician.name}</div>
                              <div className="text-sm text-gray-400">
                                {politician.party} • {politician.chamber} • {politician.state} • {politician.tradeCount} trades
                              </div>
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </form>
              <div className="mt-4 text-sm text-gray-500">
                Popular: Nancy Pelosi, Kevin McCarthy, Elizabeth Warren
              </div>
            </div>

            {/* Stock Search */}
            <div 
              className="rounded-lg p-6 border" 
              style={{ background: 'linear-gradient(10deg, var(--c-navy-700), var(--c-navy-800))', borderColor: 'var(--c-navy-600)' }}
              ref={stockDropdownRef}
            >
              <h3 className="text-xl font-semibold text-white mb-4 flex items-center">
                <svg className="w-6 h-6 mr-2 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 00-2-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                Stock Search
              </h3>
              <p className="text-gray-400 mb-4">
                See which members traded a specific stock
              </p>
              <form onSubmit={handleStockSearch}>
                <div className="relative">
                  <div className="flex gap-2">
                    <div className="flex-1 relative">
                      <input
                        type="text"
                        placeholder="Enter stock ticker or company (2+ chars)..."
                        value={stockSearchDisplay}
                        onChange={handleStockInputChange}
                        className="w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-green-400"
                      />
                      {loadingStocks && (
                        <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-green-400"></div>
                        </div>
                      )}
                    </div>
                    <button
                      type="submit"
                      className="px-6 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors"
                    >
                      Search
                    </button>
                  </div>
                  
                  {/* Stock Dropdown */}
                  {showStockDropdown && stockResults.length > 0 && (
                    <div className="absolute top-full left-0 right-14 mt-1 bg-gray-900 border border-gray-600 rounded-lg shadow-lg z-10 max-h-60 overflow-y-auto">
                      {stockResults.map((stock) => (
                        <button
                          key={stock.asset_id}
                          type="button"
                          onClick={() => handleStockSelect(stock)}
                          className="w-full px-4 py-3 text-left hover:bg-gray-700 transition-colors border-b border-gray-700 last:border-b-0"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-3">
                              <div className="w-10 h-10 bg-gradient-to-br from-green-500 to-blue-600 rounded-lg flex items-center justify-center flex-shrink-0">
                                <span className="text-white font-bold text-xs">{stock.ticker}</span>
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="text-white font-medium truncate">{stock.company_name}</div>
                                <div className="text-sm text-gray-400">
                                  {stock.ticker} • {stock.tradeCount} trades
                                </div>
                              </div>
                            </div>
                            <div className="text-right flex-shrink-0">
                              <div className="text-sm text-green-400 font-semibold">
                                {formatCurrency(stock.totalVolume)}
                              </div>
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </form>
              <div className="mt-4 text-sm text-gray-500">
                Popular: TSLA, AAPL, NVDA, MSFT, GOOGL
              </div>
            </div>
          </div>
        </section>
      </div>
    );
  } 
// webstack/src/components/IssuersTable.tsx
"use client";

import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import Link from 'next/link';
import PerformanceMonitor, { usePerformanceMonitor } from './PerformanceMonitor';

type IssuerData = {
  asset_id: number;
  company_name: string;
  ticker: string | null;
  lastTraded: Date | string | null; // Can be Date (server-side) or string (from API)
  totalVolume: number;
  tradeCount: number;
  politicianCount: number;
  sector: string;
  currentPrice: number;
  priceChange: number;
  priceData: number[]; // 30-day price sparkline data
};

type Props = {
  issuers: IssuerData[];
};

type SortOption = 'issuer' | 'lastTraded' | 'volume' | 'trades' | 'politicians' | 'price';
type SortDirection = 'asc' | 'desc';

// Pre-compute search-optimized issuer data with ALL expensive operations pre-calculated
type OptimizedIssuer = IssuerData & {
  searchString: string;
  lastTradedTime: number;
  companyNameLower: string; // Pre-computed for faster sorting
};

function formatCurrency(value: number): string {
  if (value >= 1e9) {
    return `$${(value / 1e9).toFixed(2)}B`;
  }
  if (value >= 1e6) {
    return `$${(value / 1e6).toFixed(1)}M`;
  }
  if (value >= 1e3) {
    return `$${(value / 1e3).toFixed(1)}K`;
  }
  return `$${value}`;
}

function formatDate(date: Date | string | null): string {
  if (!date) return 'N/A';
  
  // Handle both Date objects and date strings
  const dateObj = date instanceof Date ? date : new Date(date);
  
  // Check if it's a valid date
  if (isNaN(dateObj.getTime())) return 'N/A';
  
  return dateObj.toLocaleDateString('en-US', { 
    year: 'numeric', 
    month: 'short', 
    day: 'numeric' 
  });
}

// Sparkline component - memoized to prevent re-renders
const Sparkline = ({ data, className = "w-24 h-8" }: { data: number[], className?: string }) => {
  if (!data || data.length === 0) return <div className={className}></div>;
  
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min;
  
  if (range === 0) return <div className={className}></div>;
  
  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * 100;
    const y = 100 - ((value - min) / range) * 100;
    return `${x},${y}`;
  }).join(' ');
  
  const isPositive = data[data.length - 1] > data[0];
  
  return (
    <svg className={className} viewBox="0 0 100 100" preserveAspectRatio="none">
      <polyline
        fill="none"
        stroke={isPositive ? "#10b981" : "#ef4444"}
        strokeWidth="2"
        points={points}
      />
    </svg>
  );
};

// ULTRA-OPTIMIZED debounce hook - prevents ANY expensive operations on keystroke
function useDebouncedInput(delay: number) {
  const [displayValue, setDisplayValue] = useState('');
  const [debouncedValue, setDebouncedValue] = useState('');
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const setValue = useCallback((value: string) => {
    // CRITICAL: Only update display immediately - no other operations
    setDisplayValue(value);
    
    // Clear existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    
    // Set new timeout for debounced value - ONLY this triggers expensive operations
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

export default function IssuersTable({ issuers }: Props) {
  const { measureOperation } = usePerformanceMonitor('IssuersTable', process.env.NODE_ENV === 'development');

  // Use enhanced debounced inputs - NO expensive operations on keystroke
  const [issuerSearchDisplay, issuerSearchDebounced, setIssuerSearch] = useDebouncedInput(300);
  const [sectorFilter, setSectorFilter] = useState('');
  const [sortBy, setSortBy] = useState<SortOption>('volume');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  // NEW: Search state for dynamic issuer search
  const [searchResults, setSearchResults] = useState<IssuerData[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);



  // NEW: Dynamic search effect - searches ALL issuers when typing
  useEffect(() => {
    const searchIssuers = async () => {
      // Only search if issuer search has 2+ characters
      if (issuerSearchDebounced.length < 2) {
        setSearchResults([]);
        setSearchError(null);
        return;
      }

      setIsSearching(true);
      setSearchError(null);
      
      try {
        console.log(`🔍 ISSUERS: Searching for "${issuerSearchDebounced}"`);
        const response = await fetch(`/api/search/issuers?q=${encodeURIComponent(issuerSearchDebounced)}&limit=50`);
        
        if (response.ok) {
          const results = await response.json();
          setSearchResults(results);
          console.log(`📊 ISSUERS: Found ${results.length} matching issuers`);
        } else {
          throw new Error(`Search failed: ${response.status}`);
        }
      } catch (error) {
        console.error('Error searching issuers:', error);
        setSearchError('Failed to search issuers. Please try again.');
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    };

    searchIssuers();
  }, [issuerSearchDebounced]); // Only trigger on debounced issuer search changes

  // Determine which dataset to use: search results or default issuers
  const currentIssuers = useMemo(() => {
    return issuerSearchDebounced.length >= 2 ? searchResults : issuers;
  }, [issuerSearchDebounced, searchResults, issuers]);

  // Pre-compute optimized issuer data with ALL expensive operations - ONLY depends on current issuers
  const optimizedIssuers = useMemo<OptimizedIssuer[]>(() => {
    return measureOperation('optimizeIssuers', () => {
      return currentIssuers.map(issuer => {
        // Handle both Date objects and date strings from API
        let lastTradedTime = 0;
        if (issuer.lastTraded) {
          if (issuer.lastTraded instanceof Date) {
            lastTradedTime = issuer.lastTraded.getTime();
          } else if (typeof issuer.lastTraded === 'string') {
            lastTradedTime = new Date(issuer.lastTraded).getTime();
          }
        }

        return {
          ...issuer,
          searchString: `${issuer.company_name} ${issuer.ticker || ''} ${issuer.sector}`.toLowerCase(),
          lastTradedTime,
          companyNameLower: issuer.company_name.toLowerCase() // Pre-compute for faster sorting
        };
      });
    }) as OptimizedIssuer[];
  }, [currentIssuers, measureOperation]);

  // Get unique sectors for filter dropdown - ONLY depends on current issuers  
  const sectors = useMemo(() => {
    return measureOperation('computeSectors', () => {
      const uniqueSectors = new Set(currentIssuers.map(i => i.sector));
      return Array.from(uniqueSectors).sort();
    }) as string[];
  }, [currentIssuers, measureOperation]);

  // PERFORMANCE-CRITICAL: Filter function with early exits and no dependencies
  const filterIssuers = useCallback((
    issuers: OptimizedIssuer[], 
    issuerSearch: string, 
    sectorFilter: string
  ) => {
    // Only apply text filters if they have at least 2 characters
    const hasValidIssuerSearch = issuerSearch.trim().length >= 2;
    
    // If no valid filters, return original array (avoid unnecessary work)
    if (!hasValidIssuerSearch && !sectorFilter) {
      return issuers;
    }

    const lowerIssuerSearch = issuerSearch.toLowerCase();
    
    
    return issuers.filter(issuer => {
      // Sector filter first (fastest check)
      if (sectorFilter && issuer.sector !== sectorFilter) return false;
      
      // Issuer search (only if 2+ characters)
      if (hasValidIssuerSearch && !issuer.searchString.includes(lowerIssuerSearch)) return false;
      
      // Politician search removed
      
      return true;
    });
  }, []); // NO dependencies to prevent recreation

  // PERFORMANCE-CRITICAL: Sort function with no dependencies
  const sortIssuers = useCallback((issuers: OptimizedIssuer[], sortBy: SortOption, sortDirection: SortDirection) => {
    if (issuers.length <= 1) return issuers;
    
    const sorted = [...issuers];
    
    // Use optimized sorting strategies
    sorted.sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'issuer':
          // Use pre-computed lowercase for faster comparison
          comparison = a.companyNameLower < b.companyNameLower ? -1 : 
                      a.companyNameLower > b.companyNameLower ? 1 : 0;
          break;
        case 'lastTraded':
          comparison = a.lastTradedTime - b.lastTradedTime;
          break;
        case 'volume':
          comparison = a.totalVolume - b.totalVolume;
          break;
        case 'trades':
          comparison = a.tradeCount - b.tradeCount;
          break;
        case 'politicians':
          comparison = a.politicianCount - b.politicianCount;
          break;
        case 'price':
          comparison = a.currentPrice - b.currentPrice;
          break;
      }
      
      return sortDirection === 'asc' ? comparison : -comparison;
    });

    return sorted;
  }, []); // NO dependencies to prevent recreation

  // CRITICAL: Main computation ONLY triggered by debounced values - NEVER by display values
  const { filteredIssuers } = measureOperation('filterAndSort', () => {
    // Filter by search terms using ONLY debounced values - NEVER display values
    const filtered = filterIssuers(
      optimizedIssuers, 
      issuerSearchDebounced, 
      sectorFilter
    );
    
    // Sort the filtered results
    const sorted = sortIssuers(filtered, sortBy, sortDirection);

    return {
      filteredIssuers: sorted
    };
  }) as { filteredIssuers: OptimizedIssuer[] };

  // Memoized event handlers to prevent re-renders
  const handleSort = useCallback((option: SortOption) => {
    if (sortBy === option) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(option);
      setSortDirection('desc');
    }
  }, [sortBy]);

  // PERFORMANCE-CRITICAL: Input handlers that ONLY update display values
  const handleIssuerSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setIssuerSearch(e.target.value); // This only updates display value immediately
  }, [setIssuerSearch]);

  // Politician search removed

  const handleSectorFilterChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setSectorFilter(e.target.value);
  }, []);

  const getSortIcon = useCallback((option: SortOption) => {
    if (sortBy !== option) {
      return (
        <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
        </svg>
      );
    }
    
    return sortDirection === 'asc' ? (
      <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
      </svg>
    ) : (
      <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4h13M3 8h9m-9 4h9m5-4v12m0 0l-4-4m4 4l4-4" />
      </svg>
    );
  }, [sortBy, sortDirection]);

  return (
    <div>
      <PerformanceMonitor componentName="IssuersTable" enabled={process.env.NODE_ENV === 'development'} />
      
      {/* Search and Filter Bar */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
          {/* Issuer Search */}
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Issuer name or ticker
            </label>
            <div className="relative">
              <input
                type="text"
                placeholder="Search ALL companies or tickers (2+ chars)..."
                value={issuerSearchDisplay}
                onChange={handleIssuerSearchChange}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-gray-700 placeholder-gray-700 focus:outline-none focus:border-blue-400"
              />
              {isSearching && (
                <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-400"></div>
                </div>
              )}
            </div>
          </div>

          {/* Politician Search removed */}

          {/* Sector Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Sector
            </label>
            <select
              value={sectorFilter}
              onChange={handleSectorFilterChange}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-gray-200 focus:outline-none focus:border-blue-400"
            >
              <option value="" className="text-gray-900 bg-white">All Sectors</option>
              {sectors.map((sector: string) => (
                <option key={sector} value={sector} className="text-gray-900 bg-white">{sector.replace(/"/g, '&quot;')}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Results Count and Search Status */}
        <div className="flex items-center gap-4">
          <div className="text-sm text-gray-400">
            {issuerSearchDebounced.length >= 2 ? (
              <>
                {isSearching ? (
                  <span className="flex items-center gap-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-400"></div>
                    Searching all issuers...
                  </span>
                ) : (
                  <>
                    Showing {filteredIssuers.length} of {searchResults.length} search results for "{issuerSearchDebounced}"
                    {sectorFilter ? ' (filtered)' : ''}
                  </>
                )}
              </>
            ) : (
              <>
                Showing {filteredIssuers.length} of {issuers.length} top issuers
                {sectorFilter ? ' (filtered)' : ''}
              </>
            )}
          </div>
          
          {searchError && (
            <div className="text-sm text-red-400 flex items-center gap-2">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              {searchError}
            </div>
          )}
        </div>
      </div>

      {/* Main Data Table */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full" style={{ background: 'var(--c-navy-50)', color: 'var(--c-navy)' }}>
            <thead className="bg-gray-700">
              <tr className="text-left">
                <th 
                  className="px-6 py-4 text-sm font-medium text-gray-300 cursor-pointer hover:text-white transition-colors"
                  onClick={() => handleSort('issuer')}
                >
                  <div className="flex items-center gap-2">
                    TRADED ISSUER
                    {getSortIcon('issuer')}
                  </div>
                </th>
                <th 
                  className="px-6 py-4 text-sm font-medium text-gray-300 cursor-pointer hover:text-white transition-colors"
                  onClick={() => handleSort('lastTraded')}
                >
                  <div className="flex items-center gap-2">
                    LAST TRADED
                    {getSortIcon('lastTraded')}
                  </div>
                </th>
                <th 
                  className="px-6 py-4 text-sm font-medium text-gray-300 cursor-pointer hover:text-white transition-colors"
                  onClick={() => handleSort('volume')}
                >
                  <div className="flex items-center gap-2">
                    VOLUME
                    {getSortIcon('volume')}
                  </div>
                </th>
                <th 
                  className="px-6 py-4 text-sm font-medium text-gray-300 cursor-pointer hover:text-white transition-colors"
                  onClick={() => handleSort('trades')}
                >
                  <div className="flex items-center gap-2">
                    TRADES
                    {getSortIcon('trades')}
                  </div>
                </th>
                <th 
                  className="px-6 py-4 text-sm font-medium text-gray-300 cursor-pointer hover:text-white transition-colors"
                  onClick={() => handleSort('politicians')}
                >
                  <div className="flex items-center gap-2">
                    POLITICIANS
                    {getSortIcon('politicians')}
                  </div>
                </th>
                <th className="px-6 py-4 text-sm font-medium text-gray-300">SECTOR</th>
                <th className="px-6 py-4 text-sm font-medium text-gray-300">LAST 30 DAYS</th>
                <th 
                  className="px-6 py-4 text-sm font-medium text-gray-300 cursor-pointer hover:text-white transition-colors"
                  onClick={() => handleSort('price')}
                >
                  <div className="flex items-center gap-2">
                    PRICE
                    {getSortIcon('price')}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {filteredIssuers.map((issuer: OptimizedIssuer) => (
                <tr key={issuer.asset_id} className="hover:bg-[var(--c-jade-100)] transition-colors">
                  <td className="px-6 py-4">
                    <Link 
                      href={`/stocks/${issuer.asset_id}`}
                      className="text-blue-400 hover:text-blue-300"
                    >
                      <div className="font-semibold" style={{ color: 'var(--c-jade)' }}>{issuer.company_name}</div>
                      {issuer.ticker && (
                        <div className="text-sm text-gray-400 font-mono">{issuer.ticker}</div>
                      )}
                    </Link>
                  </td>
                  <td className="px-6 py-4 text-gray-300">
                    {formatDate(issuer.lastTraded)}
                  </td>
                  <td className="px-6 py-4 text-green-400 font-semibold">
                    {formatCurrency(issuer.totalVolume)}
                  </td>
                  <td className="px-6 py-4 text-blue-400 font-semibold">
                    {issuer.tradeCount}
                  </td>
                  <td className="px-6 py-4 text-yellow-400 font-semibold">
                    {issuer.politicianCount}
                  </td>
                  <td className="px-6 py-4 text-gray-300">
                    <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-gray-700 text-gray-300">
                      {issuer.sector}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <Sparkline data={issuer.priceData} />
                  </td>
                  <td className="px-6 py-4">
                    <div className="font-semibold text-white">
                      ${issuer.currentPrice.toFixed(2)}
                    </div>
                    <div className={`text-sm font-semibold ${
                      issuer.priceChange >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {issuer.priceChange >= 0 ? '+' : ''}{issuer.priceChange.toFixed(2)}%
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {filteredIssuers.length === 0 && (
            <div className="text-center py-12">
              {issuerSearchDebounced.length >= 2 ? (
                <div>
                  {/* eslint-disable-next-line react/no-unescaped-entities */}
                  <p className="text-gray-400 mb-2">No issuers found matching "{issuerSearchDebounced}"</p>
                  <p className="text-sm text-gray-500">Try a different search term or check for typos.</p>
                </div>
              ) : (
                <p className="text-gray-400">No issuers found matching your filter criteria.</p>
              )}
            </div>
          )}
          
          {/* Load More Button for Search Results */}
          {issuerSearchDebounced.length >= 2 && searchResults.length > 0 && searchResults.length >= 50 && (
            <div className="text-center py-6 border-t border-gray-700">
              <button 
                onClick={() => {
                  // Could implement loading more results here
                  console.log('Load more search results requested');
                }}
                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
              >
                Load More Results
              </button>
              <p className="text-xs text-gray-500 mt-2">
                Showing first 50 results. Click to load more.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
} 
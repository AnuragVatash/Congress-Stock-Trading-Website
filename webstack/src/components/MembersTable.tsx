// webstack/src/components/MembersTable.tsx
"use client";

import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import Link from 'next/link';
import Image from 'next/image';

type MemberWithStats = {
  member_id: number;
  name: string;
  photo_url: string | null;
  party: string | null;
  state: string | null;
  chamber: string | null;
  tradeCount: number;
  totalVolume: number;
  latestTradeDate: Date | null;
};

type SortOption = 'name' | 'volume' | 'trades' | 'latestTrade';
type SortDirection = 'asc' | 'desc';

type Props = {
  members: MemberWithStats[];
};

// Pre-compute search-optimized member data
type OptimizedMember = MemberWithStats & {
  searchString: string;
  latestTradeTime: number;
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

function formatDate(date: Date | null): string {
  if (!date) return 'N/A';
  return date.toLocaleDateString('en-US', { 
    year: 'numeric', 
    month: 'short', 
    day: 'numeric' 
  });
}

// Enhanced debounce hook that batches updates (same as IssuersTable)
function useDebouncedInput(delay: number) {
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
    
    // Set new timeout for debounced value
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

export default function MembersTable({ members }: Props) {
  // Use enhanced debounced input (same pattern as IssuersTable)
  const [searchDisplay, searchDebounced, setSearchTerm] = useDebouncedInput(150);
  const [sortBy, setSortBy] = useState<SortOption>('latestTrade');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [pageSize, setPageSize] = useState(10);

  // Pre-compute optimized member data with search strings
  const optimizedMembers = useMemo<OptimizedMember[]>(() => {
    return members.map(member => ({
      ...member,
      searchString: `${member.name} ${member.party || ''} ${member.state || ''} ${member.chamber || ''}`.toLowerCase(),
      latestTradeTime: member.latestTradeDate?.getTime() || 0
    }));
  }, [members]);

  // Memoized filter function with early exit optimization
  const filterMembers = useCallback((members: OptimizedMember[], searchTerm: string) => {
    // Only filter if search term has at least 2 characters
    if (searchTerm.trim().length < 2) return members;
    
    const lowerSearchTerm = searchTerm.toLowerCase();
    return members.filter(member => member.searchString.includes(lowerSearchTerm));
  }, []);

  // Memoized sort function
  const sortMembers = useCallback((members: OptimizedMember[], sortBy: SortOption, sortDirection: SortDirection) => {
    if (members.length <= 1) return members;
    
    const sorted = [...members];
    
    sorted.sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'volume':
          comparison = a.totalVolume - b.totalVolume;
          break;
        case 'trades':
          comparison = a.tradeCount - b.tradeCount;
          break;
        case 'latestTrade':
          comparison = a.latestTradeTime - b.latestTradeTime;
          break;
      }
      
      return sortDirection === 'asc' ? comparison : -comparison;
    });

    return sorted;
  }, []);

  // Main computation using ONLY debounced values
  const { filteredMembers, displayedMembers } = useMemo(() => {
    // Filter by search term using debounced value ONLY
    const filtered = filterMembers(optimizedMembers, searchDebounced);
    
    // Sort the filtered results
    const sorted = sortMembers(filtered, sortBy, sortDirection);

    return {
      filteredMembers: sorted,
      displayedMembers: sorted.slice(0, pageSize)
    };
  }, [optimizedMembers, searchDebounced, sortBy, sortDirection, pageSize, filterMembers, sortMembers]);

  const handleSort = useCallback((option: SortOption) => {
    if (sortBy === option) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(option);
      setSortDirection('desc');
    }
  }, [sortBy]);

  // Optimized input handler
  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(e.target.value);
  }, [setSearchTerm]);

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
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <h2 className="text-2xl font-bold text-white">All Active Trading Members</h2>
        <div className="flex flex-col sm:flex-row gap-4 sm:ml-auto">
          {/* Page Size Selector */}
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-400">Show:</label>
            <select
              value={pageSize}
              onChange={(e) => setPageSize(Number(e.target.value))}
              className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:border-blue-400"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </div>

          {/* Search Input */}
          <div className="relative">
            <input
              type="text"
              placeholder="Search members (2+ chars)..."
              value={searchDisplay}
              onChange={handleSearchChange}
              className="w-full sm:w-64 px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-400"
            />
            <svg 
              className="absolute right-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400"
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          
          {/* Results Count */}
          <div className="flex items-center text-sm text-gray-400">
            Showing {displayedMembers.length} of {filteredMembers.length} 
            {searchDebounced.trim().length >= 2 ? ' filtered' : ''} members
          </div>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full" style={{ background: 'var(--c-navy-50)', color: 'var(--c-navy)' }}>
            <thead className="bg-gray-700">
              <tr className="text-left">
                <th 
                  className="px-6 py-4 text-sm font-medium text-gray-300 cursor-pointer hover:text-white transition-colors"
                  onClick={() => handleSort('name')}
                >
                  <div className="flex items-center gap-2">
                    Member
                    {getSortIcon('name')}
                  </div>
                </th>
                <th className="px-6 py-4 text-sm font-medium text-gray-300">Party</th>
                <th className="px-6 py-4 text-sm font-medium text-gray-300">Chamber</th>
                <th className="px-6 py-4 text-sm font-medium text-gray-300">State</th>
                <th 
                  className="px-6 py-4 text-sm font-medium text-gray-300 cursor-pointer hover:text-white transition-colors"
                  onClick={() => handleSort('trades')}
                >
                  <div className="flex items-center gap-2">
                    Trades
                    {getSortIcon('trades')}
                  </div>
                </th>
                <th 
                  className="px-6 py-4 text-sm font-medium text-gray-300 cursor-pointer hover:text-white transition-colors"
                  onClick={() => handleSort('volume')}
                >
                  <div className="flex items-center gap-2">
                    Volume
                    {getSortIcon('volume')}
                  </div>
                </th>
                <th 
                  className="px-6 py-4 text-sm font-medium text-gray-300 cursor-pointer hover:text-white transition-colors"
                  onClick={() => handleSort('latestTrade')}
                >
                  <div className="flex items-center gap-2">
                    Latest Trade
                    {getSortIcon('latestTrade')}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {displayedMembers.map((member) => (
                <tr key={member.member_id} className="hover:bg-[var(--c-jade-100)] transition-colors">
                  <td className="px-6 py-4">
                    <Link 
                      href={`/members/${member.member_id}`}
                      className="flex items-center space-x-3 text-blue-400 hover:text-blue-300"
                    >
                      <div className="relative w-8 h-8 rounded-full overflow-hidden bg-gray-600 flex-shrink-0">
                        {member.photo_url ? (
                          <Image
                            src={member.photo_url}
                            alt={member.name}
                            fill
                            className="object-cover"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-gray-400 text-xs font-semibold">
                            {member.name.charAt(0)}
                          </div>
                        )}
                      </div>
                      <span className="font-medium" style={{ color: 'var(--c-navy)' }}>{member.name}</span>
                    </Link>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                      member.party === 'Republican' 
                        ? 'bg-red-900 text-red-300' 
                        : member.party === 'Democrat'
                        ? 'bg-blue-900 text-blue-300'
                        : 'bg-gray-700 text-gray-300'
                    }`}>
                      {member.party}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-300">{member.chamber}</td>
                  <td className="px-6 py-4 text-gray-300">{member.state}</td>
                  <td className="px-6 py-4 text-blue-400 font-semibold">{member.tradeCount}</td>
                  <td className="px-6 py-4 text-green-400 font-semibold">{formatCurrency(member.totalVolume)}</td>
                  <td className="px-6 py-4 text-gray-300">{formatDate(member.latestTradeDate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {displayedMembers.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-400">No members found matching your search criteria.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
} 
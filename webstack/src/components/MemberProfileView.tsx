'use client';

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import MemberProfileCard from "@/src/components/MemberProfileCard";
import TradesTable from "@/src/components/TradesTable";
import MemberTradingCharts from "./MemberTradingCharts";
import type { Members as Member, Transactions, Assets } from '@prisma/client';

// Define the type for a trade that includes its related asset
type TradeWithAsset = Transactions & {
  Assets: Assets | null;
};

// Define the props for our new client component
type MemberProfileViewProps = {
  member: Member;
  trades: TradeWithAsset[];
};

export default function MemberProfileView({ member, trades }: MemberProfileViewProps) {
  // Pagination state
  const [pageSize, setPageSize] = useState(25);
  const [currentPage, setCurrentPage] = useState(1);
  
  const totalPages = trades ? Math.ceil(trades.length / pageSize) : 0;
  const paginatedTrades = trades ? trades.slice((currentPage - 1) * pageSize, currentPage * pageSize) : [];

  // Handlers for pagination
  const handlePageSizeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setPageSize(Number(e.target.value));
    setCurrentPage(1); // Reset to first page on page size change
  };

  const handlePrevPage = () => {
    setCurrentPage((p) => Math.max(1, p - 1));
  };

  const handleNextPage = () => {
    setCurrentPage((p) => Math.min(totalPages, p + 1));
  };
  
  const handlePageClick = (page: number) => {
    setCurrentPage(page);
  };

  return (
    <div className="min-h-screen" style={{ background: 'var(--c-navy)' }}>
      {/* Back button in top left corner */}
      <div style={{ margin: '1.5rem 0 0 1.5rem', position: 'absolute', top: 0, left: 0 }}>
        <Link href="/">
          <Image src="/return.png" alt="Back to Home" width={40} height={40} style={{ cursor: 'pointer' }} />
        </Link>
      </div>
      <div className="max-w-7xl mx-auto p-4 md:p-8">
        <div className="card" style={{ background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))' }}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
            <div className="lg:col-span-1">
              <MemberProfileCard member={member} trades={trades} />
            </div>
            <div className="lg:col-span-2">
              <TradesTable trades={paginatedTrades} />
              {/* Pagination controls and page size selector */}
              <div className="flex flex-col sm:flex-row items-center justify-between mt-4 gap-2">
                <div className="flex items-center gap-2">
                  <label htmlFor="pageSize" className="text-sm text-gray-400">Transactions per page:</label>
                  <select
                    id="pageSize"
                    value={pageSize}
                    onChange={handlePageSizeChange}
                    className="px-3 py-2 !bg-gray-700 !border-gray-700 !text-gray-200 rounded-lg text-sm focus:outline-none focus:border-blue-400"
                  >
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={75}>75</option>
                    <option value={100}>100</option>
                  </select>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={handlePrevPage} disabled={currentPage === 1} className="px-2 py-1 rounded bg-gray-700 text-gray-300 disabled:opacity-50">Prev</button>
                  
                  {/* Scrollable container for page numbers */}
                  <div className="flex items-center gap-2 overflow-x-auto whitespace-nowrap px-2" style={{ maxWidth: '400px', scrollbarWidth: 'thin' }}>
                    {Array.from({ length: totalPages }, (_, i) => (
                      <button
                        key={i + 1}
                        onClick={() => handlePageClick(i + 1)}
                        className={`px-3 py-1 rounded flex-shrink-0 ${currentPage === i + 1 ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'}`}
                      >
                        {i + 1}
                      </button>
                    ))}
                  </div>

                  <button onClick={handleNextPage} disabled={currentPage === totalPages} className="px-2 py-1 rounded bg-gray-700 text-gray-300 disabled:opacity-50">Next</button>
                </div>
              </div>
            </div>
          </div>
          
          {/* Trading Charts Section */}
          <div className="mt-8">
            <MemberTradingCharts trades={trades} />
          </div>
        </div>
      </div>
    </div>
  );
} 
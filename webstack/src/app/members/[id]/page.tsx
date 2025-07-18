// /app/members/[id]/page.tsx
// OPTIMIZED - Loads only necessary data with performance monitoring

import MemberProfileCard from "@/src/components/MemberProfileCard";
import TradesTable from "@/src/components/TradesTable";
import MemberTradingCharts from "@/src/components/MemberTradingCharts";
import { PrismaClient } from '@prisma/client';
import { notFound } from 'next/navigation';

const prisma = new PrismaClient();

// Performance monitoring functions
function measureTime<T>(operationName: string, fn: () => T): T {
  const start = performance.now();
  const result = fn();
  const end = performance.now();
  const duration = end - start;
  
  console.log(`🚀 MEMBER: ${operationName} took ${duration.toFixed(2)}ms`);
  return result;
}

async function measureTimeAsync<T>(operationName: string, fn: () => Promise<T>): Promise<T> {
  const start = performance.now();
  const result = await fn();
  const end = performance.now();
  const duration = end - start;
  
  console.log(`🚀 MEMBER: ${operationName} took ${duration.toFixed(2)}ms`);
  return result;
}

export default async function MemberProfilePage({ params }: { params: { id: string } }) {
  const pageStart = performance.now();
  const memberId = Number(params.id);

  console.log(`🔍 MEMBER: Starting member ${memberId} profile page render`);

  // Fetch data in parallel with performance monitoring
  const [member, trades] = await Promise.all([
    measureTimeAsync('Member Info Query', () =>
      prisma.members.findUnique({
        where: { member_id: memberId }
      })
    ),
    measureTimeAsync('Member Trades Query', () =>
      prisma.transactions.findMany({
        where: {
          Filings: {
            member_id: memberId
          }
        },
        include: {
          Assets: true
        },
        orderBy: {
          transaction_date: 'desc'
        },
        take: 500 // Reasonable limit for performance - can add pagination later if needed
      })
    )
  ]);

  if (!member) {
    notFound();
  }

  const pageEnd = performance.now();
  console.log(`🚀 MEMBER: TOTAL PAGE TIME: ${(pageEnd - pageStart).toFixed(2)}ms`);
  console.log(`📊 MEMBER: Loaded ${trades.length} transactions for ${member.name}`);

  return (
    <div className="min-h-screen bg-gray-900">
      <div className="max-w-7xl mx-auto p-4 md:p-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
          <div className="lg:col-span-1">
            <MemberProfileCard member={member} trades={trades} />
          </div>
          <div className="lg:col-span-2">
            <TradesTable trades={trades} />
          </div>
        </div>
        
        {/* Trading Charts Section */}
        <div className="mt-8">
          <MemberTradingCharts trades={trades} memberName={member.name} />
        </div>
      </div>
    </div>
  );
}
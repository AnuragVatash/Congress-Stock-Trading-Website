// /app/members/[id]/page.tsx
// OPTIMIZED - Loads only necessary data with performance monitoring

import MemberProfileCard from "@/src/components/MemberProfileCard";
import TradesTable from "@/src/components/TradesTable";
import MemberTradingCharts from "@/src/components/MemberTradingCharts";
import { PrismaClient } from '@prisma/client';
import { notFound } from 'next/navigation';
import Link from 'next/link';

const prisma = new PrismaClient();

// Performance monitoring functions
async function measureTimeAsync<T>(operationName: string, fn: () => Promise<T>): Promise<T> {
  const start = performance.now();
  const result = await fn();
  const end = performance.now();
  const duration = end - start;
  
  console.log(`🚀 MEMBER: ${operationName} took ${duration.toFixed(2)}ms`);
  return result;
}

export async function generateStaticParams() {
  // 1. Top 5 featured members (by trade count)
  const featured = await prisma.$queryRaw<Array<{ member_id: number }>>`SELECT m.member_id FROM Members m LEFT JOIN Filings f ON m.member_id = f.member_id LEFT JOIN Transactions t ON f.filing_id = t.filing_id GROUP BY m.member_id HAVING COUNT(t.transaction_id) > 0 ORDER BY COUNT(t.transaction_id) DESC LIMIT 5`;
  // 2. Members in the 10 most recent trades
  const recent = await prisma.transactions.findMany({
    include: { Filings: { include: { Members: true } } },
    orderBy: { transaction_date: 'desc' },
    take: 10
  });
  // 3. Top 10 by total volume (from /members page)
  const topVolume = await prisma.$queryRaw<Array<{ member_id: number }>>`SELECT m.member_id FROM Members m LEFT JOIN Filings f ON m.member_id = f.member_id LEFT JOIN Transactions t ON f.filing_id = t.filing_id GROUP BY m.member_id HAVING COUNT(t.transaction_id) > 0 ORDER BY COALESCE(SUM((t.amount_range_low + t.amount_range_high) / 2.0), 0) DESC LIMIT 10`;

  // Collect all IDs
  const ids = [
    ...featured.map((m) => m.member_id),
    ...recent.map((t) => t.Filings?.Members?.member_id).filter(Boolean),
    ...topVolume.map((m) => m.member_id)
  ];
  // Deduplicate
  const uniqueIds = Array.from(new Set(ids)).map(id => ({ id: String(id) }));
  return uniqueIds;
}

export const revalidate = 3600;
export const dynamicParams = true;

export default async function MemberProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const pageStart = performance.now();
  const { id } = await params;
  const memberId = Number(id);

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
    <div className="min-h-screen" style={{ background: 'var(--c-navy)' }}>
      <div className="max-w-7xl mx-auto p-4 md:p-8">
        <div className="card" style={{ background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))' }}>
          <div className="flex items-center mb-4">
            <Link href="/" className="button-secondary">
              ← Back to Home
            </Link>
          </div>
        </div>
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
// /app/members/[id]/page.tsx
// This is now a pure Server Component for data fetching.

import { prisma } from '@/src/lib/prisma';
import { notFound } from 'next/navigation';
import MemberProfileView from '@/src/components/MemberProfileView';

// Performance monitoring functions
async function measureTimeAsync<T>(operationName: string, fn: () => Promise<T>): Promise<T> {
  const start = performance.now();
  const result = await fn();
  const end = performance.now();
  const duration = end - start;
  
  console.log(`🚀 MEMBER: ${operationName} took ${duration.toFixed(2)}ms`);
  return result;
}

// Force dynamic rendering to avoid build-time database queries
export const dynamic = 'force-dynamic';

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

  return <MemberProfileView member={member} trades={trades} />;
}
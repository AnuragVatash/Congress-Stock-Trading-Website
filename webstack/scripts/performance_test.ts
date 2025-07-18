// webstack/scripts/performance_test.ts
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function testOldQuery() {
  console.log('Testing old query (with nested includes) - FULL DATASET...');
  const start = Date.now();
  
  try {
    const assets = await prisma.assets.findMany({
      include: {
        Transactions: {
          include: {
            Filings: {
              include: {
                Members: true
              }
            }
          }
        }
      }
      // No take limit - load ALL assets
    });
    
    const end = Date.now();
    console.log(`Old query took ${end - start}ms for ${assets.length} assets`);
    console.log(`Total transactions loaded: ${assets.reduce((sum, asset) => sum + asset.Transactions.length, 0)}`);
    
    return end - start;
  } catch (error) {
    console.error('Old query failed:', error);
    return -1;
  }
}

async function testNewQuery() {
  console.log('Testing new query (with raw SQL) - FULL DATASET...');
  const start = Date.now();
  
  try {
    const aggregatedAssets = await prisma.$queryRaw<Array<{
      asset_id: number;
      company_name: string;
      ticker: string | null;
      total_volume: number;
      trade_count: number;
      politician_count: number;
      last_traded: string | null;
    }>>`
      SELECT 
        a.asset_id,
        a.company_name,
        a.ticker,
        COALESCE(SUM((t.amount_range_low + t.amount_range_high) / 2), 0) as total_volume,
        COUNT(t.transaction_id) as trade_count,
        COUNT(DISTINCT f.member_id) as politician_count,
        MAX(t.transaction_date) as last_traded
      FROM Assets a
      LEFT JOIN Transactions t ON a.asset_id = t.asset_id
      LEFT JOIN Filings f ON t.filing_id = f.filing_id
      GROUP BY a.asset_id, a.company_name, a.ticker
      HAVING trade_count > 0
      ORDER BY total_volume DESC
    `;
    
    const end = Date.now();
    console.log(`New query took ${end - start}ms for ${aggregatedAssets.length} assets`);
    console.log(`Total volume calculated: ${aggregatedAssets.reduce((sum, asset) => sum + Number(asset.total_volume), 0)}`);
    
    return end - start;
  } catch (error) {
    console.error('New query failed:', error);
    return -1;
  }
}

async function testSummaryMetrics() {
  console.log('Testing summary metrics query...');
  const start = Date.now();
  
  try {
    const [totalTrades, totalFilings, totalMembers, totalAssets, totalVolume] = await Promise.all([
      prisma.transactions.count(),
      prisma.filings.count(),
      prisma.members.count(),
      prisma.assets.count(),
      prisma.$queryRaw<Array<{ total_volume: number }>>`
        SELECT COALESCE(SUM((amount_range_low + amount_range_high) / 2), 0) as total_volume
        FROM Transactions
      `
    ]);
    
    const end = Date.now();
    console.log(`Summary metrics query took ${end - start}ms`);
    console.log(`Results: ${totalTrades} trades, ${totalFilings} filings, ${totalMembers} members, ${totalAssets} assets`);
    
    return end - start;
  } catch (error) {
    console.error('Summary metrics query failed:', error);
    return -1;
  }
}

async function main() {
  console.log('=== Performance Test Results (FULL DATASET) ===\n');
  
  const oldQueryTime = await testOldQuery();
  console.log('');
  
  const newQueryTime = await testNewQuery();
  console.log('');
  
  const summaryTime = await testSummaryMetrics();
  console.log('');
  
  if (oldQueryTime > 0 && newQueryTime > 0) {
    const improvement = ((oldQueryTime - newQueryTime) / oldQueryTime * 100).toFixed(1);
    console.log(`=== Summary ===`);
    console.log(`Performance improvement: ${improvement}% faster`);
    console.log(`Old query: ${oldQueryTime}ms`);
    console.log(`New query: ${newQueryTime}ms`);
    console.log(`Summary metrics: ${summaryTime}ms`);
  }
  
  await prisma.$disconnect();
}

main().catch(console.error); 
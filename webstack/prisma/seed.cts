// prisma/seed.ts

import { PrismaClient } from '@prisma/client';

// Initialize Prisma Client
const prisma = new PrismaClient();

// URL for the legislator data, as specified in your document
const legislatorsUrl = 'https://unitedstates.github.io/congress-legislators/legislators-current.json';

// Base URL for the photos, as specified in your document
const photoBaseUrl = 'https://theunitedstates.io/images/congress/225x275/'; // Using 225x275 for thumbnails

async function main() {
  console.log('Starting the seeding process...');

  // 1. Fetch the legislator data
  console.log('Fetching legislator data...');
  const response = await fetch(legislatorsUrl);
  if (!response.ok) {
    throw new Error('Failed to fetch legislator data');
  }
  const legislatorsData: any[] = await response.json();
  console.log(`Found ${legislatorsData.length} legislators.`);

  // 2. Process and transform the data
  for (const legislator of legislatorsData) {
    const name = `${legislator.name.first} ${legislator.name.last}`;
    const lastTerm = legislator.terms[legislator.terms.length - 1]; // Get the most recent term info
    const bioguideId = legislator.id.bioguide;

    if (!bioguideId || !lastTerm) {
      console.log(`Skipping ${name} due to missing Bioguide ID or term info.`);
      continue; // Skip if essential data is missing
    }

    // This is the complete data object that matches your Prisma schema
    const memberData = {
      name: name,
      party: lastTerm.party,
      state: lastTerm.state,
      chamber: lastTerm.type === 'sen' ? 'Senate' : 'House',
      photo_url: `${photoBaseUrl}${bioguideId}.jpg` // Construct the predictable photo URL
    };

    // 3. Load into the database using 'upsert'
    // 'upsert' is smart: it will create a new member if they don't exist,
    // or update their data if they do. This makes the seed script re-runnable.
    await prisma.members.upsert({
      where: { name: memberData.name }, // Use the 'name' field as the unique identifier
      update: memberData, // What to update if they exist
      create: memberData, // What to create if they don't exist
    });

    console.log(`Upserted: ${memberData.name}`);
  }

  console.log('Seeding process completed successfully!');
}

// Execute the main function and handle potential errors
main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    // Close the Prisma Client connection
    await prisma.$disconnect();
  });
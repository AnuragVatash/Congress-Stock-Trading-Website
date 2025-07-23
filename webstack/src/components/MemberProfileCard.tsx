// /components/MemberProfileCard.tsx

import Image from 'next/image';
import MemberStats from './MemberStats';

// Define the shape of the data this component expects
type Member = {
  name: string;
  photo_url: string | null;
  party: string | null;
  state: string | null;
  chamber: string | null;
}

type Transaction = {
  amount_range_low: number | null;
  amount_range_high: number | null;
  Assets: {
    ticker: string | null;
  } | null;
};

type Props = {
  member: Member;
  trades?: Transaction[];
};

export default function MemberProfileCard({ member, trades = [] }: Props) {
  return (
    <div 
      className="card" 
      style={{ background: 'linear-gradient(5deg, var(--c-navy), var(--c-navy-600))' }}
    >
      <div className="flex flex-col items-center">
        {/*
          THIS IS THE KEY PART:
          We use the photo_url from the database as the source for the Image.
          Next.js will automatically handle fetching and optimizing this external image.
        */}
        {member.photo_url && (
          <Image
            src={member.photo_url}
            alt={`Official portrait of ${member.name}`}
            width={128}  // Define a size for the image
            height={128}
            className="rounded-full border-4 border-gray-600"
            priority // Add priority to load the main image faster
          />
        )}
        <h1 className="text-3xl font-bold mt-4 text-white" style={{ color: 'var(--c-jade)' }}>{member.name}</h1>
        <p className="text-lg text-gray-400 mt-1">
          {member.party} | {member.chamber} of {member.state}
        </p>
      </div>

      {/* Trading stats */}
      <MemberStats trades={trades} />
    </div>
  );
}
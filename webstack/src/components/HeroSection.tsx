// webstack/src/components/HeroSection.tsx

type HeroSectionProps = {
  lastUpdate?: string;
};

export default function HeroSection({ lastUpdate = "Unknown" }: HeroSectionProps) {
  return (
    <div className="text-center px-4">
      <h1 className="text-5xl md:text-6xl font-bold text-white mb-6">
        Congressional Trading
        <span className="text-blue-400 block">Transparency</span>
      </h1>
      <p className="text-xl text-gray-300 max-w-4xl mx-auto leading-relaxed mb-8">
        Track stock trades made by members of Congress in real-time. Under the STOCK Act of 2012, 
        all members must disclose their financial transactions within 45 days. We analyze this data 
        to provide insights into congressional trading patterns and performance.
      </p>
      <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
        <div className="bg-gray-800 rounded-lg px-6 py-3 border border-gray-700">
          <span className="text-sm text-gray-400">Latest Update:</span>
          <span className="text-white ml-2 font-semibold">{lastUpdate}</span>
        </div>
        <div className="bg-gray-800 rounded-lg px-6 py-3 border border-gray-700">
          <span className="text-sm text-gray-400">Data Source:</span>
          <span className="text-white ml-2 font-semibold">
            <a 
              href="https://disclosures-clerk.house.gov/FinancialDisclosure" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 underline"
            >
              House
            </a>
            <span className="text-white"> & </span>
            <a 
              href="https://efdsearch.senate.gov/search/home/" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 underline"
            >
              Senate
            </a>
            <span className="text-white"> Disclosures</span>
          </span>
        </div>
      </div>
    </div>
  );
} 
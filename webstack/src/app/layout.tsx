import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { DebugPerformance } from "@/src/components/DebugPerformance";
import "./globals.css";
import Script from "next/script";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Congress Alpha",
  description: "Track stock trades made by members of Congress in real-time. Transparency in congressional trading through comprehensive data analysis. Powered by Congress Alpha.",
  icons: {
    icon: "/favicon.ico"
  }
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased text-white`}
      >
        <header style={{ background: 'var(--c-navy)', color: '#fff', padding: '1rem' }}>
          <nav>
            {/* Top Navigation */}
          </nav>
        </header>
        {process.env.NODE_ENV === 'development' && <DebugPerformance />}
        <main>{children}</main>
        {process.env.NODE_ENV === 'production' && (
          <>
            {/* Disguised Vercel analytics and speed insights to mitigate ad blockers */}
            <Script id="va-inline" strategy="afterInteractive">{`
              window.va = window.va || function() { (window.vaq = window.vaq || []).push(arguments); };
            `}</Script>
            <Script async src="/va/script.js" data-endpoint="/va" strategy="afterInteractive" />
            <Script async src="/vs/script.js" data-endpoint="/vs" strategy="afterInteractive" />
          </>
        )}
      </body>
    </html>
  );
}

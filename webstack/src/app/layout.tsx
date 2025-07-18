import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { DebugPerformance } from "@/src/components/DebugPerformance";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Congressional Trading Tracker",
  description: "Track stock trades made by members of Congress in real-time. Transparency in congressional trading through comprehensive data analysis.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {process.env.NODE_ENV === 'development' && <DebugPerformance />}
        {children}
      </body>
    </html>
  );
}

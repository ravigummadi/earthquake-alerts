import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "earthquake.city - Real-time Earthquake Tracker",
  description: "Track earthquakes in your area with real-time updates and a beautiful 3D globe visualization.",
  keywords: ["earthquake", "seismic", "tracker", "real-time", "USGS"],
  authors: [{ name: "earthquake.city" }],
  openGraph: {
    title: "earthquake.city",
    description: "Real-time earthquake tracking for your city",
    type: "website",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0d1117",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen font-sans antialiased">
        {children}
      </body>
    </html>
  );
}

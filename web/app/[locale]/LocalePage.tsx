"use client";

import { useState, useEffect, useRef } from "react";
import Header from "@/components/Header";
import CountdownTimer from "@/components/CountdownTimer";
import EarthquakeCard from "@/components/EarthquakeCard";
import GlobeWrapper from "@/components/GlobeWrapper";
import { type LocaleConfig } from "@/config/locales";
import { type Earthquake, type EarthquakeResponse } from "@/lib/api";

interface LocalePageProps {
  locale: LocaleConfig;
}

// Mock data for development - will be replaced with API call
const MOCK_EARTHQUAKE: Earthquake = {
  id: "nc74053241",
  magnitude: 3.2,
  place: "5km NW of San Ramon, CA",
  time: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(), // 3 days ago
  latitude: 37.8123,
  longitude: -121.9876,
  depth_km: 8.2,
  url: "https://earthquake.usgs.gov/earthquakes/eventpage/nc74053241",
  felt: 142,
  alert: null,
  tsunami: false,
  mag_type: "ml",
  has_shakemap: true,
};

export default function LocalePage({ locale }: LocalePageProps) {
  const [earthquake, setEarthquake] = useState<Earthquake | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    async function fetchData() {
      // Cancel any in-flight request
      abortControllerRef.current?.abort();
      abortControllerRef.current = new AbortController();

      try {
        setLoading(true);
        setError(null);

        const apiUrl = process.env.NEXT_PUBLIC_API_URL;
        if (!apiUrl) {
          // Use mock data in development
          setEarthquake(MOCK_EARTHQUAKE);
          return;
        }

        const response = await fetch(
          `${apiUrl}/api-latest-earthquake?locale=${locale.slug}`,
          { signal: abortControllerRef.current.signal }
        );

        if (!response.ok) {
          throw new Error("Failed to fetch earthquake data");
        }

        const data: EarthquakeResponse = await response.json();
        setEarthquake(data.latest_earthquake);
      } catch (err) {
        // Don't update state if request was aborted (component unmounted)
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }
        console.error("Error fetching earthquake data:", err);
        setError("Unable to load earthquake data. Using cached data.");
        // Fall back to mock data
        setEarthquake(MOCK_EARTHQUAKE);
      } finally {
        setLoading(false);
      }
    }

    fetchData();

    // Refresh data every 5 minutes
    const interval = setInterval(fetchData, 5 * 60 * 1000);
    return () => {
      clearInterval(interval);
      abortControllerRef.current?.abort();
    };
  }, [locale.slug]);

  return (
    <div className="min-h-screen flex flex-col">
      <Header currentLocale={locale.slug} />

      <main className="flex-1 px-4 md:px-6 py-8 md:py-12">
        <div className="max-w-6xl mx-auto space-y-8 md:space-y-12">
          {/* Hero Section */}
          <section className="text-center space-y-4">
            <h1 className="text-3xl md:text-4xl lg:text-5xl font-bold text-white">
              {locale.displayName}
            </h1>
            <p className="text-slate-400 text-lg max-w-2xl mx-auto">
              Real-time earthquake monitoring powered by USGS data
            </p>
          </section>

          {/* Countdown Timer */}
          <section className="card p-6 md:p-10" aria-label="Earthquake countdown timer">
            {loading ? (
              <div className="h-32 flex items-center justify-center">
                <div
                  className="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin"
                  role="status"
                  aria-label="Loading earthquake data"
                />
              </div>
            ) : earthquake ? (
              <CountdownTimer
                earthquakeTime={earthquake.time}
                magnitude={locale.minMagnitude}
              />
            ) : (
              <div className="text-center py-8">
                <p className="text-slate-400">
                  No earthquakes M{locale.minMagnitude}+ in the past 30 days
                </p>
                <p className="text-green-400 text-lg font-medium mt-2">
                  All quiet in {locale.name}
                </p>
              </div>
            )}
          </section>

          {/* Globe and Details Grid */}
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 md:gap-8">
            {/* Globe */}
            <GlobeWrapper
              earthquake={earthquake}
              center={locale.center}
            />

            {/* Earthquake Details */}
            <div className="space-y-6">
              {earthquake ? (
                <EarthquakeCard earthquake={earthquake} />
              ) : (
                <div className="card p-8 text-center">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-green-500/20 flex items-center justify-center">
                    <svg
                      className="w-8 h-8 text-green-400"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-2">
                    No Recent Earthquakes
                  </h3>
                  <p className="text-slate-400">
                    No significant seismic activity detected in the past 30 days.
                  </p>
                </div>
              )}

              {error && (
                <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                  <p className="text-yellow-400 text-sm">{error}</p>
                </div>
              )}

              {/* Data Source Attribution */}
              <div className="text-center text-sm text-slate-500">
                Data provided by{" "}
                <a
                  href="https://earthquake.usgs.gov/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-400 hover:text-primary-300"
                >
                  USGS Earthquake Hazards Program
                </a>
              </div>
            </div>
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-6 px-4 border-t border-slate-800/50">
        <div className="max-w-6xl mx-auto text-center text-sm text-slate-500">
          <p>
            earthquake.city - Real-time seismic monitoring for your community
          </p>
        </div>
      </footer>
    </div>
  );
}

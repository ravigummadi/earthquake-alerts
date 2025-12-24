"use client";

import { useState, useEffect, useRef } from "react";
import Header from "@/components/Header";
import CountdownTimer from "@/components/CountdownTimer";
import EarthquakeCard from "@/components/EarthquakeCard";
import MapWrapper from "@/components/MapWrapper";
import {
  type Earthquake,
  type EarthquakeResponse,
  type Region,
  type LocaleConfig,
  API_BASE_URL,
  REFRESH_INTERVAL_MS,
} from "@/lib/api";

interface LocalePageProps {
  localeSlug: string;
  initialDisplayName: string;
  initialCenter: { lat: number; lng: number };
  initialMinMagnitude: number;
  allLocales: LocaleConfig[];
}

export default function LocalePage({
  localeSlug,
  initialDisplayName,
  initialCenter,
  initialMinMagnitude,
  allLocales,
}: LocalePageProps) {
  // Transform locales for Header navigation
  const headerLocales = allLocales.map((l) => ({ slug: l.slug, name: l.name }));
  const [earthquake, setEarthquake] = useState<Earthquake | null>(null);
  const [region, setRegion] = useState<Region | null>(null);
  const [minMagnitude, setMinMagnitude] = useState(initialMinMagnitude);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Use region data from API once loaded, fallback to initial props
  const displayName = region?.display_name ?? initialDisplayName;
  const center = region?.center ?? initialCenter;

  useEffect(() => {
    async function fetchData() {
      // Cancel any in-flight request
      abortControllerRef.current?.abort();
      abortControllerRef.current = new AbortController();

      try {
        setLoading(true);
        setError(null);

        const response = await fetch(
          `${API_BASE_URL}/api-latest-earthquake?locale=${localeSlug}`,
          { signal: abortControllerRef.current.signal }
        );

        if (!response.ok) {
          throw new Error("Failed to fetch earthquake data");
        }

        const data: EarthquakeResponse = await response.json();
        setEarthquake(data.latest_earthquake);
        setRegion(data.region);
        setMinMagnitude(data.min_magnitude_filter);
      } catch (err) {
        // Don't update state if request was aborted (component unmounted)
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }
        console.error("Error fetching earthquake data:", err);
        setError("Unable to load earthquake data. Please try again later.");
      } finally {
        setLoading(false);
      }
    }

    fetchData();

    const interval = setInterval(fetchData, REFRESH_INTERVAL_MS);
    return () => {
      clearInterval(interval);
      abortControllerRef.current?.abort();
    };
  }, [localeSlug]);

  return (
    <div className="min-h-screen flex flex-col">
      <Header currentLocale={localeSlug} locales={headerLocales} />

      <main className="flex-1 px-4 md:px-6 py-8 md:py-12">
        <div className="max-w-6xl mx-auto space-y-8 md:space-y-12">
          {/* Hero Section */}
          <section className="text-center space-y-4">
            <h1 className="text-3xl md:text-4xl lg:text-5xl font-bold text-white">
              {displayName}
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
                magnitude={minMagnitude}
              />
            ) : (
              <div className="text-center py-8">
                <p className="text-slate-400">
                  No earthquakes M{minMagnitude}+ in the past 30 days
                </p>
                <p className="text-green-400 text-lg font-medium mt-2">
                  All quiet in {region?.name ?? displayName}
                </p>
              </div>
            )}
          </section>

          {/* Map and Details Grid */}
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 md:gap-8">
            {/* Map */}
            <MapWrapper
              earthquake={earthquake}
              center={center}
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

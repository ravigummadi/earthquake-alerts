"use client";

import { useState, useEffect, useRef } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import Header from "@/components/Header";
import CountdownTimer from "@/components/CountdownTimer";
import EarthquakeCard from "@/components/EarthquakeCard";
import EarthquakeTable from "@/components/EarthquakeTable";
import MapWrapper from "@/components/MapWrapper";
import {
  type Earthquake,
  type Region,
  type LocaleConfig,
  REFRESH_INTERVAL_MS,
  RECENT_EARTHQUAKES_MAX_LIMIT,
  fetchRecentEarthquakes,
} from "@/lib/api";
import {
  distanceUnitForLocale,
  filterWithinRadius,
  formatRadius,
  localeRadiusMiles,
} from "@/lib/geo";

/** Number of rows shown in the "recent earthquakes" table. */
const RECENT_TABLE_ROWS = 10;

interface LocalePageProps {
  localeSlug: string;
  initialDisplayName: string;
  initialCenter: { lat: number; lng: number };
  initialMinMagnitude: number;
  /** Per-locale radius if the API provides one; otherwise the default applies. */
  initialRadiusMiles?: number;
  allLocales: LocaleConfig[];
}

export default function LocalePage({
  localeSlug,
  initialDisplayName,
  initialCenter,
  initialMinMagnitude,
  initialRadiusMiles,
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

  // Detect if user arrived from an alert link (e.g., Slack, Twitter, WhatsApp)
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const fromAlert = searchParams.get("from") === "alert";
  const hasCleanedUrlRef = useRef(false);

  // Earthquakes within the locale radius (newest first), derived from the same
  // fetch as the headline earthquake. The table shows the first few of these.
  const [nearbyEarthquakes, setNearbyEarthquakes] = useState<Earthquake[]>([]);
  const [showRecentTable, setShowRecentTable] = useState(false);

  // Use region data from API once loaded, fallback to initial props
  const displayName = region?.display_name ?? initialDisplayName;
  const center = region?.center ?? initialCenter;
  const radiusMiles = localeRadiusMiles({
    radius_miles: region?.radius_miles ?? initialRadiusMiles,
  });
  const distanceUnit = distanceUnitForLocale(center);

  useEffect(() => {
    async function fetchData(bustCache: boolean = false) {
      // Cancel any in-flight request
      abortControllerRef.current?.abort();
      abortControllerRef.current = new AbortController();

      try {
        setLoading(true);
        setError(null);

        // The API filters by the locale's (large) bounding box only. Fetch the
        // newest quakes in that box and keep those within the locale radius,
        // so the headline quake is the latest one actually near this locale.
        // Cache-busting is used when coming from an alert link so the user
        // sees the freshest data matching their alert.
        const data = await fetchRecentEarthquakes(
          localeSlug,
          RECENT_EARTHQUAKES_MAX_LIMIT,
          { signal: abortControllerRef.current.signal, bustCache }
        );
        const radius = localeRadiusMiles({
          radius_miles: data.region.radius_miles ?? initialRadiusMiles,
        });
        const nearby = filterWithinRadius(data.earthquakes, data.region.center, radius);

        setNearbyEarthquakes(nearby);
        setEarthquake(nearby[0] ?? null);
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

    // If user arrived from alert, force fresh data and clean up URL
    const shouldBustCache = fromAlert && !hasCleanedUrlRef.current;
    fetchData(shouldBustCache);

    // Clean up the URL by removing the 'from' query parameter
    // This prevents the cache-busting from happening on every subsequent poll
    // and allows clean bookmarking
    if (fromAlert && !hasCleanedUrlRef.current) {
      hasCleanedUrlRef.current = true;
      // Use replaceState to avoid adding to browser history
      router.replace(pathname, { scroll: false });
    }

    const interval = setInterval(() => fetchData(false), REFRESH_INTERVAL_MS);
    return () => {
      clearInterval(interval);
      abortControllerRef.current?.abort();
    };
  }, [localeSlug, fromAlert, pathname, router, initialRadiusMiles]);

  // Collapse the recent table when locale changes
  useEffect(() => {
    setShowRecentTable(false);
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
            <p className="text-slate-500 text-sm">
              Showing M{minMagnitude}+ earthquakes within{" "}
              {formatRadius(radiusMiles, distanceUnit)} of {region?.name ?? displayName}
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
                  No earthquakes M{minMagnitude}+ within{" "}
                  {formatRadius(radiusMiles, distanceUnit)} in the past 30 days
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
              distanceUnit={distanceUnit}
            />

            {/* Earthquake Details */}
            <div className="space-y-6">
              {earthquake ? (
                <EarthquakeCard
                  earthquake={earthquake}
                  center={center}
                  distanceUnit={distanceUnit}
                />
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
                    No significant seismic activity within{" "}
                    {formatRadius(radiusMiles, distanceUnit)} in the past 30 days.
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

          {/* Recent Earthquakes Section */}
          <section className="space-y-4">
            {!showRecentTable ? (
              <div className="text-center">
                <button
                  onClick={() => setShowRecentTable(true)}
                  disabled={loading}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-slate-800 hover:bg-slate-700
                             disabled:bg-slate-800/50 disabled:cursor-not-allowed
                             text-white font-medium rounded-lg transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 6h16M4 10h16M4 14h16M4 18h16"
                    />
                  </svg>
                  Show Last {RECENT_TABLE_ROWS} Earthquakes
                </button>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-semibold text-white">
                    Recent Earthquakes
                  </h2>
                  <button
                    onClick={() => setShowRecentTable(false)}
                    className="text-sm text-slate-400 hover:text-white transition-colors"
                  >
                    Hide
                  </button>
                </div>
                <EarthquakeTable
                  earthquakes={nearbyEarthquakes.slice(0, RECENT_TABLE_ROWS)}
                  center={center}
                  distanceUnit={distanceUnit}
                />
              </>
            )}
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

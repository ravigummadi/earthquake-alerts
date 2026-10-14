// API base URL - uses env var at build time, falls back to Cloud Run URL
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://earthquake-api-793997436187.us-central1.run.app";

// Refresh interval for earthquake data (5 minutes)
export const REFRESH_INTERVAL_MS = 5 * 60 * 1000;

export interface Earthquake {
  id: string;
  magnitude: number;
  place: string;
  time: string;
  latitude: number;
  longitude: number;
  depth_km: number;
  url: string;
  felt: number | null;
  alert: string | null;
  tsunami: boolean;
  mag_type: string;
  has_shakemap: boolean;
}

export interface Region {
  slug: string;
  name: string;
  display_name: string;
  bounds: {
    min_latitude: number;
    max_latitude: number;
    min_longitude: number;
    max_longitude: number;
  };
  center: { lat: number; lng: number };
  /** Optional per-locale display radius. Not yet served by the API; see lib/geo.ts. */
  radius_miles?: number | null;
}

export interface EarthquakeResponse {
  region: Region;
  min_magnitude_filter: number;
  latest_earthquake: Earthquake | null;
  fetched_at: string;
}

export interface RecentEarthquakesResponse {
  region: Region;
  min_magnitude_filter: number;
  earthquakes: Earthquake[];
  count: number;
  fetched_at: string;
}

export interface LocaleConfig {
  slug: string;
  name: string;
  display_name: string;
  bounds: {
    min_latitude: number;
    max_latitude: number;
    min_longitude: number;
    max_longitude: number;
  };
  center: { lat: number; lng: number };
  min_magnitude: number;
  /** Optional per-locale display radius. Not yet served by the API; see lib/geo.ts. */
  radius_miles?: number | null;
}

export interface LocalesResponse {
  locales: LocaleConfig[];
}

/**
 * Fetch all available locales from the API.
 */
export async function fetchLocales(): Promise<LocaleConfig[]> {
  const response = await fetch(`${API_BASE_URL}/api-locales`, {
    next: { revalidate: 3600 }, // Cache for 1 hour
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch locales: ${response.status}`);
  }
  const data: LocalesResponse = await response.json();
  return data.locales;
}

export interface TimeSince {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
}

/**
 * Calculate the time elapsed since a given ISO timestamp.
 * Returns days, hours, minutes, and seconds.
 */
export function getTimeSince(isoTimestamp: string): TimeSince {
  const earthquakeTime = new Date(isoTimestamp).getTime();
  const now = Date.now();

  let diffMs = now - earthquakeTime;

  // Handle future timestamps (shouldn't happen, but be safe)
  if (diffMs < 0) {
    diffMs = 0;
  }

  const seconds = Math.floor((diffMs / 1000) % 60);
  const minutes = Math.floor((diffMs / (1000 * 60)) % 60);
  const hours = Math.floor((diffMs / (1000 * 60 * 60)) % 24);
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  return { days, hours, minutes, seconds };
}

/**
 * Get CSS class for magnitude badge based on severity.
 */
export function getMagnitudeClass(magnitude: number): string {
  if (magnitude >= 7.0) {
    return "magnitude-severe";
  } else if (magnitude >= 5.0) {
    return "magnitude-high";
  } else if (magnitude >= 3.0) {
    return "magnitude-medium";
  }
  return "magnitude-low";
}

/**
 * Get color for magnitude visualization.
 */
export function getMagnitudeColor(magnitude: number): string {
  if (magnitude >= 7.0) {
    return "#dc2626"; // red-600
  } else if (magnitude >= 5.0) {
    return "#f97316"; // orange-500
  } else if (magnitude >= 3.0) {
    return "#eab308"; // yellow-500
  }
  return "#22c55e"; // green-500
}

/**
 * Maximum `limit` accepted by /api-recent-earthquakes. The locale page fetches
 * this many so it has enough candidates left after radius filtering.
 */
export const RECENT_EARTHQUAKES_MAX_LIMIT = 50;

export interface FetchRecentOptions {
  signal?: AbortSignal;
  /** Append a timestamp and bypass caches (used when arriving from an alert link). */
  bustCache?: boolean;
}

/**
 * Fetch recent earthquakes for a locale (newest first, within the locale's
 * API bounding box). Radius filtering happens client-side in lib/geo.ts.
 */
export async function fetchRecentEarthquakes(
  localeSlug: string,
  limit: number = 10,
  options: FetchRecentOptions | AbortSignal = {}
): Promise<RecentEarthquakesResponse> {
  // Backwards compatible: third arg used to be a bare AbortSignal.
  const { signal, bustCache = false } =
    options instanceof AbortSignal ? { signal: options } : options;

  let url = `${API_BASE_URL}/api-recent-earthquakes?locale=${localeSlug}&limit=${limit}`;
  if (bustCache) {
    url += `&_t=${Date.now()}`;
  }

  const response = await fetch(url, {
    signal,
    ...(bustCache && { cache: "no-store" as RequestCache }),
  });

  if (!response.ok) {
    throw new Error("Failed to fetch recent earthquakes");
  }

  return response.json();
}

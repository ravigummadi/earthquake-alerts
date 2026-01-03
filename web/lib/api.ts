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
}

export interface LocalesResponse {
  locales: LocaleConfig[];
}

// Fallback locale - single source of truth from shared JSON
// Used when API is unavailable during build
import fallbackLocaleData from "../../shared/fallback-locale.json";

const FALLBACK_LOCALES: LocaleConfig[] = [fallbackLocaleData];

/**
 * Fetch all available locales from the API.
 * Falls back to static data during build when API is unavailable.
 */
export async function fetchLocales(): Promise<LocaleConfig[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/api-locales`, {
      next: { revalidate: 3600 }, // Cache for 1 hour
    });
    if (!response.ok) {
      console.warn("API unavailable, using fallback locale data");
      return FALLBACK_LOCALES;
    }
    const data: LocalesResponse = await response.json();
    return data.locales;
  } catch {
    // During build or when API is down, use fallback
    console.warn("Failed to fetch locales, using fallback data");
    return FALLBACK_LOCALES;
  }
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
 * Fetch recent earthquakes for a locale.
 */
export async function fetchRecentEarthquakes(
  localeSlug: string,
  limit: number = 10,
  signal?: AbortSignal
): Promise<RecentEarthquakesResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api-recent-earthquakes?locale=${localeSlug}&limit=${limit}`,
    { signal }
  );

  if (!response.ok) {
    throw new Error("Failed to fetch recent earthquakes");
  }

  return response.json();
}

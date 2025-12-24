// API base URL - hardcoded since NEXT_PUBLIC_* env vars need build-time availability
export const API_BASE_URL = "https://us-central1-gen-lang-client-0579637657.cloudfunctions.net";

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

// Fallback locale data for build time when API is unavailable
const FALLBACK_LOCALES: LocaleConfig[] = [
  {
    slug: "sanramon",
    name: "San Ramon",
    display_name: "San Ramon, CA",
    bounds: { min_latitude: 35.9024, max_latitude: 39.18543, min_longitude: -122.92603, max_longitude: -120.71777 },
    center: { lat: 37.78, lng: -121.98 },
    min_magnitude: 2.5,
  },
  {
    slug: "bayarea",
    name: "Bay Area",
    display_name: "San Francisco Bay Area",
    bounds: { min_latitude: 35.9024, max_latitude: 39.18543, min_longitude: -123.5, max_longitude: -120.5 },
    center: { lat: 37.77, lng: -122.42 },
    min_magnitude: 2.5,
  },
  {
    slug: "la",
    name: "Los Angeles",
    display_name: "Los Angeles, CA",
    bounds: { min_latitude: 33.5, max_latitude: 34.8, min_longitude: -119.0, max_longitude: -117.0 },
    center: { lat: 34.05, lng: -118.24 },
    min_magnitude: 2.5,
  },
];

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

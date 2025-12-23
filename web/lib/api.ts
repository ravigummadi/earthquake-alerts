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

export interface EarthquakeResponse {
  locale: string;
  latest_earthquake: Earthquake | null;
  updated_at: string;
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

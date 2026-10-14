/**
 * Pure geo helpers for the locale page: radius filtering and distance
 * formatting. No I/O, no React — everything here is unit-testable.
 *
 * Locales are defined in Firestore (see api/main.py) with bounds, a center
 * and a min_magnitude, but no radius. The API bounding box for a city locale
 * like "sanramon" is roughly 1° x 1° (~55 x 70 miles), which is why users saw
 * quakes near Pittsburg or Milpitas on the San Ramon page (GitHub issue #29).
 * The web page therefore narrows results to a radius around the locale center.
 */

export interface LatLng {
  lat: number;
  lng: number;
}

export interface HasCoordinates {
  latitude: number;
  longitude: number;
}

export type DistanceUnit = "mi" | "km";

/**
 * Default radius (in miles) around a locale's center within which earthquakes
 * are shown on the locale page. Used when a locale does not define its own
 * `radius_miles`. Issue #29 asked for ~15 miles for San Ramon; 25 miles keeps
 * nearby Hayward-fault and Calaveras-fault activity visible.
 */
export const DEFAULT_LOCALE_RADIUS_MILES = 25;

export const KM_PER_MILE = 1.609344;
const EARTH_RADIUS_MILES = 3958.7613;

export function kmToMiles(km: number): number {
  return km / KM_PER_MILE;
}

export function milesToKm(miles: number): number {
  return miles * KM_PER_MILE;
}

/** Great-circle distance between two points in miles (haversine). */
export function haversineMiles(a: LatLng, b: LatLng): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);

  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_MILES * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Distance in miles from an earthquake epicenter to a locale center. */
export function distanceFromCenterMiles(
  earthquake: HasCoordinates,
  center: LatLng
): number {
  return haversineMiles(
    { lat: earthquake.latitude, lng: earthquake.longitude },
    center
  );
}

/**
 * Radius to use for a locale. Honors a per-locale `radius_miles` if the API
 * ever provides one; otherwise falls back to DEFAULT_LOCALE_RADIUS_MILES.
 * Non-finite or non-positive values are treated as "not set".
 */
export function localeRadiusMiles(locale?: { radius_miles?: number | null }): number {
  const r = locale?.radius_miles;
  if (typeof r === "number" && Number.isFinite(r) && r > 0) {
    return r;
  }
  return DEFAULT_LOCALE_RADIUS_MILES;
}

/**
 * Keep only items within `radiusMiles` of `center`. Preserves input order and
 * drops items with missing/non-finite coordinates.
 */
export function filterWithinRadius<T extends HasCoordinates>(
  items: readonly T[],
  center: LatLng,
  radiusMiles: number = DEFAULT_LOCALE_RADIUS_MILES
): T[] {
  return items.filter(
    (item) =>
      Number.isFinite(item.latitude) &&
      Number.isFinite(item.longitude) &&
      distanceFromCenterMiles(item, center) <= radiusMiles
  );
}

/**
 * Rough bounding box covering the US (CONUS, Alaska, Hawaii). Locale records
 * carry no country field, so the display unit is inferred from the center.
 */
export function isUsLocale(center: LatLng): boolean {
  const { lat, lng } = center;
  const conus = lat >= 24 && lat <= 50 && lng >= -125 && lng <= -66;
  const alaska = lat >= 51 && lat <= 72 && (lng <= -129 || lng >= 172);
  const hawaii = lat >= 18 && lat <= 23 && lng >= -161 && lng <= -154;
  return conus || alaska || hawaii;
}

export function distanceUnitForLocale(center: LatLng): DistanceUnit {
  return isUsLocale(center) ? "mi" : "km";
}

/** Format a distance given in miles in the requested unit, e.g. "12.3 mi". */
export function formatDistance(
  miles: number,
  unit: DistanceUnit = "mi",
  fractionDigits: number = 1
): string {
  const value = unit === "mi" ? miles : milesToKm(miles);
  return `${value.toFixed(fractionDigits)} ${unit}`;
}

/** Format a depth given in km (USGS native unit) in the requested unit. */
export function formatDepth(depthKm: number, unit: DistanceUnit = "mi"): string {
  const value = unit === "mi" ? kmToMiles(depthKm) : depthKm;
  return `${value.toFixed(1)} ${unit}`;
}

/** Format a radius for copy like "within 25 miles of San Ramon". */
export function formatRadius(radiusMiles: number, unit: DistanceUnit = "mi"): string {
  if (unit === "mi") {
    return `${Math.round(radiusMiles)} miles`;
  }
  return `${Math.round(milesToKm(radiusMiles))} km`;
}

const USGS_PLACE_KM_PREFIX = /^(\d+(?:\.\d+)?)\s*km\s+(\w+)\s+of\s+/i;

/**
 * USGS place strings look like "15 km N of Pittsburg, CA". For US locales,
 * rewrite the leading distance in miles ("9 mi N of Pittsburg, CA"). Strings
 * without that prefix (e.g. "Northern California") are returned unchanged.
 */
export function localizePlace(place: string | null | undefined, unit: DistanceUnit = "mi"): string {
  if (!place) return "";
  if (unit !== "mi") return place;
  return place.replace(USGS_PLACE_KM_PREFIX, (_match, km: string, direction: string) => {
    const miles = Math.round(kmToMiles(parseFloat(km)));
    return `${miles} mi ${direction} of `;
  });
}

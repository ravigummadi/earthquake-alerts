// Unit tests for lib/geo.ts (pure functions, no React / network).
// Run with: npm test   (uses Node's built-in test runner + TS type stripping,
// so it needs Node >= 22.18; the Docker build image is not used for tests).
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_LOCALE_RADIUS_MILES,
  distanceFromCenterMiles,
  distanceUnitForLocale,
  filterWithinRadius,
  formatDepth,
  formatDistance,
  formatRadius,
  haversineMiles,
  isUsLocale,
  kmToMiles,
  localeRadiusMiles,
  localizePlace,
} from "./geo.ts";

// Locale centers as served by /api-locales.
const SAN_RAMON = { lat: 37.78, lng: -121.98 };
const BAY_AREA = { lat: 37.77, lng: -122.42 };

// Real events from the San Ramon bounding box (USGS ids in comments).
const PITTSBURG_M30 = { id: "nc75301426", latitude: 38.1595, longitude: -121.8888, magnitude: 2.95 }; // "15 km N of Pittsburg, CA", 2026-01-25 (issue #29)
const BRENTWOOD_M30 = { id: "nc75250000", latitude: 37.8748, longitude: -121.8098, magnitude: 2.99 }; // "9 km SW of Brentwood, CA"
const MILPITAS_M25 = { id: "nc75260000", latitude: 37.4665, longitude: -121.8025, magnitude: 2.51 }; // "10 km ENE of Milpitas, CA"
const ALUM_ROCK_M26 = { id: "nc75255000", latitude: 37.3347, longitude: -121.5945, magnitude: 2.56 }; // "21 km E of Alum Rock, CA"

test("haversineMiles: zero for identical points, symmetric", () => {
  assert.equal(haversineMiles(SAN_RAMON, SAN_RAMON), 0);
  const ab = haversineMiles(SAN_RAMON, BAY_AREA);
  const ba = haversineMiles(BAY_AREA, SAN_RAMON);
  assert.ok(Math.abs(ab - ba) < 1e-9);
});

test("haversineMiles: San Ramon to SF center is ~24 miles", () => {
  const d = haversineMiles(SAN_RAMON, BAY_AREA);
  assert.ok(d > 23 && d < 25.5, `got ${d}`);
});

test("distanceFromCenterMiles: Pittsburg quake from issue #29 is beyond 25 miles", () => {
  const d = distanceFromCenterMiles(PITTSBURG_M30, SAN_RAMON);
  assert.ok(d > DEFAULT_LOCALE_RADIUS_MILES, `got ${d}`);
});

test("filterWithinRadius: keeps nearby quakes, drops far ones, preserves order", () => {
  const input = [BRENTWOOD_M30, PITTSBURG_M30, MILPITAS_M25, ALUM_ROCK_M26];
  const result = filterWithinRadius(input, SAN_RAMON);
  assert.deepEqual(result.map((q) => q.id), [BRENTWOOD_M30.id, MILPITAS_M25.id]);
});

test("filterWithinRadius: explicit radius is honored", () => {
  assert.deepEqual(filterWithinRadius([BRENTWOOD_M30, MILPITAS_M25], SAN_RAMON, 15).map((q) => q.id), [BRENTWOOD_M30.id]);
  assert.equal(filterWithinRadius([BRENTWOOD_M30, PITTSBURG_M30, MILPITAS_M25, ALUM_ROCK_M26], SAN_RAMON, 100).length, 4);
});

test("filterWithinRadius: empty input and bad coordinates", () => {
  assert.deepEqual(filterWithinRadius([], SAN_RAMON), []);
  const bad = [{ latitude: NaN, longitude: -121.98 }, { latitude: 37.78, longitude: undefined }];
  assert.deepEqual(filterWithinRadius(bad, SAN_RAMON), []);
});

test("localeRadiusMiles: default unless a positive radius_miles is present", () => {
  assert.equal(localeRadiusMiles(undefined), DEFAULT_LOCALE_RADIUS_MILES);
  assert.equal(localeRadiusMiles({}), DEFAULT_LOCALE_RADIUS_MILES);
  assert.equal(localeRadiusMiles({ radius_miles: null }), DEFAULT_LOCALE_RADIUS_MILES);
  assert.equal(localeRadiusMiles({ radius_miles: 0 }), DEFAULT_LOCALE_RADIUS_MILES);
  assert.equal(localeRadiusMiles({ radius_miles: -5 }), DEFAULT_LOCALE_RADIUS_MILES);
  assert.equal(localeRadiusMiles({ radius_miles: 15 }), 15);
});

test("isUsLocale / distanceUnitForLocale", () => {
  assert.equal(isUsLocale(SAN_RAMON), true);
  assert.equal(isUsLocale({ lat: 34.05, lng: -118.24 }), true); // LA
  assert.equal(isUsLocale({ lat: 61.2, lng: -149.9 }), true); // Anchorage
  assert.equal(isUsLocale({ lat: 21.3, lng: -157.86 }), true); // Honolulu
  assert.equal(isUsLocale({ lat: 35.68, lng: 139.69 }), false); // Tokyo
  assert.equal(isUsLocale({ lat: 19.43, lng: -99.13 }), false); // Mexico City
  assert.equal(distanceUnitForLocale(SAN_RAMON), "mi");
  assert.equal(distanceUnitForLocale({ lat: 35.68, lng: 139.69 }), "km");
});

test("kmToMiles / formatDistance / formatDepth / formatRadius", () => {
  assert.ok(Math.abs(kmToMiles(1.609344) - 1) < 1e-12);
  assert.equal(formatDistance(12.345), "12.3 mi");
  assert.equal(formatDistance(10, "km"), "16.1 km");
  assert.equal(formatDistance(10, "mi", 0), "10 mi");
  assert.equal(formatDepth(8.2), "5.1 mi");
  assert.equal(formatDepth(8.2, "km"), "8.2 km");
  assert.equal(formatRadius(25), "25 miles");
  assert.equal(formatRadius(25, "km"), "40 km");
});

test("localizePlace: converts USGS km prefix to miles for US locales", () => {
  assert.equal(localizePlace("15 km N of Pittsburg, CA"), "9 mi N of Pittsburg, CA");
  assert.equal(localizePlace("10 km ENE of Milpitas, CA"), "6 mi ENE of Milpitas, CA");
  assert.equal(localizePlace("2.5 km SSW of Danville, CA"), "2 mi SSW of Danville, CA");
  assert.equal(localizePlace("0 km W of The Geysers, CA"), "0 mi W of The Geysers, CA");
});

test("localizePlace: leaves non-distance places, km unit, and empty input alone", () => {
  assert.equal(localizePlace("Northern California"), "Northern California");
  assert.equal(localizePlace("15 km N of Pittsburg, CA", "km"), "15 km N of Pittsburg, CA");
  assert.equal(localizePlace(null), "");
  assert.equal(localizePlace(undefined), "");
  assert.equal(localizePlace(""), "");
});

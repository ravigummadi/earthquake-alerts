export interface LocaleConfig {
  slug: string;
  name: string;
  displayName: string;
  bounds: {
    minLatitude: number;
    maxLatitude: number;
    minLongitude: number;
    maxLongitude: number;
  };
  center: {
    lat: number;
    lng: number;
  };
  minMagnitude: number;
  timezone: string;
}

export const LOCALES: Record<string, LocaleConfig> = {
  sanramon: {
    slug: "sanramon",
    name: "San Ramon",
    displayName: "San Ramon, CA",
    bounds: {
      minLatitude: 35.9024,
      maxLatitude: 39.18543,
      minLongitude: -122.92603,
      maxLongitude: -120.71777,
    },
    center: { lat: 37.78, lng: -121.98 },
    minMagnitude: 2.5,
    timezone: "America/Los_Angeles",
  },
  bayarea: {
    slug: "bayarea",
    name: "Bay Area",
    displayName: "San Francisco Bay Area",
    bounds: {
      minLatitude: 35.9024,
      maxLatitude: 39.18543,
      minLongitude: -123.5,
      maxLongitude: -120.5,
    },
    center: { lat: 37.77, lng: -122.42 },
    minMagnitude: 2.5,
    timezone: "America/Los_Angeles",
  },
  la: {
    slug: "la",
    name: "Los Angeles",
    displayName: "Los Angeles, CA",
    bounds: {
      minLatitude: 33.5,
      maxLatitude: 34.8,
      minLongitude: -119.0,
      maxLongitude: -117.0,
    },
    center: { lat: 34.05, lng: -118.24 },
    minMagnitude: 2.5,
    timezone: "America/Los_Angeles",
  },
};

export const DEFAULT_LOCALE = "sanramon";

export function getLocale(slug: string): LocaleConfig | undefined {
  return LOCALES[slug.toLowerCase()];
}

export function getAllLocales(): LocaleConfig[] {
  return Object.values(LOCALES);
}

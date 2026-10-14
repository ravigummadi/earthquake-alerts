"use client";

import { getMagnitudeClass, type Earthquake } from "@/lib/api";
import {
  distanceFromCenterMiles,
  formatDepth,
  formatDistance,
  localizePlace,
  type DistanceUnit,
  type LatLng,
} from "@/lib/geo";

interface EarthquakeTableProps {
  earthquakes: Earthquake[];
  /** Locale center; when provided, a "Distance" column is shown. */
  center?: LatLng;
  /** Unit for distance/depth and the USGS place string. Defaults to miles. */
  distanceUnit?: DistanceUnit;
}

export default function EarthquakeTable({
  earthquakes,
  center,
  distanceUnit = "mi",
}: EarthquakeTableProps) {
  if (earthquakes.length === 0) {
    return (
      <div className="card p-6 text-center text-slate-400">
        No earthquakes found in the past 30 days.
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700/50">
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                Magnitude
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                Location
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider hidden md:table-cell">
                Date & Time
              </th>
              {center && (
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                  Distance
                </th>
              )}
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider hidden sm:table-cell">
                Depth
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">
                Details
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {earthquakes.map((eq) => (
              <EarthquakeRow
                key={eq.id}
                earthquake={eq}
                center={center}
                distanceUnit={distanceUnit}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EarthquakeRow({
  earthquake,
  center,
  distanceUnit,
}: {
  earthquake: Earthquake;
  center?: LatLng;
  distanceUnit: DistanceUnit;
}) {
  const magnitudeClass = getMagnitudeClass(earthquake.magnitude);
  const date = new Date(earthquake.time);

  const formattedDate = date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });

  const formattedTime = date.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });

  return (
    <tr className="hover:bg-slate-800/30 transition-colors">
      <td className="px-4 py-3">
        <span className={`magnitude-badge ${magnitudeClass} text-sm`}>
          M{earthquake.magnitude.toFixed(1)}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className="text-white font-medium">
          {localizePlace(earthquake.place, distanceUnit)}
        </span>
        {earthquake.tsunami && (
          <span className="ml-2 text-xs text-red-400 font-medium">TSUNAMI</span>
        )}
      </td>
      <td className="px-4 py-3 text-slate-400 hidden md:table-cell">
        {formattedDate} at {formattedTime}
      </td>
      {center && (
        <td className="px-4 py-3 text-slate-400">
          {formatDistance(distanceFromCenterMiles(earthquake, center), distanceUnit)}
        </td>
      )}
      <td className="px-4 py-3 text-slate-400 hidden sm:table-cell">
        {formatDepth(earthquake.depth_km, distanceUnit)}
      </td>
      <td className="px-4 py-3 text-right">
        <a
          href={earthquake.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-primary-400 hover:text-primary-300 transition-colors"
        >
          <span className="hidden sm:inline">USGS</span>
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
        </a>
      </td>
    </tr>
  );
}

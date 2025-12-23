"use client";

import { getMagnitudeClass, type Earthquake } from "@/lib/api";

interface EarthquakeCardProps {
  earthquake: Earthquake;
}

export default function EarthquakeCard({ earthquake }: EarthquakeCardProps) {
  const magnitudeClass = getMagnitudeClass(earthquake.magnitude);
  const date = new Date(earthquake.time);

  const formattedDate = date.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  const formattedTime = date.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZoneName: "short",
  });

  return (
    <div className="card p-6 md:p-8">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg md:text-xl font-semibold text-white truncate">
            {earthquake.place}
          </h3>
          <p className="text-slate-400 text-sm mt-1">
            {formattedDate} at {formattedTime}
          </p>
        </div>

        <div className={`magnitude-badge ${magnitudeClass} text-2xl md:text-3xl`}>
          M{earthquake.magnitude.toFixed(1)}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <Stat label="Depth" value={`${earthquake.depth_km.toFixed(1)} km`} />
        <Stat label="Type" value={earthquake.mag_type.toUpperCase()} />
        <Stat
          label="Felt Reports"
          value={earthquake.felt ? earthquake.felt.toLocaleString() : "None"}
        />
        <Stat
          label="Tsunami"
          value={earthquake.tsunami ? "Warning" : "No"}
          warning={earthquake.tsunami}
        />
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <a
          href={earthquake.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700
                     text-white text-sm font-medium rounded-lg transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
          USGS Details
        </a>

        {earthquake.has_shakemap && (
          <a
            href={`${earthquake.url}/shakemap`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-500
                       text-white text-sm font-medium rounded-lg transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            ShakeMap
          </a>
        )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  warning = false
}: {
  label: string;
  value: string;
  warning?: boolean;
}) {
  return (
    <div>
      <p className="text-slate-500 text-xs uppercase tracking-wider mb-1">{label}</p>
      <p className={`font-medium ${warning ? "text-red-400" : "text-white"}`}>
        {value}
      </p>
    </div>
  );
}

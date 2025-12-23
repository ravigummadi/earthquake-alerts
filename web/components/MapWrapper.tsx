"use client";

import dynamic from "next/dynamic";
import { type Earthquake } from "@/lib/api";

const EarthquakeMap = dynamic(() => import("./EarthquakeMap"), {
  ssr: false,
  loading: () => (
    <div className="card h-[300px] md:h-[400px] flex items-center justify-center bg-slate-900/50">
      <div className="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin" />
    </div>
  ),
});

interface MapWrapperProps {
  earthquake: Earthquake | null;
  center: { lat: number; lng: number };
}

export default function MapWrapper({ earthquake, center }: MapWrapperProps) {
  return <EarthquakeMap earthquake={earthquake} center={center} />;
}

"use client";

import dynamic from "next/dynamic";
import { type Earthquake } from "@/lib/api";

const Globe = dynamic(() => import("./Globe"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full min-h-[300px] md:min-h-[400px] flex items-center justify-center bg-slate-900/50 rounded-2xl">
      <div className="w-12 h-12 border-4 border-primary-600 border-t-transparent rounded-full animate-spin" />
    </div>
  ),
});

interface GlobeWrapperProps {
  earthquake: Earthquake | null;
  center: { lat: number; lng: number };
}

export default function GlobeWrapper({ earthquake, center }: GlobeWrapperProps) {
  return (
    <div className="card overflow-hidden h-[300px] md:h-[400px] lg:h-[500px]">
      <Globe earthquake={earthquake} center={center} />
    </div>
  );
}

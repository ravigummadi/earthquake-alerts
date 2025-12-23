"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { getMagnitudeColor, type Earthquake } from "@/lib/api";
import type { GlobeInstance } from "globe.gl";

interface GlobeProps {
  earthquake: Earthquake | null;
  center: { lat: number; lng: number };
}

export default function Globe({ earthquake, center }: GlobeProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const globeRef = useRef<GlobeInstance | null>(null);
  const mountedRef = useRef(true);
  const [isLoaded, setIsLoaded] = useState(false);

  const initGlobe = useCallback(async () => {
    if (!containerRef.current || globeRef.current) return;

    // Dynamic import for client-side only
    const GlobeGL = (await import("globe.gl")).default;

    // Check if component is still mounted after async import
    if (!mountedRef.current || !containerRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;

    const globe = GlobeGL()
      .globeImageUrl("//unpkg.com/three-globe/example/img/earth-blue-marble.jpg")
      .bumpImageUrl("//unpkg.com/three-globe/example/img/earth-topology.png")
      .backgroundImageUrl("//unpkg.com/three-globe/example/img/night-sky.png")
      .width(width)
      .height(height)
      .atmosphereColor("#0ea5e9")
      .atmosphereAltitude(0.15)
      .pointOfView({ lat: center.lat, lng: center.lng, altitude: 2.5 })
      (containerRef.current);

    // Configure points for earthquake
    globe
      .pointsData(earthquake ? [earthquake] : [])
      .pointLat((d: Earthquake) => d.latitude)
      .pointLng((d: Earthquake) => d.longitude)
      .pointAltitude(0.01)
      .pointRadius((d: Earthquake) => Math.max(0.3, d.magnitude / 10))
      .pointColor((d: Earthquake) => getMagnitudeColor(d.magnitude))
      .pointLabel((d: Earthquake) => `
        <div style="background: rgba(0,0,0,0.8); padding: 8px 12px; border-radius: 8px; color: white;">
          <strong>M${d.magnitude.toFixed(1)}</strong> - ${d.place}
        </div>
      `)
      .pointsMerge(true);

    // Add ring effect around earthquake
    if (earthquake) {
      globe
        .ringsData([earthquake])
        .ringLat((d: Earthquake) => d.latitude)
        .ringLng((d: Earthquake) => d.longitude)
        .ringAltitude(0.005)
        .ringColor(() => getMagnitudeColor(earthquake.magnitude))
        .ringMaxRadius(3)
        .ringPropagationSpeed(1)
        .ringRepeatPeriod(2000);
    }

    // Disable auto-rotate for mobile performance
    globe.controls().autoRotate = false;
    globe.controls().enableZoom = true;

    globeRef.current = globe;
    setIsLoaded(true);
  }, [earthquake, center]);

  useEffect(() => {
    mountedRef.current = true;
    initGlobe();

    return () => {
      mountedRef.current = false;
      if (globeRef.current) {
        // Cleanup
        globeRef.current._destructor?.();
        globeRef.current = null;
      }
    };
  }, [initGlobe]);

  // Handle resize
  useEffect(() => {
    const handleResize = () => {
      if (globeRef.current && containerRef.current) {
        globeRef.current.width(containerRef.current.clientWidth);
        globeRef.current.height(containerRef.current.clientHeight);
      }
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Update earthquake point
  useEffect(() => {
    if (globeRef.current && isLoaded) {
      globeRef.current.pointsData(earthquake ? [earthquake] : []);
      if (earthquake) {
        globeRef.current.ringsData([earthquake]);
      } else {
        globeRef.current.ringsData([]);
      }
    }
  }, [earthquake, isLoaded]);

  return (
    <div
      className="relative w-full h-full min-h-[300px] md:min-h-[400px]"
      role="img"
      aria-label={earthquake
        ? `3D globe showing earthquake location: ${earthquake.place}, magnitude ${earthquake.magnitude}`
        : "3D globe visualization"
      }
    >
      <div
        ref={containerRef}
        className="w-full h-full"
        style={{ cursor: "grab" }}
      />
      {!isLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-900/50">
          <div
            className="w-12 h-12 border-4 border-primary-600 border-t-transparent rounded-full animate-spin"
            role="status"
            aria-label="Loading globe visualization"
          />
        </div>
      )}
    </div>
  );
}

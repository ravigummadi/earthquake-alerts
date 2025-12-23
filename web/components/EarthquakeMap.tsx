"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { getMagnitudeColor, type Earthquake } from "@/lib/api";

interface EarthquakeMapProps {
  earthquake: Earthquake | null;
  center: { lat: number; lng: number };
}

export default function EarthquakeMap({ earthquake, center }: EarthquakeMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);

  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    // Initialize map
    const map = L.map(mapRef.current, {
      zoomControl: true,
      scrollWheelZoom: true,
    }).setView(
      earthquake ? [earthquake.latitude, earthquake.longitude] : [center.lat, center.lng],
      earthquake ? 10 : 8
    );

    // Add OpenStreetMap tiles
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map);

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update marker when earthquake changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Clear existing markers
    map.eachLayer((layer) => {
      if (layer instanceof L.Marker || layer instanceof L.CircleMarker) {
        map.removeLayer(layer);
      }
    });

    if (earthquake) {
      const color = getMagnitudeColor(earthquake.magnitude);

      // Add epicenter marker
      const epicenterIcon = L.divIcon({
        className: "epicenter-marker",
        html: `
          <div style="
            width: 24px;
            height: 24px;
            background: ${color};
            border: 3px solid white;
            border-radius: 50%;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
          "></div>
        `,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });

      const marker = L.marker([earthquake.latitude, earthquake.longitude], {
        icon: epicenterIcon,
      }).addTo(map);

      // Add popup
      marker.bindPopup(`
        <div style="text-align: center; min-width: 150px;">
          <strong style="font-size: 18px; color: ${color};">M${earthquake.magnitude.toFixed(1)}</strong>
          <p style="margin: 8px 0 4px 0; font-size: 12px; color: #666;">${earthquake.place}</p>
          <p style="margin: 0; font-size: 11px; color: #999;">Depth: ${earthquake.depth_km.toFixed(1)} km</p>
        </div>
      `);

      // Add pulsing circle for visual effect
      L.circle([earthquake.latitude, earthquake.longitude], {
        color: color,
        fillColor: color,
        fillOpacity: 0.2,
        radius: earthquake.magnitude * 5000, // Scale by magnitude
        weight: 2,
      }).addTo(map);

      // Pan to earthquake location
      map.setView([earthquake.latitude, earthquake.longitude], 10, {
        animate: true,
      });
    }
  }, [earthquake]);

  return (
    <div className="card overflow-hidden h-[300px] md:h-[400px]">
      <div ref={mapRef} className="w-full h-full" />
    </div>
  );
}

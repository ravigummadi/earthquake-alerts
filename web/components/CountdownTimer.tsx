"use client";

import { useState, useEffect } from "react";
import { getTimeSince } from "@/lib/api";

interface CountdownTimerProps {
  earthquakeTime: string;
  magnitude: number;
}

export default function CountdownTimer({ earthquakeTime, magnitude }: CountdownTimerProps) {
  const [timeSince, setTimeSince] = useState(() => getTimeSince(earthquakeTime));

  useEffect(() => {
    const interval = setInterval(() => {
      setTimeSince(getTimeSince(earthquakeTime));
    }, 1000);

    return () => clearInterval(interval);
  }, [earthquakeTime]);

  const { days, hours, minutes, seconds } = timeSince;

  return (
    <div className="text-center">
      <p className="text-slate-400 text-sm uppercase tracking-wider mb-4" id="countdown-label">
        Time since last M{magnitude.toFixed(1)}+ earthquake
      </p>

      <div
        className="flex items-center justify-center gap-2 md:gap-4"
        role="timer"
        aria-labelledby="countdown-label"
        aria-live="polite"
        aria-atomic="true"
      >
        <TimeUnit value={days} label="days" />
        <Separator />
        <TimeUnit value={hours} label="hrs" />
        <Separator />
        <TimeUnit value={minutes} label="min" />
        <Separator />
        <TimeUnit value={seconds} label="sec" />
      </div>
      {/* Screen reader only text */}
      <span className="sr-only">
        {days} days, {hours} hours, {minutes} minutes, {seconds} seconds since last earthquake
      </span>
    </div>
  );
}

function TimeUnit({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex flex-col items-center">
      <span className="text-4xl md:text-6xl lg:text-7xl font-mono font-bold text-white tabular-nums">
        {value.toString().padStart(2, "0")}
      </span>
      <span className="text-xs md:text-sm text-slate-500 uppercase tracking-wider mt-1">
        {label}
      </span>
    </div>
  );
}

function Separator() {
  return (
    <span className="text-3xl md:text-5xl lg:text-6xl font-light text-slate-600 self-start mt-1">
      :
    </span>
  );
}

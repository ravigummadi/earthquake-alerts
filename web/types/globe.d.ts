declare module "globe.gl" {
  export interface GlobeInstance {
    (element: HTMLElement): GlobeInstance;

    // Globe appearance
    globeImageUrl(url: string): GlobeInstance;
    bumpImageUrl(url: string): GlobeInstance;
    backgroundImageUrl(url: string): GlobeInstance;
    showGlobe(show: boolean): GlobeInstance;
    showAtmosphere(show: boolean): GlobeInstance;
    atmosphereColor(color: string): GlobeInstance;
    atmosphereAltitude(altitude: number): GlobeInstance;

    // Size
    width(width: number): GlobeInstance;
    height(height: number): GlobeInstance;

    // Camera
    pointOfView(pov: { lat: number; lng: number; altitude?: number }): GlobeInstance;

    // Points
    pointsData(data: any[]): GlobeInstance;
    pointLat(fn: (d: any) => number): GlobeInstance;
    pointLng(fn: (d: any) => number): GlobeInstance;
    pointAltitude(val: number | ((d: any) => number)): GlobeInstance;
    pointRadius(val: number | ((d: any) => number)): GlobeInstance;
    pointColor(fn: (d: any) => string): GlobeInstance;
    pointLabel(fn: (d: any) => string): GlobeInstance;
    pointsMerge(merge: boolean): GlobeInstance;

    // Rings
    ringsData(data: any[]): GlobeInstance;
    ringLat(fn: (d: any) => number): GlobeInstance;
    ringLng(fn: (d: any) => number): GlobeInstance;
    ringAltitude(val: number | ((d: any) => number)): GlobeInstance;
    ringColor(fn: (d: any) => string): GlobeInstance;
    ringMaxRadius(val: number): GlobeInstance;
    ringPropagationSpeed(val: number): GlobeInstance;
    ringRepeatPeriod(val: number): GlobeInstance;

    // Controls
    controls(): {
      autoRotate: boolean;
      autoRotateSpeed: number;
      enableZoom: boolean;
    };

    // Cleanup
    _destructor?(): void;
  }

  const Globe: () => GlobeInstance;
  export default Globe;
}

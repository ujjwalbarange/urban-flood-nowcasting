'use client';

import React, { useEffect, useState, useRef } from 'react';
import dynamic from 'next/dynamic';
import { Layers, X, Sliders, Check, Droplets, MapPin, ShieldAlert, Waves, AlertTriangle, ChevronDown, Eye, EyeOff } from 'lucide-react';

// ── Types for real data ──
interface GeoJSONFeature {
  type: string;
  properties: Record<string, any>;
  geometry: {
    type: string;
    coordinates: any;
  };
}

interface GeoJSONCollection {
  type: string;
  features: GeoJSONFeature[];
  feature_count?: number;
  source?: string;
  data_provenance?: string;
}

interface RainfallResponse {
  provider: string;
  observations: Array<{
    rate_mmh: number;
    observed_at: string;
  }>;
}

// ── Dynamic Leaflet import (SSR-safe) ──
const MapContainer = dynamic<any>(
  () => import('react-leaflet').then(mod => mod.MapContainer),
  { ssr: false }
);
const TileLayer = dynamic<any>(
  () => import('react-leaflet').then(mod => mod.TileLayer),
  { ssr: false }
);
const GeoJSON = dynamic<any>(
  () => import('react-leaflet').then(mod => mod.GeoJSON),
  { ssr: false }
);
const Popup = dynamic<any>(
  () => import('react-leaflet').then(mod => mod.Popup),
  { ssr: false }
);
const CircleMarker = dynamic<any>(
  () => import('react-leaflet').then(mod => mod.CircleMarker),
  { ssr: false }
);
const ImageOverlay = dynamic<any>(
  () => import('react-leaflet').then(mod => mod.ImageOverlay),
  { ssr: false }
);
const MapClickHandler = dynamic<any>(
  () => import('./MapClickHandler').then(mod => mod.MapClickHandler),
  { ssr: false }
);

import { LocationInfoCard } from './LocationInfoCard';
import { Unified3DTerrainCanvas } from './Unified3DTerrainCanvas';

const API_BASE = 'http://127.0.0.1:8000/api/v1';

// Mumbai center coordinates
const MUMBAI_CENTER: [number, number] = [19.076, 72.877];

// Supported Professional GIS Basemaps (Watermark-Free, Production GIS Standards)
const BASEMAP_TILES = {
  esriGray: {
    name: 'Esri Light Gray Canvas (Clean GIS)',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors',
  },
  osm: {
    name: 'OpenStreetMap Standard',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
  esriDark: {
    name: 'Esri Dark Matter',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri, HERE, &copy; OpenStreetMap contributors',
  },
};

/** Safely extract a [lat, lng] center coordinate from any GeoJSON geometry type (Point, Polygon, MultiPolygon, LineString) */
function getFeatureCenter(geometry: any): [number, number] | null {
  if (!geometry || !geometry.coordinates) return null;
  const { type, coordinates } = geometry;

  if (type === 'Point' && Array.isArray(coordinates)) {
    const [lng, lat] = coordinates;
    if (typeof lat === 'number' && typeof lng === 'number' && !isNaN(lat) && !isNaN(lng)) {
      return [lat, lng];
    }
    return null;
  }

  if (type === 'Polygon' && Array.isArray(coordinates) && Array.isArray(coordinates[0])) {
    const ring = coordinates[0];
    if (!ring || ring.length === 0) return null;
    let sumLat = 0;
    let sumLng = 0;
    let count = 0;
    for (const pt of ring) {
      if (Array.isArray(pt) && typeof pt[1] === 'number' && typeof pt[0] === 'number') {
        sumLng += pt[0];
        sumLat += pt[1];
        count++;
      }
    }
    if (count === 0) return null;
    return [sumLat / count, sumLng / count];
  }

  if (type === 'MultiPolygon' && Array.isArray(coordinates) && Array.isArray(coordinates[0]?.[0])) {
    const ring = coordinates[0][0];
    if (!ring || ring.length === 0) return null;
    let sumLat = 0;
    let sumLng = 0;
    let count = 0;
    for (const pt of ring) {
      if (Array.isArray(pt) && typeof pt[1] === 'number' && typeof pt[0] === 'number') {
        sumLng += pt[0];
        sumLat += pt[1];
        count++;
      }
    }
    if (count === 0) return null;
    return [sumLat / count, sumLng / count];
  }

  if (type === 'LineString' && Array.isArray(coordinates)) {
    let sumLat = 0;
    let sumLng = 0;
    let count = 0;
    for (const pt of coordinates) {
      if (Array.isArray(pt) && typeof pt[1] === 'number' && typeof pt[0] === 'number') {
        sumLng += pt[0];
        sumLat += pt[1];
        count++;
      }
    }
    if (count === 0) return null;
    return [sumLat / count, sumLng / count];
  }

  if (Array.isArray(coordinates) && typeof coordinates[0] === 'number' && typeof coordinates[1] === 'number') {
    return [coordinates[1], coordinates[0]];
  }

  return null;
}

// ── Layer toggle component ──
function LayerToggle({
  label,
  color,
  enabled,
  onToggle,
  count
}: {
  label: string;
  color: string;
  enabled: boolean;
  onToggle: () => void;
  count?: number;
}) {
  return (
    <label style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: '8px',
      padding: '5px 8px',
      borderRadius: '6px',
      cursor: 'pointer',
      background: enabled ? 'rgba(37, 99, 235, 0.08)' : '#f8fafc',
      border: `1px solid ${enabled ? '#93c5fd' : '#e2e8f0'}`,
      fontSize: '11px',
      fontWeight: enabled ? 700 : 500,
      color: enabled ? '#0f172a' : '#64748b',
      transition: 'all 0.15s ease',
      userSelect: 'none',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <input
          type="checkbox"
          checked={enabled}
          onChange={onToggle}
          style={{ display: 'none' }}
        />
        <span style={{
          width: '10px', height: '10px', borderRadius: '3px',
          background: enabled ? color : 'transparent',
          border: `2px solid ${color}`,
          display: 'inline-block',
          transition: 'all 0.15s ease',
        }} />
        <span>{label}</span>
      </div>
      {count !== undefined && (
        <span style={{
          fontSize: '9px', fontWeight: 700,
          background: '#f1f5f9', padding: '1px 5px',
          borderRadius: '8px', color: '#475569',
        }}>{count}</span>
      )}
    </label>
  );
}

interface MumbaiFloodMapProps {
  confusionGeoJSON?: GeoJSONCollection | null;
  nowcastResult?: any;
  focusedLocation?: { lat: number; lon: number; zoom?: number; title?: string } | null;
  selectedWardId?: string | null;
  layerToggles?: {
    showHotspots?: boolean;
    showPumps?: boolean;
    showCitizenReports?: boolean;
    showObservedEvents?: boolean;
    showShelters?: boolean;
    showDrainage?: boolean;
    showCriticalInfra?: boolean;
    showWards?: boolean;
    showRoads?: boolean;
    showNowcastRaster?: boolean;
  };
}

export function MumbaiFloodMap({
  confusionGeoJSON,
  nowcastResult,
  focusedLocation,
  selectedWardId,
  layerToggles,
}: MumbaiFloodMapProps = {}) {
  const [mounted, setMounted] = useState(false);
  const [wards, setWards] = useState<GeoJSONCollection | null>(null);
  const [subareas, setSubareas] = useState<GeoJSONCollection | null>(null);
  const [facilities, setFacilities] = useState<GeoJSONCollection | null>(null);
  const [floodHotspots, setFloodHotspots] = useState<GeoJSONCollection | null>(null);
  const [shelters, setShelters] = useState<GeoJSONCollection | null>(null);
  const [drainageNodes, setDrainageNodes] = useState<GeoJSONCollection | null>(null);
  const [drainageLinks, setDrainageLinks] = useState<GeoJSONCollection | null>(null);
  const [roads, setRoads] = useState<GeoJSONCollection | null>(null);
  const [observedEvents, setObservedEvents] = useState<GeoJSONCollection | null>(null);
  const [pumpingStations, setPumpingStations] = useState<GeoJSONCollection | null>(null);
  const [criticalInfra, setCriticalInfra] = useState<GeoJSONCollection | null>(null);
  const [wardRisks, setWardRisks] = useState<Record<string, any>>({});
  const [citizenReports, setCitizenReports] = useState<any[]>([]);
  const [simulationFloods, setSimulationFloods] = useState<GeoJSONCollection | null>(null);
  const [confusionLayer, setConfusionLayer] = useState<GeoJSONCollection | null>(null);
  const [currentRainfall, setCurrentRainfall] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected Location & Inspector State
  const [selectedLocation, setSelectedLocation] = useState<{ lat: number; lon: number } | null>(null);
  const [locationInfo, setLocationInfo] = useState<any | null>(null);
  const [isLocationLoading, setIsLocationLoading] = useState(false);
  const [showLocationCard, setShowLocationCard] = useState(false);
  const clickAbortControllerRef = useRef<AbortController | null>(null);
  const clickSequenceIdRef = useRef<number>(0);

  // Basemap & Visual Options (Defaulting to Esri Light Gray Canvas for 100% watermark-free GIS)
  const [basemap, setBasemap] = useState<'esriGray' | 'osm' | 'esriDark'>('esriGray');
  const [rasterOpacity, setRasterOpacity] = useState(0.80);

  // Elevation / Topography 2D raster state (Copernicus GLO-30 DEM)
  const [showElevation, setShowElevation] = useState(false);
  const [elevationOpacity, setElevationOpacity] = useState(0.65);
  const [elevationRasterUrl, setElevationRasterUrl] = useState<string | null>(null);
  const [elevationBounds, setElevationBounds] = useState<[[number, number], [number, number]] | null>([[18.85, 72.65], [19.35, 73.10]]);

  // Nowcast flood raster overlay & timeline scrubbing state
  const [nowcastRasterUrl, setNowcastRasterUrl] = useState<string | null>(null);
  const [nowcastBounds, setNowcastBounds] = useState<[[number,number],[number,number]] | null>(null);
  const [showNowcastRaster, setShowNowcastRaster] = useState(true);
  const [timelineMinute, setTimelineMinute] = useState<number>(0);
  const [nowcastData, setNowcastData] = useState<any>(null);
  const [nowcastStatus, setNowcastStatus] = useState<any>(null);
  const [isTimelineLoading, setIsTimelineLoading] = useState(false);

  // Inspector State
  const [selectedFeature, setSelectedFeature] = useState<any | null>(null);
  const [colorMode, setColorMode] = useState<'risk' | 'density'>('risk');

  // Layer visibility toggles (Clean GIS defaults — prevents visual overload)
  const [showWards, setShowWards] = useState(true);
  const [showSubareas, setShowSubareas] = useState(false);
  const [showFacilities, setShowFacilities] = useState(false); // DEFAULT FALSE per explicit user requirement
  const [showSimulationFloods, setShowSimulationFloods] = useState(false); // DEFAULT FALSE to eliminate ugly boxes!
  const [showObservedEvents, setShowObservedEvents] = useState(false);     // DEFAULT FALSE to eliminate 150 overlapping circles!
  const [showHotspots, setShowHotspots] = useState(true);
  const [showPumps, setShowPumps] = useState(false);                      // DEFAULT FALSE to keep center clean
  const [showCriticalInfra, setShowCriticalInfra] = useState(false);
  const [showShelters, setShowShelters] = useState(false);
  const [showDrainage, setShowDrainage] = useState(true);                 // Master/verified drainage
  const [showVerifiedDrainage, setShowVerifiedDrainage] = useState(true);
  const [showSyntheticDrainage, setShowSyntheticDrainage] = useState(false); // DEFAULT FALSE - explicit synthetic layer
  const [syntheticDrainage, setSyntheticDrainage] = useState<GeoJSONCollection | null>(null);
  const [syntheticScenario, setSyntheticScenario] = useState<string>('normal_capacity');
  const [syntheticWarningDismissed, setSyntheticWarningDismissed] = useState(false);
  const [showRoads, setShowRoads] = useState(false);
  const [showCitizenReports, setShowCitizenReports] = useState(true);
  const [showConfusion, setShowConfusion] = useState(false);
  const [showLayerMenu, setShowLayerMenu] = useState(false);

  // ── Unified 2D / 3D Mode & Evacuation Routing State ──
  const [viewMode, setViewMode] = useState<'2d' | '3d'>('2d');
  const [activeEvacuationRoute, setActiveEvacuationRoute] = useState<any | null>(null);
  const [isComputingEvacRoute, setIsComputingEvacRoute] = useState<boolean>(false);
  const [evacRouteError, setEvacRouteError] = useState<string | null>(null);

  const activeConfusion = confusionGeoJSON || confusionLayer;

  useEffect(() => {
    setMounted(true);
    import('leaflet/dist/leaflet.css');
    loadAllData();
  }, []);

  // React to parent nowcast simulation runs
  useEffect(() => {
    if (nowcastResult) {
      setNowcastData(nowcastResult);
      setShowNowcastRaster(true);
      loadNowcastRaster(timelineMinute);
    }
  }, [nowcastResult]);

  // React to parent layer overrides
  useEffect(() => {
    if (layerToggles) {
      if (layerToggles.showHotspots !== undefined) setShowHotspots(layerToggles.showHotspots);
      if (layerToggles.showPumps !== undefined) setShowPumps(layerToggles.showPumps);
      if (layerToggles.showCitizenReports !== undefined) setShowCitizenReports(layerToggles.showCitizenReports);
      if (layerToggles.showObservedEvents !== undefined) setShowObservedEvents(layerToggles.showObservedEvents);
      if (layerToggles.showShelters !== undefined) setShowShelters(layerToggles.showShelters);
      if (layerToggles.showDrainage !== undefined) setShowDrainage(layerToggles.showDrainage);
      if (layerToggles.showCriticalInfra !== undefined) setShowCriticalInfra(layerToggles.showCriticalInfra);
      if (layerToggles.showWards !== undefined) setShowWards(layerToggles.showWards);
      if (layerToggles.showRoads !== undefined) setShowRoads(layerToggles.showRoads);
      if (layerToggles.showNowcastRaster !== undefined) setShowNowcastRaster(layerToggles.showNowcastRaster);
    }
  }, [layerToggles]);

  async function loadAllData() {
    setLoading(true);
    setError(null);
    try {
      const [
        wardsRes, subareasRes, facsRes, hotspotsRes, sheltersRes, nodesRes, linksRes, roadsRes,
        obsEventsRes, pumpsRes, infraRes, riskRes, reportsRes
      ] = await Promise.all([
        fetch(`${API_BASE}/geodata/wards`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/subareas`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/facilities?limit=2000`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/flood-hotspots`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/shelters`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/drainage/nodes`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/drainage/links`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/roads`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/observed-events?limit=150`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/pumping-stations`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/critical-infrastructure`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/ward-risk`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/citizen-reports?limit=50`).then(r => r.json()).catch(() => null),
      ]);

      if (wardsRes) setWards(wardsRes);
      if (subareasRes) setSubareas(subareasRes);
      if (facsRes) setFacilities(facsRes);
      if (hotspotsRes) setFloodHotspots(hotspotsRes);
      if (sheltersRes) setShelters(sheltersRes);
      if (nodesRes) setDrainageNodes(nodesRes);
      if (linksRes) setDrainageLinks(linksRes);
      if (roadsRes) setRoads(roadsRes);
      if (obsEventsRes) setObservedEvents(obsEventsRes);
      if (pumpsRes) setPumpingStations(pumpsRes);
      if (infraRes) setCriticalInfra(infraRes);
      if (reportsRes?.reports) setCitizenReports(reportsRes.reports);

      if (riskRes?.ward_risks) {
        const rMap: Record<string, any> = {};
        for (const wr of riskRes.ward_risks) {
          rMap[wr.ward_id] = wr;
        }
        setWardRisks(rMap);
      }

      // Fetch latest georeferenced simulation inundation (legacy)
      try {
        const simsRes = await fetch(`${API_BASE}/simulations?limit=10`).then(r => r.json());
        const completed = simsRes.simulations?.filter((s: any) => s.status === 'completed' && s.georeferenced);
        if (completed && completed.length > 0) {
          const latestSim = completed[completed.length - 1];
          const geoRes = await fetch(`${API_BASE}/simulations/${latestSim.sim_id}/geojson`).then(r => r.json());
          if (geoRes && geoRes.features && geoRes.features.length > 0) {
            setSimulationFloods(geoRes);
          }
        }
      } catch { /* simulation may not have run yet */ }

      // Fetch latest nowcast flood GeoJSON (from the real pipeline)
      try {
        const ncRes = await fetch(`${API_BASE}/nowcast/latest/geojson`).then(r => r.json());
        if (ncRes && ncRes.features && ncRes.features.length > 0) {
          setSimulationFloods(ncRes);
        }
      } catch { /* no nowcast run yet */ }

      // Fetch latest nowcast data & explanations
      try {
        const ncRes = await fetch(`${API_BASE}/nowcast/latest`).then(r => r.json());
        if (ncRes && ncRes.status === 'completed') {
          setNowcastData(ncRes);
        }
      } catch { /* nowcast fetch */ }

      // Load nowcast flood raster overlay (smooth continuous PNG)
      await loadNowcastRaster(0);

      // Fetch latest satellite validation confusion layer
      try {
        const valRes = await fetch(`${API_BASE}/validation/reports?limit=5`).then(r => r.json());
        if (valRes.reports && valRes.reports.length > 0) {
          const latestVal = valRes.reports[valRes.reports.length - 1];
          const confRes = await fetch(`${API_BASE}/validation/reports/${latestVal.report_id}/confusion-geojson`).then(r => r.json());
          if (confRes && confRes.features && confRes.features.length > 0) {
            setConfusionLayer(confRes);
          }
        }
      } catch { /* no validation run yet */ }

      // Load real 2D Copernicus GLO-30 elevation raster overlay
      try {
        const elevResp = await fetch(`${API_BASE}/geodata/elevation/raster.png`);
        if (elevResp.ok) {
          const minLat = parseFloat(elevResp.headers.get('X-Georef-MinLat') || '18.85');
          const maxLat = parseFloat(elevResp.headers.get('X-Georef-MaxLat') || '19.35');
          const minLon = parseFloat(elevResp.headers.get('X-Georef-MinLon') || '72.65');
          const maxLon = parseFloat(elevResp.headers.get('X-Georef-MaxLon') || '73.10');
          const blob = await elevResp.blob();
          setElevationRasterUrl(URL.createObjectURL(blob));
          setElevationBounds([[minLat, minLon], [maxLat, maxLon]]);
        }
      } catch { /* elevation raster load */ }

      // Fetch MSDI candidate synthetic urban drainage network
      try {
        const synthRes = await fetch(`${API_BASE}/drainage/synthetic?scenario=${syntheticScenario}`).then(r => r.json());
        if (synthRes && synthRes.features && synthRes.features.length > 0) {
          setSyntheticDrainage(synthRes);
        }
      } catch { /* synthetic drainage load */ }

      // Fetch flood simulation status (checks whether real solver output exists)
      try {
        const statusRes = await fetch(`${API_BASE}/nowcast/latest/status`).then(r => r.json());
        setNowcastStatus(statusRes);
      } catch { /* status fetch */ }

      // Fetch live rainfall
      try {
        const rainRes: RainfallResponse = await fetch(
          `${API_BASE}/rainfall/current?lat=19.076&lon=72.877`
        ).then(r => r.json());
        if (rainRes?.observations?.[0]) {
          setCurrentRainfall(rainRes.observations[0].rate_mmh);
        }
      } catch { /* rainfall offline */ }

    } catch (err) {
      setError('Failed to load map data from backend API (port 8000).');
    }
    setLoading(false);
  }

  async function loadNowcastRaster(minute?: number) {
    setIsTimelineLoading(true);
    try {
      const q = minute !== undefined ? `?minute=${minute}&t=${Date.now()}` : `?t=${Date.now()}`;
      const rasterResp = await fetch(`${API_BASE}/nowcast/latest/raster.png${q}`);
      if (rasterResp.ok && rasterResp.status !== 204) {
        const minLat = parseFloat(rasterResp.headers.get('X-Georef-MinLat') || '0');
        const maxLat = parseFloat(rasterResp.headers.get('X-Georef-MaxLat') || '0');
        const minLon = parseFloat(rasterResp.headers.get('X-Georef-MinLon') || '0');
        const maxLon = parseFloat(rasterResp.headers.get('X-Georef-MaxLon') || '0');
        if (minLat && maxLat && minLon && maxLon) {
          const blob = await rasterResp.blob();
          const url = URL.createObjectURL(blob);
          setNowcastRasterUrl(url);
          setNowcastBounds([[minLat, minLon], [maxLat, maxLon]]);
        }
      }
    } catch { /* raster loading */ }
    finally {
      setIsTimelineLoading(false);
    }
  }

  function handleTimelineStep(minute: number) {
    setTimelineMinute(minute);
    loadNowcastRaster(minute);
  }

  if (!mounted) {
    return (
      <div className="map-container" style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--bg-tertiary)', fontSize: '14px', color: 'var(--text-muted)',
      }}>
        Loading GIS Environment...
      </div>
    );
  }

  // ── Location Click & Spatial Selection Handler ──
  const handleMapClick = async (lat: number, lon: number) => {
    // Cancel any in-flight request from previous click
    if (clickAbortControllerRef.current) {
      clickAbortControllerRef.current.abort();
    }
    const controller = new AbortController();
    clickAbortControllerRef.current = controller;
    const currentSeq = ++clickSequenceIdRef.current;

    setSelectedLocation({ lat, lon });
    setShowLocationCard(true);
    setIsLocationLoading(true);
    setSelectedFeature(null);
    try {
      const res = await fetch(`${API_BASE}/geodata/lookup?lat=${lat}&lon=${lon}`, {
        signal: controller.signal,
      });
      const data = await res.json();
      if (currentSeq === clickSequenceIdRef.current) {
        setLocationInfo(data);
      }
    } catch (e: any) {
      if (e.name === 'AbortError') return;
      if (currentSeq === clickSequenceIdRef.current) {
        setLocationInfo({
          status: 'OUTSIDE_COVERAGE',
          in_coverage: false,
          coordinates: { lat, lon },
          message: 'Network error or service unavailable while resolving location.',
        });
      }
    } finally {
      if (currentSeq === clickSequenceIdRef.current) {
        setIsLocationLoading(false);
      }
    }
  };

  // ── Subarea Partition Style & Handlers ──
  const subareaStyle = () => ({
    fillColor: '#3b82f6',
    weight: 1.2,
    color: '#1d4ed8',
    dashArray: '4 3',
    opacity: 0.85,
    fillOpacity: 0.12,
  });

  const subareaOnEachFeature = (feature: any, layer: any) => {
    if (feature.properties) {
      const p = feature.properties;
      layer.on('click', (e: any) => {
        if (e.latlng) {
          handleMapClick(e.latlng.lat, e.latlng.lng);
        }
      });
      layer.bindTooltip(`
        <div style="font-size: 11px; font-weight: 700; color: #1e3a8a;">${p.subarea_name || p.subarea_id}</div>
        <div style="font-size: 10px; color: #475569;">Sector Area: ${p.subarea_area_sq_km || p.area_sq_km || '—'} km²</div>
      `, { sticky: true, opacity: 0.95 });
    }
  };

  // ── Click-to-Evacuate Handler (Direct from Map) ──
  const handleComputeEvacuationRoute = async (vehicleType: string) => {
    if (!selectedLocation) return;
    setIsComputingEvacRoute(true);
    setEvacRouteError(null);
    try {
      const res = await fetch(`${API_BASE}/subareas/point-evacuation-route`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          origin_lon: selectedLocation.lon,
          origin_lat: selectedLocation.lat,
          vehicle_type: vehicleType,
        }),
      }).then(r => r.json());

      if (res.route_found) {
        setActiveEvacuationRoute(res);
      } else {
        setActiveEvacuationRoute(res);
        setEvacRouteError(res.message || 'Evacuation corridor blocked by excessive flood depths.');
      }
    } catch (err: any) {
      setEvacRouteError(err.message || 'Failed to compute evacuation corridor');
    } finally {
      setIsComputingEvacRoute(false);
    }
  };

  // ── Ward Boundary Style (Soft, Translucent GIS Boundaries) ──
  const wardStyle = (feature: any) => {
    const wid = feature?.properties?.ward_id;
    const wr = wardRisks[wid];

    let fillColor = '#38bdf8';
    let fillOpacity = 0.06;

    if (colorMode === 'risk' && wr) {
      if (wr.risk_category === 'CRITICAL') { fillColor = '#dc2626'; fillOpacity = 0.22; }
      else if (wr.risk_category === 'HIGH') { fillColor = '#ea580c'; fillOpacity = 0.16; }
      else if (wr.risk_category === 'MODERATE') { fillColor = '#eab308'; fillOpacity = 0.10; }
      else { fillColor = '#10b981'; fillOpacity = 0.06; }
    } else {
      const density = feature?.properties?.population_density_per_sq_km || 0;
      if (density > 40000) { fillColor = '#1e3a8a'; fillOpacity = 0.20; }
      else if (density > 30000) { fillColor = '#1d4ed8'; fillOpacity = 0.15; }
      else if (density > 20000) { fillColor = '#3b82f6'; fillOpacity = 0.10; }
      else { fillColor = '#93c5fd'; fillOpacity = 0.06; }
    }

    return {
      fillColor,
      weight: 1.4,
      color: basemap === 'esriDark' ? '#64748b' : '#475569',
      dashArray: '',
      opacity: 0.8,
      fillOpacity,
    };
  };

  const wardOnEachFeature = (feature: any, layer: any) => {
    if (feature.properties) {
      const p = feature.properties;
      const wr = wardRisks[p.ward_id];
      const explanation = nowcastData?.ward_explanations?.[p.ward_id];

      layer.on('click', (e: any) => {
        if (e.latlng) {
          handleMapClick(e.latlng.lat, e.latlng.lng);
        }
        setSelectedFeature({
          title: `Ward ${p.ward_id} — ${p.ward_name}`,
          type: 'Ward Administrative Boundary',
          ward: p.ward_id,
          provenance: 'REAL GIS DATA — BMC Municipal Boundaries & Copernicus GLO-30 Analysis',
          explanation: explanation,
          data: {
            'Risk Score': wr ? `${wr.risk_score}/100 (${wr.risk_category})` : 'Calculating...',
            'Hazard Driver': wr?.primary_driver || 'Monsoon surface runoff',
            'Forecast Rainfall (3h)': explanation ? `${explanation.forecast_rainfall_3h_mm} mm` : '—',
            'Simulated Water Depth': explanation ? `${explanation.simulated_max_depth_m} m` : '—',
            'Terrain Depression': explanation?.terrain_depression || 'Low coastal basin',
            'Drainage Coupling': explanation?.drainage_stress || 'Gravity outfalls active',
            'Population (2011)': `${(p.population_2011 || 0).toLocaleString()} residents`,
            'Area': `${p.area_sq_km || '—'} km²`,
            'Population Density': `${Math.round(p.population_density_per_sq_km || 0).toLocaleString()}/km²`,
            'Chronic Hotspots': explanation?.chronic_hotspots_count ? `${explanation.chronic_hotspots_count} locations` : (wr ? `${wr.chronic_hotspots_count} locations` : '—'),
          },
          actions: explanation?.recommended_actions || [wr?.recommended_action || 'Standard municipal monitoring'],
        });
      });

      layer.on('mouseover', (e: any) => {
        e.target.setStyle({ fillOpacity: 0.35, weight: 2.2 });
      });
      layer.on('mouseout', (e: any) => {
        e.target.setStyle(wardStyle(feature));
      });
    }
  };

  // ── Drainage Links Style (Verified Infrastructure) ──
  const drainageLinkStyle = (feature: any) => ({
    color: '#0891b2',
    weight: feature?.properties?.channel_type === 'open_natural_channel' ? 3.5 : 2.5,
    opacity: 0.9,
    dashArray: feature?.properties?.channel_type === 'box_culvert' ? '6 3' : '',
  });

  // ── Synthetic Drainage Conduit Style (Dashed Indigo, strictly labeled) ──
  const syntheticDrainageStyle = (feature: any) => ({
    color: '#6366f1',
    weight: 2.2,
    opacity: 0.85,
    dashArray: '5, 5',
  });

  // ── Roads Style ──
  const roadStyle = (feature: any) => {
    const hw = feature?.properties?.highway;
    let color = '#94a3b8';
    let weight = 1.2;
    if (hw === 'trunk' || hw === 'motorway') { color = '#f59e0b'; weight = 3; }
    else if (hw === 'primary') { color = '#f97316'; weight = 2.5; }
    else if (hw === 'secondary') { color = '#eab308'; weight = 2; }
    return { color, weight, opacity: 0.75 };
  };

  // ── Simulated Flood Extent Style (borderless for smooth continuous look) ──
  const floodPolygonStyle = (feature: any) => {
    const depth = feature?.properties?.water_depth_m || 0;
    // Continuous water-depth colormap: light blue → deep blue → red
    let color = '#93c5fd'; // very shallow
    let opacity = 0.35;
    if (depth >= 1.0) { color = '#991b1b'; opacity = 0.75; }
    else if (depth >= 0.75) { color = '#dc2626'; opacity = 0.7; }
    else if (depth >= 0.5) { color = '#1e40af'; opacity = 0.65; }
    else if (depth >= 0.3) { color = '#2563eb'; opacity = 0.55; }
    else if (depth >= 0.15) { color = '#3b82f6'; opacity = 0.45; }
    else if (depth >= 0.05) { color = '#60a5fa'; opacity = 0.38; }
    return {
      fillColor: color,
      weight: 0,        // NO borders — eliminates boxy grid appearance
      color: color,      // border same as fill (invisible)
      opacity: 0,        // border fully transparent
      fillOpacity: opacity,
    };
  };

  // ── Satellite SAR Confusion Polygons Style ──
  const confusionStyle = (feature: any) => {
    const color = feature?.properties?.color || '#059669';
    return {
      fillColor: color,
      weight: 1.2,
      color: '#ffffff',
      opacity: 0.9,
      fillOpacity: 0.65,
    };
  };

  const activeLayersCount = [
    showNowcastRaster,
    showWards,
    showHotspots,
    showDrainage,
    showPumps,
    showCitizenReports,
    showShelters,
    showCriticalInfra,
    showSimulationFloods,
    showObservedEvents,
    showConfusion
  ].filter(Boolean).length;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      {/* Map Viewport */}
      <div style={{ position: 'relative', width: '100%', height: '100%' }}>
        {loading && (
          <div style={{
            position: 'absolute', inset: 0, zIndex: 1000,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(15,23,42,0.7)', backdropFilter: 'blur(4px)',
            fontSize: '13px', color: '#ffffff', fontWeight: 700,
          }}>
            Loading PostGIS layers & Copernicus DEM data...
          </div>
        )}

        {/* Floating Top Controls Overlay */}
        <div style={{
          position: 'absolute', top: '12px', left: '14px', right: '14px', zIndex: 900,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center', pointerEvents: 'none',
        }}>
          {/* Weather Ticker */}
          <div style={{ pointerEvents: 'auto' }}>
            {currentRainfall !== null && (
              <div style={{
                padding: '6px 14px',
                background: 'rgba(255, 255, 255, 0.96)',
                border: '1px solid #cbd5e1',
                borderRadius: '8px',
                boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}>
                <span className="status-dot live" />
                <span style={{ color: currentRainfall > 0 ? '#1d4ed8' : '#059669', fontSize: '11px' }}>
                  {currentRainfall > 0 ? `🌧 Rain: ${currentRainfall.toFixed(1)} mm/hr` : '☀️ Weather: 0.0 mm/hr'}
                </span>
              </div>
            )}
          </div>

          {/* Floating Interactive Forecast Timeline Player */}
          <div style={{
            pointerEvents: 'auto',
            background: 'rgba(255, 255, 255, 0.96)',
            border: '1px solid #cbd5e1',
            borderRadius: '8px',
            boxShadow: '0 2px 10px rgba(0,0,0,0.08)',
            padding: '5px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: '#0f172a',
          }}>
            <span style={{ fontSize: '11px', fontWeight: 800, color: '#1d4ed8', letterSpacing: '0.4px', textTransform: 'uppercase' }}>
              Forecast:
            </span>
            <div style={{ display: 'flex', gap: '4px' }}>
              {[0, 30, 60, 90, 120, 180].map(m => (
                <button
                  key={m}
                  onClick={() => handleTimelineStep(m)}
                  style={{
                    padding: '3px 8px',
                    borderRadius: '5px',
                    fontSize: '10.5px',
                    fontWeight: timelineMinute === m ? 800 : 600,
                    cursor: 'pointer',
                    background: timelineMinute === m ? '#1d4ed8' : '#f8fafc',
                    color: timelineMinute === m ? '#ffffff' : '#334155',
                    border: `1px solid ${timelineMinute === m ? '#1d4ed8' : '#e2e8f0'}`,
                    transition: 'all 0.15s ease',
                  }}
                >
                  {m === 0 ? 'NOW' : `+${m}m`}
                </button>
              ))}
            </div>
            {isTimelineLoading && (
              <span style={{ fontSize: '10.5px', color: '#0284c7', fontWeight: 600 }}>Updating...</span>
            )}
            {nowcastData?.results && (
              <span style={{ fontSize: '10.5px', color: '#475569', borderLeft: '1px solid #cbd5e1', paddingLeft: '8px' }}>
                Peak: <strong style={{ color: '#0f172a' }}>{nowcastData.results.max_depth_m}m</strong> | Flooded: <strong style={{ color: '#0f172a' }}>{nowcastData.results.flooded_area_km2} km²</strong>
              </span>
            )}
          </div>

          {/* Mode Switch: 2D Flat Map vs 3D Realistic Terrain (In-Place Toggle) */}
          <div style={{
            pointerEvents: 'auto',
            display: 'flex',
            borderRadius: '8px',
            border: '1px solid #cbd5e1',
            overflow: 'hidden',
            background: '#ffffff',
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
          }}>
            <button
              onClick={() => setViewMode('2d')}
              style={{
                padding: '6px 14px',
                fontSize: '11px',
                fontWeight: viewMode === '2d' ? 800 : 600,
                background: viewMode === '2d' ? '#1d4ed8' : '#ffffff',
                color: viewMode === '2d' ? '#ffffff' : '#334155',
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                transition: 'all 0.15s ease',
              }}
            >
              🗺️ 2D Map
            </button>
            <button
              onClick={() => setViewMode('3d')}
              style={{
                padding: '6px 14px',
                fontSize: '11px',
                fontWeight: viewMode === '3d' ? 800 : 600,
                background: viewMode === '3d' ? '#1d4ed8' : '#ffffff',
                color: viewMode === '3d' ? '#ffffff' : '#334155',
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                transition: 'all 0.15s ease',
              }}
            >
              🏔️ 3D Terrain
            </button>
          </div>

          {/* Floating GIS Layers Menu Trigger */}
          <div style={{ pointerEvents: 'auto', position: 'relative' }}>
            <button
              onClick={() => setShowLayerMenu(!showLayerMenu)}
              style={{
                background: showLayerMenu ? '#1d4ed8' : '#ffffff',
                border: `1px solid ${showLayerMenu ? '#1d4ed8' : '#cbd5e1'}`,
                color: showLayerMenu ? '#ffffff' : '#0f172a',
                padding: '6px 12px',
                borderRadius: '8px',
                fontWeight: 700,
                fontSize: '11px',
                boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <Layers size={13} /> GIS Layers ({activeLayersCount})
              <ChevronDown size={12} style={{ transform: showLayerMenu ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
            </button>

            {/* Floating Dropdown Panel */}
            {showLayerMenu && (
              <div style={{
                position: 'absolute', top: '36px', right: 0, width: '290px',
                maxHeight: 'calc(100vh - 200px)', overflowY: 'auto',
                background: '#ffffff',
                padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px',
                boxShadow: '0 8px 30px rgba(0,0,0,0.15)', border: '1px solid #cbd5e1',
                borderRadius: '8px',
                zIndex: 1100,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '8px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 800, color: '#1d4ed8', letterSpacing: '0.4px', textTransform: 'uppercase' }}>
                    Map Layers & Basemap
                  </span>
                  <button
                    onClick={() => setShowLayerMenu(false)}
                    style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '2px' }}
                  >
                    <X size={14} />
                  </button>
                </div>

                {/* Basemap Selection */}
                <div>
                  <div style={{ fontSize: '10px', fontWeight: 700, color: '#475569', marginBottom: '4px', textTransform: 'uppercase' }}>
                    Basemap Canvas
                  </div>
                  <select
                    value={basemap}
                    onChange={e => setBasemap(e.target.value as any)}
                    style={{
                      width: '100%', fontSize: '11px', fontWeight: 600, padding: '6px 8px', borderRadius: '6px',
                      background: '#ffffff', border: '1px solid #cbd5e1', color: '#0f172a',
                      outline: 'none',
                    }}
                  >
                    <option value="esriGray">🗺️ Esri Light Gray Canvas (Clean GIS)</option>
                    <option value="osm">🌐 OpenStreetMap Standard</option>
                    <option value="esriDark">🌑 Esri Dark Matter</option>
                  </select>
                </div>

                {/* Ward Color Mode */}
                <div>
                  <div style={{ fontSize: '10px', fontWeight: 700, color: '#475569', marginBottom: '4px', textTransform: 'uppercase' }}>
                    Ward Thematic Style
                  </div>
                  <select
                    value={colorMode}
                    onChange={e => setColorMode(e.target.value as any)}
                    style={{
                      width: '100%', fontSize: '11px', fontWeight: 600, padding: '6px 8px', borderRadius: '6px',
                      background: '#ffffff', border: '1px solid #cbd5e1', color: '#0f172a',
                      outline: 'none',
                    }}
                  >
                    <option value="risk">Color by Risk Category (CRI)</option>
                    <option value="density">Color by Population Density</option>
                  </select>
                </div>

                {/* Topography & Elevation Group */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginTop: '2px' }}>
                    Topography & Elevation
                  </div>
                  <LayerToggle
                    label="🏔️ Real 2D Elevation (Copernicus DEM)"
                    color="#10b981"
                    enabled={showElevation}
                    onToggle={() => setShowElevation(!showElevation)}
                  />
                  {showElevation && (
                    <div style={{ background: '#f8fafc', padding: '6px 8px', borderRadius: '6px', border: '1px solid #e2e8f0', marginTop: '2px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9.5px', fontWeight: 700, color: '#475569', marginBottom: '3px' }}>
                        <span>ELEVATION OPACITY</span>
                        <strong style={{ color: '#059669' }}>{Math.round(elevationOpacity * 100)}%</strong>
                      </div>
                      <input
                        type="range"
                        min="0.2"
                        max="1.0"
                        step="0.05"
                        value={elevationOpacity}
                        onChange={e => setElevationOpacity(parseFloat(e.target.value))}
                        style={{ width: '100%', cursor: 'pointer', accentColor: '#059669' }}
                      />
                    </div>
                  )}
                </div>

                {/* Inundation & Hazard Group */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginTop: '2px' }}>
                    Flood Inundation Surface
                  </div>
                  <LayerToggle
                    label="🌊 2D Flood-Depth Heatmap"
                    color="#0284c7"
                    enabled={showNowcastRaster}
                    onToggle={() => setShowNowcastRaster(!showNowcastRaster)}
                  />
                  {showNowcastRaster && (
                    <div style={{ background: '#f8fafc', padding: '6px 8px', borderRadius: '6px', border: '1px solid #e2e8f0', marginTop: '2px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9.5px', fontWeight: 700, color: '#475569', marginBottom: '3px' }}>
                        <span>WATER DEPTH OPACITY</span>
                        <strong style={{ color: '#1d4ed8' }}>{Math.round(rasterOpacity * 100)}%</strong>
                      </div>
                      <input
                        type="range"
                        min="0.2"
                        max="1.0"
                        step="0.05"
                        value={rasterOpacity}
                        onChange={e => setRasterOpacity(parseFloat(e.target.value))}
                        style={{ width: '100%', cursor: 'pointer', accentColor: '#1d4ed8' }}
                      />
                    </div>
                  )}
                  <LayerToggle
                    label="Chronic Hotspots"
                    color="#dc2626"
                    enabled={showHotspots}
                    onToggle={() => setShowHotspots(!showHotspots)}
                    count={floodHotspots?.feature_count}
                  />
                  <LayerToggle
                    label="🔲 Cell Mesh (Diagnostic)"
                    color="#64748b"
                    enabled={showSimulationFloods}
                    onToggle={() => setShowSimulationFloods(!showSimulationFloods)}
                    count={simulationFloods?.features?.length}
                  />
                  {activeConfusion?.features && activeConfusion.features.length > 0 && (
                    <LayerToggle
                      label="Documented Extent Validation"
                      color="#059669"
                      enabled={showConfusion}
                      onToggle={() => setShowConfusion(!showConfusion)}
                      count={activeConfusion.features.length}
                    />
                  )}
                </div>

                {/* Drainage & Hydrology Group */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginTop: '2px' }}>
                    Drainage & Hydrology
                  </div>
                  <LayerToggle
                    label="Verified Drainage (BRIMSTOWAD)"
                    color="#0891b2"
                    enabled={showVerifiedDrainage}
                    onToggle={() => {
                      const next = !showVerifiedDrainage;
                      setShowVerifiedDrainage(next);
                      setShowDrainage(next);
                    }}
                    count={drainageLinks?.feature_count || drainageNodes?.feature_count}
                  />
                  <LayerToggle
                    label="Synthetic Drainage (MSDI v1)"
                    color="#6366f1"
                    enabled={showSyntheticDrainage}
                    onToggle={() => {
                      const next = !showSyntheticDrainage;
                      setShowSyntheticDrainage(next);
                      if (next) setSyntheticWarningDismissed(false);
                    }}
                    count={syntheticDrainage?.features?.length}
                  />
                  {showSyntheticDrainage && (
                    <div style={{ background: '#eef2ff', padding: '6px 8px', borderRadius: '6px', border: '1px solid #c7d2fe', marginTop: '2px' }}>
                      <div style={{ fontSize: '9px', fontWeight: 700, color: '#3730a3', marginBottom: '3px', textTransform: 'uppercase' }}>
                        Synthetic Hydraulic Scenario
                      </div>
                      <select
                        value={syntheticScenario}
                        onChange={async e => {
                          const sc = e.target.value;
                          setSyntheticScenario(sc);
                          try {
                            const res = await fetch(`${API_BASE}/drainage/synthetic?scenario=${sc}`).then(r => r.json());
                            if (res && res.features) setSyntheticDrainage(res);
                          } catch { /* reload error */ }
                        }}
                        style={{
                          width: '100%', fontSize: '10px', fontWeight: 600, padding: '4px',
                          borderRadius: '4px', background: '#ffffff', border: '1px solid #a5b4fc',
                          color: '#1e1b4b', outline: 'none',
                        }}
                      >
                        <option value="normal_capacity">Normal Capacity (100%)</option>
                        <option value="reduced_capacity_silted">Silted / Reduced (50%)</option>
                        <option value="blocked">Choked / Blocked (10%)</option>
                      </select>
                    </div>
                  )}
                </div>

                {/* Municipal Infrastructure Group */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginTop: '2px' }}>
                    Municipal Infrastructure
                  </div>
                  <LayerToggle label="Wards (24 BMC)" color="#2563eb" enabled={showWards} onToggle={() => setShowWards(!showWards)} count={wards?.feature_count} />
                  <LayerToggle label="Subarea Partitions (80)" color="#3b82f6" enabled={showSubareas} onToggle={() => setShowSubareas(!showSubareas)} count={subareas?.features?.length} />
                  <LayerToggle label="Emergency Facilities" color="#dc2626" enabled={showFacilities} onToggle={() => setShowFacilities(!showFacilities)} count={facilities?.features?.length} />
                  <LayerToggle label="Pumping Stations (Rated)" color="#0891b2" enabled={showPumps} onToggle={() => setShowPumps(!showPumps)} count={pumpingStations?.features?.length} />
                  <LayerToggle label="Emergency Shelters" color="#059669" enabled={showShelters} onToggle={() => setShowShelters(!showShelters)} count={shelters?.feature_count} />
                  <LayerToggle label="Road Network" color="#f59e0b" enabled={showRoads} onToggle={() => setShowRoads(!showRoads)} count={roads?.feature_count} />
                </div>

                {/* Observations & Citizen Data */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginTop: '2px' }}>
                    Observations & Reports
                  </div>
                  <LayerToggle label="Citizen Reports" color="#f97316" enabled={showCitizenReports} onToggle={() => setShowCitizenReports(!showCitizenReports)} count={citizenReports.length} />
                  <LayerToggle label="Observed Events (2016-25)" color="#8b5cf6" enabled={showObservedEvents} onToggle={() => setShowObservedEvents(!showObservedEvents)} count={observedEvents?.features?.length} />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 2D Flat Map Viewport */}
        <div style={{ display: viewMode === '2d' ? 'block' : 'none', height: '100%', width: '100%' }}>
          <MapContainer
            center={MUMBAI_CENTER}
            zoom={11}
            style={{ height: '100%', width: '100%' }}
            scrollWheelZoom={true}
            zoomControl={true}
          >
          <TileLayer
            key={basemap}
            attribution={BASEMAP_TILES[basemap].attribution}
            url={BASEMAP_TILES[basemap].url}
          />

          <MapClickHandler onMapClick={handleMapClick} />

            {/* Ward boundaries — soft & translucent */}
            {showWards && wards?.features && (
              <GeoJSON
                key={`wards-${colorMode}-${basemap}-${wards.features.length}`}
                data={wards as any}
                style={wardStyle}
                onEachFeature={wardOnEachFeature}
              />
            )}

            {/* Derived Subarea boundaries */}
            {showSubareas && subareas?.features && (
              <GeoJSON
                key={`subareas-${subareas.features.length}`}
                data={subareas as any}
                style={subareaStyle}
                onEachFeature={subareaOnEachFeature}
              />
            )}

            {/* Real 2D Simulated Inundation Extent */}
            {showSimulationFloods && simulationFloods?.features && (
              <GeoJSON
                key={`sim-floods-${simulationFloods.features.length}`}
                data={simulationFloods as any}
                style={floodPolygonStyle}
                onEachFeature={(f: any, layer: any) => {
                  layer.on('click', () => {
                    const p = f.properties;
                    setSelectedFeature({
                      title: 'Simulated Inundation Element',
                      type: '2D Hydrodynamic Surface Water',
                      provenance: 'MODELLED DATA — 2D Diffusive Wave on Copernicus GLO-30 DEM',
                      data: {
                        'Water Depth': `${p.water_depth_m} m (${Math.round(p.water_depth_m * 100)} cm)`,
                        'Hazard Severity': p.severity || 'Moderate',
                        'Governing Solver': 'de Almeida 2012 Diffusive Wave',
                        'Grid Mesh': '30m terrain resolution',
                      },
                    });
                  });
                }}
              />
            )}

            {/* Real 2D Copernicus GLO-30 Elevation / Topography Raster Overlay */}
            {showElevation && elevationRasterUrl && elevationBounds && (
              <ImageOverlay
                key={`elevation-raster-${elevationRasterUrl}`}
                url={elevationRasterUrl}
                bounds={elevationBounds}
                opacity={elevationOpacity}
                zIndex={350}
              />
            )}

            {/* Nowcast Flood Raster Overlay (smooth continuous water surface) */}
            {showNowcastRaster && nowcastRasterUrl && nowcastBounds && (
              <ImageOverlay
                key={`raster-${nowcastRasterUrl}-${timelineMinute}`}
                url={nowcastRasterUrl}
                bounds={nowcastBounds}
                opacity={rasterOpacity}
                zIndex={400}
              />
            )}

            {/* Verified Drainage Trunk Links (BRIMSTOWAD) */}
            {showVerifiedDrainage && showDrainage && drainageLinks?.features && (
              <GeoJSON
                key="drainage-links"
                data={drainageLinks as any}
                style={drainageLinkStyle}
                onEachFeature={(f: any, layer: any) => {
                  layer.on('click', () => {
                    const p = f.properties;
                    setSelectedFeature({
                      title: p.name || p.link_id,
                      type: 'Stormwater Drainage Trunk Channel',
                      provenance: 'REAL INFRASTRUCTURE — BRIMSTOWAD Master Plan / BMC',
                      data: {
                        'Channel Type': p.channel_type || 'Open Channel',
                        'Width x Depth': `${p.width_m || '—'}m x ${p.depth_m || '—'}m`,
                        'Manning n': p.manning_n || '0.025',
                        'Slope': p.slope || '—',
                        'Length': `${p.length_m || '—'} m`,
                      },
                    });
                  });
                }}
              />
            )}

            {/* Synthetic Drainage Network (MSDI v1) - strictly labeled, lines only */}
            {showSyntheticDrainage && syntheticDrainage?.features && (
              <GeoJSON
                key={`synthetic-drainage-${syntheticDrainage.features.length}-${syntheticScenario}`}
                data={syntheticDrainage as any}
                filter={(f: any) => f?.geometry?.type === 'LineString' || f?.geometry?.type === 'MultiLineString'}
                style={syntheticDrainageStyle}
                onEachFeature={(f: any, layer: any) => {
                  layer.on('click', () => {
                    const p = f.properties || {};
                    setSelectedFeature({
                      title: p.name || p.link_id || p.node_id || 'Synthetic Drainage Feature',
                      type: p.feature_type === 'candidate_inlet' ? 'Candidate Storm Inlet' :
                            p.feature_type === 'candidate_outfall' ? 'Candidate Coastal Outfall' :
                            'Candidate Storm Conduit',
                      ward: p.associated_road || 'Subterranean Network',
                      provenance: 'SYNTHETIC — MUFNS Synthetic Drainage Inference (MSDI v1.0)',
                      confidence: 'UNVERIFIED INFERENCE (Hydraulic Assumption)',
                      data: {
                        'Feature Type': p.feature_type,
                        'Associated Road': p.associated_road || '—',
                        'Road Classification': p.road_class || '—',
                        'Assumed Diameter': p.assumed_parameters?.pipe_diameter_mm ? `${p.assumed_parameters.pipe_diameter_mm} mm` : '—',
                        'Full Bore Capacity': p.assumed_parameters?.full_bore_capacity_cumecs ? `${p.assumed_parameters.full_bore_capacity_cumecs} m³/s` : '—',
                        'Effective Capacity': p.assumed_parameters?.effective_capacity_cumecs ? `${p.assumed_parameters.effective_capacity_cumecs} m³/s` : '—',
                        'Operating Scenario': p.operating_scenario || syntheticScenario,
                        'Ground Elevation': p.ground_elevation_m !== undefined ? `${p.ground_elevation_m} m MSL` : (p.upstream_elevation_m !== undefined ? `${p.upstream_elevation_m} m → ${p.downstream_elevation_m} m` : '—'),
                        'Calculated Slope': p.calculated_ground_slope ? `${(p.calculated_ground_slope * 100).toFixed(2)}%` : '—',
                        'Length': p.length_m ? `${p.length_m} m` : '—',
                        'Confidence': 'UNVERIFIED INFERENCE — Engineering Assumption',
                      },
                    });
                  });
                }}
              />
            )}

            {/* Roads */}
            {showRoads && roads?.features && (
              <GeoJSON
                key="roads"
                data={roads as any}
                style={roadStyle}
                onEachFeature={(f: any, layer: any) => {
                  layer.on('click', () => {
                    const p = f.properties;
                    setSelectedFeature({
                      title: p.name || 'Unnamed Road Segment',
                      type: 'Road Transit Arterial',
                      provenance: 'REAL GIS DATA — OpenStreetMap Contributors',
                      data: {
                        'Classification': p.highway || 'road',
                        'Flood Vulnerability': p.flood_vulnerability || 'moderate',
                        'Lanes': p.lanes || '—',
                        'Surface': p.surface || 'asphalt',
                      },
                    });
                  });
                }}
              />
            )}

            {/* Observed Historical Flood Events (2016-2025) */}
            {showObservedEvents && observedEvents?.features?.map((f, i) => {
              const center = getFeatureCenter(f.geometry);
              if (!center) return null;
              const p = f.properties;
              return (
                <CircleMarker
                  key={`obs-evt-${i}`}
                  center={center}
                  radius={4}
                  pathOptions={{
                    fillColor: '#8b5cf6',
                    color: '#ffffff',
                    weight: 1,
                    opacity: 0.9,
                    fillOpacity: 0.75,
                  }}
                  eventHandlers={{
                    click: () => {
                      setSelectedFeature({
                        title: `${p.locality || 'Flood Event'} (${p.date || p.year})`,
                        type: 'Historical Ground-Truth Flood Observation',
                        ward: p.ward,
                        provenance: 'REAL OBSERVED DATA — IMD / MCGM Disaster Management',
                        data: {
                          'Date Recorded': p.date || `${p.year}`,
                          'Recorded Water Depth': `${p.flood_depth_cm || '—'} cm (${p.flood_depth_m || '—'} m)`,
                          '1h Rainfall': `${p.rainfall_1h_mm || '—'} mm`,
                          '24h Rainfall': `${p.rainfall_24h_mm || '—'} mm`,
                          'Flood Severity': p.flood_severity || 'Moderate',
                          'People Affected': p.people_affected ? p.people_affected.toLocaleString() : '—',
                          'Roads Disrupted': p.roads_affected ? `${p.roads_affected} segments` : '—',
                          'Economic Loss': p.economic_loss || '—',
                          'Drainage Stress Index': p.drainage_stress_index || '—',
                        },
                      });
                    },
                  }}
                />
              );
            })}

            {/* Flood Hotspots */}
            {showHotspots && floodHotspots?.features?.map((f, i) => {
              const center = getFeatureCenter(f.geometry);
              if (!center) return null;
              const p = f.properties;
              const depth = p.typical_water_depth_m || 0.8;
              const color = depth >= 1.5 ? '#dc2626' : depth >= 1.0 ? '#ea580c' : depth >= 0.5 ? '#d97706' : '#059669';
              return (
                <CircleMarker
                  key={`hotspot-${i}`}
                  center={center}
                  radius={5}
                  pathOptions={{
                    fillColor: color,
                    color: '#ffffff',
                    weight: 1.5,
                    opacity: 0.95,
                    fillOpacity: 0.85,
                  }}
                  eventHandlers={{
                    click: () => {
                      setSelectedFeature({
                        title: p.location_name,
                        type: 'Chronic Flood Hotspot',
                        ward: p.ward,
                        provenance: 'REAL OBSERVED DATA — BMC Disaster Management Inventory',
                        data: {
                          'Typical Inundation': `${depth} meters`,
                          'Max Recorded Depth': `${p.maximum_recorded_depth_m || '—'} meters`,
                          'Basin / Catchment': p.drainage_basin || 'Central Mumbai',
                          'Traffic Disruption': p.traffic_impact || 'Severe',
                          'Mitigation Measures': p.mitigation_status || 'Monitored by MCGM',
                        },
                      });
                    },
                  }}
                />
              );
            })}

            {/* Pumping Stations */}
            {showPumps && pumpingStations?.features?.map((f, i) => {
              const center = getFeatureCenter(f.geometry);
              if (!center) return null;
              const p = f.properties;
              return (
                <CircleMarker
                  key={`pump-${i}`}
                  center={center}
                  radius={5}
                  pathOptions={{
                    fillColor: '#0891b2',
                    color: '#ffffff',
                    weight: 1.5,
                    opacity: 0.95,
                    fillOpacity: 0.9,
                  }}
                  eventHandlers={{
                    click: () => {
                      setSelectedFeature({
                        title: p.name,
                        type: 'Municipal Stormwater Pumping Station',
                        ward: p.ward,
                        provenance: 'REAL INFRASTRUCTURE — BRIMSTOWAD Master Plan / BMC',
                        data: {
                          'Rated Capacity': `${p.rated_capacity_mld || '—'} MLD (${p.capacity_m3_per_sec || '—'} m³/s)`,
                          'Installed Pumps': `${p.num_pumps || '—'} high-discharge pumps`,
                          'Operating Status': p.current_status || 'operational',
                          'Operational Capacity': `${p.operational_capacity_pct || 100}%`,
                          'Outfall Destination': (p.attributes || {}).water_body || 'Arabian Sea / Creek',
                        },
                      });
                    },
                  }}
                />
              );
            })}

            {/* Critical Infrastructure */}
            {showCriticalInfra && criticalInfra?.features?.map((f, i) => {
              const center = getFeatureCenter(f.geometry);
              if (!center) return null;
              const p = f.properties;
              return (
                <CircleMarker
                  key={`infra-${i}`}
                  center={center}
                  radius={4}
                  pathOptions={{
                    fillColor: '#f59e0b',
                    color: '#ffffff',
                    weight: 1,
                    opacity: 0.9,
                    fillOpacity: 0.85,
                  }}
                  eventHandlers={{
                    click: () => {
                      setSelectedFeature({
                        title: p.name,
                        type: `Critical Infrastructure (${p.category})`,
                        ward: p.ward,
                        provenance: 'REAL GIS DATA — OpenStreetMap / BMC Disaster Plan',
                        data: {
                          'Facility Category': p.category || 'Civic',
                          'Elevation': `${p.elevation_m || '—'} m MSL`,
                          'Flood Vulnerable': p.flood_vulnerable ? 'YES (Low elevation)' : 'NO',
                        },
                      });
                    },
                  }}
                />
              );
            })}

            {/* Emergency Shelters */}
            {showShelters && shelters?.features?.map((f, i) => {
              const center = getFeatureCenter(f.geometry);
              if (!center) return null;
              const p = f.properties;
              return (
                <CircleMarker
                  key={`shelter-${i}`}
                  center={center}
                  radius={5}
                  pathOptions={{
                    fillColor: '#059669',
                    color: '#ffffff',
                    weight: 1.5,
                    opacity: 0.95,
                    fillOpacity: 0.9,
                  }}
                  eventHandlers={{
                    click: () => {
                      setSelectedFeature({
                        title: p.name,
                        type: 'Designated Emergency Relief Shelter',
                        ward: p.ward,
                        provenance: 'REAL GIS DATA — BMC Disaster Management Plan',
                        data: {
                          'Shelter Capacity': `${p.capacity_persons} persons`,
                          'Address': p.address || '—',
                          'Backup Generator': p.backup_power_generator === 'yes' ? 'Available' : 'None',
                          'First Aid Post': p.medical_first_aid_post === 'yes' ? 'Equipped' : 'None',
                          'Drinking Water Storage': `${p.drinking_water_storage_liters?.toLocaleString() || '—'} L`,
                        },
                      });
                    },
                  }}
                />
              );
            })}

            {/* Citizen Incident Reports */}
            {showCitizenReports && citizenReports.map((r, i) => {
              if (typeof r.latitude !== 'number' || typeof r.longitude !== 'number' || isNaN(r.latitude) || isNaN(r.longitude)) return null;
              return (
                <CircleMarker
                  key={`rpt-${i}`}
                  center={[r.latitude, r.longitude]}
                  radius={6}
                pathOptions={{
                  fillColor: r.verified ? '#10b981' : '#f97316',
                  color: '#ffffff',
                  weight: 1.5,
                  opacity: 1,
                  fillOpacity: 0.9,
                }}
                eventHandlers={{
                  click: () => {
                    setSelectedFeature({
                      title: `Citizen Report (${r.category})`,
                      type: 'Crowdsourced Incident Observation',
                      ward: r.ward_id,
                      provenance: r.data_provenance || 'CITIZEN OBSERVED',
                      data: {
                        'Reported Water Depth': `${r.water_depth_cm} cm (${r.water_depth_m} m)`,
                        'Severity': r.severity,
                        'Verification Status': r.verification_status || 'unverified',
                        'Description': r.description,
                        'Reported Time': r.timestamp,
                      },
                    });
                  },
                }}
              />
            );
          })}

            {/* Documented / Surveyed Flood Extent Validation Layer */}
            {showConfusion && activeConfusion?.features && (
              <GeoJSON
                key={`confusion-layer-${activeConfusion.features.length}`}
                data={activeConfusion as any}
                style={confusionStyle}
                onEachFeature={(f: any, layer: any) => {
                  layer.on('click', () => {
                    const p = f.properties;
                    setSelectedFeature({
                      title: `Surveyed Flood Extent: ${p.classification === 'TP' ? 'Model Match' : p.classification === 'FP' ? 'Simulated Inundation' : 'Surveyed Inundation'}`,
                      type: 'Documented / Surveyed Flood Extent Comparison',
                      provenance: 'REAL SURVEYED EXTENT — Official BMC Disaster Cell Post-Event Survey (Not SAR)',
                      data: {
                        'Classification': p.classification,
                        'Description': p.description,
                        'Reconstructed Depth': `${p.simulated_depth_m} m`,
                        'Coordinates': `${p.center_lat}, ${p.center_lon}`,
                      },
                    });
                  });
                }}
              />
            )}

            {/* Real Emergency Facilities (Hospitals, Clinics, Police, Fire, Shelters) */}
            {showFacilities && facilities?.features?.map((f: any, i: number) => {
              const center = getFeatureCenter(f.geometry);
              if (!center) return null;
              const p = f.properties;
              const cat = p.category || 'facility';
              let markerColor = '#dc2626';
              let radius = 5;
              if (cat === 'hospital') { markerColor = '#dc2626'; radius = 6; }
              else if (cat === 'clinic') { markerColor = '#0284c7'; radius = 4.5; }
              else if (cat === 'police') { markerColor = '#1d4ed8'; radius = 5; }
              else if (cat === 'fire_station') { markerColor = '#ea580c'; radius = 5.5; }
              else if (cat === 'shelter') { markerColor = '#16a34a'; radius = 6; }

              return (
                <CircleMarker
                  key={`facility-${f.id || i}`}
                  center={center}
                  radius={radius}
                  pathOptions={{
                    fillColor: markerColor,
                    color: '#ffffff',
                    weight: 1.5,
                    opacity: 0.95,
                    fillOpacity: 0.9,
                  }}
                >
                  <Popup>
                    <div style={{ padding: '4px 6px', minWidth: '160px' }}>
                      <div style={{ fontSize: '12px', fontWeight: 800, color: '#0f172a' }}>{p.name}</div>
                      <div style={{ fontSize: '10px', color: '#64748b', margin: '2px 0 4px' }}>{p.address}</div>
                      <span style={{
                        fontSize: '9px', fontWeight: 700, textTransform: 'uppercase',
                        padding: '2px 6px', borderRadius: '4px',
                        background: '#f1f5f9', color: '#334155'
                      }}>
                        {cat.replace('_', ' ')}
                      </span>
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}

            {/* Active Flood Evacuation Corridor (Drawn directly on Map in 2D) */}
            {activeEvacuationRoute?.geometry && (
              <GeoJSON
                key={`evac-route-2d-${activeEvacuationRoute.total_distance_km}-${activeEvacuationRoute.passability_verdict}`}
                data={activeEvacuationRoute.geometry as any}
                style={() => ({
                  color: activeEvacuationRoute.passability_verdict?.includes('CLEAR') ? '#0284c7' : '#f59e0b',
                  weight: 5,
                  opacity: 0.9,
                  lineJoin: 'round',
                  lineCap: 'round',
                })}
              />
            )}

            {/* Selected Location Point Marker with Pulsing Ring */}
            {selectedLocation && (
              <>
                <CircleMarker
                  center={[selectedLocation.lat, selectedLocation.lon]}
                  radius={16}
                  pathOptions={{
                    color: '#ef4444',
                    weight: 2,
                    fillColor: '#ef4444',
                    fillOpacity: 0.25,
                  }}
                />
                <CircleMarker
                  center={[selectedLocation.lat, selectedLocation.lon]}
                  radius={8}
                  pathOptions={{
                    color: '#ffffff',
                    weight: 3,
                    fillColor: '#dc2626',
                    fillOpacity: 1,
                  }}
                >
                  <Popup>
                    <div style={{ padding: '4px', fontSize: '11px', fontWeight: 700 }}>
                      Selected Point: {selectedLocation.lat.toFixed(5)}° N, {selectedLocation.lon.toFixed(5)}° E
                    </div>
                  </Popup>
                </CircleMarker>
              </>
            )}
          </MapContainer>
        </div>

        {/* 3D Realistic Topography & Floodwater Simulation Viewport */}
        {viewMode === '3d' && (
          <div style={{ position: 'absolute', inset: 0, zIndex: 10 }}>
            <Unified3DTerrainCanvas
              selectedLocation={selectedLocation}
              onSelectLocation={(lat, lon) => handleMapClick(lat, lon)}
              activeRoute={activeEvacuationRoute}
              timelineMinute={timelineMinute}
              showWaterOverlay={showNowcastRaster}
              onClose3D={() => setViewMode('2d')}
            />
          </div>
        )}

        {/* Location Information Card (opens on clicking any point on the map) */}
        {showLocationCard && (
          <LocationInfoCard
            locationData={locationInfo}
            isLoading={isLocationLoading}
            onClose={() => {
              setShowLocationCard(false);
              setSelectedLocation(null);
            }}
            showFacilitiesOnMap={showFacilities}
            onToggleFacilities={() => setShowFacilities(!showFacilities)}
            activeEvacuationRoute={activeEvacuationRoute}
            onComputeEvacuationRoute={handleComputeEvacuationRoute}
            isComputingRoute={isComputingEvacRoute}
            onClearEvacuationRoute={() => setActiveEvacuationRoute(null)}
          />
        )}

          {/* Synthetic Drainage Safety Warning Banner (Section 8.7) */}
          {showSyntheticDrainage && !syntheticWarningDismissed && (
            <div style={{
              position: 'absolute', top: '14px', left: '50%', transform: 'translateX(-50%)',
              zIndex: 1000, maxWidth: '680px', width: '92%',
              background: '#fffbeb', border: '2px solid #f59e0b', borderRadius: '8px',
              boxShadow: '0 4px 16px rgba(0,0,0,0.18)', padding: '10px 14px',
              display: 'flex', alignItems: 'center', gap: '12px', fontSize: '11.5px', color: '#92400e',
            }}>
              <span style={{ fontSize: '20px', flexShrink: 0 }}>⚠️</span>
              <div style={{ flex: 1, lineHeight: '1.4' }}>
                <strong style={{ color: '#78350f' }}>Synthetic / Inferred Drainage Data Notice:</strong><br />
                Synthetic/inferred drainage data — not a verified map of municipal infrastructure. Do not use this layer alone for real-world safety or evacuation decisions.
              </div>
              <button
                onClick={() => setSyntheticWarningDismissed(true)}
                style={{
                  background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: '4px',
                  padding: '4px 10px', fontSize: '11px', fontWeight: 700, color: '#b45309',
                  cursor: 'pointer', whiteSpace: 'nowrap',
                }}
              >
                Acknowledge
              </button>
            </div>
          )}

          {/* Missing Simulation Raster Status Alert (Section 7.2) */}
          {showNowcastRaster && nowcastStatus && !nowcastStatus.available && (
            <div style={{
              position: 'absolute', top: '70px', left: '50%', transform: 'translateX(-50%)',
              zIndex: 1000, maxWidth: '580px', width: '88%',
              background: '#fef2f2', border: '2px solid #ef4444', borderRadius: '8px',
              boxShadow: '0 4px 14px rgba(0,0,0,0.14)', padding: '10px 14px',
              display: 'flex', alignItems: 'center', gap: '10px', fontSize: '11.5px', color: '#991b1b',
            }}>
              <span style={{ fontSize: '18px', flexShrink: 0 }}>🚫</span>
              <div style={{ flex: 1, lineHeight: '1.4' }}>
                <strong>Flood-depth output unavailable:</strong><br />
                {nowcastStatus.error_detail || 'No valid simulation raster is currently available.'} Zero-mock policy active: no placeholder depths are shown.
              </div>
            </div>
          )}

          {/* Dynamic Multi-Layer GIS Legend (Section 5) — Adapts strictly to visible layers */}
          <div style={{
            position: 'absolute', bottom: '16px', left: '16px', zIndex: 1000,
            background: 'rgba(255, 255, 255, 0.96)',
            padding: '10px 14px', borderRadius: '8px', boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
            border: '1px solid #cbd5e1', fontSize: '11px', color: '#0f172a',
            maxWidth: '380px', maxHeight: '420px', overflowY: 'auto',
          }}>
            <div style={{ fontWeight: 800, marginBottom: '8px', color: '#0f172a', letterSpacing: '0.4px', fontSize: '11px', borderBottom: '1px solid #e2e8f0', paddingBottom: '4px' }}>
              🗺️ DYNAMIC GIS MAP LEGEND
            </div>

            {/* Flood Depth Inundation Scale */}
            {(showNowcastRaster || showSimulationFloods) && (
              <div style={{ marginBottom: '10px' }}>
                <div style={{ fontWeight: 700, color: '#1d4ed8', fontSize: '10px', marginBottom: '4px', textTransform: 'uppercase' }}>
                  🌊 2D Flood Depth (metres)
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '4px', textAlign: 'center', marginBottom: '3px' }}>
                  <div>
                    <div style={{ height: '7px', background: '#38bdf8', borderRadius: '2px' }} />
                    <div style={{ marginTop: '2px', fontSize: '8.5px', color: '#64748b' }}>&lt;0.15m</div>
                  </div>
                  <div>
                    <div style={{ height: '7px', background: '#0284c7', borderRadius: '2px' }} />
                    <div style={{ marginTop: '2px', fontSize: '8.5px', color: '#64748b' }}>0.15–0.3m</div>
                  </div>
                  <div>
                    <div style={{ height: '7px', background: '#eab308', borderRadius: '2px' }} />
                    <div style={{ marginTop: '2px', fontSize: '8.5px', color: '#64748b' }}>0.3–0.5m</div>
                  </div>
                  <div>
                    <div style={{ height: '7px', background: '#ea580c', borderRadius: '2px' }} />
                    <div style={{ marginTop: '2px', fontSize: '8.5px', color: '#64748b' }}>0.5–1.0m</div>
                  </div>
                  <div>
                    <div style={{ height: '7px', background: '#dc2626', borderRadius: '2px' }} />
                    <div style={{ marginTop: '2px', fontSize: '8.5px', color: '#64748b' }}>&gt;1.0m</div>
                  </div>
                </div>
                <div style={{ fontSize: '8.5px', color: '#64748b', fontStyle: 'italic' }}>
                  Dry cells (&lt;0.01m) transparent · 2D Diffusive Wave Solver (30m)
                </div>
              </div>
            )}

            {/* Real Copernicus DEM Elevation Hypsometric Scale */}
            {showElevation && (
              <div style={{ marginBottom: '10px', borderTop: '1px dashed #e2e8f0', paddingTop: '6px' }}>
                <div style={{ fontWeight: 700, color: '#047857', fontSize: '10px', marginBottom: '4px', textTransform: 'uppercase' }}>
                  ⛰️ Elevation (m MSL — Copernicus GLO-30)
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '4px', textAlign: 'center', marginBottom: '3px' }}>
                  <div>
                    <div style={{ height: '7px', background: '#1a9850', borderRadius: '2px' }} />
                    <div style={{ marginTop: '2px', fontSize: '8.5px', color: '#64748b' }}>0–5m</div>
                  </div>
                  <div>
                    <div style={{ height: '7px', background: '#91cf60', borderRadius: '2px' }} />
                    <div style={{ marginTop: '2px', fontSize: '8.5px', color: '#64748b' }}>5–15m</div>
                  </div>
                  <div>
                    <div style={{ height: '7px', background: '#fee08b', borderRadius: '2px' }} />
                    <div style={{ marginTop: '2px', fontSize: '8.5px', color: '#64748b' }}>15–30m</div>
                  </div>
                  <div>
                    <div style={{ height: '7px', background: '#fc8d59', borderRadius: '2px' }} />
                    <div style={{ marginTop: '2px', fontSize: '8.5px', color: '#64748b' }}>30–60m</div>
                  </div>
                  <div>
                    <div style={{ height: '7px', background: '#d73027', borderRadius: '2px' }} />
                    <div style={{ marginTop: '2px', fontSize: '8.5px', color: '#64748b' }}>&gt;60m</div>
                  </div>
                </div>
                <div style={{ fontSize: '8.5px', color: '#64748b', fontStyle: 'italic' }}>
                  Vertical datum: EGM96 Geoid · 1 arc-sec (~30.8m)
                </div>
              </div>
            )}

            {/* Linear Networks (Verified vs Synthetic Drainage, Roads) */}
            {(showVerifiedDrainage || showSyntheticDrainage || showRoads) && (
              <div style={{ marginBottom: '8px', borderTop: '1px dashed #e2e8f0', paddingTop: '6px' }}>
                <div style={{ fontWeight: 700, color: '#475569', fontSize: '9.5px', marginBottom: '4px', textTransform: 'uppercase' }}>
                  Network Layers
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', fontSize: '9.5px' }}>
                  {showVerifiedDrainage && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ display: 'inline-block', width: '18px', height: '3.5px', background: '#0284c7', borderRadius: '2px' }} />
                      <span><strong>BRIMSTOWAD Master Drains</strong> (Verified)</span>
                    </div>
                  )}
                  {showSyntheticDrainage && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ display: 'inline-block', width: '18px', height: '2.5px', borderTop: '2px dashed #8b5cf6' }} />
                      <span style={{ color: '#7c3aed' }}><strong>MSDI v1.0 Drainage</strong> (Synthetic Inference)</span>
                    </div>
                  )}
                  {showRoads && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ display: 'inline-block', width: '18px', height: '2px', background: '#64748b' }} />
                      <span><strong>Road Network</strong> (OSM Arterials)</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Active Point Layers */}
            <div style={{ borderTop: '1px dashed #e2e8f0', paddingTop: '6px' }}>
              <div style={{ fontWeight: 700, color: '#475569', fontSize: '9.5px', marginBottom: '4px', textTransform: 'uppercase' }}>
                Active Municipal & Incident Points
              </div>
              <div style={{ display: 'flex', gap: '8px', fontSize: '9px', color: '#475569', flexWrap: 'wrap' }}>
                {showHotspots && <span>🔴 Chronic Hotspot</span>}
                {showPumps && <span>⚙️ Pumping Station</span>}
                {showShelters && <span>🏥 Relief Shelter</span>}
                {showCriticalInfra && <span>🏛️ Critical Infrastructure</span>}
                {showCitizenReports && <span>🟠 Citizen Report</span>}
                {showObservedEvents && <span>🟣 Observed Event</span>}
                {showFacilities && <span>✚ Emergency Facility</span>}
                {!showHotspots && !showPumps && !showShelters && !showCriticalInfra && !showCitizenReports && !showObservedEvents && !showFacilities && (
                  <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>No point layers enabled in Layer Controls</span>
                )}
              </div>
            </div>
          </div>

          {/* Floating Feature Inspector Side-Drawer */}
          {selectedFeature && (
            <div style={{
              position: 'absolute', top: '56px', right: '14px', width: '340px',
              maxHeight: 'calc(100% - 76px)', overflowY: 'auto', zIndex: 1000,
              padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px',
              background: '#ffffff',
              boxShadow: '0 8px 30px rgba(0,0,0,0.15)', border: '1px solid #cbd5e1',
              borderRadius: '8px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#1d4ed8', textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                    {selectedFeature.type}
                  </div>
                  <h4 style={{ margin: '3px 0 0', fontSize: '14px', fontWeight: 800, color: '#0f172a' }}>
                    {selectedFeature.title}
                  </h4>
                </div>
                <button
                  onClick={() => setSelectedFeature(null)}
                  style={{
                    background: 'none', border: 'none', fontSize: '16px', cursor: 'pointer',
                    color: '#64748b', padding: '2px 4px',
                  }}
                >
                  ✕
                </button>
              </div>

              <div style={{
                padding: '5px 8px', borderRadius: '6px', fontSize: '9.5px', fontWeight: 700,
                background: '#f8fafc', color: '#475569', border: '1px solid #e2e8f0',
              }}>
                PROVENANCE: {selectedFeature.provenance}
              </div>

              {/* Contributing Flood Drivers */}
              {selectedFeature.explanation && (
                <div style={{
                  background: '#f0f9ff',
                  border: '1px solid #bae6fd',
                  borderRadius: '8px',
                  padding: '10px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                }}>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#0284c7', textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                    🔍 Contributing Flood Drivers
                  </div>
                  <div style={{ fontSize: '11px', color: '#0f172a', lineHeight: '1.4' }}>
                    • <strong>{selectedFeature.explanation.forecast_rainfall_3h_mm} mm</strong> forecast rain / 3h<br/>
                    • <strong>{selectedFeature.explanation.terrain_depression}</strong><br/>
                    • <strong>{selectedFeature.explanation.drainage_stress}</strong><br/>
                    {selectedFeature.explanation.chronic_hotspots_count > 0 && (
                      <>• <strong>{selectedFeature.explanation.chronic_hotspots_count}</strong> chronic hotspots ({selectedFeature.explanation.chronic_hotspots.slice(0, 2).join(', ')})<br/></>
                    )}
                    • Simulated depth: <strong>{selectedFeature.explanation.simulated_max_depth_m} m</strong>
                  </div>
                </div>
              )}

              {/* Recommended Municipal Actions */}
              {selectedFeature.actions && selectedFeature.actions.length > 0 && (
                <div style={{
                  background: '#fff7ed',
                  border: '1px solid #ffedd5',
                  borderRadius: '8px',
                  padding: '10px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                }}>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#c2410c', textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                    🚨 Recommended Municipal Directives
                  </div>
                  <ul style={{ margin: 0, paddingLeft: '14px', fontSize: '10.5px', color: '#7c2d12', lineHeight: '1.4' }}>
                    {selectedFeature.actions.map((act: string, idx: number) => (
                      <li key={idx} style={{ marginBottom: '3px' }}>{act}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px' }}>
                {Object.entries(selectedFeature.data).map(([k, v]) => (
                  <div key={k} style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '3px', borderBottom: '1px solid #f1f5f9' }}>
                    <span style={{ color: '#64748b' }}>{k}:</span>
                    <strong style={{ color: '#0f172a', textAlign: 'right', maxWidth: '180px' }}>{String(v)}</strong>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: 'auto', paddingTop: '8px' }}>
                <button
                  style={{
                    width: '100%', fontSize: '11px', padding: '7px',
                    background: '#f1f5f9', border: '1px solid #cbd5e1', borderRadius: '6px',
                    color: '#0f172a', fontWeight: 600, cursor: 'pointer'
                  }}
                  onClick={() => setSelectedFeature(null)}
                >
                  Dismiss Inspector
                </button>
              </div>
            </div>
          )}
      </div>
    </div>
  );
}

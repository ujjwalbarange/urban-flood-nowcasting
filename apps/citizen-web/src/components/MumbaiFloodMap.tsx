'use client';

import React, { useEffect, useState, useRef } from 'react';
import dynamic from 'next/dynamic';

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
const Marker = dynamic<any>(
  () => import('react-leaflet').then(mod => mod.Marker),
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

/** Safely extract a [lat, lng] center coordinate from any GeoJSON geometry type */
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
      gap: '8px',
      padding: '8px 12px',
      borderRadius: '8px',
      cursor: 'pointer',
      background: enabled ? 'var(--color-info-bg)' : 'transparent',
      border: `1px solid ${enabled ? 'var(--color-info-border)' : 'var(--border-light)'}`,
      fontSize: '13px',
      fontWeight: enabled ? 600 : 500,
      color: enabled ? 'var(--text-primary)' : 'var(--text-secondary)',
      transition: 'all 0.15s ease',
      userSelect: 'none' as const,
    }}>
      <span style={{
        width: '12px', height: '12px', borderRadius: '3px',
        background: enabled ? color : '#e2e8f0',
        border: `2px solid ${color}`,
        display: 'inline-block',
        transition: 'background 0.15s ease',
      }} />
      {label}
      {count !== undefined && (
        <span style={{
          fontSize: '11px', fontWeight: 700,
          background: 'var(--bg-tertiary)', padding: '1px 6px',
          borderRadius: '10px', color: 'var(--text-muted)',
        }}>{count}</span>
      )}
    </label>
  );
}

export function MumbaiFloodMap() {
  const [mounted, setMounted] = useState(false);
  const [wards, setWards] = useState<GeoJSONCollection | null>(null);
  const [floodHotspots, setFloodHotspots] = useState<GeoJSONCollection | null>(null);
  const [subareas, setSubareas] = useState<GeoJSONCollection | null>(null);
  const [facilities, setFacilities] = useState<GeoJSONCollection | null>(null);
  const [shelters, setShelters] = useState<GeoJSONCollection | null>(null);
  const [drainageNodes, setDrainageNodes] = useState<GeoJSONCollection | null>(null);
  const [drainageLinks, setDrainageLinks] = useState<GeoJSONCollection | null>(null);
  const [roads, setRoads] = useState<GeoJSONCollection | null>(null);
  const [simulationFloods, setSimulationFloods] = useState<GeoJSONCollection | null>(null);
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

  // Layer visibility
  const [showWards, setShowWards] = useState(true);
  const [showSubareas, setShowSubareas] = useState(false);
  const [showFacilities, setShowFacilities] = useState(false); // DEFAULT FALSE per explicit user requirement
  const [showHotspots, setShowHotspots] = useState(true);
  const [showShelters, setShowShelters] = useState(false);
  const [showDrainage, setShowDrainage] = useState(false);
  const [showVerifiedDrainage, setShowVerifiedDrainage] = useState(false);
  const [showSyntheticDrainage, setShowSyntheticDrainage] = useState(false);
  const [syntheticDrainage, setSyntheticDrainage] = useState<GeoJSONCollection | null>(null);
  const [syntheticWarningDismissed, setSyntheticWarningDismissed] = useState(false);
  const [showRoads, setShowRoads] = useState(false);
  const [showSimulationFloods, setShowSimulationFloods] = useState(true);

  // Phase 3: Real Elevation Topography (Copernicus GLO-30 DEM)
  const [showElevation, setShowElevation] = useState(false);
  const [elevationRasterUrl, setElevationRasterUrl] = useState<string | null>(null);
  const [elevationBounds, setElevationBounds] = useState<[[number, number], [number, number]] | null>(null);
  const [elevationOpacity, setElevationOpacity] = useState(0.65);

  // Phase 3: Real Flood-Depth Heatmap Raster Overlay
  const [showNowcastRaster, setShowNowcastRaster] = useState(true);
  const [nowcastRasterUrl, setNowcastRasterUrl] = useState<string | null>(null);
  const [nowcastBounds, setNowcastBounds] = useState<[[number, number], [number, number]] | null>(null);
  const [nowcastStatus, setNowcastStatus] = useState<any | null>(null);
  const [rasterOpacity, setRasterOpacity] = useState(0.75);

  // ── Unified 2D / 3D Mode & Evacuation Routing State ──
  const [viewMode, setViewMode] = useState<'2d' | '3d'>('2d');
  const [activeEvacuationRoute, setActiveEvacuationRoute] = useState<any | null>(null);
  const [isComputingEvacRoute, setIsComputingEvacRoute] = useState<boolean>(false);
  const [evacRouteError, setEvacRouteError] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
    // Import Leaflet CSS client-side
    import('leaflet/dist/leaflet.css');
    loadAllData();
  }, []);

  async function loadAllData() {
    setLoading(true);
    setError(null);
    try {
      const [wardsRes, subareasRes, facsRes, hotspotsRes, sheltersRes, nodesRes, linksRes, roadsRes] = await Promise.all([
        fetch(`${API_BASE}/geodata/wards`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/subareas`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/facilities?limit=2000`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/flood-hotspots`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/shelters`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/drainage/nodes`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/drainage/links`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/roads`).then(r => r.json()).catch(() => null),
      ]);

      if (wardsRes) setWards(wardsRes);
      if (subareasRes) setSubareas(subareasRes);
      if (facsRes) setFacilities(facsRes);
      if (hotspotsRes) setFloodHotspots(hotspotsRes);
      if (sheltersRes) setShelters(sheltersRes);
      if (nodesRes) setDrainageNodes(nodesRes);
      if (linksRes) setDrainageLinks(linksRes);
      if (roadsRes) setRoads(roadsRes);

      // Fetch latest georeferenced simulation inundation
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

      // Phase 3: Fetch real Copernicus GLO-30 elevation raster
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
      } catch { /* elevation raster */ }

      // Phase 3: Fetch nowcast flood raster overlay
      try {
        const rasterResp = await fetch(`${API_BASE}/nowcast/latest/raster.png?t=${Date.now()}`);
        if (rasterResp.ok && rasterResp.status !== 204) {
          const minLat = parseFloat(rasterResp.headers.get('X-Georef-MinLat') || '0');
          const maxLat = parseFloat(rasterResp.headers.get('X-Georef-MaxLat') || '0');
          const minLon = parseFloat(rasterResp.headers.get('X-Georef-MinLon') || '0');
          const maxLon = parseFloat(rasterResp.headers.get('X-Georef-MaxLon') || '0');
          if (minLat && maxLat && minLon && maxLon) {
            const blob = await rasterResp.blob();
            setNowcastRasterUrl(URL.createObjectURL(blob));
            setNowcastBounds([[minLat, minLon], [maxLat, maxLon]]);
          }
        }
      } catch { /* raster fetch */ }

      // Phase 3: Fetch simulation status (zero-mock check)
      try {
        const statusRes = await fetch(`${API_BASE}/nowcast/latest/status`).then(r => r.json());
        setNowcastStatus(statusRes);
      } catch { /* status fetch */ }

      // Phase 3: Fetch candidate synthetic drainage network
      try {
        const synthRes = await fetch(`${API_BASE}/drainage/synthetic`).then(r => r.json());
        if (synthRes && synthRes.features && synthRes.features.length > 0) {
          setSyntheticDrainage(synthRes);
        }
      } catch { /* synthetic drainage */ }

      // Fetch live rainfall
      try {
        const rainRes: RainfallResponse = await fetch(
          `${API_BASE}/rainfall/current?lat=19.076&lon=72.877`
        ).then(r => r.json());
        if (rainRes?.observations?.[0]) {
          setCurrentRainfall(rainRes.observations[0].rate_mmh);
        }
      } catch { /* rainfall may be offline */ }

    } catch (err) {
      setError('Failed to load map data. Is the API running on port 8000?');
    }
    setLoading(false);
  }


  if (!mounted) {
    return (
      <div className="map-container" style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--bg-tertiary)', fontSize: '14px', color: 'var(--text-muted)',
      }}>
        Loading map...
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

  // ── Ward style (color by population density) ──
  const wardStyle = (feature: any) => {
    const density = feature?.properties?.population_density_per_sq_km || 0;
    let fillColor = '#bfdbfe'; // light blue default
    if (density > 40000) fillColor = '#1e40af';
    else if (density > 30000) fillColor = '#2563eb';
    else if (density > 20000) fillColor = '#3b82f6';
    else if (density > 10000) fillColor = '#60a5fa';
    return {
      fillColor,
      weight: 1.5,
      color: '#1e40af',
      opacity: 0.7,
      fillOpacity: 0.15,
      dashArray: '',
    };
  };

  const wardOnEachFeature = (feature: any, layer: any) => {
    if (feature.properties) {
      const p = feature.properties;
      layer.on('click', (e: any) => {
        if (e.latlng) {
          handleMapClick(e.latlng.lat, e.latlng.lng);
        }
      });
      layer.bindPopup(`
        <div style="padding: 12px; min-width: 220px;">
          <h4 style="margin: 0 0 8px; font-size: 15px; font-weight: 700; color: #0f172a;">${p.ward_name || p.ward_id}</h4>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 12px;">
            <div><span style="color: #64748b;">Zone:</span> <strong>${p.zone || '—'}</strong></div>
            <div><span style="color: #64748b;">Area:</span> <strong>${p.area_sq_km || '—'} km²</strong></div>
            <div><span style="color: #64748b;">Population:</span> <strong>${(p.population_2011 || 0).toLocaleString()}</strong></div>
            <div><span style="color: #64748b;">Density:</span> <strong>${Math.round(p.population_density_per_sq_km || 0).toLocaleString()}/km²</strong></div>
          </div>
        </div>
      `);
      layer.on('mouseover', (e: any) => {
        e.target.setStyle({ fillOpacity: 0.35, weight: 2.5 });
      });
      layer.on('mouseout', (e: any) => {
        e.target.setStyle(wardStyle(feature));
      });
    }
  };

  // ── Drainage link style ──
  const drainageLinkStyle = (feature: any) => ({
    color: '#0284c7',
    weight: feature?.properties?.channel_type === 'open_natural_channel' ? 3 : 2,
    opacity: 0.8,
    dashArray: feature?.properties?.channel_type === 'box_culvert' ? '8 4' : '',
  });

  const drainageLinkPopup = (feature: any, layer: any) => {
    if (feature.properties) {
      const p = feature.properties;
      layer.bindPopup(`
        <div style="padding: 12px; min-width: 200px;">
          <h4 style="margin: 0 0 6px; font-size: 14px; font-weight: 700; color: #0f172a;">🏞️ ${p.name || p.link_id}</h4>
          <div style="font-size: 12px; color: #475569; line-height: 1.8;">
            <div>Type: <strong>${p.channel_type || '—'}</strong></div>
            <div>Width: <strong>${p.width_m || '—'}m</strong> × Depth: <strong>${p.depth_m || '—'}m</strong></div>
            <div>Manning's n: <strong>${p.manning_n || '—'}</strong></div>
            <div>Slope: <strong>${p.slope || '—'}</strong></div>
            <div>Length: <strong>${p.length_m || '—'}m</strong></div>
          </div>
        </div>
      `);
    }
  };

  // ── Synthetic Drainage (MSDI v1.0) style ──
  const syntheticDrainageStyle = (feature: any) => ({
    color: '#8b5cf6',
    weight: 2,
    opacity: 0.85,
    dashArray: '5, 5',
  });

  const syntheticDrainagePopup = (feature: any, layer: any) => {
    if (feature.properties) {
      const p = feature.properties;
      layer.bindPopup(`
        <div style="padding: 10px; min-width: 220px;">
          <div style="font-size: 10px; font-weight: 800; color: #7c3aed; text-transform: uppercase;">SYNTHETIC DRAINAGE (MSDI v1.0)</div>
          <h4 style="margin: 3px 0 6px; font-size: 13px; font-weight: 700;">${p.name || p.link_id || 'Inferred Conduit'}</h4>
          <div style="padding: 4px 6px; background: #fffbeb; border: 1px solid #f59e0b; border-radius: 4px; font-size: 10px; color: #92400e; margin-bottom: 6px;">
            ⚠️ UNVERIFIED INFERENCE — Engineering Assumption
          </div>
          <div style="font-size: 11px; color: #475569; line-height: 1.6;">
            <div>Type: <strong>${p.feature_type || 'Candidate Conduit'}</strong></div>
            <div>Assumed Dia: <strong>${p.assumed_parameters?.pipe_diameter_mm ? p.assumed_parameters.pipe_diameter_mm + ' mm' : '—'}</strong></div>
            <div>Effective Cap: <strong>${p.assumed_parameters?.effective_capacity_cumecs ? p.assumed_parameters.effective_capacity_cumecs + ' m³/s' : '—'}</strong></div>
            <div>Slope: <strong>${p.calculated_ground_slope ? (p.calculated_ground_slope * 100).toFixed(2) + '%' : '—'}</strong></div>
          </div>
        </div>
      `);
    }
  };

  // ── Road style ──
  const roadStyle = (feature: any) => {
    const hw = feature?.properties?.highway;
    let color = '#94a3b8';
    let weight = 1;
    if (hw === 'trunk' || hw === 'motorway') { color = '#f59e0b'; weight = 3; }
    else if (hw === 'primary') { color = '#f97316'; weight = 2.5; }
    else if (hw === 'secondary') { color = '#eab308'; weight = 2; }
    return { color, weight, opacity: 0.7 };
  };

  const roadPopup = (feature: any, layer: any) => {
    if (feature.properties) {
      const p = feature.properties;
      layer.bindPopup(`
        <div style="padding: 10px;">
          <h4 style="margin: 0 0 4px; font-size: 13px; font-weight: 700;">${p.name || 'Unnamed Road'}</h4>
          <div style="font-size: 12px; color: #475569;">
            <div>Type: ${p.highway} • Lanes: ${p.lanes || '—'} • Surface: ${p.surface || '—'}</div>
            <div>Flood vulnerability: <strong style="color: ${p.flood_vulnerability === 'high' ? '#dc2626' : p.flood_vulnerability === 'medium' ? '#d97706' : '#059669'}">${p.flood_vulnerability || '—'}</strong></div>
          </div>
        </div>
      `);
    }
  };

  // ── Simulated Flood Extent style (Copernicus DEM Diffusive Wave) ──
  const floodPolygonStyle = (feature: any) => {
    const depth = feature?.properties?.water_depth_m || 0;
    const color = feature?.properties?.color || (depth >= 0.5 ? '#dc2626' : depth >= 0.25 ? '#ea580c' : '#0284c7');
    return {
      fillColor: color,
      weight: 1,
      color: '#ffffff',
      opacity: 0.8,
      fillOpacity: 0.65,
    };
  };

  const floodPolygonPopup = (feature: any, layer: any) => {
    if (feature.properties) {
      const p = feature.properties;
      layer.bindPopup(`
        <div style="padding: 10px; min-width: 190px;">
          <h4 style="margin: 0 0 6px; font-size: 13px; font-weight: 700; color: #0f172a;">🌊 Simulated Water Depth</h4>
          <div style="font-size: 16px; font-weight: 800; color: ${p.color}; margin-bottom: 4px;">
            ${p.water_depth_m} m
          </div>
          <div style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: 600;">
            Risk: <span style="color: ${p.color}; font-weight: 800;">${p.severity}</span>
          </div>
          <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">
            Terrain: Copernicus GLO-30 DEM
          </div>
        </div>
      `);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Layer Controls & 2D/3D Mode Selector */}
      <div className="card" style={{
        padding: '10px 16px', display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center',
      }}>
        {/* Mode Switch: 2D Flat Map vs 3D Realistic Terrain (In-Place Toggle) */}
        <div style={{
          display: 'flex',
          borderRadius: '8px',
          border: '1px solid #cbd5e1',
          overflow: 'hidden',
          background: '#ffffff',
          boxShadow: '0 2px 6px rgba(0,0,0,0.06)',
          marginRight: '6px',
        }}>
          <button
            onClick={() => setViewMode('2d')}
            style={{
              padding: '5px 12px',
              fontSize: '11px',
              fontWeight: viewMode === '2d' ? 800 : 600,
              background: viewMode === '2d' ? '#1d4ed8' : '#ffffff',
              color: viewMode === '2d' ? '#ffffff' : '#334155',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              transition: 'all 0.15s ease',
            }}
          >
            🗺️ 2D Map
          </button>
          <button
            onClick={() => setViewMode('3d')}
            style={{
              padding: '5px 12px',
              fontSize: '11px',
              fontWeight: viewMode === '3d' ? 800 : 600,
              background: viewMode === '3d' ? '#1d4ed8' : '#ffffff',
              color: viewMode === '3d' ? '#ffffff' : '#334155',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              transition: 'all 0.15s ease',
            }}
          >
            🏔️ 3D Terrain
          </button>
        </div>

        <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' as const, letterSpacing: '0.5px' }}>
          Layers:
        </span>
        <LayerToggle label="Ward Boundaries" color="#2563eb" enabled={showWards} onToggle={() => setShowWards(!showWards)} count={wards?.feature_count} />
        <LayerToggle label="Subareas" color="#3b82f6" enabled={showSubareas} onToggle={() => setShowSubareas(!showSubareas)} count={subareas?.features?.length} />
        <LayerToggle label="Copernicus DEM (Elevation)" color="#10b981" enabled={showElevation} onToggle={() => setShowElevation(!showElevation)} />
        <LayerToggle label="2D Flood Depth Raster" color="#0284c7" enabled={showNowcastRaster} onToggle={() => setShowNowcastRaster(!showNowcastRaster)} />
        <LayerToggle label="Simulated Inundation Polygons" color="#0ea5e9" enabled={showSimulationFloods} onToggle={() => setShowSimulationFloods(!showSimulationFloods)} count={simulationFloods?.features?.length} />
        <LayerToggle label="BRIMSTOWAD Master Drains" color="#0284c7" enabled={showVerifiedDrainage} onToggle={() => setShowVerifiedDrainage(!showVerifiedDrainage)} count={drainageLinks?.features?.length} />
        <LayerToggle label="Synthetic Drainage (MSDI)" color="#8b5cf6" enabled={showSyntheticDrainage} onToggle={() => setShowSyntheticDrainage(!showSyntheticDrainage)} count={syntheticDrainage?.features?.length} />
        <LayerToggle label="Emergency Facilities" color="#dc2626" enabled={showFacilities} onToggle={() => setShowFacilities(!showFacilities)} count={facilities?.features?.length} />
        <LayerToggle label="Flood Hotspots" color="#dc2626" enabled={showHotspots} onToggle={() => setShowHotspots(!showHotspots)} count={floodHotspots?.feature_count} />
        <LayerToggle label="Shelters" color="#059669" enabled={showShelters} onToggle={() => setShowShelters(!showShelters)} count={shelters?.feature_count} />
        <LayerToggle label="Drainage Pumps" color="#0284c7" enabled={showDrainage} onToggle={() => setShowDrainage(!showDrainage)} count={drainageNodes?.feature_count} />
        <LayerToggle label="Roads" color="#f59e0b" enabled={showRoads} onToggle={() => setShowRoads(!showRoads)} count={roads?.feature_count} />


        {currentRainfall !== null && (
          <div style={{
            marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px',
            padding: '6px 14px', borderRadius: 'var(--radius-full)',
            background: currentRainfall > 0 ? 'var(--color-info-bg)' : 'var(--color-success-bg)',
            border: `1px solid ${currentRainfall > 0 ? 'var(--color-info-border)' : 'var(--color-success-border)'}`,
            fontSize: '13px', fontWeight: 700,
            color: currentRainfall > 0 ? 'var(--color-info)' : 'var(--color-success)',
          }}>
            <span className="status-dot live" />
            {currentRainfall > 0 ? `🌧 ${currentRainfall.toFixed(1)} mm/hr` : '☀️ No Rain'}
          </div>
        )}
      </div>

      {/* Map */}
      {error ? (
        <div className="alert-banner danger">
          <span>⚠️ {error}</span>
          <button className="btn-secondary" onClick={loadAllData} style={{ fontSize: '12px', padding: '6px 12px' }}>Retry</button>
        </div>
      ) : (
        <div className="map-container" style={{ position: 'relative' }}>
          {/* 2D Flat Map Viewport */}
          <div style={{ display: viewMode === '2d' ? 'block' : 'none', height: '100%', width: '100%' }}>
            {loading && (
              <div style={{
                position: 'absolute', inset: 0, zIndex: 10,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: 'rgba(255,255,255,0.8)', backdropFilter: 'blur(4px)',
                fontSize: '14px', color: 'var(--text-secondary)', fontWeight: 600,
              }}>
                Loading Mumbai GIS & Flood Layers...
              </div>
            )}
            <MapContainer
              center={MUMBAI_CENTER}
              zoom={11}
              style={{ height: '100%', width: '100%' }}
              scrollWheelZoom={true}
              zoomControl={true}
            >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            <MapClickHandler onMapClick={handleMapClick} />

            {/* Ward boundaries */}
            {showWards && wards?.features && (
              <GeoJSON
                key="wards"
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

            {/* Nowcast Flood Raster Overlay (real solver depth heatmap) */}
            {showNowcastRaster && nowcastRasterUrl && nowcastBounds && (
              <ImageOverlay
                key={`nowcast-raster-${nowcastRasterUrl}`}
                url={nowcastRasterUrl}
                bounds={nowcastBounds}
                opacity={rasterOpacity}
                zIndex={400}
              />
            )}

            {/* Real 2D Simulated Inundation Extent (Copernicus GLO-30 DEM) */}
            {showSimulationFloods && simulationFloods?.features && (
              <GeoJSON
                key={`sim-floods-${simulationFloods.features.length}`}
                data={simulationFloods as any}
                style={floodPolygonStyle}
                onEachFeature={floodPolygonPopup}
              />
            )}

            {/* Verified Drainage Trunk Links (BRIMSTOWAD) */}
            {(showVerifiedDrainage || showDrainage) && drainageLinks?.features && (
              <GeoJSON
                key="drainage-links"
                data={drainageLinks as any}
                style={drainageLinkStyle}
                onEachFeature={drainageLinkPopup}
              />
            )}

            {/* Synthetic Drainage Network (MSDI v1.0) - lines only */}
            {showSyntheticDrainage && syntheticDrainage?.features && (
              <GeoJSON
                key={`synthetic-drainage-${syntheticDrainage.features.length}`}
                data={syntheticDrainage as any}
                filter={(f: any) => f?.geometry?.type === 'LineString' || f?.geometry?.type === 'MultiLineString'}
                style={syntheticDrainageStyle}
                onEachFeature={syntheticDrainagePopup}
              />
            )}

            {/* Roads */}
            {showRoads && roads?.features && (
              <GeoJSON
                key="roads"
                data={roads as any}
                style={roadStyle}
                onEachFeature={roadPopup}
              />
            )}

            {/* Flood hotspots (circle markers) */}
            {showHotspots && floodHotspots?.features?.map((f, i) => {
              const center = getFeatureCenter(f.geometry);
              if (!center) return null;
              const p = f.properties;
              const depth = p.typical_water_depth_m || 0;
              const color = depth >= 1.5 ? '#dc2626' : depth >= 1.0 ? '#ea580c' : depth >= 0.5 ? '#d97706' : '#059669';
              const radius = Math.max(8, depth * 10);
              return (
                <CircleMarker
                  key={`hotspot-${i}`}
                  center={center}
                  radius={radius}
                  pathOptions={{
                    fillColor: color,
                    color: '#ffffff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.8,
                  }}
                >
                  <Popup>
                    <div style={{ padding: '12px', minWidth: '250px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                        <span style={{ fontSize: '18px' }}>🔴</span>
                        <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#0f172a' }}>
                          {p.location_name}
                        </h4>
                      </div>
                      <div style={{
                        display: 'inline-block', padding: '4px 10px', borderRadius: '6px',
                        background: depth >= 1.0 ? '#fef2f2' : '#fffbeb',
                        color: depth >= 1.0 ? '#dc2626' : '#d97706',
                        fontSize: '13px', fontWeight: 800, marginBottom: '8px',
                      }}>
                        ⚠ Typical depth: {depth}m • Max: {p.maximum_recorded_depth_m || '—'}m
                      </div>
                      <div style={{ fontSize: '12px', color: '#475569', lineHeight: '1.7' }}>
                        <div><strong>Ward:</strong> {p.ward} ({p.zone})</div>
                        <div><strong>Basin:</strong> {p.drainage_basin || '—'}</div>
                        <div><strong>Traffic:</strong> {p.traffic_impact || '—'}</div>
                        <div><strong>Railway:</strong> {p.railway_impact || '—'}</div>
                        {p.mitigation_status && (
                          <div style={{ marginTop: '6px', padding: '6px 10px', background: '#f0fdf4', borderRadius: '6px', color: '#059669' }}>
                            ✅ {p.mitigation_status}
                          </div>
                        )}
                      </div>
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}

            {/* Drainage nodes (pumping stations) */}
            {showDrainage && drainageNodes?.features?.map((f, i) => {
              const center = getFeatureCenter(f.geometry);
              if (!center) return null;
              const p = f.properties;
              return (
                <CircleMarker
                  key={`drain-node-${i}`}
                  center={center}
                  radius={6}
                  pathOptions={{
                    fillColor: '#0284c7',
                    color: '#ffffff',
                    weight: 2,
                    fillOpacity: 0.9,
                  }}
                >
                  <Popup>
                    <div style={{ padding: '10px', minWidth: '200px' }}>
                      <h4 style={{ margin: '0 0 6px', fontSize: '13px', fontWeight: 700 }}>⚙️ {p.name || p.node_id}</h4>
                      <div style={{ fontSize: '12px', color: '#475569', lineHeight: '1.7' }}>
                        <div>Type: <strong>{p.type}</strong></div>
                        <div>Ward: <strong>{p.ward}</strong></div>
                        {p.pump_capacity_m3_per_sec && <div>Pump capacity: <strong>{p.pump_capacity_m3_per_sec} m³/s</strong></div>}
                        {p.num_pumps && <div>Pumps: <strong>{p.num_pumps}</strong></div>}
                        <div>Status: <strong style={{ color: p.status === 'operational' ? '#059669' : '#dc2626' }}>{p.status}</strong></div>
                      </div>
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}

            {/* Shelters */}
            {showShelters && shelters?.features?.map((f, i) => {
              const center = getFeatureCenter(f.geometry);
              if (!center) return null;
              const p = f.properties;
              return (
                <CircleMarker
                  key={`shelter-${i}`}
                  center={center}
                  radius={7}
                  pathOptions={{
                    fillColor: '#059669',
                    color: '#ffffff',
                    weight: 2,
                    fillOpacity: 0.85,
                  }}
                >
                  <Popup>
                    <div style={{ padding: '12px', minWidth: '240px' }}>
                      <h4 style={{ margin: '0 0 6px', fontSize: '14px', fontWeight: 700, color: '#059669' }}>
                        🏥 {p.name}
                      </h4>
                      <div style={{ fontSize: '12px', color: '#475569', lineHeight: '1.8' }}>
                        <div>{p.address}</div>
                        <div style={{ marginTop: '6px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
                          <div>Capacity: <strong>{p.capacity_persons} persons</strong></div>
                          <div>Ward: <strong>{p.ward}</strong></div>
                          <div>Generator: <strong>{p.backup_power_generator === 'yes' ? '✅' : '❌'}</strong></div>
                          <div>Medical: <strong>{p.medical_first_aid_post === 'yes' ? '✅' : '❌'}</strong></div>
                          <div>Water: <strong>{p.drinking_water_storage_liters?.toLocaleString()}L</strong></div>
                        </div>
                      </div>
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}

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
                      Selected: {selectedLocation.lat.toFixed(5)}° N, {selectedLocation.lon.toFixed(5)}° E
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
              timelineMinute={0}
              showWaterOverlay={showNowcastRaster}
              onClose3D={() => setViewMode('2d')}
            />
          </div>
        )}

          {/* Synthetic Drainage Safety Warning Banner (Section 8.7) */}
          {showSyntheticDrainage && !syntheticWarningDismissed && (
            <div style={{
              position: 'absolute', top: '14px', left: '50%', transform: 'translateX(-50%)',
              zIndex: 1000, maxWidth: '640px', width: '92%',
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
            maxWidth: '360px', maxHeight: '400px', overflowY: 'auto',
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
                  Dry cells (&lt;0.01m) transparent · 2D Diffusive Wave Solver
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
                {showDrainage && <span>⚙️ Pumping Station</span>}
                {showShelters && <span>🏥 Relief Shelter</span>}
                {showFacilities && <span>✚ Emergency Facility</span>}
                {!showHotspots && !showDrainage && !showShelters && !showFacilities && (
                  <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>No point layers enabled</span>
                )}
              </div>
            </div>
          </div>

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
        </div>
      )}
    </div>
  );
}

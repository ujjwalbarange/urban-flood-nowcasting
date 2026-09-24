'use client';

import React, { useEffect, useState } from 'react';
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

const API_BASE = 'http://127.0.0.1:8000/api/v1';

// Mumbai center coordinates
const MUMBAI_CENTER: [number, number] = [19.076, 72.877];

// Supported Professional GIS Basemaps
const BASEMAP_TILES = {
  positron: {
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://carto.com/">CARTO</a> Positron, &copy; OpenStreetMap',
  },
  dark: {
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://carto.com/">CARTO</a> Dark Matter, &copy; OpenStreetMap',
  },
  osm: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  },
};

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
      padding: '7px 11px',
      borderRadius: '8px',
      cursor: 'pointer',
      background: enabled ? 'var(--color-info-bg)' : 'transparent',
      border: `1px solid ${enabled ? 'var(--color-info-border)' : 'var(--border-light)'}`,
      fontSize: '12px',
      fontWeight: enabled ? 700 : 500,
      color: enabled ? 'var(--text-primary)' : 'var(--text-secondary)',
      transition: 'all 0.15s ease',
      userSelect: 'none' as const,
    }}>
      <input
        type="checkbox"
        checked={enabled}
        onChange={onToggle}
        style={{ display: 'none' }}
      />
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

interface MumbaiFloodMapProps {
  confusionGeoJSON?: GeoJSONCollection | null;
}

export function MumbaiFloodMap({ confusionGeoJSON }: MumbaiFloodMapProps = {}) {
  const [mounted, setMounted] = useState(false);
  const [wards, setWards] = useState<GeoJSONCollection | null>(null);
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

  // Basemap & Visual Options
  const [basemap, setBasemap] = useState<'positron' | 'dark' | 'osm'>('positron');
  const [rasterOpacity, setRasterOpacity] = useState(0.80);

  // Nowcast flood raster overlay & timeline scrubbing state
  const [nowcastRasterUrl, setNowcastRasterUrl] = useState<string | null>(null);
  const [nowcastBounds, setNowcastBounds] = useState<[[number,number],[number,number]] | null>(null);
  const [showNowcastRaster, setShowNowcastRaster] = useState(true);
  const [timelineMinute, setTimelineMinute] = useState<number>(0);
  const [nowcastData, setNowcastData] = useState<any>(null);
  const [isTimelineLoading, setIsTimelineLoading] = useState(false);

  // Inspector State
  const [selectedFeature, setSelectedFeature] = useState<any | null>(null);
  const [colorMode, setColorMode] = useState<'risk' | 'density'>('risk');

  // Layer visibility toggles (default clean GIS state)
  const [showWards, setShowWards] = useState(true);
  const [showSimulationFloods, setShowSimulationFloods] = useState(false); // DEFAULT FALSE to eliminate ugly boxes!
  const [showObservedEvents, setShowObservedEvents] = useState(false);
  const [showHotspots, setShowHotspots] = useState(true);
  const [showPumps, setShowPumps] = useState(true);
  const [showCriticalInfra, setShowCriticalInfra] = useState(false);
  const [showShelters, setShowShelters] = useState(false);
  const [showDrainage, setShowDrainage] = useState(true);
  const [showRoads, setShowRoads] = useState(false);
  const [showCitizenReports, setShowCitizenReports] = useState(true);
  const [showConfusion, setShowConfusion] = useState(false);

  const activeConfusion = confusionGeoJSON || confusionLayer;

  useEffect(() => {
    setMounted(true);
    import('leaflet/dist/leaflet.css');
    loadAllData();
  }, []);

  async function loadAllData() {
    setLoading(true);
    setError(null);
    try {
      const [
        wardsRes, hotspotsRes, sheltersRes, nodesRes, linksRes, roadsRes,
        obsEventsRes, pumpsRes, infraRes, riskRes, reportsRes
      ] = await Promise.all([
        fetch(`${API_BASE}/geodata/wards`).then(r => r.json()).catch(() => null),
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
      weight: 1.2,
      color: basemap === 'dark' ? '#94a3b8' : '#475569',
      dashArray: '4 3',
      opacity: 0.65,
      fillOpacity,
    };
  };

  const wardOnEachFeature = (feature: any, layer: any) => {
    if (feature.properties) {
      const p = feature.properties;
      const wr = wardRisks[p.ward_id];
      const explanation = nowcastData?.ward_explanations?.[p.ward_id];

      layer.on('click', () => {
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

  // ── Drainage Links Style ──
  const drainageLinkStyle = (feature: any) => ({
    color: '#0284c7',
    weight: feature?.properties?.channel_type === 'open_natural_channel' ? 3.5 : 2.5,
    opacity: 0.85,
    dashArray: feature?.properties?.channel_type === 'box_culvert' ? '6 3' : '',
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Layer Controls Bar */}
      <div className="card" style={{
        padding: '12px 16px', display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center',
        background: 'var(--bg-secondary)', border: '1px solid var(--border-light)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginRight: '6px' }}>
          <span style={{ fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            GIS Layers:
          </span>
          {/* Color Mode Switcher */}
          <select
            value={colorMode}
            onChange={e => setColorMode(e.target.value as any)}
            style={{
              fontSize: '11px', fontWeight: 700, padding: '4px 8px', borderRadius: '6px',
              background: 'var(--bg-primary)', border: '1px solid var(--border-medium)', color: 'var(--text-primary)',
            }}
          >
            <option value="risk">Color Wards: Risk Level</option>
            <option value="density">Color Wards: Population Density</option>
          </select>

          {/* Basemap Switcher */}
          <select
            value={basemap}
            onChange={e => setBasemap(e.target.value as any)}
            style={{
              fontSize: '11px', fontWeight: 700, padding: '4px 8px', borderRadius: '6px',
              background: 'var(--bg-primary)', border: '1px solid var(--border-medium)', color: 'var(--text-primary)',
            }}
          >
            <option value="positron">🗺️ Basemap: CartoDB Positron (Clean GIS)</option>
            <option value="dark">🌑 Basemap: CartoDB Dark Matter</option>
            <option value="osm">🌐 Basemap: OpenStreetMap Standard</option>
          </select>
        </div>

        {/* Primary Flood Layer: Smooth Continuous Water Surface */}
        <LayerToggle
          label="🌊 Continuous Flood Surface"
          color="#0284c7"
          enabled={showNowcastRaster}
          onToggle={() => setShowNowcastRaster(!showNowcastRaster)}
        />
        <LayerToggle label="Wards" color="#2563eb" enabled={showWards} onToggle={() => setShowWards(!showWards)} count={wards?.feature_count} />
        <LayerToggle label="Pumping Stations" color="#0891b2" enabled={showPumps} onToggle={() => setShowPumps(!showPumps)} count={pumpingStations?.features?.length} />
        <LayerToggle label="Drainage Trunk" color="#0284c7" enabled={showDrainage} onToggle={() => setShowDrainage(!showDrainage)} count={drainageNodes?.feature_count} />
        <LayerToggle label="Chronic Hotspots" color="#dc2626" enabled={showHotspots} onToggle={() => setShowHotspots(!showHotspots)} count={floodHotspots?.feature_count} />
        <LayerToggle label="Citizen Reports" color="#f97316" enabled={showCitizenReports} onToggle={() => setShowCitizenReports(!showCitizenReports)} count={citizenReports.length} />
        <LayerToggle label="🔲 Cell Mesh (Diagnostic)" color="#64748b" enabled={showSimulationFloods} onToggle={() => setShowSimulationFloods(!showSimulationFloods)} count={simulationFloods?.features?.length} />
        <LayerToggle label="Observed Events (2016-25)" color="#8b5cf6" enabled={showObservedEvents} onToggle={() => setShowObservedEvents(!showObservedEvents)} count={observedEvents?.features?.length} />
        <LayerToggle label="Critical Infrastructure" color="#f59e0b" enabled={showCriticalInfra} onToggle={() => setShowCriticalInfra(!showCriticalInfra)} count={criticalInfra?.features?.length} />
        <LayerToggle label="Shelters" color="#059669" enabled={showShelters} onToggle={() => setShowShelters(!showShelters)} count={shelters?.feature_count} />

        {activeConfusion?.features && activeConfusion.features.length > 0 && (
          <LayerToggle
            label="🛰️ Sourced Extent Validation"
            color="#059669"
            enabled={showConfusion}
            onToggle={() => setShowConfusion(!showConfusion)}
            count={activeConfusion.features.length}
          />
        )}

        {currentRainfall !== null && (
          <div style={{
            marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px',
            padding: '5px 12px', borderRadius: 'var(--radius-full)',
            background: currentRainfall > 0 ? 'var(--color-info-bg)' : 'var(--color-success-bg)',
            border: `1px solid ${currentRainfall > 0 ? 'var(--color-info-border)' : 'var(--color-success-border)'}`,
            fontSize: '12px', fontWeight: 700,
            color: currentRainfall > 0 ? 'var(--color-info)' : 'var(--color-success)',
          }}>
            <span className="status-dot live" />
            {currentRainfall > 0 ? `🌧 ${currentRainfall.toFixed(1)} mm/hr` : '☀️ Live Weather: 0.0 mm/hr'}
          </div>
        )}
      </div>

      {/* Map + Inspector Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: selectedFeature ? '1fr 360px' : '1fr', gap: '12px' }}>
        {/* Map Viewport */}
        <div className="map-container" style={{ position: 'relative', height: '640px', borderRadius: '12px', overflow: 'hidden' }}>
          {loading && (
            <div style={{
              position: 'absolute', inset: 0, zIndex: 1000,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'rgba(15,23,42,0.65)', backdropFilter: 'blur(4px)',
              fontSize: '14px', color: '#ffffff', fontWeight: 700,
            }}>
              Loading PostGIS layers & Copernicus DEM data...
            </div>
          )}

          {/* Floating Interactive Forecast Timeline Player */}
          <div style={{
            position: 'absolute', top: '14px', left: '50%', transform: 'translateX(-50%)', zIndex: 1000,
            background: 'rgba(15, 23, 42, 0.90)', backdropFilter: 'blur(10px)',
            padding: '6px 14px', borderRadius: '10px', boxShadow: '0 8px 30px rgba(0,0,0,0.4)',
            border: '1px solid rgba(255,255,255,0.15)', display: 'flex', alignItems: 'center', gap: '8px',
            color: '#f8fafc',
          }}>
            <span style={{ fontSize: '10px', fontWeight: 800, color: '#38bdf8', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
              Forecast Nowcast:
            </span>
            <div style={{ display: 'flex', gap: '4px' }}>
              {[0, 30, 60, 90, 120, 180].map(m => (
                <button
                  key={m}
                  onClick={() => handleTimelineStep(m)}
                  style={{
                    padding: '3px 8px',
                    borderRadius: '5px',
                    fontSize: '10px',
                    fontWeight: timelineMinute === m ? 800 : 600,
                    cursor: 'pointer',
                    background: timelineMinute === m ? '#2563eb' : 'rgba(255,255,255,0.08)',
                    color: timelineMinute === m ? '#ffffff' : '#cbd5e1',
                    border: `1px solid ${timelineMinute === m ? '#60a5fa' : 'transparent'}`,
                    transition: 'all 0.15s ease',
                  }}
                >
                  {m === 0 ? 'NOW' : `+${m}m`}
                </button>
              ))}
            </div>
            {isTimelineLoading && (
              <span style={{ fontSize: '10px', color: '#93c5fd' }}>Updating...</span>
            )}
            {nowcastData?.results && (
              <span style={{ fontSize: '10px', color: '#94a3b8', borderLeft: '1px solid rgba(255,255,255,0.2)', paddingLeft: '8px' }}>
                Peak: <strong style={{ color: '#38bdf8' }}>{nowcastData.results.max_depth_m}m</strong> | Flooded: <strong style={{ color: '#38bdf8' }}>{nowcastData.results.flooded_area_km2} km²</strong>
              </span>
            )}
          </div>

          {/* Floating Water Opacity Control */}
          {showNowcastRaster && nowcastRasterUrl && (
            <div style={{
              position: 'absolute', top: '14px', right: '14px', zIndex: 1000,
              background: 'rgba(15, 23, 42, 0.88)', backdropFilter: 'blur(8px)',
              padding: '6px 10px', borderRadius: '8px', boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
              border: '1px solid rgba(255,255,255,0.12)', display: 'flex', alignItems: 'center', gap: '6px',
              fontSize: '10px', color: '#f8fafc',
            }}>
              <span style={{ color: '#94a3b8', fontWeight: 700 }}>WATER OPACITY:</span>
              <input
                type="range"
                min="0.2"
                max="1.0"
                step="0.05"
                value={rasterOpacity}
                onChange={e => setRasterOpacity(parseFloat(e.target.value))}
                style={{ width: '65px', cursor: 'pointer' }}
              />
              <span style={{ color: '#38bdf8', fontWeight: 800 }}>{Math.round(rasterOpacity * 100)}%</span>
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
              key={basemap}
              attribution={BASEMAP_TILES[basemap].attribution}
              url={BASEMAP_TILES[basemap].url}
            />

            {/* Ward boundaries — soft & translucent */}
            {showWards && wards?.features && (
              <GeoJSON
                key={`wards-${colorMode}-${basemap}-${wards.features.length}`}
                data={wards as any}
                style={wardStyle}
                onEachFeature={wardOnEachFeature}
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

            {/* Drainage Links */}
            {showDrainage && drainageLinks?.features && (
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
              const coords = f.geometry.coordinates;
              const p = f.properties;
              const depth = p.flood_depth_cm ? p.flood_depth_cm / 100 : 0.3;
              const radius = Math.min(18, Math.max(7, depth * 8));
              return (
                <CircleMarker
                  key={`obs-evt-${i}`}
                  center={[coords[1], coords[0]]}
                  radius={radius}
                  pathOptions={{
                    fillColor: '#8b5cf6',
                    color: '#ffffff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.85,
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
              const coords = f.geometry.coordinates;
              const p = f.properties;
              const depth = p.typical_water_depth_m || 0.8;
              const color = depth >= 1.5 ? '#dc2626' : depth >= 1.0 ? '#ea580c' : depth >= 0.5 ? '#d97706' : '#059669';
              const radius = Math.max(9, depth * 9);
              return (
                <CircleMarker
                  key={`hotspot-${i}`}
                  center={[coords[1], coords[0]]}
                  radius={radius}
                  pathOptions={{
                    fillColor: color,
                    color: '#ffffff',
                    weight: 2.5,
                    opacity: 1,
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
              const coords = f.geometry.coordinates;
              const p = f.properties;
              return (
                <CircleMarker
                  key={`pump-${i}`}
                  center={[coords[1], coords[0]]}
                  radius={9}
                  pathOptions={{
                    fillColor: '#0891b2',
                    color: '#ffffff',
                    weight: 2.5,
                    opacity: 1,
                    fillOpacity: 0.95,
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
              const coords = f.geometry.coordinates;
              const p = f.properties;
              return (
                <CircleMarker
                  key={`infra-${i}`}
                  center={[coords[1], coords[0]]}
                  radius={7}
                  pathOptions={{
                    fillColor: '#f59e0b',
                    color: '#ffffff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.9,
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
              const coords = f.geometry.coordinates;
              const p = f.properties;
              return (
                <CircleMarker
                  key={`shelter-${i}`}
                  center={[coords[1], coords[0]]}
                  radius={8}
                  pathOptions={{
                    fillColor: '#059669',
                    color: '#ffffff',
                    weight: 2,
                    opacity: 1,
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
            {showCitizenReports && citizenReports.map((r, i) => (
              <CircleMarker
                key={`rpt-${i}`}
                center={[r.latitude, r.longitude]}
                radius={8}
                pathOptions={{
                  fillColor: '#f97316',
                  color: '#ffffff',
                  weight: 2.5,
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
            ))}

            {/* Satellite SAR Confusion Matrix Layer */}
            {showConfusion && activeConfusion?.features && (
              <GeoJSON
                key={`confusion-layer-${activeConfusion.features.length}`}
                data={activeConfusion as any}
                style={confusionStyle}
                onEachFeature={(f: any, layer: any) => {
                  layer.on('click', () => {
                    const p = f.properties;
                    setSelectedFeature({
                      title: `SAR Validation: ${p.classification === 'TP' ? 'True Positive' : p.classification === 'FP' ? 'False Positive' : 'False Negative'}`,
                      type: 'Sentinel-1 SAR Ground Truth Comparison',
                      provenance: 'SATELLITE DERIVED — ESA Sentinel-1 C-Band SAR Change Detection',
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
          </MapContainer>

          {/* Floating Continuous Depth & Risk Legend */}
          <div style={{
            position: 'absolute', bottom: '16px', left: '16px', zIndex: 1000,
            background: 'rgba(15, 23, 42, 0.92)', backdropFilter: 'blur(8px)',
            padding: '12px 14px', borderRadius: '10px', boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
            border: '1px solid rgba(255,255,255,0.1)', fontSize: '11px', color: '#f8fafc',
          }}>
            <div style={{ fontWeight: 800, marginBottom: '6px', color: '#38bdf8', letterSpacing: '0.3px' }}>
              🌊 FLOOD DEPTH CLASSIFICATION
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '4px', textAlign: 'center', marginBottom: '8px' }}>
              <div>
                <div style={{ height: '8px', background: '#38bdf8', borderRadius: '2px' }} />
                <div style={{ marginTop: '2px', fontSize: '9px', color: '#94a3b8' }}>&lt;0.15m</div>
              </div>
              <div>
                <div style={{ height: '8px', background: '#0284c7', borderRadius: '2px' }} />
                <div style={{ marginTop: '2px', fontSize: '9px', color: '#94a3b8' }}>0.15-0.3m</div>
              </div>
              <div>
                <div style={{ height: '8px', background: '#eab308', borderRadius: '2px' }} />
                <div style={{ marginTop: '2px', fontSize: '9px', color: '#94a3b8' }}>0.3-0.5m</div>
              </div>
              <div>
                <div style={{ height: '8px', background: '#ea580c', borderRadius: '2px' }} />
                <div style={{ marginTop: '2px', fontSize: '9px', color: '#94a3b8' }}>0.5-1.0m</div>
              </div>
              <div>
                <div style={{ height: '8px', background: '#dc2626', borderRadius: '2px' }} />
                <div style={{ marginTop: '2px', fontSize: '9px', color: '#94a3b8' }}>&gt;1.0m</div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px', fontSize: '10px', color: '#cbd5e1' }}>
              <span>🔴 Hotspot</span>
              <span>⚙️ Pump Station</span>
              <span>🏥 Shelter</span>
              <span>🟣 Observed Event</span>
              <span>🟠 Citizen Report</span>
            </div>
          </div>
        </div>

        {/* Feature Inspector Side-Drawer */}
        {selectedFeature && (
          <div className="card fade-in" style={{
            padding: '18px', display: 'flex', flexDirection: 'column', gap: '12px',
            background: 'var(--bg-secondary)', border: '1px solid var(--border-medium)',
            overflowY: 'auto', maxHeight: '620px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--brand-blue)', textTransform: 'uppercase' }}>
                  {selectedFeature.type}
                </div>
                <h4 style={{ margin: '4px 0 0', fontSize: '15px', fontWeight: 800, color: 'var(--text-primary)' }}>
                  {selectedFeature.title}
                </h4>
              </div>
              <button
                onClick={() => setSelectedFeature(null)}
                style={{
                  background: 'none', border: 'none', fontSize: '16px', cursor: 'pointer',
                  color: 'var(--text-muted)', padding: '2px 6px',
                }}
              >
                ✕
              </button>
            </div>

            <div style={{
              padding: '6px 10px', borderRadius: '6px', fontSize: '10px', fontWeight: 700,
              background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-light)',
            }}>
              DATA PROVENANCE: {selectedFeature.provenance}
            </div>

            {/* "Why is this area flooding?" Contributing Factors */}
            {selectedFeature.explanation && (
              <div style={{
                background: 'rgba(14, 165, 233, 0.08)',
                border: '1px solid rgba(14, 165, 233, 0.3)',
                borderRadius: '8px',
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
              }}>
                <div style={{ fontSize: '11px', fontWeight: 800, color: 'var(--brand-blue)', textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                  🔍 Contributing Flood Drivers
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-primary)', lineHeight: '1.5' }}>
                  • <strong>{selectedFeature.explanation.forecast_rainfall_3h_mm} mm</strong> forecast rainfall / 3h<br/>
                  • <strong>{selectedFeature.explanation.terrain_depression}</strong><br/>
                  • <strong>{selectedFeature.explanation.drainage_stress}</strong><br/>
                  {selectedFeature.explanation.chronic_hotspots_count > 0 && (
                    <>• <strong>{selectedFeature.explanation.chronic_hotspots_count}</strong> chronic flood hotspots ({selectedFeature.explanation.chronic_hotspots.slice(0, 2).join(', ')})<br/></>
                  )}
                  • Current simulated depth: <strong>{selectedFeature.explanation.simulated_max_depth_m} m</strong>
                </div>
              </div>
            )}

            {/* Recommended Municipal Actions */}
            {selectedFeature.actions && selectedFeature.actions.length > 0 && (
              <div style={{
                background: 'rgba(234, 88, 12, 0.08)',
                border: '1px solid rgba(234, 88, 12, 0.3)',
                borderRadius: '8px',
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
              }}>
                <div style={{ fontSize: '11px', fontWeight: 800, color: '#ea580c', textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                  🚨 Recommended Operator Actions
                </div>
                <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '11px', color: 'var(--text-primary)', lineHeight: '1.4' }}>
                  {selectedFeature.actions.map((act: string, idx: number) => (
                    <li key={idx} style={{ marginBottom: '4px' }}>{act}</li>
                  ))}
                </ul>
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
              {Object.entries(selectedFeature.data).map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '4px', borderBottom: '1px solid var(--border-light)' }}>
                  <span style={{ color: 'var(--text-muted)' }}>{k}:</span>
                  <strong style={{ color: 'var(--text-primary)', textAlign: 'right', maxWidth: '180px' }}>{String(v)}</strong>
                </div>
              ))}
            </div>

            <div style={{ marginTop: 'auto', paddingTop: '10px' }}>
              <button
                className="btn-secondary"
                style={{ width: '100%', fontSize: '12px', padding: '8px' }}
                onClick={() => setSelectedFeature(null)}
              >
                Close Inspector
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

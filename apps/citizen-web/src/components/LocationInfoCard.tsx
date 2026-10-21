'use client';

import React, { useState } from 'react';
import {
  MapPin, X, Building2, Hospital, Shield, Flame, Home,
  Compass, AlertCircle, CheckCircle2, ChevronRight, Eye, EyeOff,
  Cloud, CloudRain, CloudDrizzle, CloudLightning, Sun, Thermometer,
  Droplets, Wind, Gauge, History, Calendar, AlertTriangle, Layers, Info, Clock, Navigation
} from 'lucide-react';

interface FacilityItem {
  facility_id?: string | number;
  name: string;
  category: string;
  distance_km?: number;
  address?: string;
  capacity_persons?: number;
  amenity?: string;
}

interface CurrentWeather {
  temperature_c?: number;
  apparent_temperature_c?: number;
  relative_humidity_percent?: number;
  precipitation_mm?: number;
  stratiform_rain_mm?: number;
  convective_showers_mm?: number;
  effective_rainfall_rate_mmh?: number;
  weather_code?: number;
  weather_description?: string;
  condition_key?: string;
  surface_pressure_hpa?: number;
  wind_speed_kmh?: number;
  wind_direction_deg?: number;
  wind_gusts_kmh?: number;
  observation_time?: string;
  timezone?: string;
  elevation_m?: number;
  source?: string;
  data_quality?: string;
  note?: string;
}

interface DailyForecastItem {
  date: string;
  day_name: string;
  weather_code: number;
  weather_description: string;
  condition_key: string;
  temp_max_c?: number;
  temp_min_c?: number;
  precipitation_sum_mm?: number;
  rain_sum_mm?: number;
  showers_sum_mm?: number;
  precipitation_hours?: number;
  precipitation_probability_max?: number;
  wind_speed_max_kmh?: number;
  wind_gusts_max_kmh?: number;
}

interface HourlyForecastItem {
  time: string;
  temperature_c?: number;
  precipitation_rate_mmh?: number;
  precipitation_probability_percent?: number;
  weather_code?: number;
  weather_description?: string;
  condition_key?: string;
  wind_speed_kmh?: number;
}

interface HistoricalComparison {
  source?: string;
  sample_window?: string;
  sample_hours_count?: number;
  hourly_percentiles?: {
    p50: number;
    p75: number;
    p90: number;
    p95: number;
    p99: number;
    record_max: number;
  };
  daily_24h_percentiles?: {
    p50: number;
    p75: number;
    p90: number;
    p95: number;
    p99: number;
    record_max: number;
  };
  rolling_max_mm?: {
    max_3h_mm: number;
    max_6h_mm: number;
    max_12h_mm: number;
    max_24h_mm: number;
  };
  antecedent_rainfall_sample_72h_mm?: number;
  from_cache?: boolean;
  comparison?: {
    current_rate_mmh: number;
    current_hourly_percentile_rank: string;
    current_severity: string;
    forecast_24h_mm: number;
    forecast_24h_percentile_rank: string;
  };
}

interface FloodEvidenceEvent {
  event_id?: string;
  date?: string;
  year?: number;
  ward?: string;
  locality?: string;
  distance_km?: number;
  rainfall_1h_mm?: number;
  rainfall_24h_mm?: number;
  flood_depth_cm?: number;
  flood_depth_m?: number;
  waterlogging_duration_hours?: number;
  flood_duration_hours?: number;
  flood_severity?: string;
  people_affected?: number;
  roads_affected?: number;
  data_source?: string;
  data_provenance?: string;
  similarity_delta?: number;
}

interface WeatherIntelligence {
  status?: string;
  current_conditions?: CurrentWeather;
  forecast_7day?: {
    daily?: DailyForecastItem[];
    hourly?: HourlyForecastItem[];
    peak_summary?: {
      peak_hourly_rate_mmh?: number;
      peak_hour_timestamp?: string;
      forecast_24h_accumulation_mm?: number;
      forecast_7day_accumulation_mm?: number;
      highest_rain_day?: string;
    };
  };
  historical_comparison?: HistoricalComparison;
  historical_flood_evidence?: {
    source?: string;
    query_radius_km?: number;
    nearby_records_count?: number;
    nearby_records?: FloodEvidenceEvent[];
    has_local_evidence?: boolean;
    status_statement?: string;
    weather_analogue_storms?: FloodEvidenceEvent[];
  };
  hazard_assessment?: {
    hazard_level?: string;
    hazard_color?: string;
    headline?: string;
    recommendation?: string;
    weather_analogue_narrative?: string;
    evidence_confidence?: string;
    confidence_notes?: string;
    scientific_disclaimer?: string;
  };
  data_provenance?: Record<string, string>;
}

interface LocationInfoCardProps {
  locationData: {
    status: string;
    in_coverage: boolean;
    coordinates: { lat: number; lon: number };
    message?: string;
    ward?: {
      ward_id: string;
      ward_name: string;
      zone: string;
      headquarters?: string;
      area_sq_km?: number;
      population_2011?: number;
      population_density_per_sq_km?: number;
    } | null;
    subarea?: {
      subarea_id: string;
      subarea_name: string;
      subarea_area_sq_km?: number;
    } | null;
    nearby_facilities?: FacilityItem[];
    weather_intelligence?: WeatherIntelligence | null;
    extension_points?: Record<string, any>;
  } | null;
  isLoading?: boolean;
  onClose: () => void;
  onToggleFacilities?: () => void;
  showFacilitiesOnMap?: boolean;
  activeEvacuationRoute?: any | null;
  onComputeEvacuationRoute?: (vehicleType: string) => void;
  isComputingRoute?: boolean;
  onClearEvacuationRoute?: () => void;
}

type TabType = 'overview' | 'weather' | 'forecast' | 'historical' | 'risk';

export function LocationInfoCard({
  locationData,
  isLoading,
  onClose,
  onToggleFacilities,
  showFacilitiesOnMap = false,
  activeEvacuationRoute,
  onComputeEvacuationRoute,
  isComputingRoute = false,
  onClearEvacuationRoute,
}: LocationInfoCardProps) {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [evacVehicleType, setEvacVehicleType] = useState<string>('standard_car');

  if (!locationData && !isLoading) return null;

  const weatherIntel = locationData?.weather_intelligence;
  const current = weatherIntel?.current_conditions;
  const forecast = weatherIntel?.forecast_7day;
  const histComp = weatherIntel?.historical_comparison;
  const floodEvidence = weatherIntel?.historical_flood_evidence;
  const hazard = weatherIntel?.hazard_assessment;

  const getCategoryIcon = (category: string) => {
    switch (category?.toLowerCase()) {
      case 'hospital':
        return <Hospital size={14} color="#dc2626" />;
      case 'clinic':
        return <Hospital size={14} color="#0284c7" />;
      case 'police':
        return <Shield size={14} color="#1d4ed8" />;
      case 'fire_station':
        return <Flame size={14} color="#ea580c" />;
      case 'shelter':
        return <Home size={14} color="#16a34a" />;
      default:
        return <Building2 size={14} color="#64748b" />;
    }
  };

  const getCategoryBadgeStyle = (category: string) => {
    switch (category?.toLowerCase()) {
      case 'hospital':
        return { bg: '#fef2f2', text: '#991b1b', border: '#fecaca' };
      case 'clinic':
        return { bg: '#f0f9ff', text: '#0369a1', border: '#bae6fd' };
      case 'police':
        return { bg: '#eff6ff', text: '#1e40af', border: '#bfdbfe' };
      case 'fire_station':
        return { bg: '#fff7ed', text: '#9a3412', border: '#fed7aa' };
      case 'shelter':
        return { bg: '#f0fdf4', text: '#166534', border: '#bbf7d0' };
      default:
        return { bg: '#f8fafc', text: '#475569', border: '#e2e8f0' };
    }
  };

  const getWeatherIcon = (condKey?: string, size = 16) => {
    switch (condKey) {
      case 'clear':
      case 'mainly_clear':
        return <Sun size={size} color="#eab308" />;
      case 'partly_cloudy':
      case 'overcast':
        return <Cloud size={size} color="#64748b" />;
      case 'drizzle':
      case 'showers_light':
        return <CloudDrizzle size={size} color="#0284c7" />;
      case 'rain_light':
      case 'rain_moderate':
      case 'showers_moderate':
        return <CloudRain size={size} color="#2563eb" />;
      case 'rain_heavy':
      case 'showers_violent':
        return <CloudRain size={size} color="#1d4ed8" />;
      case 'thunderstorm':
        return <CloudLightning size={size} color="#7c3aed" />;
      default:
        return <Cloud size={size} color="#64748b" />;
    }
  };

  const tabs: { id: TabType; label: string; icon: React.ReactNode; badge?: string | number }[] = [
    { id: 'overview', label: 'Overview', icon: <MapPin size={13} /> },
    {
      id: 'weather',
      label: 'Weather',
      icon: <Cloud size={13} />,
      badge: current?.temperature_c !== undefined ? `${Math.round(current.temperature_c)}°` : undefined,
    },
    {
      id: 'forecast',
      label: '7-Day',
      icon: <Calendar size={13} />,
      badge: forecast?.daily?.length ? '7d' : undefined,
    },
    {
      id: 'historical',
      label: 'History',
      icon: <History size={13} />,
    },
    {
      id: 'risk',
      label: 'Flood Intel',
      icon: <AlertTriangle size={13} />,
      badge: floodEvidence?.nearby_records_count ? String(floodEvidence.nearby_records_count) : undefined,
    },
  ];

  return (
    <div
      style={{
        position: 'absolute',
        top: '74px',
        right: '16px',
        width: '420px',
        maxHeight: 'calc(100vh - 110px)',
        background: '#ffffff',
        borderRadius: '12px',
        boxShadow: '0 8px 30px rgba(0, 0, 0, 0.16)',
        border: '1px solid #cbd5e1',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 1000,
        overflow: 'hidden',
        animation: 'fadeInSlide 0.2s ease-out',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '10px 14px',
          background: '#0f172a',
          color: '#ffffff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #1e293b',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '26px',
              height: '26px',
              borderRadius: '6px',
              background: '#2563eb',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <MapPin size={15} color="#ffffff" />
          </div>
          <div>
            <div style={{ fontSize: '12.5px', fontWeight: 800, letterSpacing: '0.2px' }}>
              Citizen Location Inspector
            </div>
            <div style={{ fontSize: '10px', color: '#94a3b8', fontFamily: 'monospace' }}>
              {locationData?.coordinates
                ? `${locationData.coordinates.lat.toFixed(5)}° N, ${locationData.coordinates.lon.toFixed(5)}° E`
                : 'Inspecting coordinate...'}
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: '#94a3b8',
            cursor: 'pointer',
            padding: '4px',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          title="Clear location selection"
        >
          <X size={16} />
        </button>
      </div>

      {/* Navigation Tabs */}
      <div
        style={{
          display: 'flex',
          background: '#f8fafc',
          borderBottom: '1px solid #e2e8f0',
          padding: '0 4px',
          overflowX: 'auto',
        }}
      >
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                flex: '1 0 auto',
                padding: '8px 10px',
                fontSize: '11px',
                fontWeight: isActive ? 700 : 500,
                color: isActive ? '#1d4ed8' : '#64748b',
                background: 'transparent',
                border: 'none',
                borderBottom: isActive ? '2px solid #2563eb' : '2px solid transparent',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '5px',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease',
              }}
            >
              {tab.icon}
              <span>{tab.label}</span>
              {tab.badge && (
                <span
                  style={{
                    fontSize: '9px',
                    padding: '1px 5px',
                    borderRadius: '10px',
                    background: isActive ? '#dbeafe' : '#e2e8f0',
                    color: isActive ? '#1e40af' : '#475569',
                    fontWeight: 700,
                  }}
                >
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Card Content Body */}
      <div
        style={{
          padding: '14px',
          overflowY: 'auto',
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          fontSize: '12px',
          color: '#1e293b',
        }}
      >
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: '28px 0', color: '#64748b' }}>
            <div
              style={{
                width: '24px',
                height: '24px',
                border: '3px solid #cbd5e1',
                borderTopColor: '#2563eb',
                borderRadius: '50%',
                margin: '0 auto 10px',
                animation: 'spin 0.8s linear infinite',
              }}
            />
            <div style={{ fontSize: '12px', fontWeight: 600 }}>Resolving location & weather intelligence...</div>
            <div style={{ fontSize: '10.5px', color: '#94a3b8', marginTop: '4px' }}>
              Point-in-polygon spatial matching & Open-Meteo telemetry
            </div>
          </div>
        ) : locationData?.in_coverage ? (
          <>
            {/* ══════════════ TAB 1: OVERVIEW ══════════════ */}
            {activeTab === 'overview' && (
              <>
                {/* Administrative Jurisdiction Status */}
                <div
                  style={{
                    padding: '8px 12px',
                    borderRadius: '8px',
                    background: '#f0fdf4',
                    border: '1px solid #bbf7d0',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <CheckCircle2 size={14} color="#16a34a" />
                    <span style={{ fontSize: '11px', fontWeight: 700, color: '#166534' }}>
                      WITHIN BMC JURISDICTION
                    </span>
                  </div>
                  <span
                    style={{
                      fontSize: '10.5px',
                      color: '#15803d',
                      background: '#dcfce7',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      fontWeight: 600,
                    }}
                  >
                    Zone: {locationData.ward?.zone || 'Mumbai'}
                  </span>
                </div>

                {/* Ward Identification */}
                <div
                  style={{
                    padding: '10px',
                    background: '#f8fafc',
                    borderRadius: '8px',
                    border: '1px solid #e2e8f0',
                  }}
                >
                  <div style={{ fontSize: '12px', fontWeight: 800, color: '#0f172a' }}>
                    {locationData.ward?.ward_name || `Ward ${locationData.ward?.ward_id}`}
                  </div>
                  <div style={{ fontSize: '10.5px', color: '#64748b', marginTop: '2px' }}>
                    Ward ID: <span style={{ fontWeight: 700, color: '#0f172a' }}>{locationData.ward?.ward_id}</span> • Area:{' '}
                    {locationData.ward?.area_sq_km || '—'} km² • Pop.{' '}
                    {locationData.ward?.population_2011 ? locationData.ward.population_2011.toLocaleString() : '—'}
                  </div>
                </div>

                {/* Subarea Partition Details */}
                <div
                  style={{
                    padding: '10px',
                    background: '#eff6ff',
                    borderRadius: '8px',
                    border: '1px solid #bfdbfe',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                    <Layers size={13} color="#2563eb" />
                    <span style={{ fontSize: '10px', fontWeight: 800, color: '#1d4ed8', letterSpacing: '0.4px' }}>
                      DERIVED SUBAREA PARTITION
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: '#1e3a8a' }}>
                    {locationData.subarea?.subarea_name || locationData.subarea?.subarea_id || 'Subarea Unassigned'}
                  </div>
                  <div style={{ fontSize: '10.5px', color: '#3b82f6', marginTop: '2px' }}>
                    Subarea ID: <span style={{ fontWeight: 700 }}>{locationData.subarea?.subarea_id || '—'}</span> • Subarea Area:{' '}
                    {locationData.subarea?.subarea_area_sq_km || '—'} km²
                  </div>
                </div>

                {/* Flood-Aware Evacuation Routing Section */}
                <div
                  style={{
                    padding: '10px 12px',
                    background: activeEvacuationRoute ? '#f0fdf4' : '#f8fafc',
                    borderRadius: '8px',
                    border: `1px solid ${activeEvacuationRoute ? '#86efac' : '#cbd5e1'}`,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Navigation size={13} color={activeEvacuationRoute ? '#16a34a' : '#2563eb'} />
                      <span style={{ fontSize: '10px', fontWeight: 800, color: activeEvacuationRoute ? '#15803d' : '#1d4ed8', letterSpacing: '0.4px', textTransform: 'uppercase' }}>
                        {activeEvacuationRoute ? 'Active Evacuation Corridor' : 'Flood-Aware Evacuation'}
                      </span>
                    </div>
                    {activeEvacuationRoute && onClearEvacuationRoute && (
                      <button
                        onClick={onClearEvacuationRoute}
                        style={{
                          background: 'none', border: 'none', color: '#64748b', fontSize: '10px',
                          cursor: 'pointer', padding: '0 2px', textDecoration: 'underline',
                        }}
                      >
                        Clear Route
                      </button>
                    )}
                  </div>

                  {activeEvacuationRoute ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {/* Stale Route Warning Banner (Batch 5.3) */}
                      {activeEvacuationRoute.is_stale && (
                        <div style={{
                          padding: '6px 8px', borderRadius: '4px', background: '#fef2f2', border: '1px solid #fecaca',
                          color: '#dc2626', fontSize: '9px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px',
                        }}>
                          <AlertTriangle size={12} />
                          ROUTE STALE: New flood nowcast available. Recalculation advised.
                        </div>
                      )}

                      <div style={{ fontSize: '11.5px', fontWeight: 800, color: '#0f172a' }}>
                        🏁 {activeEvacuationRoute.destination_name}
                      </div>

                      {/* Destination Eligibility (Batch 5.1) */}
                      {activeEvacuationRoute.route_explanation?.destination_eligibility_reason && (
                        <div style={{ fontSize: '9px', color: '#15803d', fontStyle: 'italic', background: '#ffffff', padding: '3px 6px', borderRadius: '4px', border: '1px solid #dcfce7' }}>
                          ✓ {activeEvacuationRoute.route_explanation.destination_eligibility_reason}
                        </div>
                      )}

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '4px', fontSize: '9.5px' }}>
                        <div style={{ background: '#ffffff', padding: '4px 6px', borderRadius: '4px', border: '1px solid #bbf7d0' }}>
                          <span style={{ color: '#64748b', display: 'block' }}>Distance</span>
                          <strong style={{ color: '#0f172a' }}>{activeEvacuationRoute.total_distance_km} km</strong>
                        </div>
                        <div style={{ background: '#ffffff', padding: '4px 6px', borderRadius: '4px', border: '1px solid #bbf7d0' }}>
                          <span style={{ color: '#64748b', display: 'block' }}>Est. Time</span>
                          <strong style={{ color: '#0f172a' }}>{activeEvacuationRoute.estimated_travel_time_min} min</strong>
                        </div>
                        <div style={{ background: '#ffffff', padding: '4px 6px', borderRadius: '4px', border: '1px solid #bbf7d0' }}>
                          <span style={{ color: '#64748b', display: 'block' }}>Max Depth</span>
                          <strong style={{ color: activeEvacuationRoute.max_flood_depth_along_route_m >= 0.15 ? '#b45309' : '#15803d' }}>
                            {activeEvacuationRoute.max_flood_depth_along_route_m.toFixed(2)} m
                          </strong>
                        </div>
                      </div>

                      {/* Segment Exposure Breakdown */}
                      {activeEvacuationRoute.route_explanation?.road_exposure_breakdown && (
                        <div style={{ background: '#ffffff', padding: '6px', borderRadius: '4px', border: '1px solid #e2e8f0', fontSize: '9px' }}>
                          <span style={{ color: '#475569', fontWeight: 700, display: 'block', marginBottom: '3px' }}>
                            Corridor Exposure ({activeEvacuationRoute.route_explanation.road_exposure_breakdown.total_segments} OSM segments):
                          </span>
                          <div style={{ display: 'flex', gap: '4px', height: '6px', borderRadius: '2px', overflow: 'hidden', marginBottom: '4px' }}>
                            <div style={{ width: `${activeEvacuationRoute.route_explanation.road_exposure_breakdown.clear_segments_pct}%`, background: '#22c55e' }} title="Clear (<0.15m)" />
                            <div style={{ width: `${activeEvacuationRoute.route_explanation.road_exposure_breakdown.caution_segments_pct}%`, background: '#f59e0b' }} title="Caution (0.15–0.30m)" />
                            <div style={{ width: `${activeEvacuationRoute.route_explanation.road_exposure_breakdown.hazardous_segments_pct}%`, background: '#ef4444' }} title="Hazardous (>0.30m)" />
                          </div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748b', fontSize: '8.5px' }}>
                            <span style={{ color: '#16a34a' }}>● Clear: {activeEvacuationRoute.route_explanation.road_exposure_breakdown.clear_segments_pct}%</span>
                            <span style={{ color: '#d97706' }}>● Caution: {activeEvacuationRoute.route_explanation.road_exposure_breakdown.caution_segments_pct}%</span>
                            <span style={{ color: '#dc2626' }}>● Hazardous: {activeEvacuationRoute.route_explanation.road_exposure_breakdown.hazardous_segments_pct}%</span>
                          </div>
                        </div>
                      )}

                      <div style={{
                        padding: '4px 8px', borderRadius: '4px', fontSize: '9px', fontWeight: 700,
                        background: activeEvacuationRoute.passability_verdict?.includes('CLEAR') ? '#dcfce7' : '#fef3c7',
                        color: activeEvacuationRoute.passability_verdict?.includes('CLEAR') ? '#166534' : '#92400e',
                      }}>
                        {activeEvacuationRoute.passability_verdict}
                      </div>

                      {/* Alternative Corridor Comparison Card (Batch 5.2) */}
                      {activeEvacuationRoute.alternative_route && (
                        <div style={{ background: '#f8fafc', padding: '6px 8px', borderRadius: '4px', border: '1px solid #cbd5e1', fontSize: '9px' }}>
                          <span style={{ fontWeight: 800, color: '#334155', display: 'block', marginBottom: '2px' }}>
                            ⚖️ Candidate Alternative Evaluated:
                          </span>
                          <div style={{ color: '#0f172a', fontWeight: 700 }}>
                            {activeEvacuationRoute.alternative_route.destination_name}
                          </div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748b', marginTop: '2px' }}>
                            <span>Dist: {activeEvacuationRoute.alternative_route.total_distance_km} km</span>
                            <span>Time: {activeEvacuationRoute.alternative_route.estimated_travel_time_min} min</span>
                            <span>Max: {activeEvacuationRoute.alternative_route.max_flood_depth_m.toFixed(2)} m</span>
                          </div>
                          <div style={{ marginTop: '3px', color: '#1d4ed8', fontWeight: 600, fontSize: '8.5px' }}>
                            {activeEvacuationRoute.alternative_route.tradeoff_summary}
                          </div>
                        </div>
                      )}

                      {/* Spatial Resolution Limitation Caveat (Batch 5.4) */}
                      <div style={{ fontSize: '8px', color: '#64748b', lineHeight: '1.3' }}>
                        ℹ️ <strong>Resolution Note:</strong> Hydrodynamic depth is sampled from 30m Copernicus DEM cells. Local curbs (15cm) and culvert blockages are not fully resolved.
                      </div>

                      {activeEvacuationRoute.route_explanation?.simulation_run_id_used && (
                        <div style={{ fontSize: '7.5px', color: '#94a3b8' }}>
                          Run ID: {activeEvacuationRoute.route_explanation.simulation_run_id_used} · Solver: 2D Diffusive Wave
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        {(['standard_car', 'emergency_high_clearance', 'pedestrian'] as const).map(v => (
                          <button
                            key={v}
                            onClick={() => setEvacVehicleType(v)}
                            style={{
                              flex: 1, padding: '4px 2px', borderRadius: '4px', fontSize: '9.5px', fontWeight: evacVehicleType === v ? 800 : 600,
                              background: evacVehicleType === v ? '#2563eb' : '#ffffff',
                              color: evacVehicleType === v ? '#ffffff' : '#475569',
                              border: `1px solid ${evacVehicleType === v ? '#2563eb' : '#cbd5e1'}`,
                              cursor: 'pointer', transition: 'all 0.15s ease',
                            }}
                          >
                            {v === 'standard_car' ? '🚗 Car' : v === 'emergency_high_clearance' ? '🚙 High Clr' : '🚶 Pedestrian'}
                          </button>
                        ))}
                      </div>
                      {onComputeEvacuationRoute && (
                        <button
                          onClick={() => onComputeEvacuationRoute(evacVehicleType)}
                          disabled={isComputingRoute}
                          style={{
                            width: '100%', padding: '6px', borderRadius: '6px', border: 'none',
                            background: isComputingRoute ? '#94a3b8' : '#059669', color: '#ffffff',
                            fontWeight: 700, fontSize: '11px', cursor: isComputingRoute ? 'wait' : 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                          }}
                        >
                          <Navigation size={12} />
                          {isComputingRoute ? 'Finding Safest Evacuation Corridor...' : 'Find Safest Evacuation Route'}
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {/* Quick Weather Snapshot inside Overview */}
                {current && (
                  <div
                    style={{
                      padding: '10px',
                      background: '#faf5ff',
                      borderRadius: '8px',
                      border: '1px solid #e9d5ff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {getWeatherIcon(current.condition_key, 22)}
                      <div>
                        <div style={{ fontSize: '12px', fontWeight: 700, color: '#581c87' }}>
                          {current.temperature_c}°C • {current.weather_description}
                        </div>
                        <div style={{ fontSize: '10px', color: '#7e22ce' }}>
                          Rain: {current.effective_rainfall_rate_mmh || 0} mm/h • Humidity: {current.relative_humidity_percent || 0}%
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => setActiveTab('weather')}
                      style={{
                        padding: '4px 8px',
                        background: '#9333ea',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '4px',
                        fontSize: '10px',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      Weather Details &rarr;
                    </button>
                  </div>
                )}

                {/* Nearby Emergency Facilities */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <div style={{ fontSize: '11px', fontWeight: 800, color: '#475569', letterSpacing: '0.4px' }}>
                      EMERGENCY FACILITIES IN VICINITY ({locationData.nearby_facilities?.length || 0})
                    </div>
                    {onToggleFacilities && (
                      <button
                        onClick={onToggleFacilities}
                        style={{
                          fontSize: '10.5px',
                          color: '#2563eb',
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontWeight: 600,
                        }}
                      >
                        {showFacilitiesOnMap ? <EyeOff size={12} /> : <Eye size={12} />}
                        {showFacilitiesOnMap ? 'Hide on Map' : 'Show on Map'}
                      </button>
                    )}
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '160px', overflowY: 'auto' }}>
                    {locationData.nearby_facilities && locationData.nearby_facilities.length > 0 ? (
                      locationData.nearby_facilities.map((fac, idx) => {
                        const style = getCategoryBadgeStyle(fac.category);
                        return (
                          <div
                            key={fac.facility_id || idx}
                            style={{
                              padding: '8px 10px',
                              background: '#ffffff',
                              border: '1px solid #e2e8f0',
                              borderRadius: '6px',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                              <div style={{ flexShrink: 0 }}>{getCategoryIcon(fac.category)}</div>
                              <div style={{ minWidth: 0, overflow: 'hidden' }}>
                                <div
                                  style={{
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    color: '#0f172a',
                                    whiteSpace: 'nowrap',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                  }}
                                  title={fac.name}
                                >
                                  {fac.name || 'Unnamed Emergency Facility'}
                                </div>
                                <div style={{ fontSize: '9.5px', color: '#64748b' }}>
                                  {fac.address || 'Mumbai City'}
                                </div>
                              </div>
                            </div>
                            <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: '8px' }}>
                              <span
                                style={{
                                  fontSize: '9px',
                                  fontWeight: 800,
                                  textTransform: 'uppercase',
                                  padding: '2px 5px',
                                  borderRadius: '3px',
                                  background: style.bg,
                                  color: style.text,
                                  border: `1px solid ${style.border}`,
                                }}
                              >
                                {fac.category}
                              </span>
                              <div style={{ fontSize: '10px', fontWeight: 700, color: '#2563eb', marginTop: '2px' }}>
                                {fac.distance_km !== undefined ? `${fac.distance_km} km` : '—'}
                              </div>
                            </div>
                          </div>
                        );
                      })
                    ) : (
                      <div style={{ fontSize: '11px', color: '#94a3b8', fontStyle: 'italic', padding: '6px' }}>
                        No emergency infrastructure registered within 3 km of this coordinate.
                      </div>
                    )}
                  </div>
                </div>

                {/* Extension Points / Future Capabilities */}
                <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: '8px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: '#94a3b8', letterSpacing: '0.4px', marginBottom: '6px' }}>
                    FUTURE PHASE CAPABILITIES
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                    <div style={{ padding: '6px 8px', background: '#f8fafc', border: '1px dashed #cbd5e1', borderRadius: '6px', fontSize: '10px', color: '#64748b' }}>
                      <div style={{ fontWeight: 700, color: '#475569' }}>2D Inundation Depth</div>
                      <span style={{ fontSize: '9px', color: '#94a3b8' }}>Phase 3 Hydrodynamics</span>
                    </div>
                    <div style={{ padding: '6px 8px', background: '#f8fafc', border: '1px dashed #cbd5e1', borderRadius: '6px', fontSize: '10px', color: '#64748b' }}>
                      <div style={{ fontWeight: 700, color: '#475569' }}>Evacuation Routing</div>
                      <span style={{ fontSize: '9px', color: '#94a3b8' }}>Phase 3 Navigation</span>
                    </div>
                  </div>
                </div>
              </>
            )}

            {/* ══════════════ TAB 2: CURRENT WEATHER ══════════════ */}
            {activeTab === 'weather' && (
              <>
                {current ? (
                  <>
                    {/* Hero Current Weather Banner */}
                    <div
                      style={{
                        padding: '14px',
                        background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
                        color: '#ffffff',
                        borderRadius: '10px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.5px' }}>
                          {current.temperature_c !== undefined ? `${current.temperature_c}°C` : '—'}
                        </div>
                        <div style={{ fontSize: '12px', fontWeight: 600, color: '#93c5fd', marginTop: '2px' }}>
                          {current.weather_description || 'Clear Sky'}
                        </div>
                        <div style={{ fontSize: '10px', color: '#94a3b8', marginTop: '4px' }}>
                          Feels like {current.apparent_temperature_c ?? '—'}°C • Elev: {current.elevation_m ?? '—'}m
                        </div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        {getWeatherIcon(current.condition_key, 36)}
                        <div style={{ fontSize: '9.5px', color: '#cbd5e1', marginTop: '4px' }}>
                          WMO Code {current.weather_code}
                        </div>
                      </div>
                    </div>

                    {/* Meteorological Observation Grid */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
                      <div style={{ padding: '8px 10px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#0284c7', fontSize: '10.5px', fontWeight: 700 }}>
                          <Droplets size={13} />
                          <span>Precipitation Rate</span>
                        </div>
                        <div style={{ fontSize: '15px', fontWeight: 800, color: '#0f172a', marginTop: '4px' }}>
                          {current.effective_rainfall_rate_mmh ?? 0} <span style={{ fontSize: '10px', fontWeight: 500 }}>mm/h</span>
                        </div>
                        <div style={{ fontSize: '9px', color: '#64748b', marginTop: '2px' }}>
                          Stratiform: {current.stratiform_rain_mm ?? 0} mm • Showers: {current.convective_showers_mm ?? 0} mm
                        </div>
                      </div>

                      <div style={{ padding: '8px 10px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#2563eb', fontSize: '10.5px', fontWeight: 700 }}>
                          <Gauge size={13} />
                          <span>Relative Humidity</span>
                        </div>
                        <div style={{ fontSize: '15px', fontWeight: 800, color: '#0f172a', marginTop: '4px' }}>
                          {current.relative_humidity_percent ?? '—'} <span style={{ fontSize: '10px', fontWeight: 500 }}>%</span>
                        </div>
                        <div style={{ fontSize: '9px', color: '#64748b', marginTop: '2px' }}>
                          Surface Pressure: {current.surface_pressure_hpa ?? '—'} hPa
                        </div>
                      </div>

                      <div style={{ padding: '8px 10px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#0d9488', fontSize: '10.5px', fontWeight: 700 }}>
                          <Wind size={13} />
                          <span>Wind Speed</span>
                        </div>
                        <div style={{ fontSize: '15px', fontWeight: 800, color: '#0f172a', marginTop: '4px' }}>
                          {current.wind_speed_kmh ?? '—'} <span style={{ fontSize: '10px', fontWeight: 500 }}>km/h</span>
                        </div>
                        <div style={{ fontSize: '9px', color: '#64748b', marginTop: '2px' }}>
                          Direction: {current.wind_direction_deg ?? '—'}°
                        </div>
                      </div>

                      <div style={{ padding: '8px 10px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#d97706', fontSize: '10.5px', fontWeight: 700 }}>
                          <Wind size={13} />
                          <span>Peak Gusts</span>
                        </div>
                        <div style={{ fontSize: '15px', fontWeight: 800, color: '#0f172a', marginTop: '4px' }}>
                          {current.wind_gusts_kmh ?? '—'} <span style={{ fontSize: '10px', fontWeight: 500 }}>km/h</span>
                        </div>
                        <div style={{ fontSize: '9px', color: '#64748b', marginTop: '2px' }}>
                          Monsoon gust threshold: 45 km/h
                        </div>
                      </div>
                    </div>

                    {/* Scientific Note on Precipitation vs Rainfall */}
                    <div style={{ padding: '8px 10px', background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: '6px', fontSize: '10.5px', color: '#0369a1' }}>
                      <div style={{ fontWeight: 700, marginBottom: '2px' }}>Precipitation Physics Breakdown:</div>
                      <div>Total Liquid Precipitation: <b>{current.precipitation_mm ?? 0} mm</b></div>
                      <div>Large-Scale Stratiform Rain: <b>{current.stratiform_rain_mm ?? 0} mm</b> • Convective Showers: <b>{current.convective_showers_mm ?? 0} mm</b></div>
                    </div>

                    {/* Provenance Footnote */}
                    <div style={{ fontSize: '9.5px', color: '#94a3b8', borderTop: '1px solid #f1f5f9', paddingTop: '6px' }}>
                      Source: {current.source} • Observation Time: {current.observation_time || 'Recent'} ({current.timezone})
                    </div>
                  </>
                ) : (
                  <div style={{ textAlign: 'center', padding: '20px', color: '#94a3b8' }}>
                    Live weather telemetry is currently synchronizing with Open-Meteo.
                  </div>
                )}
              </>
            )}

            {/* ══════════════ TAB 3: 7-DAY FORECAST ══════════════ */}
            {activeTab === 'forecast' && (
              <>
                {/* Forecast Peak Summary */}
                {forecast?.peak_summary && (
                  <div style={{ padding: '10px', background: '#eff6ff', borderRadius: '8px', border: '1px solid #bfdbfe' }}>
                    <div style={{ fontSize: '11px', fontWeight: 800, color: '#1d4ed8', marginBottom: '4px' }}>
                      7-DAY NWP RAINFALL ACCUMULATION PROJECTION
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px', textAlign: 'center' }}>
                      <div style={{ background: '#ffffff', padding: '6px', borderRadius: '4px', border: '1px solid #dbeafe' }}>
                        <div style={{ fontSize: '9.5px', color: '#64748b' }}>24h Total</div>
                        <div style={{ fontSize: '14px', fontWeight: 800, color: '#0f172a' }}>
                          {forecast.peak_summary.forecast_24h_accumulation_mm ?? 0} <span style={{ fontSize: '9px' }}>mm</span>
                        </div>
                      </div>
                      <div style={{ background: '#ffffff', padding: '6px', borderRadius: '4px', border: '1px solid #dbeafe' }}>
                        <div style={{ fontSize: '9.5px', color: '#64748b' }}>Peak Rate</div>
                        <div style={{ fontSize: '14px', fontWeight: 800, color: '#2563eb' }}>
                          {forecast.peak_summary.peak_hourly_rate_mmh ?? 0} <span style={{ fontSize: '9px' }}>mm/h</span>
                        </div>
                      </div>
                      <div style={{ background: '#ffffff', padding: '6px', borderRadius: '4px', border: '1px solid #dbeafe' }}>
                        <div style={{ fontSize: '9.5px', color: '#64748b' }}>7-Day Total</div>
                        <div style={{ fontSize: '14px', fontWeight: 800, color: '#0f172a' }}>
                          {forecast.peak_summary.forecast_7day_accumulation_mm ?? 0} <span style={{ fontSize: '9px' }}>mm</span>
                        </div>
                      </div>
                    </div>
                    {forecast.peak_summary.peak_hour_timestamp && (
                      <div style={{ fontSize: '9.5px', color: '#3b82f6', marginTop: '6px', textAlign: 'center' }}>
                        Peak Intensity Expected Around: <b>{forecast.peak_summary.peak_hour_timestamp.replace('T', ' ')} IST</b>
                      </div>
                    )}
                  </div>
                )}

                {/* Daily Cards */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ fontSize: '11px', fontWeight: 800, color: '#475569', letterSpacing: '0.4px' }}>
                    DAILY PROJECTIONS (7-DAY NWP HORIZON)
                  </div>
                  {forecast?.daily?.map((day, idx) => {
                    const isHighRain = (day.precipitation_sum_mm || 0) > 65;
                    const isModRain = (day.precipitation_sum_mm || 0) > 20;
                    return (
                      <div
                        key={day.date || idx}
                        style={{
                          padding: '8px 10px',
                          background: idx === 0 ? '#f0fdf4' : '#ffffff',
                          border: `1px solid ${idx === 0 ? '#bbf7d0' : '#e2e8f0'}`,
                          borderRadius: '6px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <div style={{ textAlign: 'center', minWidth: '36px' }}>
                            <div style={{ fontSize: '11.5px', fontWeight: 800, color: '#0f172a' }}>
                              {idx === 0 ? 'Today' : day.day_name}
                            </div>
                            <div style={{ fontSize: '9px', color: '#64748b' }}>{day.date.slice(5)}</div>
                          </div>
                          <div>{getWeatherIcon(day.condition_key, 18)}</div>
                          <div>
                            <div style={{ fontSize: '11px', fontWeight: 700, color: '#1e293b' }}>
                              {day.weather_description}
                            </div>
                            <div style={{ fontSize: '9.5px', color: '#64748b' }}>
                              {day.temp_min_c !== undefined ? `${Math.round(day.temp_min_c)}°` : '—'} /{' '}
                              {day.temp_max_c !== undefined ? `${Math.round(day.temp_max_c)}°C` : '—'} • Prob:{' '}
                              {day.precipitation_probability_max ?? 0}%
                            </div>
                          </div>
                        </div>

                        <div style={{ textAlign: 'right' }}>
                          <span
                            style={{
                              fontSize: '11px',
                              fontWeight: 800,
                              color: isHighRain ? '#dc2626' : isModRain ? '#d97706' : '#2563eb',
                            }}
                          >
                            {day.precipitation_sum_mm ?? 0} mm
                          </span>
                          <div style={{ fontSize: '9px', color: '#64748b' }}>
                            {day.precipitation_hours ?? 0}h rain
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Hourly Forecast Scroll Strip (Next 24 Hours) */}
                {forecast?.hourly && forecast.hourly.length > 0 && (
                  <div>
                    <div style={{ fontSize: '11px', fontWeight: 800, color: '#475569', letterSpacing: '0.4px', marginBottom: '6px' }}>
                      NEXT 24 HOURS HOURLY BREAKDOWN
                    </div>
                    <div
                      style={{
                        display: 'flex',
                        gap: '6px',
                        overflowX: 'auto',
                        paddingBottom: '6px',
                      }}
                    >
                      {forecast.hourly.slice(0, 24).map((h, i) => (
                        <div
                          key={i}
                          style={{
                            minWidth: '55px',
                            background: '#f8fafc',
                            border: '1px solid #e2e8f0',
                            borderRadius: '6px',
                            padding: '6px 4px',
                            textAlign: 'center',
                            flexShrink: 0,
                          }}
                        >
                          <div style={{ fontSize: '9.5px', color: '#64748b', fontWeight: 600 }}>
                            {h.time.slice(11, 16)}
                          </div>
                          <div style={{ margin: '4px 0' }}>{getWeatherIcon(h.condition_key, 14)}</div>
                          <div style={{ fontSize: '10px', fontWeight: 800, color: (h.precipitation_rate_mmh || 0) > 5 ? '#dc2626' : '#0f172a' }}>
                            {h.precipitation_rate_mmh ?? 0} <span style={{ fontSize: '8px' }}>mm</span>
                          </div>
                          <div style={{ fontSize: '8.5px', color: '#2563eb' }}>
                            {h.precipitation_probability_percent ?? 0}%
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* ══════════════ TAB 4: HISTORICAL COMPARISON ══════════════ */}
            {activeTab === 'historical' && (
              <>
                {histComp ? (
                  <>
                    {/* Percentile Ranking Banner */}
                    <div style={{ padding: '10px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', fontWeight: 800, color: '#0f172a', marginBottom: '4px' }}>
                        MONSOON HISTORICAL PERCENTILE BENCHMARK
                      </div>
                      <div style={{ fontSize: '10.5px', color: '#475569' }}>
                        Current Rain Intensity Rank:{' '}
                        <b style={{ color: '#2563eb' }}>{histComp.comparison?.current_hourly_percentile_rank}</b>
                      </div>
                      <div style={{ fontSize: '10.5px', color: '#475569', marginTop: '2px' }}>
                        24h Forecast Total Rank:{' '}
                        <b style={{ color: '#0f172a' }}>{histComp.comparison?.forecast_24h_percentile_rank}</b>
                      </div>
                    </div>

                    {/* Historical Distribution Table */}
                    <div>
                      <div style={{ fontSize: '11px', fontWeight: 800, color: '#475569', letterSpacing: '0.4px', marginBottom: '6px' }}>
                        ERA5-LAND MONSOON RAINFALL DISTRIBUTION
                      </div>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10.5px' }}>
                        <thead>
                          <tr style={{ background: '#f1f5f9', color: '#475569', textAlign: 'left' }}>
                            <th style={{ padding: '4px 8px', borderRadius: '4px 0 0 4px' }}>Percentile</th>
                            <th style={{ padding: '4px 8px' }}>Hourly Rate</th>
                            <th style={{ padding: '4px 8px', borderRadius: '0 4px 4px 0' }}>24h Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                            <td style={{ padding: '5px 8px', color: '#64748b' }}>50th (Median)</td>
                            <td style={{ padding: '5px 8px', fontWeight: 600 }}>{histComp.hourly_percentiles?.p50 ?? 0} mm/h</td>
                            <td style={{ padding: '5px 8px', fontWeight: 600 }}>{histComp.daily_24h_percentiles?.p50 ?? 0} mm</td>
                          </tr>
                          <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                            <td style={{ padding: '5px 8px', color: '#64748b' }}>75th (Moderate)</td>
                            <td style={{ padding: '5px 8px', fontWeight: 600 }}>{histComp.hourly_percentiles?.p75 ?? 0} mm/h</td>
                            <td style={{ padding: '5px 8px', fontWeight: 600 }}>{histComp.daily_24h_percentiles?.p75 ?? 0} mm</td>
                          </tr>
                          <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                            <td style={{ padding: '5px 8px', color: '#64748b' }}>90th (Heavy)</td>
                            <td style={{ padding: '5px 8px', fontWeight: 600, color: '#d97706' }}>{histComp.hourly_percentiles?.p90 ?? 0} mm/h</td>
                            <td style={{ padding: '5px 8px', fontWeight: 600, color: '#d97706' }}>{histComp.daily_24h_percentiles?.p90 ?? 0} mm</td>
                          </tr>
                          <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                            <td style={{ padding: '5px 8px', color: '#64748b' }}>95th (Very Heavy)</td>
                            <td style={{ padding: '5px 8px', fontWeight: 700, color: '#ea580c' }}>{histComp.hourly_percentiles?.p95 ?? 0} mm/h</td>
                            <td style={{ padding: '5px 8px', fontWeight: 700, color: '#ea580c' }}>{histComp.daily_24h_percentiles?.p95 ?? 0} mm</td>
                          </tr>
                          <tr style={{ borderBottom: '1px solid #f1f5f9' }}>
                            <td style={{ padding: '5px 8px', color: '#64748b' }}>99th (Extreme)</td>
                            <td style={{ padding: '5px 8px', fontWeight: 800, color: '#dc2626' }}>{histComp.hourly_percentiles?.p99 ?? 0} mm/h</td>
                            <td style={{ padding: '5px 8px', fontWeight: 800, color: '#dc2626' }}>{histComp.daily_24h_percentiles?.p99 ?? 0} mm</td>
                          </tr>
                          <tr style={{ background: '#fef2f2' }}>
                            <td style={{ padding: '5px 8px', fontWeight: 800, color: '#991b1b' }}>Record Max</td>
                            <td style={{ padding: '5px 8px', fontWeight: 800, color: '#991b1b' }}>{histComp.hourly_percentiles?.record_max ?? 0} mm/h</td>
                            <td style={{ padding: '5px 8px', fontWeight: 800, color: '#991b1b' }}>{histComp.daily_24h_percentiles?.record_max ?? 0} mm</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    {/* Historical Rolling Extremes */}
                    <div>
                      <div style={{ fontSize: '11px', fontWeight: 800, color: '#475569', letterSpacing: '0.4px', marginBottom: '6px' }}>
                        HISTORICAL ROLLING ACCUMULATION EXTREMES
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '4px', textAlign: 'center' }}>
                        <div style={{ background: '#f8fafc', padding: '6px 4px', border: '1px solid #e2e8f0', borderRadius: '4px' }}>
                          <div style={{ fontSize: '9px', color: '#64748b' }}>Max 3h</div>
                          <div style={{ fontSize: '11.5px', fontWeight: 800, color: '#0f172a' }}>{histComp.rolling_max_mm?.max_3h_mm} mm</div>
                        </div>
                        <div style={{ background: '#f8fafc', padding: '6px 4px', border: '1px solid #e2e8f0', borderRadius: '4px' }}>
                          <div style={{ fontSize: '9px', color: '#64748b' }}>Max 6h</div>
                          <div style={{ fontSize: '11.5px', fontWeight: 800, color: '#0f172a' }}>{histComp.rolling_max_mm?.max_6h_mm} mm</div>
                        </div>
                        <div style={{ background: '#f8fafc', padding: '6px 4px', border: '1px solid #e2e8f0', borderRadius: '4px' }}>
                          <div style={{ fontSize: '9px', color: '#64748b' }}>Max 12h</div>
                          <div style={{ fontSize: '11.5px', fontWeight: 800, color: '#0f172a' }}>{histComp.rolling_max_mm?.max_12h_mm} mm</div>
                        </div>
                        <div style={{ background: '#f8fafc', padding: '6px 4px', border: '1px solid #e2e8f0', borderRadius: '4px' }}>
                          <div style={{ fontSize: '9px', color: '#64748b' }}>Max 24h</div>
                          <div style={{ fontSize: '11.5px', fontWeight: 800, color: '#0f172a' }}>{histComp.rolling_max_mm?.max_24h_mm} mm</div>
                        </div>
                      </div>
                    </div>

                    {/* Antecedent Wetness */}
                    <div style={{ padding: '8px 10px', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '6px', fontSize: '10.5px' }}>
                      <div style={{ fontWeight: 700, color: '#166534', marginBottom: '2px' }}>Antecedent Rainfall Wetness Index:</div>
                      <div style={{ color: '#15803d' }}>
                        72h Preceding Monsoon Accumulation: <b>{histComp.antecedent_rainfall_sample_72h_mm ?? 0} mm</b>
                      </div>
                    </div>

                    {/* Provenance */}
                    <div style={{ fontSize: '9px', color: '#94a3b8' }}>
                      Source: {histComp.source} ({histComp.sample_window}) • Sample: {histComp.sample_hours_count} hourly records
                    </div>
                  </>
                ) : (
                  <div style={{ textAlign: 'center', padding: '20px', color: '#94a3b8' }}>
                    Historical comparison baseline loading...
                  </div>
                )}
              </>
            )}

            {/* ══════════════ TAB 5: FLOOD EVIDENCE & RISK ══════════════ */}
            {activeTab === 'risk' && (
              <>
                {/* Transparent Hazard Level Banner */}
                {hazard && (
                  <div
                    style={{
                      padding: '12px',
                      background: hazard.hazard_level === 'NORMAL_CONDITIONS' ? '#f0fdf4' : '#fef2f2',
                      border: `1px solid ${hazard.hazard_color || '#cbd5e1'}`,
                      borderRadius: '8px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span
                        style={{
                          fontSize: '10px',
                          fontWeight: 800,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          background: hazard.hazard_color || '#2563eb',
                          color: '#ffffff',
                          letterSpacing: '0.4px',
                        }}
                      >
                        {hazard.hazard_level?.replace('_', ' ')}
                      </span>
                      <span style={{ fontSize: '9.5px', fontWeight: 700, color: '#475569' }}>
                        Confidence: {hazard.evidence_confidence}
                      </span>
                    </div>
                    <div style={{ fontSize: '12.5px', fontWeight: 800, color: '#0f172a', marginTop: '4px' }}>
                      {hazard.headline}
                    </div>
                    <div style={{ fontSize: '11px', color: '#334155', marginTop: '4px', lineHeight: '1.4' }}>
                      {hazard.recommendation}
                    </div>
                  </div>
                )}

                {/* Weather Analogue Storm Match */}
                {hazard?.weather_analogue_narrative && (
                  <div style={{ padding: '10px', background: '#eff6ff', borderRadius: '8px', border: '1px solid #bfdbfe' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '4px' }}>
                      <History size={13} color="#2563eb" />
                      <span style={{ fontSize: '11px', fontWeight: 800, color: '#1d4ed8' }}>
                        HISTORICAL WEATHER ANALOGUE MATCH
                      </span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#1e3a8a', lineHeight: '1.4' }}>
                      {hazard.weather_analogue_narrative}
                    </div>
                  </div>
                )}

                {/* Verified Historical Flood Incidents (2016-2025) */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <div style={{ fontSize: '11px', fontWeight: 800, color: '#475569', letterSpacing: '0.4px' }}>
                      VERIFIED FLOOD INCIDENTS IN VICINITY ({floodEvidence?.nearby_records_count || 0})
                    </div>
                    <span style={{ fontSize: '9.5px', color: '#94a3b8' }}>Radius: 5.0 km</span>
                  </div>

                  {floodEvidence?.nearby_records && floodEvidence.nearby_records.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '180px', overflowY: 'auto' }}>
                      {floodEvidence.nearby_records.map((ev, idx) => (
                        <div
                          key={`${ev.event_id || 'evt'}-${idx}`}
                          style={{
                            padding: '8px',
                            background: '#ffffff',
                            border: '1px solid #e2e8f0',
                            borderRadius: '6px',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '3px',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: '11px', fontWeight: 800, color: '#0f172a' }}>
                              {ev.locality || 'Mumbai Hotspot'}
                            </span>
                            <span style={{ fontSize: '10px', fontWeight: 700, color: '#dc2626' }}>
                              {ev.flood_depth_cm !== undefined ? `${ev.flood_depth_cm} cm depth` : 'Inundated'}
                            </span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '9.5px', color: '#64748b' }}>
                            <span>
                              Date: <b>{ev.date}</b> ({ev.ward}) • Dist: <b>{ev.distance_km} km</b>
                            </span>
                            <span
                              style={{
                                padding: '1px 4px',
                                borderRadius: '3px',
                                background: ev.flood_severity === 'Severe' ? '#fee2e2' : '#fef3c7',
                                color: ev.flood_severity === 'Severe' ? '#991b1b' : '#92400e',
                                fontWeight: 700,
                              }}
                            >
                              {ev.flood_severity || 'Moderate'}
                            </span>
                          </div>
                          <div style={{ fontSize: '9px', color: '#64748b' }}>
                            Rainfall 24h: <b>{ev.rainfall_24h_mm || '—'} mm</b> • Duration: <b>{ev.flood_duration_hours || '—'}h</b>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ padding: '10px', background: '#f8fafc', borderRadius: '6px', border: '1px dashed #cbd5e1', fontSize: '11px', color: '#64748b', textAlign: 'center' }}>
                      {floodEvidence?.status_statement || 'No historical flood incident records documented within 5.0 km in the 2016-2025 municipal inventory.'}
                    </div>
                  )}
                </div>

                {/* Mandatory Scientific Disclaimer */}
                <div
                  style={{
                    padding: '8px 10px',
                    background: '#fffbeb',
                    border: '1px solid #fef3c7',
                    borderRadius: '6px',
                    fontSize: '9.5px',
                    color: '#92400e',
                    lineHeight: '1.4',
                  }}
                >
                  <div style={{ fontWeight: 700, marginBottom: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Info size={11} color="#b45309" />
                    <span>Scientific Disclaimer on Flood Risk Interpretation:</span>
                  </div>
                  <div>
                    {hazard?.scientific_disclaimer ||
                      'Weather similarity is an analogue hazard indicator based on atmospheric rainfall magnitude and historical storm similarity. It is NOT a calibrated deterministic flood probability. Actual flooding at this coordinate is governed by micro-topography, storm sewer capacity, tidal backwater gates, and municipal pump station operation.'}
                  </div>
                </div>

                {/* Data Provenance */}
                <div style={{ fontSize: '9px', color: '#94a3b8' }}>
                  Source: {floodEvidence?.source} • 202 Official Municipal Records
                </div>
              </>
            )}
          </>
        ) : (
          /* Outside Coverage State */
          <div
            style={{
              background: '#fff1f2',
              border: '1px solid #fecdd3',
              borderRadius: '8px',
              padding: '14px',
              textAlign: 'center',
            }}
          >
            <AlertCircle size={28} color="#e11d48" style={{ margin: '0 auto 8px' }} />
            <div style={{ fontSize: '13px', fontWeight: 800, color: '#9f1239', marginBottom: '4px' }}>
              Outside Municipal Coverage
            </div>
            <div style={{ fontSize: '11px', color: '#881337', lineHeight: '1.4' }}>
              {locationData?.message ||
                'The clicked point lies outside the surveyed Brihanmumbai Municipal Corporation (BMC) administrative boundaries.'}
            </div>
            <div
              style={{
                marginTop: '10px',
                padding: '6px 10px',
                background: '#ffffff',
                borderRadius: '6px',
                fontSize: '10.5px',
                color: '#475569',
                fontFamily: 'monospace',
                border: '1px solid #ffe4e6',
              }}
            >
              Latitude: {locationData?.coordinates?.lat.toFixed(5)}° N<br />
              Longitude: {locationData?.coordinates?.lon.toFixed(5)}° E
            </div>

            {/* If weather intelligence exists for metro region */}
            {current && (
              <div
                style={{
                  marginTop: '10px',
                  padding: '8px 10px',
                  background: '#ffffff',
                  borderRadius: '6px',
                  border: '1px solid #fecdd3',
                  textAlign: 'left',
                }}
              >
                <div style={{ fontSize: '10px', fontWeight: 800, color: '#9f1239', marginBottom: '2px' }}>
                  REGIONAL ATMOSPHERIC CONDITIONS:
                </div>
                <div style={{ fontSize: '11px', color: '#334155' }}>
                  {current.temperature_c}°C • {current.weather_description} • Rain: {current.effective_rainfall_rate_mmh || 0} mm/h
                </div>
              </div>
            )}

            <div style={{ fontSize: '10px', color: '#94a3b8', marginTop: '8px' }}>
              MUFNS nowcasting coverage is calibrated specifically for the 24 BMC Greater Mumbai administrative wards.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

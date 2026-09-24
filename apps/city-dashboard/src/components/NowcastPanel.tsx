'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';

const API_BASE = 'http://127.0.0.1:8000/api/v1';

interface WeatherPoint {
  name: string;
  lat: number;
  lon: number;
  rainfall_mmh: number;
  temperature_c: number | null;
  humidity_pct: number | null;
  pressure_hpa: number | null;
  wind_speed_kmh: number | null;
  cloud_cover_pct: number | null;
  weather_code: number | null;
}

interface WeatherData {
  status: string;
  provider: string;
  retrieved_at: string;
  latency_ms: number;
  spatial_summary: {
    mean_rainfall_mmh: number;
    max_rainfall_mmh: number;
    min_rainfall_mmh: number;
    monitoring_points: number;
  };
  accumulation: {
    last_1h_mm: number;
    last_3h_mm: number;
    last_6h_mm: number;
  };
  current_conditions: WeatherPoint[];
  forecast_hourly: Array<{
    hour_offset: number;
    mean_rainfall_mmh: number;
    max_rainfall_mmh: number;
  }>;
  recent_hourly: Array<{
    hour_offset: number;
    mean_rainfall_mmh: number;
    max_rainfall_mmh: number;
  }>;
}

interface NowcastRun {
  run_id: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  forcing: {
    source: string;
    rainfall_rate_mmh: number;
    accum_1h_mm: number;
    accum_3h_mm: number;
    accum_6h_mm: number;
    mean_rainfall_mmh: number;
    max_rainfall_mmh: number;
    monitoring_points: number;
  };
  model: {
    catchment: string;
    dem_source: string;
    solver: string;
    grid_shape: number[] | null;
    cell_size_m: number;
    duration_hours: number;
    runtime_seconds: number;
  };
  results: {
    max_depth_m: number;
    mean_depth_m: number;
    flooded_area_km2: number;
    flooded_cells: number;
    mass_balance_error_pct: number;
  };
  timeline: Array<{
    time_hours: number;
    time_minutes: number;
    max_depth_m: number;
    flooded_cells: number;
    flooded_area_km2: number;
    volume_m3: number;
  }>;
  error: string | null;
}

interface NowcastPanelProps {
  onFloodUpdate?: (geojson: any, georef: any) => void;
  onWeatherUpdate?: (weather: WeatherData) => void;
}

function timeAgo(isoStr: string): string {
  const diff = Date.now() - new Date(isoStr).getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} min ago`;
  const hr = Math.floor(min / 60);
  return `${hr}h ${min % 60}m ago`;
}

function getWeatherIcon(code: number | null): string {
  if (code === null) return '🌤️';
  if (code === 0) return '☀️';
  if (code <= 3) return '⛅';
  if (code <= 48) return '🌫️';
  if (code <= 57) return '🌧️';
  if (code <= 67) return '🌧️';
  if (code <= 77) return '❄️';
  if (code <= 82) return '🌧️';
  if (code <= 86) return '🌨️';
  if (code <= 99) return '⛈️';
  return '🌤️';
}

function getRainIntensity(mmh: number): { label: string; color: string; bg: string } {
  if (mmh <= 0) return { label: 'Dry', color: '#059669', bg: '#ecfdf5' };
  if (mmh < 2.5) return { label: 'Light', color: '#0284c7', bg: '#f0f9ff' };
  if (mmh < 10) return { label: 'Moderate', color: '#1d4ed8', bg: '#eff6ff' };
  if (mmh < 35) return { label: 'Heavy', color: '#b45309', bg: '#fffbeb' };
  if (mmh < 64) return { label: 'Very Heavy', color: '#dc2626', bg: '#fef2f2' };
  return { label: 'Extreme', color: '#7f1d1d', bg: '#fef2f2' };
}

export function NowcastPanel({ onFloodUpdate, onWeatherUpdate }: NowcastPanelProps) {
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [weatherError, setWeatherError] = useState<string | null>(null);
  const [lastWeatherFetch, setLastWeatherFetch] = useState<string | null>(null);

  const [nowcast, setNowcast] = useState<NowcastRun | null>(null);
  const [nowcastLoading, setNowcastLoading] = useState(false);
  const [nowcastError, setNowcastError] = useState<string | null>(null);

  const [selectedCatchment, setSelectedCatchment] = useState('hindmata_dadar');
  const [scenarioMode, setScenarioMode] = useState(false);
  const [scenarioRain, setScenarioRain] = useState(60);

  const [timelineIndex, setTimelineIndex] = useState(0);
  const [showForecast, setShowForecast] = useState(true);

  // Auto-fetch weather on mount
  useEffect(() => {
    fetchWeather();
    // Refresh weather every 5 minutes
    const interval = setInterval(fetchWeather, 300_000);
    return () => clearInterval(interval);
  }, []);

  const fetchWeather = useCallback(async () => {
    setWeatherLoading(true);
    setWeatherError(null);
    try {
      const res = await fetch(`${API_BASE}/nowcast/weather`);
      const data: WeatherData = await res.json();
      setWeather(data);
      setLastWeatherFetch(new Date().toISOString());
      onWeatherUpdate?.(data);
    } catch (e: any) {
      setWeatherError(e.message || 'Failed to fetch weather');
    } finally {
      setWeatherLoading(false);
    }
  }, [onWeatherUpdate]);

  const runNowcast = useCallback(async () => {
    setNowcastLoading(true);
    setNowcastError(null);
    try {
      const params = new URLSearchParams({
        catchment: selectedCatchment,
        duration_hours: '3.0',
        grid_size: '60',
      });
      if (scenarioMode) {
        params.set('force_rainfall_mmh', scenarioRain.toString());
      }
      const res = await fetch(`${API_BASE}/nowcast/run?${params}`, { method: 'POST' });
      const data: NowcastRun = await res.json();
      setNowcast(data);
      setTimelineIndex(0);

      // Fetch flood GeoJSON for map
      if (data.status === 'completed') {
        const geoRes = await fetch(`${API_BASE}/nowcast/latest/geojson`);
        const geoData = await geoRes.json();
        onFloodUpdate?.(geoData, null);
      }
    } catch (e: any) {
      setNowcastError(e.message || 'Nowcast failed');
    } finally {
      setNowcastLoading(false);
    }
  }, [selectedCatchment, scenarioMode, scenarioRain, onFloodUpdate]);

  const intensity = weather ? getRainIntensity(weather.spatial_summary.mean_rainfall_mmh) : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>

      {/* ── Live Weather Section ── */}
      <div style={{
        background: 'rgba(255,255,255,0.95)', borderRadius: '12px',
        padding: '16px', border: '1px solid rgba(0,0,0,0.06)',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '14px' }}>🌦️</span>
            <span style={{ fontSize: '13px', fontWeight: 700, color: '#0f172a' }}>Live Weather</span>
            {weather && (
              <span style={{
                fontSize: '10px', fontWeight: 600, padding: '2px 6px', borderRadius: '4px',
                background: weather.status === 'ok' ? '#dcfce7' : '#fef3c7',
                color: weather.status === 'ok' ? '#15803d' : '#92400e',
              }}>
                {weather.status === 'ok' ? 'CONNECTED' : 'DEGRADED'}
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {lastWeatherFetch && (
              <span style={{ fontSize: '10px', color: '#94a3b8' }}>
                {timeAgo(lastWeatherFetch)}
              </span>
            )}
            <button
              onClick={fetchWeather}
              disabled={weatherLoading}
              style={{
                padding: '3px 8px', borderRadius: '4px', border: '1px solid #e2e8f0',
                background: 'white', cursor: 'pointer', fontSize: '10px', fontWeight: 600,
                color: '#64748b',
              }}
            >
              {weatherLoading ? '⏳' : '↻'}
            </button>
          </div>
        </div>

        {weatherError && (
          <div style={{ padding: '6px 10px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px', fontSize: '11px', color: '#dc2626', marginBottom: '8px' }}>
            {weatherError}
          </div>
        )}

        {weather && (
          <>
            {/* Summary Row */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginBottom: '10px' }}>
              <div style={{
                padding: '10px', borderRadius: '8px', textAlign: 'center',
                background: intensity?.bg || '#f8fafc', border: `1px solid ${intensity?.color}20`,
              }}>
                <div style={{ fontSize: '20px', fontWeight: 800, color: intensity?.color || '#0f172a' }}>
                  {weather.spatial_summary.mean_rainfall_mmh.toFixed(1)}
                </div>
                <div style={{ fontSize: '10px', color: '#64748b', fontWeight: 600 }}>mm/hr avg</div>
                <div style={{
                  fontSize: '9px', fontWeight: 700, color: intensity?.color,
                  marginTop: '2px',
                }}>
                  {intensity?.label}
                </div>
              </div>
              <div style={{ padding: '10px', borderRadius: '8px', textAlign: 'center', background: '#f8fafc' }}>
                <div style={{ fontSize: '20px', fontWeight: 800, color: '#0f172a' }}>
                  {weather.current_conditions[0]?.temperature_c?.toFixed(0) || '--'}°
                </div>
                <div style={{ fontSize: '10px', color: '#64748b', fontWeight: 600 }}>Temperature</div>
              </div>
              <div style={{ padding: '10px', borderRadius: '8px', textAlign: 'center', background: '#f8fafc' }}>
                <div style={{ fontSize: '20px', fontWeight: 800, color: '#0f172a' }}>
                  {weather.current_conditions[0]?.humidity_pct?.toFixed(0) || '--'}%
                </div>
                <div style={{ fontSize: '10px', color: '#64748b', fontWeight: 600 }}>Humidity</div>
              </div>
            </div>

            {/* Accumulation */}
            <div style={{
              display: 'flex', gap: '6px', marginBottom: '10px',
            }}>
              {[
                { label: '1h', val: weather.accumulation.last_1h_mm },
                { label: '3h', val: weather.accumulation.last_3h_mm },
                { label: '6h', val: weather.accumulation.last_6h_mm },
              ].map(a => (
                <div key={a.label} style={{
                  flex: 1, padding: '6px 8px', borderRadius: '6px',
                  background: a.val > 0 ? '#eff6ff' : '#f8fafc',
                  border: '1px solid #e2e8f0', textAlign: 'center',
                }}>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: a.val > 0 ? '#1d4ed8' : '#64748b' }}>
                    {a.val.toFixed(1)}
                  </div>
                  <div style={{ fontSize: '9px', color: '#94a3b8', fontWeight: 600 }}>
                    {a.label} mm
                  </div>
                </div>
              ))}
            </div>

            {/* Monitoring Points */}
            <div style={{ marginBottom: '8px' }}>
              <div style={{ fontSize: '10px', fontWeight: 700, color: '#94a3b8', marginBottom: '4px', textTransform: 'uppercase' as const, letterSpacing: '0.5px' }}>
                {weather.spatial_summary.monitoring_points} monitoring stations
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '3px' }}>
                {weather.current_conditions.map(pt => (
                  <div key={pt.name} style={{
                    padding: '3px 7px', borderRadius: '4px', fontSize: '10px', fontWeight: 600,
                    background: pt.rainfall_mmh > 0 ? '#dbeafe' : '#f1f5f9',
                    color: pt.rainfall_mmh > 0 ? '#1e40af' : '#94a3b8',
                  }}>
                    {pt.name}: {pt.rainfall_mmh.toFixed(1)}
                  </div>
                ))}
              </div>
            </div>

            {/* Forecast Timeline */}
            {showForecast && weather.forecast_hourly.length > 0 && (
              <div>
                <div style={{ fontSize: '10px', fontWeight: 700, color: '#94a3b8', marginBottom: '4px', textTransform: 'uppercase' as const }}>
                  Forecast →
                </div>
                <div style={{ display: 'flex', gap: '2px', alignItems: 'flex-end', height: '36px' }}>
                  {weather.forecast_hourly.slice(0, 6).map((fc, i) => {
                    const maxRate = Math.max(...weather.forecast_hourly.slice(0, 6).map(f => f.mean_rainfall_mmh), 1);
                    const h = Math.max(4, (fc.mean_rainfall_mmh / maxRate) * 32);
                    return (
                      <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1px' }}>
                        <div style={{
                          width: '100%', height: `${h}px`, borderRadius: '2px',
                          background: fc.mean_rainfall_mmh > 10 ? '#3b82f6' : fc.mean_rainfall_mmh > 0 ? '#93c5fd' : '#e2e8f0',
                          transition: 'height 0.3s',
                        }} />
                        <div style={{ fontSize: '8px', color: '#94a3b8' }}>+{fc.hour_offset}h</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            <div style={{ fontSize: '9px', color: '#cbd5e1', marginTop: '4px' }}>
              Source: Open-Meteo · {weather.latency_ms}ms
            </div>
          </>
        )}
      </div>

      {/* ── Nowcast Control ── */}
      <div style={{
        background: 'rgba(255,255,255,0.95)', borderRadius: '12px',
        padding: '16px', border: '1px solid rgba(0,0,0,0.06)',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
          <span style={{ fontSize: '14px' }}>🌊</span>
          <span style={{ fontSize: '13px', fontWeight: 700, color: '#0f172a' }}>Flood Nowcast</span>
        </div>

        <div style={{ marginBottom: '8px' }}>
          <label style={{ fontSize: '10px', fontWeight: 600, color: '#64748b', display: 'block', marginBottom: '4px' }}>
            CATCHMENT
          </label>
          <select
            value={selectedCatchment}
            onChange={e => setSelectedCatchment(e.target.value)}
            style={{
              width: '100%', padding: '7px 10px', borderRadius: '6px',
              border: '1px solid #e2e8f0', fontSize: '12px', fontWeight: 600,
              background: 'white', color: '#0f172a',
            }}
          >
            <option value="hindmata_dadar">Hindmata / Dadar Basin</option>
            <option value="mithi_basin">Mithi River Catchment</option>
            <option value="mumbai_city">South Mumbai (Island City)</option>
            <option value="western_suburbs">Western Suburbs</option>
          </select>
        </div>

        {/* Scenario Toggle */}
        <div style={{ marginBottom: '8px' }}>
          <label style={{
            display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer',
            fontSize: '11px', fontWeight: 600, color: '#64748b',
          }}>
            <input
              type="checkbox"
              checked={scenarioMode}
              onChange={e => setScenarioMode(e.target.checked)}
              style={{ accentColor: '#3b82f6' }}
            />
            Scenario mode (override rainfall)
          </label>
          {scenarioMode && (
            <div style={{ marginTop: '4px' }}>
              <input
                type="range" min={0} max={200} step={5}
                value={scenarioRain}
                onChange={e => setScenarioRain(Number(e.target.value))}
                style={{ width: '100%' }}
              />
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#1d4ed8', textAlign: 'center' }}>
                {scenarioRain} mm/hr
              </div>
            </div>
          )}
        </div>

        <button
          onClick={runNowcast}
          disabled={nowcastLoading}
          style={{
            width: '100%', padding: '10px', borderRadius: '8px',
            background: nowcastLoading ? '#94a3b8' : 'linear-gradient(135deg, #1e40af, #0ea5e9)',
            color: '#fff', fontSize: '12px', fontWeight: 700,
            border: 'none', cursor: nowcastLoading ? 'not-allowed' : 'pointer',
            boxShadow: nowcastLoading ? 'none' : '0 2px 8px rgba(30,64,175,0.3)',
          }}
        >
          {nowcastLoading ? '⏳ Running model...' : scenarioMode ? '⚡ Run Scenario' : '🌊 Run Live Nowcast'}
        </button>

        {nowcastError && (
          <div style={{ marginTop: '6px', padding: '6px 10px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px', fontSize: '11px', color: '#dc2626' }}>
            {nowcastError}
          </div>
        )}
      </div>

      {/* ── Model Results ── */}
      {nowcast && nowcast.status === 'completed' && (
        <div style={{
          background: 'rgba(255,255,255,0.95)', borderRadius: '12px',
          padding: '16px', border: '1px solid rgba(0,0,0,0.06)',
          boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '14px' }}>📊</span>
              <span style={{ fontSize: '13px', fontWeight: 700, color: '#0f172a' }}>Model Results</span>
            </div>
            <span style={{
              fontSize: '9px', fontWeight: 600, padding: '2px 6px', borderRadius: '4px',
              background: '#dcfce7', color: '#15803d',
            }}>
              {nowcast.model.runtime_seconds.toFixed(1)}s
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginBottom: '10px' }}>
            <div style={{ padding: '10px', borderRadius: '8px', background: nowcast.results.max_depth_m >= 0.3 ? '#fef2f2' : '#f0f9ff' }}>
              <div style={{ fontSize: '18px', fontWeight: 800, color: nowcast.results.max_depth_m >= 0.3 ? '#dc2626' : '#0284c7' }}>
                {nowcast.results.max_depth_m.toFixed(2)}m
              </div>
              <div style={{ fontSize: '9px', color: '#64748b', fontWeight: 600 }}>Max Depth</div>
            </div>
            <div style={{ padding: '10px', borderRadius: '8px', background: '#f0fdf4' }}>
              <div style={{ fontSize: '18px', fontWeight: 800, color: '#059669' }}>
                {nowcast.results.flooded_area_km2.toFixed(2)}
              </div>
              <div style={{ fontSize: '9px', color: '#64748b', fontWeight: 600 }}>km² flooded</div>
            </div>
          </div>

          {/* Timeline */}
          {nowcast.timeline.length > 0 && (
            <div>
              <div style={{ fontSize: '10px', fontWeight: 700, color: '#94a3b8', marginBottom: '6px', textTransform: 'uppercase' as const }}>
                Flood Timeline
              </div>
              <div style={{ display: 'flex', gap: '2px', alignItems: 'flex-end', height: '40px' }}>
                {nowcast.timeline.filter((_, i) => i % Math.max(1, Math.floor(nowcast.timeline.length / 12)) === 0).map((t, i) => {
                  const maxD = Math.max(...nowcast.timeline.map(x => x.max_depth_m), 0.01);
                  const h = Math.max(4, (t.max_depth_m / maxD) * 36);
                  return (
                    <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1px' }}>
                      <div style={{
                        width: '100%', height: `${h}px`, borderRadius: '2px',
                        background: t.max_depth_m > 0.3 ? '#ef4444' : t.max_depth_m > 0.1 ? '#3b82f6' : '#93c5fd',
                        transition: 'height 0.3s',
                      }} />
                      <div style={{ fontSize: '7px', color: '#94a3b8' }}>{t.time_minutes}m</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Mass Balance */}
          <div style={{
            marginTop: '8px', padding: '6px 10px', borderRadius: '6px',
            background: '#f8fafc', fontSize: '10px', color: '#64748b',
          }}>
            <div>Forcing: {nowcast.forcing.source}</div>
            <div>Rain: {nowcast.forcing.rainfall_rate_mmh} mm/hr · Grid: {nowcast.model.grid_shape?.join('×')}</div>
            <div>Mass balance error: {nowcast.results.mass_balance_error_pct}%</div>
            <div>DEM: {nowcast.model.dem_source} · Solver: {nowcast.model.solver}</div>
          </div>
        </div>
      )}
    </div>
  );
}

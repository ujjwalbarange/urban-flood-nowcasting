'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { MumbaiFloodMap } from '../components/MumbaiFloodMap';
import { NowcastPanel } from '../components/NowcastPanel';
import {
  LayoutDashboard, Activity, Waves, Users, ShieldCheck,
  MessageSquarePlus, BarChart3, Target, ChevronLeft, ChevronRight,
  AlertTriangle
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api/v1';

// ── Secondary panel views ──
type PanelView = 'nowcast' | 'risk' | 'reports' | 'events' | 'drainage' | 'health' | 'simulation' | 'validation';

export default function CityDashboardPage() {
  const [panelView, setPanelView] = useState<PanelView>('nowcast');
  const [panelOpen, setPanelOpen] = useState(true);
  const [confusionGeoJSON, setConfusionGeoJSON] = useState<any>(null);

  // ── Data state ──
  const [wardRisks, setWardRisks] = useState<any[]>([]);
  const [citizenReports, setCitizenReports] = useState<any[]>([]);
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [observedEvents, setObservedEvents] = useState<any[]>([]);
  const [drainageNodes, setDrainageNodes] = useState<any[]>([]);
  const [historicalEvents, setHistoricalEvents] = useState<any[]>([]);

  // ── Simulation state (existing) ──
  const [simRegion, setSimRegion] = useState('hindmata_dadar');
  const [simRainfall, setSimRainfall] = useState('heavy_rain_15min');
  const [simDuration, setSimDuration] = useState(1.5);
  const [simStatus, setSimStatus] = useState<'idle' | 'running' | 'completed' | 'failed'>('idle');
  const [currentSim, setCurrentSim] = useState<any>(null);
  const [simError, setSimError] = useState<string | null>(null);

  // ── Validation state (existing) ──
  const [selectedValEvent, setSelectedValEvent] = useState('HIST_FLOOD_2005_07_26');
  const [valStatus, setValStatus] = useState<'idle' | 'running' | 'completed' | 'failed'>('idle');
  const [valReport, setValReport] = useState<any>(null);
  const [valError, setValError] = useState<string | null>(null);

  useEffect(() => {
    loadSecondaryData();
  }, []);

  async function loadSecondaryData() {
    try {
      const [riskRes, reportsRes, healthRes, obsRes, nodesRes, histRes] = await Promise.all([
        fetch(`${API_BASE}/geodata/ward-risk`).then(r => r.json()).catch(() => ({})),
        fetch(`${API_BASE}/geodata/citizen-reports?limit=100`).then(r => r.json()).catch(() => ({ reports: [] })),
        fetch(`${API_BASE}/geodata/system-health`).then(r => r.json()).catch(() => null),
        fetch(`${API_BASE}/geodata/observed-events?limit=200`).then(r => r.json()).catch(() => ({ features: [] })),
        fetch(`${API_BASE}/geodata/drainage/nodes`).then(r => r.json()).catch(() => ({ features: [] })),
        fetch(`${API_BASE}/geodata/rainfall/historical-events`).then(r => r.json()).catch(() => ({ events: [] })),
      ]);
      if (riskRes?.ward_risks) setWardRisks(riskRes.ward_risks);
      if (reportsRes?.reports) setCitizenReports(reportsRes.reports);
      if (healthRes) setSystemHealth(healthRes);
      if (obsRes?.features) setObservedEvents(obsRes.features);
      if (nodesRes?.features) setDrainageNodes(nodesRes.features.map((f: any) => f.properties));
      if (histRes?.events) setHistoricalEvents(histRes.events);
    } catch {}
  }

  async function handleRunSimulation() {
    setSimStatus('running');
    setSimError(null);
    setCurrentSim(null);
    try {
      const res = await fetch(
        `${API_BASE}/simulations/run?terrain_source=copernicus_glo30&region=${simRegion}&rainfall_source=${simRainfall}&duration_hours=${simDuration}&grid_size=50`,
        { method: 'POST' }
      ).then(r => r.json());
      const simId = res.sim_id;
      if (!simId) throw new Error('Failed to queue simulation');
      const poll = setInterval(async () => {
        try {
          const sRes = await fetch(`${API_BASE}/simulations/${simId}`).then(r => r.json());
          if (sRes.status === 'completed') {
            clearInterval(poll);
            setSimStatus('completed');
            setCurrentSim(sRes);
          } else if (sRes.status === 'failed') {
            clearInterval(poll);
            setSimStatus('failed');
            setSimError(sRes.error || 'Simulation failed');
          }
        } catch {
          clearInterval(poll);
          setSimStatus('failed');
          setSimError('Failed to retrieve simulation progress');
        }
      }, 1500);
    } catch (err: any) {
      setSimStatus('failed');
      setSimError(err.message);
    }
  }

  async function handleRunValidation() {
    setValStatus('running');
    setValError(null);
    setValReport(null);
    try {
      const res = await fetch(
        `${API_BASE}/validation/run?event_id=${selectedValEvent}&catchment=mithi_basin&rainfall_source=nasa_imerg&min_flood_depth_m=0.08&duration_hours=2.0`,
        { method: 'POST' }
      ).then(r => r.json());
      if (res.report_id) {
        setValReport(res);
        if (res.confusion_geojson) setConfusionGeoJSON(res.confusion_geojson);
        setValStatus('completed');
      } else {
        throw new Error(res.detail || 'Validation failed');
      }
    } catch (err: any) {
      setValStatus('failed');
      setValError(err.message);
    }
  }

  async function handleUpdateReport(reportId: string, status: string) {
    try {
      await fetch(`${API_BASE}/geodata/citizen-reports/${reportId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ verification_status: status }),
      });
      const res = await fetch(`${API_BASE}/geodata/citizen-reports?limit=100`).then(r => r.json());
      if (res.reports) setCitizenReports(res.reports);
    } catch {}
  }

  const navItems: { key: PanelView; icon: any; label: string; badge?: number }[] = [
    { key: 'nowcast', icon: Activity, label: 'Nowcast' },
    { key: 'risk', icon: ShieldCheck, label: 'Risk' },
    { key: 'reports', icon: MessageSquarePlus, label: 'Reports', badge: citizenReports.length },
    { key: 'events', icon: BarChart3, label: 'History' },
    { key: 'drainage', icon: Waves, label: 'Drainage' },
    { key: 'simulation', icon: Target, label: 'Simulate' },
    { key: 'validation', icon: Target, label: 'Validate' },
    { key: 'health', icon: Activity, label: 'System' },
  ];

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#0f172a', overflow: 'hidden' }}>

      {/* ── Compact Header ── */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '6px 16px', background: 'rgba(15,23,42,0.98)', borderBottom: '1px solid rgba(255,255,255,0.06)',
        zIndex: 100,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '28px', height: '28px', borderRadius: '6px',
            background: 'linear-gradient(135deg, #1e40af, #0ea5e9)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <LayoutDashboard size={16} color="#fff" />
          </div>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 800, color: '#f1f5f9', letterSpacing: '-0.3px' }}>
              MUFNS Command Center
            </div>
            <div style={{ fontSize: '9px', color: '#64748b', fontWeight: 500 }}>
              Mumbai Urban Flood Nowcasting System • SIH26085
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            fontSize: '9px', fontWeight: 600, padding: '2px 8px', borderRadius: '4px',
            background: 'rgba(234,179,8,0.15)', color: '#fbbf24', border: '1px solid rgba(234,179,8,0.2)',
          }}>
            <AlertTriangle size={10} style={{ verticalAlign: 'middle', marginRight: '3px' }} />
            Research Prototype
          </span>
        </div>
      </header>

      {/* ── Main Layout: Nav + Map + Panel ── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* ── Left Nav Bar ── */}
        <nav style={{
          width: '56px', background: 'rgba(15,23,42,0.95)', borderRight: '1px solid rgba(255,255,255,0.04)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '8px 0', gap: '2px',
          zIndex: 50,
        }}>
          {navItems.map(item => {
            const Icon = item.icon;
            const active = panelView === item.key && panelOpen;
            return (
              <button
                key={item.key}
                onClick={() => {
                  if (panelView === item.key && panelOpen) {
                    setPanelOpen(false);
                  } else {
                    setPanelView(item.key);
                    setPanelOpen(true);
                  }
                }}
                title={item.label}
                style={{
                  width: '42px', height: '42px', borderRadius: '8px',
                  border: 'none', cursor: 'pointer',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '2px',
                  background: active ? 'rgba(59,130,246,0.15)' : 'transparent',
                  color: active ? '#60a5fa' : '#64748b',
                  transition: 'all 0.15s',
                  position: 'relative',
                }}
              >
                <Icon size={16} />
                <span style={{ fontSize: '8px', fontWeight: 600, lineHeight: 1 }}>{item.label}</span>
                {item.badge && item.badge > 0 && (
                  <span style={{
                    position: 'absolute', top: '2px', right: '2px',
                    width: '14px', height: '14px', borderRadius: '7px',
                    background: '#ef4444', color: '#fff', fontSize: '8px', fontWeight: 700,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {item.badge > 9 ? '9+' : item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* ── Map (Primary Visual Element) ── */}
        <div style={{ flex: 1, position: 'relative' }}>
          <MumbaiFloodMap confusionGeoJSON={confusionGeoJSON} />
        </div>

        {/* ── Side Panel ── */}
        {panelOpen && (
          <div style={{
            width: '340px', background: '#f8fafc', borderLeft: '1px solid rgba(0,0,0,0.08)',
            overflow: 'auto', display: 'flex', flexDirection: 'column',
          }}>
            <div style={{
              padding: '12px 16px', borderBottom: '1px solid #e2e8f0',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              background: '#fff',
            }}>
              <span style={{ fontSize: '13px', fontWeight: 700, color: '#0f172a' }}>
                {navItems.find(n => n.key === panelView)?.label}
              </span>
              <button
                onClick={() => setPanelOpen(false)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: '#94a3b8', padding: '2px',
                }}
              >
                <ChevronRight size={16} />
              </button>
            </div>

            <div style={{ flex: 1, overflow: 'auto', padding: '12px' }}>
              {/* ── Nowcast Panel ── */}
              {panelView === 'nowcast' && <NowcastPanel />}

              {/* ── Ward Risk Panel ── */}
              {panelView === 'risk' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    Ward Risk Assessment (Hazard 40% + Exposure 35% + Vulnerability 25%)
                  </div>
                  {wardRisks.map(wr => (
                    <div key={wr.ward_id} style={{
                      padding: '10px 12px', borderRadius: '8px', background: '#fff',
                      border: `1px solid ${wr.risk_category === 'CRITICAL' ? '#fecaca' : wr.risk_category === 'HIGH' ? '#fed7aa' : '#e2e8f0'}`,
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '12px', fontWeight: 700 }}>{wr.ward_name}</span>
                        <span style={{
                          fontSize: '9px', fontWeight: 700, padding: '2px 6px', borderRadius: '4px',
                          background: wr.risk_category === 'CRITICAL' ? '#fef2f2' : wr.risk_category === 'HIGH' ? '#fffbeb' : '#f0fdf4',
                          color: wr.risk_category === 'CRITICAL' ? '#dc2626' : wr.risk_category === 'HIGH' ? '#d97706' : '#059669',
                        }}>
                          {wr.risk_score} — {wr.risk_category}
                        </span>
                      </div>
                      <div style={{ fontSize: '10px', color: '#64748b', marginTop: '4px' }}>
                        Pop: {(wr.population/1e3).toFixed(0)}K · Hotspots: {wr.chronic_hotspots_count} · Events: {wr.historical_flood_events_recorded}
                      </div>
                      <div style={{ display: 'flex', gap: '4px', marginTop: '4px' }}>
                        {[
                          { label: 'Hazard', val: wr.components.hazard_score, color: '#dc2626' },
                          { label: 'Exposure', val: wr.components.exposure_score, color: '#d97706' },
                          { label: 'Vuln', val: wr.components.vulnerability_score, color: '#7c3aed' },
                        ].map(c => (
                          <div key={c.label} style={{ flex: 1 }}>
                            <div style={{ height: '3px', borderRadius: '2px', background: '#f1f5f9', overflow: 'hidden' }}>
                              <div style={{ height: '100%', width: `${c.val}%`, background: c.color, borderRadius: '2px' }} />
                            </div>
                            <div style={{ fontSize: '8px', color: '#94a3b8', textAlign: 'center', marginTop: '1px' }}>{c.label}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* ── Citizen Reports Panel ── */}
              {panelView === 'reports' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    {citizenReports.length} citizen incident reports
                  </div>
                  {citizenReports.slice(0, 20).map(r => (
                    <div key={r.report_id} style={{
                      padding: '10px 12px', borderRadius: '8px', background: '#fff',
                      border: '1px solid #e2e8f0',
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '11px', fontWeight: 700 }}>{r.category}</span>
                        <span style={{
                          fontSize: '9px', fontWeight: 600, padding: '2px 6px', borderRadius: '4px',
                          background: r.verified ? '#dcfce7' : '#fef3c7',
                          color: r.verified ? '#15803d' : '#92400e',
                        }}>
                          {r.verification_status}
                        </span>
                      </div>
                      <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px' }}>
                        Ward {r.ward_id} · {r.water_depth_cm ? `${r.water_depth_cm}cm` : ''} · {r.severity}
                      </div>
                      {r.description && (
                        <div style={{ fontSize: '10px', color: '#475569', marginTop: '4px', fontStyle: 'italic' }}>
                          "{r.description.substring(0, 80)}"
                        </div>
                      )}
                      <div style={{ display: 'flex', gap: '4px', marginTop: '6px' }}>
                        <button
                          onClick={() => handleUpdateReport(r.report_id, 'verified')}
                          style={{ flex: 1, padding: '4px', borderRadius: '4px', border: '1px solid #a7f3d0', background: '#ecfdf5', fontSize: '9px', fontWeight: 600, color: '#059669', cursor: 'pointer' }}
                        >
                          ✓ Verify
                        </button>
                        <button
                          onClick={() => handleUpdateReport(r.report_id, 'rejected')}
                          style={{ flex: 1, padding: '4px', borderRadius: '4px', border: '1px solid #fecaca', background: '#fef2f2', fontSize: '9px', fontWeight: 600, color: '#dc2626', cursor: 'pointer' }}
                        >
                          ✗ Reject
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* ── Historical Events Panel ── */}
              {panelView === 'events' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    {observedEvents.length} observed flood events (2016-2025)
                  </div>
                  {observedEvents.slice(0, 30).map((ev, i) => {
                    const p = ev.properties || {};
                    return (
                      <div key={i} style={{
                        padding: '8px 10px', borderRadius: '6px', background: '#fff',
                        border: '1px solid #e2e8f0', fontSize: '11px',
                      }}>
                        <div style={{ fontWeight: 700, color: '#0f172a' }}>{p.locality || p.ward || 'Unknown'}</div>
                        <div style={{ color: '#64748b', fontSize: '10px' }}>
                          {p.date ? new Date(p.date).toLocaleDateString() : ''} · {p.flood_severity || ''} · Depth: {p.flood_depth_cm ? `${p.flood_depth_cm}cm` : 'N/A'}
                        </div>
                        {p.rainfall_1h_mm && <div style={{ color: '#1d4ed8', fontSize: '10px' }}>Rain 1h: {p.rainfall_1h_mm}mm</div>}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* ── Drainage Panel ── */}
              {panelView === 'drainage' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    Drainage infrastructure · {drainageNodes.length} nodes
                  </div>
                  <div style={{ padding: '10px', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '8px', fontSize: '10px', color: '#92400e' }}>
                    ⚠️ Drainage coupling code exists but is not yet mapped to the simulation grid. Infrastructure data shown is from PostGIS (rated capacity, not live telemetry).
                  </div>
                  {drainageNodes.filter(n => n.type === 'pumping_station' || n.pump_capacity_m3_per_sec).slice(0, 15).map((n, i) => (
                    <div key={i} style={{
                      padding: '8px 10px', borderRadius: '6px', background: '#fff',
                      border: '1px solid #e2e8f0', fontSize: '11px',
                    }}>
                      <div style={{ fontWeight: 700 }}>{n.name}</div>
                      <div style={{ color: '#64748b', fontSize: '10px' }}>
                        {n.type} · Ward {n.ward} · {n.pump_capacity_m3_per_sec ? `${n.pump_capacity_m3_per_sec} m³/s rated` : ''}
                      </div>
                      <span style={{
                        fontSize: '9px', fontWeight: 600, padding: '1px 5px', borderRadius: '3px',
                        background: '#f1f5f9', color: '#64748b',
                      }}>
                        STATIC INFRASTRUCTURE DATA
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* ── Simulation Panel (legacy) ── */}
              {panelView === 'simulation' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase' }}>
                    Direct 2D Hydraulic Simulation (Copernicus DEM)
                  </div>
                  <select value={simRegion} onChange={e => setSimRegion(e.target.value)} style={{ padding: '8px', borderRadius: '6px', border: '1px solid #e2e8f0', fontSize: '12px' }}>
                    <option value="hindmata_dadar">Hindmata / Dadar Basin</option>
                    <option value="mithi_basin">Mithi River Catchment</option>
                    <option value="mumbai_city">South Mumbai</option>
                    <option value="western_suburbs">Western Suburbs</option>
                  </select>
                  <select value={simRainfall} onChange={e => setSimRainfall(e.target.value)} style={{ padding: '8px', borderRadius: '6px', border: '1px solid #e2e8f0', fontSize: '12px' }}>
                    <option value="heavy_rain_15min">Heavy Monsoon (60 mm/hr)</option>
                    <option value="extreme_rain_15min">Extreme Storm (100 mm/hr)</option>
                    <option value="cloudburst_pulse_15min">Cloudburst (150 mm/hr)</option>
                  </select>
                  <button onClick={handleRunSimulation} disabled={simStatus === 'running'} style={{
                    padding: '10px', borderRadius: '8px',
                    background: simStatus === 'running' ? '#94a3b8' : 'linear-gradient(135deg, #1e40af, #0ea5e9)',
                    color: '#fff', fontSize: '12px', fontWeight: 700, border: 'none', cursor: simStatus === 'running' ? 'not-allowed' : 'pointer',
                  }}>
                    {simStatus === 'running' ? '⏳ Computing...' : '⚡ Run Simulation'}
                  </button>
                  {simError && <div style={{ padding: '8px', background: '#fef2f2', borderRadius: '6px', fontSize: '11px', color: '#dc2626' }}>{simError}</div>}
                  {currentSim?.results && (
                    <div style={{ padding: '10px', background: '#f0fdf4', borderRadius: '8px', fontSize: '11px', color: '#059669' }}>
                      ✅ Max depth: {currentSim.results.max_depth_m}m · Flooded: {currentSim.results.max_flooded_cells} cells
                    </div>
                  )}
                </div>
              )}

              {/* ── Validation Panel ── */}
              {panelView === 'validation' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase' }}>
                    Historical Flood Reconstruction & Validation
                  </div>
                  <div style={{ padding: '8px', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '6px', fontSize: '10px', color: '#92400e' }}>
                    ⚠️ Observed flood extents are documented/surveyed polygons, not Sentinel-1 SAR change-detection products.
                  </div>
                  <select value={selectedValEvent} onChange={e => setSelectedValEvent(e.target.value)} style={{ padding: '8px', borderRadius: '6px', border: '1px solid #e2e8f0', fontSize: '12px' }}>
                    <option value="HIST_FLOOD_2005_07_26">July 26, 2005 — Mithi River Corridor</option>
                    <option value="HIST_FLOOD_2005_07_26_SOUTH">July 26, 2005 — Hindmata-Parel</option>
                    <option value="HIST_FLOOD_2017_08_29">August 29, 2017 — Lower Parel</option>
                    <option value="HIST_FLOOD_2020_08_05">August 5, 2020 — South Mumbai</option>
                  </select>
                  <button onClick={handleRunValidation} disabled={valStatus === 'running'} style={{
                    padding: '10px', borderRadius: '8px',
                    background: valStatus === 'running' ? '#94a3b8' : 'linear-gradient(135deg, #059669, #0284c7)',
                    color: '#fff', fontSize: '12px', fontWeight: 700, border: 'none', cursor: valStatus === 'running' ? 'not-allowed' : 'pointer',
                  }}>
                    {valStatus === 'running' ? '⏳ Running replay...' : '🔬 Run Validation Replay'}
                  </button>
                  {valError && <div style={{ padding: '8px', background: '#fef2f2', borderRadius: '6px', fontSize: '11px', color: '#dc2626' }}>{valError}</div>}
                  {valReport && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                        <div style={{ padding: '8px', background: '#f0fdf4', borderRadius: '6px', textAlign: 'center' }}>
                          <div style={{ fontSize: '16px', fontWeight: 800, color: '#166534' }}>{(valReport.metrics?.critical_success_index_csi || 0).toFixed(3)}</div>
                          <div style={{ fontSize: '9px', color: '#15803d' }}>CSI</div>
                        </div>
                        <div style={{ padding: '8px', background: '#eff6ff', borderRadius: '6px', textAlign: 'center' }}>
                          <div style={{ fontSize: '16px', fontWeight: 800, color: '#1e40af' }}>{(valReport.metrics?.iou_jaccard || 0).toFixed(3)}</div>
                          <div style={{ fontSize: '9px', color: '#1d4ed8' }}>IoU</div>
                        </div>
                        <div style={{ padding: '8px', background: '#fef3c7', borderRadius: '6px', textAlign: 'center' }}>
                          <div style={{ fontSize: '16px', fontWeight: 800, color: '#92400e' }}>{((valReport.metrics?.recall_pod || 0)*100).toFixed(1)}%</div>
                          <div style={{ fontSize: '9px', color: '#b45309' }}>Recall</div>
                        </div>
                        <div style={{ padding: '8px', background: '#f8fafc', borderRadius: '6px', textAlign: 'center' }}>
                          <div style={{ fontSize: '16px', fontWeight: 800, color: '#0f172a' }}>{((valReport.metrics?.precision || 0)*100).toFixed(1)}%</div>
                          <div style={{ fontSize: '9px', color: '#64748b' }}>Precision</div>
                        </div>
                      </div>
                      <div style={{ fontSize: '9px', color: '#94a3b8', padding: '4px' }}>
                        Observed extent source: Documented/Surveyed Flood Polygons (NOT SAR)
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* ── System Health Panel ── */}
              {panelView === 'health' && systemHealth && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    System Health & Data Provenance
                  </div>
                  {Object.entries(systemHealth.subsystems || {}).map(([key, sub]: [string, any]) => (
                    <div key={key} style={{
                      padding: '10px', borderRadius: '8px', background: '#fff',
                      border: `1px solid ${sub.status === 'connected' || sub.status === 'ready' || sub.status === 'operational' ? '#a7f3d0' : '#fde68a'}`,
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '11px', fontWeight: 700 }}>{key.replace(/_/g, ' ')}</span>
                        <span style={{
                          fontSize: '9px', fontWeight: 700, padding: '2px 6px', borderRadius: '4px',
                          background: sub.status === 'connected' || sub.status === 'ready' || sub.status === 'operational' ? '#dcfce7' : '#fef3c7',
                          color: sub.status === 'connected' || sub.status === 'ready' || sub.status === 'operational' ? '#15803d' : '#92400e',
                        }}>
                          {sub.status?.toUpperCase()}
                        </span>
                      </div>
                      {sub.latency_ms && <div style={{ fontSize: '10px', color: '#64748b' }}>Latency: {sub.latency_ms}ms</div>}
                      {sub.provider && <div style={{ fontSize: '10px', fontWeight: 600, color: '#334155' }}>Source: {sub.provider}</div>}
                      {sub.role && <div style={{ fontSize: '10px', color: '#0284c7' }}>Role: {sub.role}</div>}
                      {sub.satellite && <div style={{ fontSize: '10px', color: '#64748b' }}>Platform: {sub.satellite} ({sub.dataset_id})</div>}
                      {sub.spatial_resolution && <div style={{ fontSize: '10px', color: '#64748b' }}>Resolution: {sub.spatial_resolution}</div>}
                      {sub.resolution && <div style={{ fontSize: '10px', color: '#64748b' }}>Resolution: {sub.resolution}</div>}
                      {sub.solver && <div style={{ fontSize: '10px', color: '#64748b' }}>Solver: {sub.solver}</div>}
                      {sub.coupling && <div style={{ fontSize: '10px', color: '#059669' }}>Coupling: {sub.coupling}</div>}
                      {sub.method && <div style={{ fontSize: '10px', color: '#64748b' }}>Method: {sub.method}</div>}
                      {sub.latest_granule?.identifier && (
                        <div style={{ fontSize: '9px', color: '#64748b', wordBreak: 'break-all' }}>
                          Granule: {sub.latest_granule.identifier}
                        </div>
                      )}
                      {sub.latest_granule?.title && (
                        <div style={{ fontSize: '9px', color: '#64748b', wordBreak: 'break-all' }}>
                          Granule: {sub.latest_granule.title}
                        </div>
                      )}
                      {sub.rows && (
                        <div style={{ fontSize: '9px', color: '#64748b', marginTop: '2px' }}>
                          Records: {Object.entries(sub.rows).map(([t, c]) => `${t}:${c}`).join(' · ')}
                        </div>
                      )}
                    </div>
                  ))}
                  <div style={{ fontSize: '9px', color: '#cbd5e1', padding: '4px' }}>
                    Check time: {systemHealth.total_check_time_ms}ms · {systemHealth.timestamp_utc}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Compass, RotateCcw, ZoomIn, ZoomOut, Eye, Layers, Shield,
  AlertTriangle, Navigation, CheckCircle2, XCircle, ChevronRight,
  Building, Hospital, ArrowRight, RefreshCw, Info, Waves, Mountain
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api/v1';

interface SubareaItem {
  subarea_id: string;
  name: string;
  parent_ward_id: string;
  parent_ward_name: string;
  area_sq_km: number;
  centroid: [number, number];
  bounds: { min_lon: number; min_lat: number; max_lon: number; max_lat: number };
}

interface DestinationItem {
  destination_id: string;
  name: string;
  type: string;
  category: string;
  ward: string;
  coordinates: [number, number];
  distance_km: number;
  modeled_depth_m: number;
  is_flood_safe: boolean;
  capacity_persons: number;
  backup_generator: boolean;
  medical_post: boolean;
  provenance: string;
}

interface RouteResult {
  subarea_id: string;
  subarea_name: string;
  route_found: boolean;
  origin: [number, number];
  destination: [number, number];
  destination_name: string;
  vehicle_type: string;
  total_distance_km: number;
  estimated_travel_time_min: number;
  max_flood_depth_along_route_m: number;
  passability_verdict: string;
  inundated_segments_count: number;
  primary_roads: string[];
  geometry: { type: string; coordinates: [number, number][] };
  disclaimer: string;
  provenance: string;
  blocked_message?: string;
}

interface Subarea3DViewerProps {
  initialSubareaId?: string;
  onClose?: () => void;
}

export const Subarea3DViewer: React.FC<Subarea3DViewerProps> = ({
  initialSubareaId = 'A_SA1',
  onClose
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // ── Subarea Hierarchy State ──
  const [subareas, setSubareas] = useState<SubareaItem[]>([]);
  const [selectedSubareaId, setSelectedSubareaId] = useState<string>(initialSubareaId);
  const [subareaDetail, setSubareaDetail] = useState<any | null>(null);
  const [loadingSubareas, setLoadingSubareas] = useState<boolean>(true);

  // ── 3D Terrain & Flood State ──
  const [terrainData, setTerrainData] = useState<any | null>(null);
  const [floodData, setFloodData] = useState<any | null>(null);
  const [loading3D, setLoading3D] = useState<boolean>(false);
  const [error3D, setError3D] = useState<string | null>(null);

  // ── 3D Camera Controls ──
  const [rotAngle, setRotAngle] = useState<number>(Math.PI / 4); // 45 deg azimuth
  const [tiltAngle, setTiltAngle] = useState<number>(Math.PI / 6); // 30 deg pitch
  const [zoom, setZoom] = useState<number>(3.5);
  const [vertExaggeration, setVertExaggeration] = useState<number>(1.8);
  const [renderMode, setRenderMode] = useState<'shaded' | 'wireframe'>('shaded');
  const [showWater, setShowWater] = useState<boolean>(true);
  const [showContextFade, setShowContextFade] = useState<boolean>(true);

  // ── Evacuation Routing State ──
  const [destinations, setDestinations] = useState<DestinationItem[]>([]);
  const [selectedDestId, setSelectedDestId] = useState<string>('');
  const [vehicleType, setVehicleType] = useState<'standard_car' | 'emergency_high_clearance'>('standard_car');
  const [routingResult, setRoutingResult] = useState<RouteResult | null>(null);
  const [calculatingRoute, setCalculatingRoute] = useState<boolean>(false);
  const [routeError, setRouteError] = useState<string | null>(null);

  // ── Interaction State (Drag to rotate) ──
  const isDraggingRef = useRef(false);
  const lastMousePosRef = useRef({ x: 0, y: 0 });

  // 1. Fetch Subareas List
  useEffect(() => {
    async function fetchSubareas() {
      try {
        setLoadingSubareas(true);
        const res = await fetch(`${API_BASE}/subareas`).then(r => r.json());
        if (res.subareas) {
          setSubareas(res.subareas);
        }
      } catch (err: any) {
        console.error('Failed to load subareas:', err);
      } finally {
        setLoadingSubareas(false);
      }
    }
    fetchSubareas();
  }, []);

  // 2. Fetch Detail, Terrain 3D, Flood 3D, and Destinations whenever active subarea changes
  useEffect(() => {
    if (!selectedSubareaId) return;

    let isCurrent = true;
    async function loadSubareaData() {
      setLoading3D(true);
      setError3D(null);
      setRoutingResult(null);
      setRouteError(null);

      try {
        const [detailRes, terrainRes, floodRes, destsRes] = await Promise.all([
          fetch(`${API_BASE}/subareas/${selectedSubareaId}`).then(r => r.json()).catch(() => null),
          fetch(`${API_BASE}/subareas/${selectedSubareaId}/terrain3d`).then(r => r.json()).catch(() => null),
          fetch(`${API_BASE}/subareas/${selectedSubareaId}/flood3d`).then(r => r.json()).catch(() => null),
          fetch(`${API_BASE}/subareas/${selectedSubareaId}/destinations`).then(r => r.json()).catch(() => ({ destinations: [] })),
        ]);

        if (!isCurrent) return;

        if (detailRes && !detailRes.error) setSubareaDetail(detailRes);
        if (terrainRes && terrainRes.elevations) setTerrainData(terrainRes);
        if (floodRes) setFloodData(floodRes);

        if (destsRes?.destinations) {
          setDestinations(destsRes.destinations);
          if (destsRes.destinations.length > 0) {
            setSelectedDestId(destsRes.destinations[0].destination_id);
          }
        }
      } catch (err: any) {
        if (isCurrent) setError3D(err.message || 'Failed to load 3D subarea data');
      } finally {
        if (isCurrent) setLoading3D(false);
      }
    }

    loadSubareaData();
    return () => { isCurrent = false; };
  }, [selectedSubareaId]);

  // 3. Compute Evacuation Route
  const handleCalculateRoute = async () => {
    if (!selectedSubareaId || !selectedDestId) return;
    setCalculatingRoute(true);
    setRouteError(null);

    try {
      const res = await fetch(`${API_BASE}/subareas/${selectedSubareaId}/evacuation-route`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          destination_id: selectedDestId,
          vehicle_type: vehicleType,
        }),
      }).then(r => r.json());

      if (res.route_found) {
        setRoutingResult(res);
      } else {
        setRoutingResult(res);
        setRouteError(res.blocked_message || 'Evacuation corridor blocked by excessive flood depths.');
      }
    } catch (err: any) {
      setRouteError(err.message || 'Failed to compute evacuation corridor');
    } finally {
      setCalculatingRoute(false);
    }
  };

  // 4. Render 3D Canvas
  const render3DScene = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !terrainData || !terrainData.elevations) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    // Deep Dark Space / Modern GIS Backdrop
    const grad = ctx.createLinearGradient(0, 0, 0, height);
    grad.addColorStop(0, '#090d16');
    grad.addColorStop(1, '#0f172a');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, width, height);

    // Draw Subtle Spatial Background Grid
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
    ctx.lineWidth = 1;
    for (let x = 0; x < width; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    const elevations = terrainData.elevations;
    const subareaMask = terrainData.subarea_mask || [];
    const depths = floodData?.depths || [];
    const isFlooded = floodData?.is_flooded || [];
    const rows = elevations.length;
    const cols = elevations[0].length;
    const bounds = terrainData.bounds;

    const minElev = terrainData.min_elevation_m || 0;
    const maxElev = Math.max(terrainData.max_elevation_m || 50, minElev + 1);

    const cx = width / 2;
    const cy = height / 2 + 30;

    // Projection Function: Grid (r, c, elev) -> Screen (X, Y)
    const project = (r: number, c: number, zElev: number) => {
      // Center grid at origin
      const xNorm = (c - cols / 2);
      const yNorm = (r - rows / 2);

      // Rotate by azimuth (rotAngle)
      const cosA = Math.cos(rotAngle);
      const sinA = Math.sin(rotAngle);
      const xRot = xNorm * cosA - yNorm * sinA;
      const yRot = xNorm * sinA + yNorm * cosA;

      // Project isometric with tilt (tiltAngle) and vertical exaggeration
      const isoX = (xRot - yRot) * Math.cos(Math.PI / 6);
      const isoY = (xRot + yRot) * Math.sin(Math.PI / 6) * Math.sin(tiltAngle);

      // Elev offset
      const elevNorm = (zElev - minElev) * vertExaggeration;
      const zOffset = elevNorm * Math.cos(tiltAngle);

      const screenX = cx + isoX * zoom * 3.2;
      const screenY = cy + (isoY - zOffset) * zoom * 1.8;
      return { x: screenX, y: screenY, depthSort: xRot + yRot };
    };

    // Hypsometric tint color lookup
    const getTerrainColor = (elev: number, inMask: boolean) => {
      const t = Math.max(0, Math.min(1, (elev - minElev) / (maxElev - minElev)));
      if (!inMask && showContextFade) {
        // Faded Context Tint
        const val = Math.floor(40 + t * 50);
        return `rgb(${val}, ${val + 5}, ${val + 10})`;
      }
      // Topographic Palette: Coastal plains (deep emerald) -> Lowlands (tan) -> Ridges (slate/white)
      if (t < 0.25) {
        const r = Math.floor(16 + t * 40);
        const g = Math.floor(70 + t * 140);
        const b = Math.floor(40 + t * 60);
        return `rgb(${r}, ${g}, ${b})`;
      } else if (t < 0.65) {
        const t2 = (t - 0.25) / 0.4;
        const r = Math.floor(35 + t2 * 120);
        const g = Math.floor(105 + t2 * 60);
        const b = Math.floor(55 - t2 * 20);
        return `rgb(${r}, ${g}, ${b})`;
      } else {
        const t3 = (t - 0.65) / 0.35;
        const r = Math.floor(155 + t3 * 80);
        const g = Math.floor(165 + t3 * 70);
        const b = Math.floor(140 + t3 * 100);
        return `rgb(${r}, ${g}, ${b})`;
      }
    };

    // Scientific Flood Color Palette
    const getFloodColor = (depth: number) => {
      if (depth < 0.15) return 'rgba(56, 189, 248, 0.65)'; // Minor puddle: Light Sky Cyan
      if (depth < 0.30) return 'rgba(2, 132, 199, 0.78)';  // Street water: Strong Cyan
      if (depth < 0.60) return 'rgba(234, 179, 8, 0.85)';  // Waterlogging: Amber Warning
      if (depth < 1.00) return 'rgba(220, 38, 38, 0.88)';  // Deep Flood: Alert Crimson
      return 'rgba(124, 58, 237, 0.92)';                   // Severe Inundation: Violet Hazard
    };

    // Determine render order from back to front
    const rStart = Math.sin(rotAngle) >= 0 ? 0 : rows - 2;
    const rEnd = Math.sin(rotAngle) >= 0 ? rows - 1 : -1;
    const rStep = Math.sin(rotAngle) >= 0 ? 1 : -1;

    const cStart = Math.cos(rotAngle) >= 0 ? 0 : cols - 2;
    const cEnd = Math.cos(rotAngle) >= 0 ? cols - 1 : -1;
    const cStep = Math.cos(rotAngle) >= 0 ? 1 : -1;

    // ── DRAW 3D TERRAIN SURFACE ──
    for (let r = rStart; r !== rEnd; r += rStep) {
      for (let c = cStart; c !== cEnd; c += cStep) {
        const nextR = r + 1;
        const nextC = c + 1;
        if (nextR >= rows || nextC >= cols) continue;

        const p0 = project(r, c, elevations[r][c]);
        const p1 = project(r, nextC, elevations[r][nextC]);
        const p2 = project(nextR, nextC, elevations[nextR][nextC]);
        const p3 = project(nextR, c, elevations[nextR][c]);

        const inMask = Boolean(subareaMask[r]?.[c]);
        const avgElev = (elevations[r][c] + elevations[r][nextC] + elevations[nextR][nextC] + elevations[nextR][c]) / 4;

        ctx.beginPath();
        ctx.moveTo(p0.x, p0.y);
        ctx.lineTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.lineTo(p3.x, p3.y);
        ctx.closePath();

        if (renderMode === 'shaded') {
          ctx.fillStyle = getTerrainColor(avgElev, inMask);
          ctx.fill();
          ctx.strokeStyle = inMask ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.15)';
          ctx.lineWidth = 0.5;
          ctx.stroke();
        } else {
          ctx.strokeStyle = inMask ? '#38bdf8' : 'rgba(148, 163, 184, 0.25)';
          ctx.lineWidth = inMask ? 0.8 : 0.4;
          ctx.stroke();
        }

        // Active Subarea Border Edge Highlight
        if (inMask && (!subareaMask[r - 1]?.[c] || !subareaMask[r]?.[c - 1])) {
          ctx.strokeStyle = '#38bdf8';
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }

        // ── DRAPE 3D SIMULATED WATER SURFACE ──
        if (showWater && depths.length > 0) {
          const d0 = depths[r]?.[c] || 0;
          const d1 = depths[r]?.[nextC] || 0;
          const d2 = depths[nextR]?.[nextC] || 0;
          const d3 = depths[nextR]?.[c] || 0;

          const maxCellDepth = Math.max(d0, d1, d2, d3);
          // Strictly dry cells (h < 0.01m) remain transparent
          if (maxCellDepth >= 0.01) {
            const wp0 = project(r, c, elevations[r][c] + d0);
            const wp1 = project(r, nextC, elevations[r][nextC] + d1);
            const wp2 = project(nextR, nextC, elevations[nextR][nextC] + d2);
            const wp3 = project(nextR, c, elevations[nextR][c] + d3);

            ctx.beginPath();
            ctx.moveTo(wp0.x, wp0.y);
            ctx.lineTo(wp1.x, wp1.y);
            ctx.lineTo(wp2.x, wp2.y);
            ctx.lineTo(wp3.x, wp3.y);
            ctx.closePath();

            ctx.fillStyle = getFloodColor(maxCellDepth);
            ctx.fill();
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
            ctx.lineWidth = 0.6;
            ctx.stroke();
          }
        }
      }
    }

    // ── DRAW 3D DRAPED EVACUATION CORRIDOR ──
    if (routingResult?.geometry?.coordinates && routingResult.geometry.coordinates.length > 1) {
      const coords = routingResult.geometry.coordinates;
      const b = bounds;
      const routePoints: { x: number; y: number }[] = [];

      for (let k = 0; k < coords.length; k++) {
        const [lon, lat] = coords[k];
        // Normalize to grid [0..rows-1, 0..cols-1]
        const cFloat = ((lon - b.min_lon) / (b.max_lon - b.min_lon)) * (cols - 1);
        const rFloat = ((b.max_lat - lat) / (b.max_lat - b.min_lat)) * (rows - 1);

        const rInt = Math.max(0, Math.min(rows - 1, Math.round(rFloat)));
        const cInt = Math.max(0, Math.min(cols - 1, Math.round(cFloat)));
        const elev = (elevations[rInt]?.[cInt] || minElev) + 1.2;

        const pt = project(rFloat, cFloat, elev);
        routePoints.push(pt);
      }

      // Draw Glowing Route Polyline
      ctx.shadowColor = '#10b981';
      ctx.shadowBlur = 12;
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 4.5;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';

      ctx.beginPath();
      ctx.moveTo(routePoints[0].x, routePoints[0].y);
      for (let k = 1; k < routePoints.length; k++) {
        ctx.lineTo(routePoints[k].x, routePoints[k].y);
      }
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Route Outer Line
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.8;
      ctx.stroke();

      // Start Pin (Origin)
      const startPt = routePoints[0];
      ctx.fillStyle = '#3b82f6';
      ctx.beginPath();
      ctx.arc(startPt.x, startPt.y, 7, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Destination Pin (Shelter/Hospital)
      const endPt = routePoints[routePoints.length - 1];
      ctx.fillStyle = '#10b981';
      ctx.beginPath();
      ctx.arc(endPt.x, endPt.y, 9, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2.5;
      ctx.stroke();

      // Destination Pin Label
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 11px sans-serif';
      ctx.fillText(`🏁 ${routingResult.destination_name}`, endPt.x + 12, endPt.y + 4);
    }

    // ── HUD OVERLAY: Compass & Orientation ──
    const compassX = 55;
    const compassY = height - 55;
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(compassX, compassY, 26, 0, Math.PI * 2);
    ctx.stroke();

    // North Indicator Arrow
    const northAngle = -rotAngle - Math.PI / 4;
    const nx = compassX + Math.sin(northAngle) * 20;
    const ny = compassY - Math.cos(northAngle) * 20;

    ctx.strokeStyle = '#ef4444';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(compassX, compassY);
    ctx.lineTo(nx, ny);
    ctx.stroke();

    ctx.fillStyle = '#ef4444';
    ctx.font = 'bold 11px sans-serif';
    ctx.fillText('N', nx - 4, ny - 6);

  }, [terrainData, floodData, rotAngle, tiltAngle, zoom, vertExaggeration, renderMode, showWater, showContextFade, routingResult]);

  useEffect(() => {
    render3DScene();
  }, [render3DScene]);

  // ── Mouse Drag Interaction Handlers ──
  const handleMouseDown = (e: React.MouseEvent) => {
    isDraggingRef.current = true;
    lastMousePosRef.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDraggingRef.current) return;
    const dx = e.clientX - lastMousePosRef.current.x;
    const dy = e.clientY - lastMousePosRef.current.y;
    lastMousePosRef.current = { x: e.clientX, y: e.clientY };

    setRotAngle(prev => prev + dx * 0.008);
    setTiltAngle(prev => Math.max(0.1, Math.min(Math.PI / 2.5, prev - dy * 0.006)));
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    setZoom(prev => Math.max(1.5, Math.min(8.0, prev - e.deltaY * 0.002)));
  };

  const resetCamera = () => {
    setRotAngle(Math.PI / 4);
    setTiltAngle(Math.PI / 6);
    setZoom(3.5);
    setVertExaggeration(1.8);
  };

  const subareasByWard = subareas.reduce((acc: { [ward: string]: SubareaItem[] }, item) => {
    const w = item.parent_ward_id || 'Other';
    if (!acc[w]) acc[w] = [];
    acc[w].push(item);
    return acc;
  }, {});

  const currentSubarea = subareas.find(s => s.subarea_id === selectedSubareaId);

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      width: '100%', background: '#090d16', color: '#f8fafc',
      position: 'relative', overflow: 'hidden', minHeight: '620px', borderRadius: '12px',
      border: '1px solid rgba(255, 255, 255, 0.1)'
    }}>

      {/* ── TOP CONTROL & SUBAREA SELECTION STRIP ── */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 16px', background: 'rgba(15, 23, 42, 0.95)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
        backdropFilter: 'blur(8px)', zIndex: 30, flexWrap: 'wrap', gap: '8px'
      }}>
        {/* Left: Subarea Selector & Info */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Mountain size={18} color="#38bdf8" />
            <span style={{ fontSize: '13px', fontWeight: 800, letterSpacing: '0.5px', color: '#ffffff' }}>
              3D SUBAREA EVACUATION NAVIGATOR
            </span>
            <span style={{ fontSize: '10px', background: '#059669', color: '#ffffff', padding: '2px 6px', borderRadius: '4px', fontWeight: 700 }}>
              LIVE GIS 3D
            </span>
          </div>

          {/* Dynamic Subarea Dropdown */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <label style={{ fontSize: '11px', color: '#94a3b8', fontWeight: 600 }}>Subarea:</label>
            <select
              value={selectedSubareaId}
              onChange={(e) => setSelectedSubareaId(e.target.value)}
              style={{
                background: '#1e293b', border: '1px solid #334155', color: '#f8fafc',
                fontSize: '12px', padding: '5px 10px', borderRadius: '6px', fontWeight: 600,
                outline: 'none', maxWidth: '300px', cursor: 'pointer'
              }}
              disabled={loadingSubareas}
            >
              {Object.keys(subareasByWard).sort().map(wardId => (
                <optgroup key={wardId} label={`BMC Ward ${wardId}`}>
                  {subareasByWard[wardId].map(sub => (
                    <option key={sub.subarea_id} value={sub.subarea_id}>
                      {sub.subarea_id} — {sub.name.length > 36 ? sub.name.substring(0, 36) + '...' : sub.name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>

          {currentSubarea && (
            <span style={{ fontSize: '11px', color: '#94a3b8' }}>
              Area: <strong style={{ color: '#38bdf8' }}>{currentSubarea.area_sq_km} km²</strong>
            </span>
          )}
        </div>

        {/* Right: Camera Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => setRenderMode(prev => prev === 'shaded' ? 'wireframe' : 'shaded')}
            style={{
              display: 'flex', alignItems: 'center', gap: '4px', padding: '5px 9px',
              borderRadius: '6px', background: renderMode === 'wireframe' ? '#0284c7' : '#1e293b',
              border: '1px solid #334155', color: '#ffffff', fontSize: '11px', cursor: 'pointer'
            }}
          >
            <Layers size={13} /> {renderMode === 'shaded' ? 'Wireframe' : 'Shaded'}
          </button>

          <button
            onClick={() => setShowWater(prev => !prev)}
            style={{
              display: 'flex', alignItems: 'center', gap: '4px', padding: '5px 9px',
              borderRadius: '6px', background: showWater ? '#0369a1' : '#1e293b',
              border: '1px solid #334155', color: '#ffffff', fontSize: '11px', cursor: 'pointer'
            }}
          >
            <Waves size={13} /> {showWater ? 'Water ON' : 'Water OFF'}
          </button>

          <button
            onClick={() => setZoom(prev => Math.min(8.0, prev + 0.5))}
            style={{ padding: '5px 8px', borderRadius: '6px', background: '#1e293b', border: '1px solid #334155', color: '#ffffff', cursor: 'pointer' }}
          >
            <ZoomIn size={14} />
          </button>
          <button
            onClick={() => setZoom(prev => Math.max(1.5, prev - 0.5))}
            style={{ padding: '5px 8px', borderRadius: '6px', background: '#1e293b', border: '1px solid #334155', color: '#ffffff', cursor: 'pointer' }}
          >
            <ZoomOut size={14} />
          </button>
          <button
            onClick={resetCamera}
            style={{ padding: '5px 8px', borderRadius: '6px', background: '#1e293b', border: '1px solid #334155', color: '#ffffff', cursor: 'pointer' }}
          >
            <RotateCcw size={14} />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              style={{
                padding: '5px 12px', borderRadius: '6px', background: '#dc2626',
                border: 'none', color: '#ffffff', fontSize: '11px', fontWeight: 700, cursor: 'pointer'
              }}
            >
              Close 3D
            </button>
          )}
        </div>
      </div>

      {/* ── WORKSPACE BODY ── */}
      <div style={{ flex: 1, display: 'flex', position: 'relative', overflow: 'hidden' }}>

        {/* ── 3D CANVAS VIEWPORT ── */}
        <div
          style={{ flex: 1, position: 'relative', height: '100%', minHeight: '520px', cursor: 'grab' }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
        >
          <canvas
            ref={canvasRef}
            width={1200}
            height={700}
            style={{ width: '100%', height: '100%', display: 'block' }}
          />

          {loading3D && (
            <div style={{
              position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
              background: 'rgba(15, 23, 42, 0.85)', padding: '16px 24px', borderRadius: '8px',
              border: '1px solid #38bdf8', display: 'flex', alignItems: 'center', gap: '10px',
              color: '#ffffff', fontSize: '13px', fontWeight: 600
            }}>
              <RefreshCw size={18} className="spin" color="#38bdf8" />
              Loading 3D Terrain & Flood Elevation Mesh...
            </div>
          )}

          {error3D && (
            <div style={{
              position: 'absolute', top: '20px', left: '20px',
              background: 'rgba(220, 38, 38, 0.9)', padding: '10px 16px', borderRadius: '6px',
              color: '#ffffff', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px'
            }}>
              <AlertTriangle size={16} /> {error3D}
            </div>
          )}

          {/* Navigation Hint */}
          <div style={{
            position: 'absolute', bottom: '14px', left: '16px',
            background: 'rgba(15, 23, 42, 0.75)', padding: '6px 12px', borderRadius: '6px',
            border: '1px solid rgba(255, 255, 255, 0.1)', fontSize: '10.5px', color: '#94a3b8'
          }}>
            🖱️ <strong>Left Click + Drag</strong> to rotate & pitch | <strong>Scroll</strong> to zoom
          </div>

          {/* 3D Flood Color Legend */}
          <div style={{
            position: 'absolute', bottom: '14px', right: '16px',
            background: 'rgba(15, 23, 42, 0.85)', padding: '10px 14px', borderRadius: '8px',
            border: '1px solid rgba(255, 255, 255, 0.15)', backdropFilter: 'blur(6px)',
            fontSize: '11px', display: 'flex', flexDirection: 'column', gap: '6px'
          }}>
            <span style={{ fontWeight: 700, color: '#f8fafc', fontSize: '10.5px', textTransform: 'uppercase' }}>
              Modeled Water Depth $h$
            </span>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px', fontSize: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '12px', height: '10px', background: '#38bdf8', borderRadius: '2px' }} />
                <span>&lt;0.15m Minor</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '12px', height: '10px', background: '#0284c7', borderRadius: '2px' }} />
                <span>0.15–0.30m Street</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '12px', height: '10px', background: '#eab308', borderRadius: '2px' }} />
                <span>0.30–0.60m Waterlog</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '12px', height: '10px', background: '#dc2626', borderRadius: '2px' }} />
                <span>0.60–1.00m Deep</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', gridColumn: 'span 2' }}>
                <span style={{ width: '12px', height: '10px', background: '#7c3aed', borderRadius: '2px' }} />
                <span>&gt;1.00m Severe Inundation</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── RIGHT DOCKED SIDEBAR: EVACUATION & NEIGHBORS ── */}
        <aside style={{
          width: '380px', background: '#0f172a', borderLeft: '1px solid rgba(255, 255, 255, 0.1)',
          display: 'flex', flexDirection: 'column', overflowY: 'auto', zIndex: 20
        }}>

          {/* Subarea Details & Neighbors */}
          <div style={{ padding: '14px 16px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
            <h3 style={{ fontSize: '13px', fontWeight: 800, color: '#38bdf8', textTransform: 'uppercase', margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Compass size={15} /> Topological Subarea Context
            </h3>

            {subareaDetail?.neighbors && subareaDetail.neighbors.length > 0 && (
              <div style={{ marginTop: '8px' }}>
                <div style={{ fontSize: '10.5px', color: '#94a3b8', marginBottom: '6px' }}>
                  Adjacent Sectors ({subareaDetail.neighbors.length}):
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                  {subareaDetail.neighbors.map((nb: any) => (
                    <button
                      key={nb.neighbor_subarea_id}
                      onClick={() => setSelectedSubareaId(nb.neighbor_subarea_id)}
                      style={{
                        padding: '3px 7px', borderRadius: '4px', background: '#1e293b',
                        border: '1px solid #334155', color: '#38bdf8', fontSize: '10.5px',
                        cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '3px'
                      }}
                    >
                      <span>{nb.neighbor_subarea_id}</span>
                      <ArrowRight size={9} />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Evacuation Routing Console */}
          <div style={{ padding: '16px', flex: 1 }}>
            <h3 style={{ fontSize: '13px', fontWeight: 800, color: '#10b981', textTransform: 'uppercase', margin: '0 0 10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Navigation size={16} /> Live Evacuation Route
            </h3>
            <p style={{ fontSize: '11px', color: '#94a3b8', margin: '0 0 12px', lineHeight: 1.4 }}>
              Dijkstra routing over 14,563 OSM road corridors with dynamic flood impedance.
            </p>

            {/* Vehicle Mode */}
            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '11px', color: '#cbd5e1', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
                Vehicle Clearance:
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                <button
                  onClick={() => setVehicleType('standard_car')}
                  style={{
                    padding: '6px', borderRadius: '6px',
                    background: vehicleType === 'standard_car' ? '#0369a1' : '#1e293b',
                    border: vehicleType === 'standard_car' ? '1.5px solid #38bdf8' : '1px solid #334155',
                    color: '#ffffff', fontSize: '10.5px', fontWeight: 600, cursor: 'pointer'
                  }}
                >
                  🚗 Car (Safe &lt;0.30m)
                </button>
                <button
                  onClick={() => setVehicleType('emergency_high_clearance')}
                  style={{
                    padding: '6px', borderRadius: '6px',
                    background: vehicleType === 'emergency_high_clearance' ? '#0369a1' : '#1e293b',
                    border: vehicleType === 'emergency_high_clearance' ? '1.5px solid #38bdf8' : '1px solid #334155',
                    color: '#ffffff', fontSize: '10.5px', fontWeight: 600, cursor: 'pointer'
                  }}
                >
                  🚒 High Clearance (&lt;0.50m)
                </button>
              </div>
            </div>

            {/* Destination Selector */}
            <div style={{ marginBottom: '14px' }}>
              <label style={{ fontSize: '11px', color: '#cbd5e1', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
                Designated Safe Destination:
              </label>
              <select
                value={selectedDestId}
                onChange={(e) => setSelectedDestId(e.target.value)}
                style={{
                  width: '100%', background: '#1e293b', border: '1px solid #334155',
                  color: '#f8fafc', fontSize: '11px', padding: '7px', borderRadius: '6px',
                  outline: 'none', cursor: 'pointer'
                }}
              >
                {destinations.map(d => (
                  <option key={d.destination_id} value={d.destination_id}>
                    {d.name} ({d.category} — {d.distance_km} km)
                  </option>
                ))}
              </select>
            </div>

            {/* Calculate Button */}
            <button
              onClick={handleCalculateRoute}
              disabled={calculatingRoute || !selectedDestId}
              style={{
                width: '100%', padding: '10px', borderRadius: '6px',
                background: calculatingRoute ? '#334155' : 'linear-gradient(135deg, #059669, #10b981)',
                border: 'none', color: '#ffffff', fontSize: '11.5px', fontWeight: 700,
                cursor: calculatingRoute ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                marginBottom: '12px'
              }}
            >
              {calculatingRoute ? (
                <>
                  <RefreshCw size={14} className="spin" />
                  Routing via OSM Network...
                </>
              ) : (
                <>
                  <Navigation size={14} />
                  Calculate Evacuation Corridor
                </>
              )}
            </button>

            {/* Route Output Summary Card */}
            {routingResult && (
              <div style={{
                background: '#1e293b', border: '1px solid #334155', borderRadius: '8px',
                padding: '12px', marginBottom: '12px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: '#f8fafc' }}>
                    {routingResult.destination_name}
                  </span>
                  <span style={{
                    fontSize: '9.5px', fontWeight: 800, padding: '2px 6px', borderRadius: '4px',
                    background: routingResult.route_found ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                    color: routingResult.route_found ? '#34d399' : '#f87171',
                    border: routingResult.route_found ? '1px solid #10b981' : '1px solid #ef4444'
                  }}>
                    {routingResult.passability_verdict}
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginBottom: '8px' }}>
                  <div style={{ background: '#0f172a', padding: '6px 8px', borderRadius: '4px' }}>
                    <div style={{ fontSize: '9.5px', color: '#94a3b8' }}>Distance</div>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: '#ffffff' }}>
                      {routingResult.total_distance_km.toFixed(2)} km
                    </div>
                  </div>
                  <div style={{ background: '#0f172a', padding: '6px 8px', borderRadius: '4px' }}>
                    <div style={{ fontSize: '9.5px', color: '#94a3b8' }}>Est. Time</div>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: '#38bdf8' }}>
                      {routingResult.estimated_travel_time_min.toFixed(0)} min
                    </div>
                  </div>
                </div>

                {/* MANDATORY DISCLAIMER AS REQUIRED BY PHASE 4 */}
                <div style={{
                  background: 'rgba(234, 179, 8, 0.1)', border: '1px solid rgba(234, 179, 8, 0.3)',
                  borderRadius: '6px', padding: '8px', display: 'flex', alignItems: 'flex-start',
                  gap: '6px', fontSize: '9.5px', color: '#fef08a', lineHeight: 1.35
                }}>
                  <AlertTriangle size={14} color="#eab308" style={{ flexShrink: 0, marginTop: '1px' }} />
                  <div>
                    <strong>SAFETY ADVISORY:</strong> {routingResult.disclaimer}
                  </div>
                </div>
              </div>
            )}

            {/* Blocked Route Alert */}
            {routeError && !routingResult?.route_found && (
              <div style={{
                background: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444',
                borderRadius: '8px', padding: '10px', display: 'flex', alignItems: 'flex-start',
                gap: '6px', color: '#fca5a5', fontSize: '10.5px'
              }}>
                <XCircle size={16} color="#ef4444" style={{ flexShrink: 0 }} />
                <div>
                  <strong>ALL GROUND ROUTES IMPASSABLE:</strong> {routeError}
                  <div style={{ marginTop: '4px', color: '#ffffff', fontWeight: 700 }}>
                    Seek immediate vertical shelter on upper floors.
                  </div>
                </div>
              </div>
            )}

          </div>
        </aside>
      </div>

    </div>
  );
};

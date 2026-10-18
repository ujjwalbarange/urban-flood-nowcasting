'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Compass, RotateCcw, ZoomIn, ZoomOut, Eye, Layers, Shield,
  AlertTriangle, Navigation, CheckCircle2, ChevronDown,
  Building, Hospital, Waves, Mountain, RefreshCw, X, Sliders
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api/v1';

export interface Unified3DTerrainCanvasProps {
  selectedLocation: { lat: number; lon: number } | null;
  onSelectLocation: (lat: number, lon: number) => void;
  activeRoute?: any | null;
  timelineMinute?: number;
  showWaterOverlay?: boolean;
  onClose3D?: () => void;
}

interface SubareaOption {
  subarea_id: string;
  name: string;
  parent_ward_id: string;
}

export const Unified3DTerrainCanvas: React.FC<Unified3DTerrainCanvasProps> = ({
  selectedLocation,
  onSelectLocation,
  activeRoute,
  timelineMinute = 0,
  showWaterOverlay = true,
  onClose3D,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // ── Focus & Hierarchy State ──
  const [focusMode, setFocusMode] = useState<string>('citywide'); // 'citywide' or subarea_id
  const [subareasList, setSubareasList] = useState<SubareaOption[]>([]);
  const [loadingTerrain, setLoadingTerrain] = useState<boolean>(true);
  const [terrainError, setTerrainError] = useState<string | null>(null);

  // ── Terrain & Flood Heightfield Data ──
  const [terrainData, setTerrainData] = useState<any | null>(null);
  const [floodData, setFloodData] = useState<any | null>(null);

  // ── Realistic Camera Controls (Natural Scale Default) ──
  const [azimuth, setAzimuth] = useState<number>(Math.PI * 0.15);
  const [pitch, setPitch] = useState<number>(Math.PI * 0.22);
  const [zoom, setZoom] = useState<number>(1.1);
  const [vertExaggeration, setVertExaggeration] = useState<number>(1.2);
  const [renderMode, setRenderMode] = useState<'shaded' | 'wireframe'>('shaded');
  const [showWater, setShowWater] = useState<boolean>(showWaterOverlay);
  const [showContextFade, setShowContextFade] = useState<boolean>(true);
  const [showControlsDrawer, setShowControlsDrawer] = useState<boolean>(false);

  // ── Mouse Drag / Click Tracking ──
  const isDraggingRef = useRef(false);
  const dragStartPosRef = useRef({ x: 0, y: 0 });
  const dragDeltaRef = useRef({ x: 0, y: 0 });

  // 1. Discover all subareas dynamically (never hardcoded)
  useEffect(() => {
    async function fetchSubareas() {
      try {
        const res = await fetch(`${API_BASE}/subareas`).then(r => r.json());
        if (res.subareas) {
          setSubareasList(res.subareas);
        }
      } catch { /* subareas list fallback */ }
    }
    fetchSubareas();
  }, []);

  // 2. Fetch Terrain & Flood Data whenever focus area or timeline minute changes
  useEffect(() => {
    let active = true;
    async function load3DData() {
      setLoadingTerrain(true);
      setTerrainError(null);
      try {
        let terrainUrl = `${API_BASE}/subareas/city-terrain-3d?target_dim=96`;
        let floodUrl = `${API_BASE}/subareas/city-flood-3d?target_dim=96&minute=${timelineMinute}`;

        if (focusMode !== 'citywide') {
          terrainUrl = `${API_BASE}/subareas/${focusMode}/terrain3d?target_dim=80`;
          floodUrl = `${API_BASE}/subareas/${focusMode}/flood3d?target_dim=80&minute=${timelineMinute}`;
        }

        const [tRes, fRes] = await Promise.all([
          fetch(terrainUrl).then(r => r.ok ? r.json() : null),
          fetch(floodUrl).then(r => r.ok ? r.json() : null),
        ]);

        if (!active) return;
        if (tRes && tRes.elevations) {
          setTerrainData(tRes);
        } else {
          throw new Error('Copernicus GLO-30 DEM heightfield unavailable.');
        }

        if (fRes) {
          setFloodData(fRes);
        }
      } catch (err: any) {
        if (active) {
          setTerrainError(err.message || 'Failed to initialize 3D terrain surface.');
        }
      } finally {
        if (active) setLoadingTerrain(false);
      }
    }

    load3DData();
    return () => { active = false; };
  }, [focusMode, timelineMinute]);

  useEffect(() => {
    setShowWater(showWaterOverlay);
  }, [showWaterOverlay]);

  // 3. Coordinate Projection Math: Geographic (lon, lat, elev) -> Screen (X, Y)
  const projectPoint = useCallback((
    lon: number,
    lat: number,
    elev: number,
    bounds: { min_lon: number; max_lon: number; min_lat: number; max_lat: number },
    width_m: number,
    height_m: number,
    canvasWidth: number,
    canvasHeight: number,
    minElev: number,
  ) => {
    const c_lon = (bounds.min_lon + bounds.max_lon) / 2.0;
    const c_lat = (bounds.min_lat + bounds.max_lat) / 2.0;

    const dx_m = (lon - c_lon) * 111320.0 * Math.cos((c_lat * Math.PI) / 180.0);
    const dy_m = -(lat - c_lat) * 110700.0;

    const z_m = Math.max(0, elev - minElev) * vertExaggeration;

    const cosA = Math.cos(azimuth);
    const sinA = Math.sin(azimuth);
    const x_rot = dx_m * cosA - dy_m * sinA;
    const y_rot = dx_m * sinA + dy_m * cosA;

    const maxDim_m = Math.max(width_m, height_m);
    const minDim_px = Math.min(canvasWidth, canvasHeight);
    const scale = (minDim_px * 0.72 * zoom) / maxDim_m;

    const sinP = Math.sin(pitch);
    const cosP = Math.cos(pitch);

    const screenX = canvasWidth / 2.0 + x_rot * scale;
    const screenY = canvasHeight / 2.0 + (y_rot * sinP - z_m * scale * cosP);
    const depthSort = y_rot;

    return { x: screenX, y: screenY, depthSort, scale };
  }, [azimuth, pitch, zoom, vertExaggeration]);

  // 4. Unproject Screen (X, Y) -> Geographic (lat, lon) for click-to-select
  const unprojectPoint = useCallback((screenX: number, screenY: number) => {
    if (!terrainData || !terrainData.bounds) return null;
    const canvas = canvasRef.current;
    if (!canvas) return null;

    const bounds = terrainData.bounds;
    const width_m = terrainData.dimensions.width_m || 31500;
    const height_m = terrainData.dimensions.height_m || 48700;
    const maxDim_m = Math.max(width_m, height_m);
    const minDim_px = Math.min(canvas.width, canvas.height);
    const scale = (minDim_px * 0.72 * zoom) / maxDim_m;

    const c_lon = (bounds.min_lon + bounds.max_lon) / 2.0;
    const c_lat = (bounds.min_lat + bounds.max_lat) / 2.0;

    const sinP = Math.sin(pitch);
    const cosA = Math.cos(azimuth);
    const sinA = Math.sin(azimuth);

    const relX = (screenX - canvas.width / 2.0) / scale;
    const relY = (screenY - canvas.height / 2.0) / (scale * Math.max(sinP, 0.15));

    const dx_m = relX * cosA + relY * sinA;
    const dy_m = -relX * sinA + relY * cosA;

    const lon = c_lon + dx_m / (111320.0 * Math.cos((c_lat * Math.PI) / 180.0));
    const lat = c_lat - dy_m / 110700.0;

    if (lon < bounds.min_lon - 0.05 || lon > bounds.max_lon + 0.05 ||
        lat < bounds.min_lat - 0.05 || lat > bounds.max_lat + 0.05) {
      return null;
    }

    return { lat, lon };
  }, [terrainData, zoom, pitch, azimuth]);

  // 5. Main Canvas Rendering Loop
  const renderScene = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !terrainData || !terrainData.elevations) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    const bgGrad = ctx.createLinearGradient(0, 0, 0, height);
    bgGrad.addColorStop(0, '#0b1329');
    bgGrad.addColorStop(1, '#1e293b');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, width, height);

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.035)';
    ctx.lineWidth = 1;
    for (let x = 0; x < width; x += 48) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += 48) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    const elevations: number[][] = terrainData.elevations;
    const rows = elevations.length;
    const cols = elevations[0].length;
    const bounds = terrainData.bounds;
    const width_m = terrainData.dimensions.width_m || 31500;
    const height_m = terrainData.dimensions.height_m || 48700;
    const minElev = terrainData.min_elevation_m || 0.0;
    const maxElev = Math.max(terrainData.max_elevation_m || 50, minElev + 1);

    const subareaMask: boolean[][] = terrainData.subarea_mask || [];
    const floodDepths: number[][] = floodData?.depths || [];

    const projectedGrid: Array<Array<{ x: number; y: number; depthSort: number }>> = [];
    const waterProjectedGrid: Array<Array<{ x: number; y: number } | null>> = [];

    for (let r = 0; r < rows; r++) {
      projectedGrid[r] = [];
      waterProjectedGrid[r] = [];
      const lat = bounds.max_lat - r * (bounds.max_lat - bounds.min_lat) / (rows - 1);

      for (let c = 0; c < cols; c++) {
        const lon = bounds.min_lon + c * (bounds.max_lon - bounds.min_lon) / (cols - 1);
        const elev = elevations[r][c];

        const pt = projectPoint(
          lon, lat, elev, bounds, width_m, height_m, width, height, minElev
        );
        projectedGrid[r][c] = pt;

        const depth = floodDepths[r]?.[c] || 0.0;
        if (showWater && depth >= 0.01) {
          const waterPt = projectPoint(
            lon, lat, elev + depth, bounds, width_m, height_m, width, height, minElev
          );
          waterProjectedGrid[r][c] = { x: waterPt.x, y: waterPt.y };
        } else {
          waterProjectedGrid[r][c] = null;
        }
      }
    }

    interface QuadFace {
      r: number;
      c: number;
      depthSort: number;
      meanElev: number;
      inMask: boolean;
      depth: number;
    }

    const quads: QuadFace[] = [];
    for (let r = 0; r < rows - 1; r++) {
      for (let c = 0; c < cols - 1; c++) {
        const p0 = projectedGrid[r][c];
        const p1 = projectedGrid[r][c + 1];
        const p2 = projectedGrid[r + 1][c + 1];
        const p3 = projectedGrid[r + 1][c];

        const avgDepthSort = (p0.depthSort + p1.depthSort + p2.depthSort + p3.depthSort) / 4.0;
        const meanElev = (elevations[r][c] + elevations[r][c + 1] + elevations[r + 1][c + 1] + elevations[r + 1][c]) / 4.0;
        const inMask = subareaMask.length > 0 ? Boolean(subareaMask[r]?.[c]) : true;
        const depth = floodDepths[r]?.[c] || 0.0;

        quads.push({ r, c, depthSort: avgDepthSort, meanElev, inMask, depth });
      }
    }

    quads.sort((a, b) => b.depthSort - a.depthSort);

    const lx = -0.5;
    const ly = -0.5;
    const lz = 0.707;

    const getTerrainFill = (r: number, c: number, elev: number, inMask: boolean) => {
      const t = Math.max(0, Math.min(1, (elev - minElev) / (maxElev - minElev)));

      let dz_dx = 0;
      let dz_dy = 0;
      if (c + 1 < cols && c > 0) {
        dz_dx = (elevations[r][c + 1] - elevations[r][c - 1]) * 0.5;
      }
      if (r + 1 < rows && r > 0) {
        dz_dy = (elevations[r + 1][c] - elevations[r - 1][c]) * 0.5;
      }

      const normLen = Math.sqrt(dz_dx * dz_dx + dz_dy * dz_dy + 1.0);
      const nx = -dz_dx / normLen;
      const ny = -dz_dy / normLen;
      const nz = 1.0 / normLen;
      const dot = Math.max(0, nx * lx + ny * ly + nz * lz);
      const hillshade = 0.75 + dot * 0.45;

      if (!inMask && showContextFade && focusMode !== 'citywide') {
        const shade = Math.floor(45 * hillshade);
        return `rgb(${shade}, ${shade + 4}, ${shade + 10})`;
      }

      let baseR = 74, baseG = 135, baseB = 85;
      if (t < 0.12) {
        const f = t / 0.12;
        baseR = Math.floor(65 + f * 45);
        baseG = Math.floor(130 + f * 35);
        baseB = Math.floor(80 - f * 20);
      } else if (t < 0.40) {
        const f = (t - 0.12) / 0.28;
        baseR = Math.floor(110 + f * 70);
        baseG = Math.floor(165 - f * 20);
        baseB = Math.floor(60 - f * 20);
      } else if (t < 0.75) {
        const f = (t - 0.40) / 0.35;
        baseR = Math.floor(180 + f * 20);
        baseG = Math.floor(145 - f * 40);
        baseB = Math.floor(40 + f * 20);
      } else {
        const f = (t - 0.75) / 0.25;
        baseR = Math.floor(140 - f * 40);
        baseG = Math.floor(145 - f * 35);
        baseB = Math.floor(155 - f * 30);
      }

      const rVal = Math.min(255, Math.floor(baseR * hillshade));
      const gVal = Math.min(255, Math.floor(baseG * hillshade));
      const bVal = Math.min(255, Math.floor(baseB * hillshade));
      return `rgb(${rVal}, ${gVal}, ${bVal})`;
    };

    const getWaterFill = (depth: number) => {
      if (depth < 0.15) return 'rgba(56, 189, 248, 0.72)';
      if (depth < 0.30) return 'rgba(2, 132, 199, 0.82)';
      if (depth < 0.60) return 'rgba(234, 179, 8, 0.86)';
      if (depth < 1.00) return 'rgba(234, 88, 12, 0.90)';
      return 'rgba(220, 38, 38, 0.94)';
    };

    for (const q of quads) {
      const p0 = projectedGrid[q.r][q.c];
      const p1 = projectedGrid[q.r][q.c + 1];
      const p2 = projectedGrid[q.r + 1][q.c + 1];
      const p3 = projectedGrid[q.r + 1][q.c];

      ctx.beginPath();
      ctx.moveTo(p0.x, p0.y);
      ctx.lineTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.lineTo(p3.x, p3.y);
      ctx.closePath();

      if (renderMode === 'shaded') {
        ctx.fillStyle = getTerrainFill(q.r, q.c, q.meanElev, q.inMask);
        ctx.fill();
        ctx.strokeStyle = 'rgba(0, 0, 0, 0.08)';
        ctx.lineWidth = 0.5;
        ctx.stroke();
      } else {
        ctx.strokeStyle = q.inMask ? 'rgba(34, 197, 94, 0.65)' : 'rgba(100, 116, 139, 0.35)';
        ctx.lineWidth = 0.8;
        ctx.stroke();
      }

      if (showWater && q.depth >= 0.01) {
        const wp0 = waterProjectedGrid[q.r][q.c] || p0;
        const wp1 = waterProjectedGrid[q.r][q.c + 1] || p1;
        const wp2 = waterProjectedGrid[q.r + 1][q.c + 1] || p2;
        const wp3 = waterProjectedGrid[q.r + 1][q.c] || p3;

        ctx.beginPath();
        ctx.moveTo(wp0.x, wp0.y);
        ctx.lineTo(wp1.x, wp1.y);
        ctx.lineTo(wp2.x, wp2.y);
        ctx.lineTo(wp3.x, wp3.y);
        ctx.closePath();

        ctx.fillStyle = getWaterFill(q.depth);
        ctx.fill();
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.4)';
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }
    }

    // 6. Drape Active Evacuation Route Polyline across 3D Terrain
    if (activeRoute?.geometry?.coordinates && activeRoute.geometry.coordinates.length > 1) {
      const coords: [number, number][] = activeRoute.geometry.coordinates;
      const pts: Array<{ x: number; y: number }> = [];

      for (let i = 0; i < coords.length; i++) {
        const lon = coords[i][0];
        const lat = coords[i][1];
        const r_idx = Math.max(0, Math.min(rows - 1, (bounds.max_lat - lat) / (bounds.max_lat - bounds.min_lat) * (rows - 1)));
        const c_idx = Math.max(0, Math.min(cols - 1, (lon - bounds.min_lon) / (bounds.max_lon - bounds.min_lon) * (cols - 1)));
        const r0 = Math.floor(r_idx);
        const c0 = Math.floor(c_idx);
        const baseElev = elevations[r0]?.[c0] || minElev;
        const pt = projectPoint(lon, lat, baseElev + 1.5, bounds, width_m, height_m, width, height, minElev);
        pts.push(pt);
      }

      if (pts.length > 1) {
        const isClear = (activeRoute.passability_verdict || '').includes('CLEAR');
        const routeColor = isClear ? '#06b6d4' : '#f59e0b';

        ctx.beginPath();
        ctx.moveTo(pts[0].x, pts[0].y);
        for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
        ctx.strokeStyle = isClear ? 'rgba(6, 182, 212, 0.35)' : 'rgba(245, 158, 11, 0.35)';
        ctx.lineWidth = 8;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(pts[0].x, pts[0].y);
        for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
        ctx.strokeStyle = routeColor;
        ctx.lineWidth = 3.5;
        ctx.stroke();

        const destPt = pts[pts.length - 1];
        ctx.beginPath();
        ctx.arc(destPt.x, destPt.y, 8, 0, Math.PI * 2);
        ctx.fillStyle = '#10b981';
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.font = 'bold 11px system-ui, -apple-system, sans-serif';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.fillText(`🏁 ${activeRoute.destination_name || 'Emergency Shelter'}`, destPt.x, destPt.y - 14);
      }
    }

    // 7. Drape Selected Origin Pin Marker
    if (selectedLocation) {
      const r_idx = Math.max(0, Math.min(rows - 1, (bounds.max_lat - selectedLocation.lat) / (bounds.max_lat - bounds.min_lat) * (rows - 1)));
      const c_idx = Math.max(0, Math.min(cols - 1, (selectedLocation.lon - bounds.min_lon) / (bounds.max_lon - bounds.min_lon) * (cols - 1)));
      const baseElev = elevations[Math.floor(r_idx)]?.[Math.floor(c_idx)] || minElev;

      const selPt = projectPoint(
        selectedLocation.lon, selectedLocation.lat, baseElev + 2.0,
        bounds, width_m, height_m, width, height, minElev
      );

      ctx.beginPath();
      ctx.arc(selPt.x, selPt.y, 14, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(59, 130, 246, 0.5)';
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(selPt.x, selPt.y, 6, 0, Math.PI * 2);
      ctx.fillStyle = '#ef4444';
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(selPt.x, selPt.y);
      ctx.lineTo(selPt.x, selPt.y + 12);
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.font = 'bold 10px system-ui, sans-serif';
      ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
      const tagText = `${selectedLocation.lat.toFixed(4)}°N, ${selectedLocation.lon.toFixed(4)}°E (${baseElev.toFixed(1)}m)`;
      const textWidth = ctx.measureText(tagText).width;
      ctx.fillRect(selPt.x - textWidth / 2 - 4, selPt.y - 28, textWidth + 8, 16);
      ctx.fillStyle = '#38bdf8';
      ctx.textAlign = 'center';
      ctx.fillText(tagText, selPt.x, selPt.y - 16);
    }

  }, [
    terrainData, floodData, projectPoint, azimuth, pitch, zoom,
    vertExaggeration, renderMode, showWater, showContextFade,
    focusMode, activeRoute, selectedLocation
  ]);

  useEffect(() => {
    function handleResize() {
      const container = containerRef.current;
      const canvas = canvasRef.current;
      if (!container || !canvas) return;
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
      renderScene();
    }

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [renderScene]);

  useEffect(() => {
    renderScene();
  }, [renderScene]);

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    isDraggingRef.current = true;
    dragStartPosRef.current = { x: e.clientX, y: e.clientY };
    dragDeltaRef.current = { x: 0, y: 0 };
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDraggingRef.current) return;
    const dx = e.clientX - dragStartPosRef.current.x;
    const dy = e.clientY - dragStartPosRef.current.y;
    dragDeltaRef.current = { x: dx, y: dy };

    setAzimuth(prev => prev + dx * 0.006);
    setPitch(prev => Math.max(0.1, Math.min(Math.PI * 0.45, prev + dy * 0.005)));

    dragStartPosRef.current = { x: e.clientX, y: e.clientY };
    renderScene();
  };

  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const wasDragging = Math.abs(dragDeltaRef.current.x) > 3 || Math.abs(dragDeltaRef.current.y) > 3;
    isDraggingRef.current = false;

    if (!wasDragging) {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (rect) {
        const clickX = e.clientX - rect.left;
        const clickY = e.clientY - rect.top;
        const geo = unprojectPoint(clickX, clickY);
        if (geo) {
          onSelectLocation(geo.lat, geo.lon);
        }
      }
    }
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.08 : 0.92;
    setZoom(prev => Math.max(0.6, Math.min(4.5, prev * factor)));
  };

  const handleResetCamera = () => {
    setAzimuth(Math.PI * 0.15);
    setPitch(Math.PI * 0.22);
    setZoom(1.1);
    setVertExaggeration(1.2);
  };

  return (
    <div
      ref={containerRef}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        userSelect: 'none',
      }}
    >
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onWheel={handleWheel}
        style={{
          width: '100%',
          height: '100%',
          display: 'block',
          cursor: isDraggingRef.current ? 'grabbing' : 'crosshair',
        }}
      />

      {loadingTerrain && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 30,
          background: 'rgba(11, 19, 41, 0.75)', backdropFilter: 'blur(4px)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          gap: '12px', color: '#ffffff',
        }}>
          <RefreshCw size={26} className="animate-spin text-blue-400" />
          <span style={{ fontSize: '12.5px', fontWeight: 700, letterSpacing: '0.4px' }}>
            Rendering Copernicus GLO-30 3D Topography...
          </span>
          <span style={{ fontSize: '10.5px', color: '#94a3b8' }}>
            Physical Metric Elevation • EGM96 Geoid Vertical Datum
          </span>
        </div>
      )}

      {terrainError && (
        <div style={{
          position: 'absolute', top: '64px', left: '50%', transform: 'translateX(-50%)',
          zIndex: 40, background: '#fef2f2', border: '1px solid #ef4444',
          borderRadius: '8px', padding: '10px 16px', boxShadow: '0 4px 14px rgba(0,0,0,0.2)',
          display: 'flex', alignItems: 'center', gap: '10px', fontSize: '12px', color: '#991b1b',
        }}>
          <AlertTriangle size={16} color="#ef4444" />
          <span>{terrainError}</span>
          <button
            onClick={() => setFocusMode('citywide')}
            style={{
              background: '#ef4444', color: '#ffffff', border: 'none',
              padding: '4px 10px', borderRadius: '4px', fontWeight: 700, cursor: 'pointer',
            }}
          >
            Reset Citywide
          </button>
        </div>
      )}

      <div style={{
        position: 'absolute', top: '64px', left: '14px', zIndex: 20,
        display: 'flex', flexDirection: 'column', gap: '8px', pointerEvents: 'auto',
      }}>
        <div style={{
          background: 'rgba(15, 23, 42, 0.92)', backdropFilter: 'blur(8px)',
          border: '1px solid rgba(255, 255, 255, 0.15)',
          borderRadius: '8px', padding: '6px 10px', display: 'flex', alignItems: 'center', gap: '8px',
          boxShadow: '0 4px 16px rgba(0,0,0,0.2)',
        }}>
          <Mountain size={14} color="#38bdf8" />
          <select
            value={focusMode}
            onChange={e => setFocusMode(e.target.value)}
            style={{
              background: 'transparent', border: 'none', color: '#f8fafc',
              fontSize: '11px', fontWeight: 700, outline: 'none', cursor: 'pointer',
              maxWidth: '220px',
            }}
          >
            <option value="citywide" style={{ background: '#0f172a', color: '#f8fafc' }}>
              🌐 Greater Mumbai (City-Wide Default)
            </option>
            <optgroup label="Dynamic Subarea Focus (Copernicus DEM)">
              {subareasList.map(s => (
                <option key={s.subarea_id} value={s.subarea_id} style={{ background: '#0f172a', color: '#f8fafc' }}>
                  {s.name} ({s.subarea_id})
                </option>
              ))}
            </optgroup>
          </select>
        </div>

        <div style={{
          background: 'rgba(15, 23, 42, 0.92)', backdropFilter: 'blur(8px)',
          border: '1px solid rgba(255, 255, 255, 0.15)',
          borderRadius: '8px', padding: '4px 6px', display: 'flex', alignItems: 'center', gap: '4px',
          boxShadow: '0 4px 16px rgba(0,0,0,0.2)',
        }}>
          <button
            onClick={() => setAzimuth(prev => prev + 0.25)}
            title="Rotate Left (Yaw)"
            style={{
              background: 'transparent', border: 'none', color: '#94a3b8',
              padding: '5px', borderRadius: '4px', cursor: 'pointer', fontSize: '12px',
            }}
          >
            🔄
          </button>
          <button
            onClick={() => setPitch(prev => Math.min(Math.PI * 0.45, prev + 0.08))}
            title="Tilt Up"
            style={{
              background: 'transparent', border: 'none', color: '#94a3b8',
              padding: '5px', borderRadius: '4px', cursor: 'pointer', fontSize: '12px',
            }}
          >
            📐
          </button>
          <button
            onClick={() => setZoom(prev => Math.min(4.0, prev * 1.15))}
            title="Zoom In"
            style={{
              background: 'transparent', border: 'none', color: '#94a3b8',
              padding: '5px', borderRadius: '4px', cursor: 'pointer', fontSize: '12px',
            }}
          >
            <ZoomIn size={13} />
          </button>
          <button
            onClick={() => setZoom(prev => Math.max(0.6, prev * 0.85))}
            title="Zoom Out"
            style={{
              background: 'transparent', border: 'none', color: '#94a3b8',
              padding: '5px', borderRadius: '4px', cursor: 'pointer', fontSize: '12px',
            }}
          >
            <ZoomOut size={13} />
          </button>
          <button
            onClick={handleResetCamera}
            title="Reset Camera & Compass"
            style={{
              background: 'transparent', border: 'none', color: '#38bdf8',
              padding: '5px', borderRadius: '4px', cursor: 'pointer', fontSize: '12px',
            }}
          >
            <RotateCcw size={13} />
          </button>
          <div style={{ width: '1px', height: '16px', background: 'rgba(255,255,255,0.2)', margin: '0 2px' }} />
          <button
            onClick={() => setShowControlsDrawer(!showControlsDrawer)}
            title="Topography & Exaggeration Settings"
            style={{
              background: showControlsDrawer ? '#1d4ed8' : 'transparent',
              border: 'none', color: showControlsDrawer ? '#ffffff' : '#94a3b8',
              padding: '5px 7px', borderRadius: '4px', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '4px', fontSize: '10.5px', fontWeight: 700,
            }}
          >
            <Sliders size={12} /> Relief
          </button>
        </div>

        {showControlsDrawer && (
          <div style={{
            background: 'rgba(15, 23, 42, 0.95)', backdropFilter: 'blur(10px)',
            border: '1px solid rgba(255, 255, 255, 0.18)', borderRadius: '8px',
            padding: '12px', width: '240px', display: 'flex', flexDirection: 'column', gap: '8px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.3)', color: '#f8fafc',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '11px', fontWeight: 800, color: '#38bdf8', textTransform: 'uppercase' }}>
                3D Relief Controls
              </span>
              <button
                onClick={() => setShowControlsDrawer(false)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#cbd5e1', marginBottom: '3px' }}>
                <span>VERTICAL EXAGGERATION</span>
                <strong style={{ color: '#38bdf8' }}>{vertExaggeration.toFixed(1)}×</strong>
              </div>
              <input
                type="range"
                min="0.8"
                max="2.5"
                step="0.1"
                value={vertExaggeration}
                onChange={e => setVertExaggeration(parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: '#0284c7', cursor: 'pointer' }}
              />
              <div style={{ fontSize: '8.5px', color: '#94a3b8', marginTop: '2px' }}>
                1.0× = Natural physical scale (No mountain spikes)
              </div>
            </div>

            <div style={{ display: 'flex', gap: '4px' }}>
              <button
                onClick={() => setRenderMode('shaded')}
                style={{
                  flex: 1, padding: '4px', borderRadius: '4px', fontSize: '10px', fontWeight: 700,
                  background: renderMode === 'shaded' ? '#0284c7' : 'rgba(255,255,255,0.08)',
                  color: '#ffffff', border: 'none', cursor: 'pointer',
                }}
              >
                Topographic Shaded
              </button>
              <button
                onClick={() => setRenderMode('wireframe')}
                style={{
                  flex: 1, padding: '4px', borderRadius: '4px', fontSize: '10px', fontWeight: 700,
                  background: renderMode === 'wireframe' ? '#0284c7' : 'rgba(255,255,255,0.08)',
                  color: '#ffffff', border: 'none', cursor: 'pointer',
                }}
              >
                Wireframe Mesh
              </button>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '6px' }}>
              <span style={{ fontSize: '10.5px', color: '#cbd5e1' }}>Simulated Water Drape</span>
              <button
                onClick={() => setShowWater(!showWater)}
                style={{
                  background: showWater ? '#0284c7' : 'rgba(255,255,255,0.1)',
                  color: '#ffffff', border: 'none', padding: '3px 8px', borderRadius: '4px',
                  fontSize: '9.5px', fontWeight: 700, cursor: 'pointer',
                }}
              >
                {showWater ? '🌊 ON' : 'OFF'}
              </button>
            </div>
          </div>
        )}
      </div>

      <div style={{
        position: 'absolute', bottom: '16px', right: '16px', zIndex: 20,
        background: 'rgba(15, 23, 42, 0.88)', backdropFilter: 'blur(8px)',
        border: '1px solid rgba(255, 255, 255, 0.15)', borderRadius: '8px',
        padding: '6px 10px', fontSize: '10px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '8px',
      }}>
        <span>🖱️ <strong>Click</strong> to select • <strong>Drag</strong> to rotate • <strong>Scroll</strong> to zoom</span>
        <span style={{ color: '#38bdf8', fontWeight: 700 }}>
          {focusMode === 'citywide' ? 'City-Wide (96×96 Copernicus DEM)' : `Focus: ${focusMode}`}
        </span>
      </div>
    </div>
  );
};

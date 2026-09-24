'use client';

import React, { useState } from 'react';
import { ColorRamp, SimulationTelemetry, DrainageNodeTelemetry } from '../types/dashboard';
import { Eye, Layers, Compass, Wind, Droplets, AlertTriangle, Maximize2 } from 'lucide-react';

interface SimulationViewportProps {
  currentFrame: SimulationTelemetry;
  drainageNodes: DrainageNodeTelemetry[];
  onSelectNode: (node: DrainageNodeTelemetry) => void;
  selectedNode: DrainageNodeTelemetry | null;
}

export const SimulationViewport: React.FC<SimulationViewportProps> = ({
  currentFrame,
  drainageNodes,
  onSelectNode,
  selectedNode
}) => {
  const [colorRamp, setColorRamp] = useState<ColorRamp>('water');
  const [showVectors, setShowVectors] = useState(true);
  const [showNetwork, setShowNetwork] = useState(true);
  const [showDEM, setShowDEM] = useState(true);

  // Time-scaled depth multiplier
  const depthMult = currentFrame.maxFloodDepthM / 0.52;

  const getColorRampGradient = () => {
    switch (colorRamp) {
      case 'thermal':
        return 'linear-gradient(to right, #000004, #51127c, #b63679, #fb8861, #fcfdbf)';
      case 'turbo':
        return 'linear-gradient(to right, #30123b, #4686fb, #1ae4b6, #a2fc3c, #f8ca36, #e2430b, #7a0403)';
      default:
        return 'linear-gradient(to right, #08306b, #08519c, #2171b5, #4292c6, #6baed6, #fed976, #feb24c, #fd8d3c, #f03b20, #bd0026)';
    }
  };

  return (
    <div style={{
      position: 'relative',
      width: '100%',
      height: '100%',
      minHeight: '520px',
      background: '#040711',
      borderRadius: '16px',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column'
    }}>
      {/* Viewport Top Floating Controls */}
      <div style={{
        position: 'absolute',
        top: '16px',
        left: '16px',
        right: '16px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        zIndex: 20,
        pointerEvents: 'none'
      }}>
        {/* Left: Resolution & Horizon HUD */}
        <div className="glass-panel" style={{ padding: '8px 14px', pointerEvents: 'auto', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div>
            <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 700, letterSpacing: '0.5px' }}>
              SPATIAL GRID RES
            </div>
            <div style={{ fontSize: '13px', fontWeight: 800, color: '#38bdf8' }}>
              Schematic grid (not georeferenced)
            </div>
          </div>
          <div style={{ borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: '10px' }}>
            <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 700 }}>DEMO PLAYBACK</div>
            <div style={{ fontSize: '13px', fontWeight: 800, color: '#f8fafc' }}>
              {currentFrame.timeLabel}
            </div>
          </div>
        </div>

        {/* Right: Layer Toggles & Color Ramp Selector */}
        <div className="glass-panel" style={{ padding: '6px 12px', pointerEvents: 'auto', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: '#94a3b8' }}>
            <span>RAMP:</span>
            <select
              value={colorRamp}
              onChange={(e) => setColorRamp(e.target.value as ColorRamp)}
              style={{
                background: 'rgba(15, 23, 42, 0.9)',
                color: '#f8fafc',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '6px',
                padding: '3px 8px',
                fontSize: '11px',
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              <option value="water">Hydro Depth</option>
              <option value="thermal">Thermal Heat</option>
              <option value="turbo">Turbo Spectral</option>
            </select>
          </div>

          <button
            onClick={() => setShowVectors(!showVectors)}
            className={`glass-btn ${showVectors ? 'glass-btn-active' : ''}`}
            style={{ padding: '4px 8px', fontSize: '11px' }}
          >
            <Wind size={12} /> Vectors
          </button>

          <button
            onClick={() => setShowNetwork(!showNetwork)}
            className={`glass-btn ${showNetwork ? 'glass-btn-active' : ''}`}
            style={{ padding: '4px 8px', fontSize: '11px' }}
          >
            <Layers size={12} /> Drains
          </button>
        </div>
      </div>

      {/* Main 2D Simulation Canvas / SVG Raster */}
      <div style={{ flex: 1, position: 'relative', width: '100%', height: '100%' }}>
        <svg
          viewBox="0 0 1000 650"
          style={{ width: '100%', height: '100%', display: 'block' }}
        >
          <defs>
            {/* Grid Pattern */}
            <pattern id="sim-grid" width="50" height="50" patternUnits="userSpaceOnUse">
              <path d="M 50 0 L 0 0 0 50" fill="none" stroke="rgba(255, 255, 255, 0.04)" strokeWidth="1" />
            </pattern>
            {/* Gradient Mask for Inundation Pool */}
            <radialGradient id="pool-hindmata" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#ef4444" stopOpacity={0.7 * depthMult} />
              <stop offset="40%" stopColor="#f97316" stopOpacity={0.5 * depthMult} />
              <stop offset="75%" stopColor="#38bdf8" stopOpacity={0.3 * depthMult} />
              <stop offset="100%" stopColor="#08306b" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="pool-gandhi" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#dc2626" stopOpacity={0.75 * depthMult} />
              <stop offset="50%" stopColor="#f97316" stopOpacity={0.55 * depthMult} />
              <stop offset="85%" stopColor="#38bdf8" stopOpacity={0.3 * depthMult} />
              <stop offset="100%" stopColor="#08306b" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="pool-milan" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#b91c1c" stopOpacity={0.85 * depthMult} />
              <stop offset="60%" stopColor="#ef4444" stopOpacity={0.6 * depthMult} />
              <stop offset="100%" stopColor="#08306b" stopOpacity="0" />
            </radialGradient>
          </defs>

          {/* Base Background */}
          <rect width="1000" height="650" fill="#040711" />
          <rect width="1000" height="650" fill="url(#sim-grid)" />

          {/* Topographic Contour Elevations */}
          {showDEM && (
            <g stroke="rgba(255, 255, 255, 0.07)" strokeWidth="1.2" fill="none">
              <ellipse cx="450" cy="300" rx="420" ry="260" strokeDasharray="6 3" />
              <ellipse cx="480" cy="320" rx="360" ry="220" />
              <ellipse cx="500" cy="340" rx="280" ry="170" />
              <ellipse cx="520" cy="360" rx="200" ry="120" stroke="rgba(56, 189, 248, 0.15)" />
              <ellipse cx="530" cy="380" rx="120" ry="70" stroke="rgba(56, 189, 248, 0.25)" />
            </g>
          )}

          {/* Mithi River Tidal Estuary Channel */}
          <path
            d="M 680 80 Q 640 180 600 290 T 520 400 Q 420 450 360 480 L 320 540"
            fill="none"
            stroke="#0369a1"
            strokeWidth="18"
            strokeLinecap="round"
            strokeOpacity="0.4"
          />
          <path
            d="M 680 80 Q 640 180 600 290 T 520 400 Q 420 450 360 480 L 320 540"
            fill="none"
            stroke="#38bdf8"
            strokeWidth="4"
            strokeDasharray="8 4"
            strokeOpacity="0.8"
          />

          {/* Surface Inundation Pools (Dynamic radii scaled with simulation depth) */}
          {/* Hindmata Depression */}
          <circle cx="440" cy="520" r={45 * Math.max(0.6, depthMult)} fill="url(#pool-hindmata)" />
          {/* Gandhi Market Depression */}
          <circle cx="560" cy="460" r={52 * Math.max(0.6, depthMult)} fill="url(#pool-gandhi)" />
          {/* Milan Subway Sump */}
          <circle cx="360" cy="280" r={58 * Math.max(0.6, depthMult)} fill="url(#pool-milan)" />
          {/* Kurla Kamani Basin */}
          <circle cx="680" cy="340" r={42 * Math.max(0.6, depthMult)} fill="url(#pool-hindmata)" />
          {/* Andheri Subway */}
          <circle cx="380" cy="150" r={38 * Math.max(0.6, depthMult)} fill="url(#pool-hindmata)" />

          {/* Stormwater Drainage Network Graph */}
          {showNetwork && (
            <g>
              {/* Trunk lines connecting nodes */}
              <line x1="440" y1="520" x2="560" y2="460" stroke="#ef4444" strokeWidth="3" strokeDasharray="5 3" />
              <line x1="560" y1="460" x2="680" y2="340" stroke="#f97316" strokeWidth="2.5" />
              <line x1="360" y1="280" x2="380" y2="150" stroke="#34d399" strokeWidth="2" />
              <line x1="680" y1="340" x2="520" y2="400" stroke="#38bdf8" strokeWidth="4" />
            </g>
          )}

          {/* Diffusive Wave Velocity Flow Vectors */}
          {showVectors && (
            <g stroke="#38bdf8" strokeWidth="1.2" opacity="0.65">
              {/* Flow vectors pointing into Hindmata */}
              <path d="M 400 480 L 430 510 M 430 510 L 420 505 M 430 510 L 425 498" />
              <path d="M 480 490 L 450 515 M 450 515 L 460 510 M 450 515 L 455 503" />
              {/* Flow vectors pointing into Gandhi Market */}
              <path d="M 520 420 L 550 450 M 550 450 L 540 445 M 550 450 L 545 438" />
              <path d="M 600 430 L 570 455 M 570 455 L 580 450 M 570 455 L 575 443" />
              {/* Flow vectors pointing into Milan Subway */}
              <path d="M 320 250 L 350 275 M 350 275 L 340 270 M 350 275 L 345 263" />
            </g>
          )}

          {/* Drainage Manholes / Hydraulic Exchange Nodes */}
          {drainageNodes.map((node) => {
            // Position mapping
            let cx = 500, cy = 300;
            if (node.id === 'NODE_HM_01') { cx = 440; cy = 520; }
            if (node.id === 'NODE_GM_02') { cx = 560; cy = 460; }
            if (node.id === 'NODE_MS_03') { cx = 360; cy = 280; }
            if (node.id === 'NODE_KL_04') { cx = 680; cy = 340; }
            if (node.id === 'NODE_DH_05') { cx = 410; cy = 570; }

            const isSelected = selectedNode?.id === node.id;
            const isSurcharging = node.isBackflowing;

            return (
              <g
                key={node.id}
                transform={`translate(${cx}, ${cy})`}
                style={{ cursor: 'pointer' }}
                onClick={() => onSelectNode(node)}
              >
                {/* Backflow Pulsing Ring */}
                {isSurcharging && (
                  <circle r="20" fill="none" stroke="#ef4444" strokeWidth="2" className="animate-ping" />
                )}

                <circle
                  r={isSelected ? "11" : "8"}
                  fill={isSurcharging ? "#ef4444" : "#34d399"}
                  stroke="#ffffff"
                  strokeWidth={isSelected ? "2.5" : "1.5"}
                />

                <text
                  x="14"
                  y="4"
                  fill="#ffffff"
                  fontSize="11"
                  fontWeight="700"
                  stroke="#000000"
                  strokeWidth="2.5"
                  paintOrder="stroke"
                >
                  {node.name.split(' ')[0]} {node.isBackflowing ? '⚠️ BACKFLOW' : ''}
                </text>
                <text
                  x="14"
                  y="16"
                  fill="#94a3b8"
                  fontSize="9.5"
                  stroke="#000000"
                  strokeWidth="2"
                  paintOrder="stroke"
                >
                  Q_in: {node.inflowM3s} / Cap: {node.capacityM3s} m³/s
                </text>
              </g>
            );
          })}
        </svg>

        {/* Bottom Floating Color Ramp Legend */}
        <div style={{
          position: 'absolute',
          bottom: '16px',
          left: '16px',
          background: 'rgba(8, 12, 22, 0.9)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '10px',
          padding: '10px 14px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          zIndex: 20
      }}>
      <div role="note" style={{ position: 'absolute', left: '16px', bottom: '16px', zIndex: 20, padding: '8px 12px', borderRadius: '8px', color: '#7c2d12', background: '#fff7ed', border: '1px solid #fdba74', fontSize: '12px', fontWeight: 700 }}>
        Illustrative animation only — not simulation output or a Mumbai flood map.
      </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10.5px', color: '#94a3b8', fontWeight: 600 }}>
            <span>0.00m (Dry)</span>
            <span>0.30m (Caution)</span>
            <span>&gt; 0.90m (Critical)</span>
          </div>
          <div style={{
            width: '240px',
            height: '10px',
            borderRadius: '4px',
            background: getColorRampGradient(),
            border: '1px solid rgba(255, 255, 255, 0.2)'
          }} />
          <div style={{ fontSize: '10px', color: '#64748b', display: 'flex', justifyContent: 'space-between' }}>
            <span>Sol: Horton + Manning</span>
            <span>Coupling: Orifice 2-Way</span>
          </div>
        </div>

        {/* Selected Node Telemetry Floating Card */}
        {selectedNode && (
          <div style={{
            position: 'absolute',
            bottom: '16px',
            right: '16px',
            width: '320px',
            background: 'rgba(11, 17, 32, 0.95)',
            backdropFilter: 'blur(20px)',
            border: '1px solid var(--glass-border-active)',
            borderRadius: '12px',
            padding: '14px 16px',
            boxShadow: '0 10px 30px rgba(0,0,0,0.8)',
            zIndex: 20
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <span style={{
                  fontSize: '10px',
                  fontWeight: 800,
                  padding: '2px 6px',
                  borderRadius: '4px',
                  background: selectedNode.isBackflowing ? 'rgba(239, 68, 68, 0.2)' : 'rgba(52, 211, 153, 0.2)',
                  color: selectedNode.isBackflowing ? '#ef4444' : '#34d399',
                  border: `1px solid ${selectedNode.isBackflowing ? '#ef4444' : '#34d399'}`
                }}>
                  {selectedNode.waterLevelStatus}
                </span>
                <h4 style={{ fontSize: '13.5px', fontWeight: 800, color: '#f8fafc', marginTop: '6px' }}>
                  {selectedNode.name}
                </h4>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '12px' }}>
              <div className="glass-card" style={{ padding: '8px' }}>
                <div style={{ fontSize: '10px', color: '#94a3b8' }}>INFLOW RATE</div>
                <div style={{ fontSize: '15px', fontWeight: 800, color: '#38bdf8' }}>
                  {selectedNode.inflowM3s} <span style={{ fontSize: '10px' }}>m³/s</span>
                </div>
              </div>

              <div className="glass-card" style={{ padding: '8px' }}>
                <div style={{ fontSize: '10px', color: '#94a3b8' }}>PIPE CAPACITY</div>
                <div style={{ fontSize: '15px', fontWeight: 800, color: '#f8fafc' }}>
                  {selectedNode.capacityM3s} <span style={{ fontSize: '10px' }}>m³/s</span>
                </div>
              </div>

              <div className="glass-card" style={{ padding: '8px' }}>
                <div style={{ fontSize: '10px', color: '#94a3b8' }}>SURCHARGE HEAD</div>
                <div style={{ fontSize: '15px', fontWeight: 800, color: selectedNode.surchargeDepthM > 0 ? '#ef4444' : '#34d399' }}>
                  +{selectedNode.surchargeDepthM} <span style={{ fontSize: '10px' }}>m</span>
                </div>
              </div>

              <div className="glass-card" style={{ padding: '8px' }}>
                <div style={{ fontSize: '10px', color: '#94a3b8' }}>EXCHANGE FLUX</div>
                <div style={{ fontSize: '15px', fontWeight: 800, color: selectedNode.isBackflowing ? '#ef4444' : '#34d399' }}>
                  {selectedNode.isBackflowing ? 'SURFACE OUT' : 'CAPTURE IN'}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

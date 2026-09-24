'use client';

import React, { useState } from 'react';
import { WaterHotspot, Shelter } from '../types/citizen';
import { AlertTriangle, Droplets, Navigation, Shield, Info, Eye, CheckCircle2, XCircle } from 'lucide-react';

interface RadarMapProps {
  hotspots: WaterHotspot[];
  shelters: Shelter[];
  onSelectHotspot: (spot: WaterHotspot) => void;
  selectedSpot: WaterHotspot | null;
  onNavigateToShelter: (shelter: Shelter) => void;
}

export const RadarMap: React.FC<RadarMapProps> = ({
  hotspots,
  shelters,
  onSelectHotspot,
  selectedSpot,
  onNavigateToShelter
}) => {
  const [showShelters, setShowShelters] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [showDrains, setShowDrains] = useState(true);

  // Map coordinates normalized to SVG viewBox [0, 0, 800, 600]
  // Mumbai coordinates approx: Lat 19.00 - 19.14, Lng 72.82 - 72.90
  const latMin = 19.00, latMax = 19.14;
  const lngMin = 72.82, lngMax = 72.90;

  const projectToMap = (lat: number, lng: number) => {
    const x = ((lng - lngMin) / (lngMax - lngMin)) * 740 + 30;
    const y = ((latMax - lat) / (latMax - latMin)) * 520 + 40;
    return { x, y };
  };

  const getDepthColor = (depth: number) => {
    if (depth < 0.15) return '#38bdf8'; // Cyan
    if (depth < 0.30) return '#f59e0b'; // Amber
    if (depth < 0.50) return '#f97316'; // Orange
    return '#ef4444'; // Red
  };

  return (
    <div className="glass-panel" style={{ padding: '16px', position: 'relative', overflow: 'hidden' }}>
      {/* Top Map Control Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '10px',
        marginBottom: '14px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '14px', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Droplets size={16} color="#38bdf8" /> Live Inundation & Hazard Radar
          </span>
          <span style={{
            fontSize: '11px',
            padding: '2px 8px',
            borderRadius: '999px',
            background: 'rgba(239, 68, 68, 0.2)',
            color: '#ef4444',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            fontWeight: 600
          }}>
            NOWCAST T+30M
          </span>
        </div>

        {/* Layer Toggles */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <button
            onClick={() => setShowHeatmap(!showHeatmap)}
            className="btn-ghost"
            style={{
              background: showHeatmap ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.05)',
              borderColor: showHeatmap ? '#38bdf8' : 'rgba(255, 255, 255, 0.1)',
              fontSize: '11px',
              padding: '4px 10px'
            }}
          >
            Flood Depth {showHeatmap ? '✓' : ''}
          </button>
          <button
            onClick={() => setShowShelters(!showShelters)}
            className="btn-ghost"
            style={{
              background: showShelters ? 'rgba(52, 211, 153, 0.2)' : 'rgba(255, 255, 255, 0.05)',
              borderColor: showShelters ? '#34d399' : 'rgba(255, 255, 255, 0.1)',
              fontSize: '11px',
              padding: '4px 10px'
            }}
          >
            Relief Shelters {showShelters ? '✓' : ''}
          </button>
          <button
            onClick={() => setShowDrains(!showDrains)}
            className="btn-ghost"
            style={{
              background: showDrains ? 'rgba(249, 115, 22, 0.2)' : 'rgba(255, 255, 255, 0.05)',
              borderColor: showDrains ? '#f97316' : 'rgba(255, 255, 255, 0.1)',
              fontSize: '11px',
              padding: '4px 10px'
            }}
          >
            Surcharging Drains {showDrains ? '✓' : ''}
          </button>
        </div>
      </div>

      {/* Map Canvas Frame */}
      <div style={{
        position: 'relative',
        width: '100%',
        height: '420px',
        borderRadius: '12px',
        background: 'radial-gradient(ellipse at 50% 50%, #0a1122 0%, #03060c 100%)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        overflow: 'hidden'
      }}>
        {/* SVG Interactive Map */}
        <svg
          viewBox="0 0 800 600"
          style={{ width: '100%', height: '100%', display: 'block' }}
        >
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
            </pattern>
            {/* Coastal Outline Glow */}
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Background Grid */}
          <rect width="800" height="600" fill="url(#grid)" />

          {/* Mumbai Coastal Shoreline & Creek Paths (Arabian Sea on Left, Mithi River in Center) */}
          <path
            d="M 120 580 Q 150 450 180 380 T 210 250 T 260 140 T 320 40"
            fill="none"
            stroke="rgba(56, 189, 248, 0.25)"
            strokeWidth="3"
            strokeDasharray="4 2"
          />
          {/* Mithi River Channel */}
          <path
            d="M 520 120 Q 480 200 450 290 T 390 380 Q 320 420 280 440"
            fill="none"
            stroke="#0284c7"
            strokeWidth="5"
            strokeOpacity="0.6"
          />
          <text x="460" y="240" fill="rgba(56, 189, 248, 0.6)" fontSize="11" fontStyle="italic">
            Mithi River (Tidal Reach)
          </text>

          {/* Major Road Arteries (Western Express Hwy, Eastern Express Hwy, SV Road, LBS Marg) */}
          <path d="M 280 40 L 290 580" stroke="rgba(255, 255, 255, 0.12)" strokeWidth="2" />
          <path d="M 420 50 L 440 580" stroke="rgba(255, 255, 255, 0.12)" strokeWidth="2" />
          <path d="M 180 500 L 550 480" stroke="rgba(255, 255, 255, 0.09)" strokeWidth="1.5" />
          <path d="M 220 320 L 520 310" stroke="rgba(255, 255, 255, 0.09)" strokeWidth="1.5" />

          {/* Area labels */}
          <text x="310" y="520" fill="rgba(255, 255, 255, 0.3)" fontSize="11" fontWeight="600">DADAR</text>
          <text x="430" y="460" fill="rgba(255, 255, 255, 0.3)" fontSize="11" fontWeight="600">SION / MATUNGA</text>
          <text x="510" y="340" fill="rgba(255, 255, 255, 0.3)" fontSize="11" fontWeight="600">KURLA (WARD L)</text>
          <text x="240" y="280" fill="rgba(255, 255, 255, 0.3)" fontSize="11" fontWeight="600">SANTACRUZ / BANDRA</text>
          <text x="270" y="160" fill="rgba(255, 255, 255, 0.3)" fontSize="11" fontWeight="600">ANDHERI</text>

          {/* Inundation Heatmap Polygons */}
          {showHeatmap && (
            <>
              {/* Hindmata Pool */}
              <circle cx="340" cy="510" r="38" fill="rgba(239, 68, 68, 0.25)" stroke="#ef4444" strokeWidth="1" strokeDasharray="3 3" />
              {/* Gandhi Market Pool */}
              <circle cx="430" cy="450" r="44" fill="rgba(239, 68, 68, 0.3)" stroke="#ef4444" strokeWidth="1.5" strokeDasharray="4 2" />
              {/* Milan Subway Pool */}
              <circle cx="280" cy="270" r="46" fill="rgba(239, 68, 68, 0.35)" stroke="#ef4444" strokeWidth="2" />
              {/* Kurla Kamani Pool */}
              <circle cx="520" cy="325" r="36" fill="rgba(249, 115, 22, 0.28)" stroke="#f97316" strokeWidth="1" />
              {/* Andheri Subway Pool */}
              <circle cx="290" cy="150" r="32" fill="rgba(249, 115, 22, 0.28)" stroke="#f97316" strokeWidth="1" />
            </>
          )}

          {/* Shelters Pins */}
          {showShelters && shelters.map((sh) => {
            const pos = projectToMap(sh.lat, sh.lng);
            return (
              <g
                key={sh.id}
                transform={`translate(${pos.x}, ${pos.y})`}
                style={{ cursor: 'pointer' }}
                onClick={() => onNavigateToShelter(sh)}
              >
                <circle r="14" fill="rgba(16, 185, 129, 0.2)" stroke="#10b981" strokeWidth="1.5" />
                <rect x="-6" y="-6" width="12" height="12" rx="3" fill="#10b981" />
                <text x="0" y="3" textAnchor="middle" fill="#000000" fontSize="8" fontWeight="bold">S</text>
                <text x="16" y="4" fill="#6ee7b7" fontSize="10" fontWeight="600">
                  {sh.name.split(' ')[0]}
                </text>
              </g>
            );
          })}

          {/* Hotspot Markers */}
          {hotspots.map((spot) => {
            const pos = projectToMap(spot.lat, spot.lng);
            const color = getDepthColor(spot.currentDepthMeters);
            const isSelected = selectedSpot?.id === spot.id;

            return (
              <g
                key={spot.id}
                transform={`translate(${pos.x}, ${pos.y})`}
                style={{ cursor: 'pointer' }}
                onClick={() => onSelectHotspot(spot)}
              >
                {/* Sonar Ripple */}
                <circle r="22" fill={color} fillOpacity="0.2" className="animate-ping" />
                <circle
                  r={isSelected ? "13" : "10"}
                  fill={color}
                  stroke="#ffffff"
                  strokeWidth={isSelected ? "3" : "1.5"}
                  filter="url(#glow)"
                />
                <text
                  x="0"
                  y="3.5"
                  textAnchor="middle"
                  fill="#ffffff"
                  fontSize="9"
                  fontWeight="bold"
                >
                  {Math.round(spot.currentDepthMeters * 100)}
                </text>
                <text
                  x="14"
                  y="-4"
                  fill="#ffffff"
                  fontSize="11"
                  fontWeight="700"
                  stroke="#070a14"
                  strokeWidth="2.5"
                  paintOrder="stroke"
                >
                  {spot.name}
                </text>
                <text
                  x="14"
                  y="9"
                  fill={color}
                  fontSize="9.5"
                  fontWeight="600"
                  stroke="#070a14"
                  strokeWidth="2"
                  paintOrder="stroke"
                >
                  {spot.currentDepthMeters.toFixed(2)}m (Pred: {spot.predictedDepth30m.toFixed(2)}m)
                </text>
              </g>
            );
          })}
        </svg>

        {/* Legend Overlay in Bottom Left */}
        <div style={{
          position: 'absolute',
          bottom: '12px',
          left: '12px',
          background: 'rgba(7, 10, 20, 0.9)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '8px',
          padding: '8px 12px',
          fontSize: '11px',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px'
        }}>
          <span style={{ fontWeight: 700, color: '#94a3b8', marginBottom: '2px' }}>WATER DEPTH (CM)</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#38bdf8' }} />
            <span style={{ color: '#cbd5e1' }}>&lt; 15 cm: Passable</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#f59e0b' }} />
            <span style={{ color: '#cbd5e1' }}>15 - 30 cm: Caution</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#f97316' }} />
            <span style={{ color: '#cbd5e1' }}>30 - 50 cm: Hazardous</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#ef4444' }} />
            <span style={{ color: '#cbd5e1' }}>&gt; 50 cm: SUBMERGED</span>
          </div>
        </div>
      </div>

      {/* Selected Hotspot Detailed Telemetry Drawer */}
      {selectedSpot && (
        <div style={{
          marginTop: '14px',
          background: 'rgba(15, 23, 42, 0.95)',
          border: '1px solid var(--card-border-active)',
          borderRadius: '12px',
          padding: '14px 18px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '14px',
          boxShadow: '0 10px 25px rgba(0,0,0,0.6)'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h4 style={{ fontSize: '15px', fontWeight: 800, color: '#f8fafc' }}>
                {selectedSpot.name}
              </h4>
              <span style={{
                fontSize: '11px',
                padding: '2px 8px',
                borderRadius: '4px',
                background: 'rgba(56, 189, 248, 0.2)',
                color: '#38bdf8',
                fontWeight: 600
              }}>
                Ward {selectedSpot.ward}
              </span>
            </div>
            <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
              Drain Network: <strong style={{ color: selectedSpot.drainStatus === 'normal' ? '#34d399' : '#f97316' }}>
                {selectedSpot.drainStatus.toUpperCase()}
              </strong> • Flow Speed: {selectedSpot.flowVelocityMs} m/s • Updated {selectedSpot.lastUpdated}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {/* Current vs Predicted Depth */}
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>NOW DEPTH</div>
              <div style={{ fontSize: '18px', fontWeight: 800, color: getDepthColor(selectedSpot.currentDepthMeters) }}>
                {selectedSpot.currentDepthMeters.toFixed(2)} m
              </div>
            </div>
            <div style={{ textAlign: 'center', borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: '14px' }}>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>T+30M NOWCAST</div>
              <div style={{ fontSize: '18px', fontWeight: 800, color: '#fca5a5' }}>
                {selectedSpot.predictedDepth30m.toFixed(2)} m
              </div>
            </div>

            {/* Passability Flags */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: selectedSpot.isPassableWalking ? '#34d399' : '#ef4444' }}>
                {selectedSpot.isPassableWalking ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
                Walking
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: selectedSpot.isPassableCar ? '#34d399' : '#ef4444' }}>
                {selectedSpot.isPassableCar ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
                Passenger Car
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

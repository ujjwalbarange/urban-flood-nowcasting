'use client';

import React, { useState } from 'react';
import { SafeRoute, RouteStep } from '../types/citizen';
import { Navigation, Footprints, Bike, Car, Truck, AlertTriangle, ShieldCheck, ArrowRight, Clock, MapPin } from 'lucide-react';

interface RoutePlannerProps {
  routes: SafeRoute[];
  onSelectRoute: (route: SafeRoute) => void;
}

export const RoutePlanner: React.FC<RoutePlannerProps> = ({ routes, onSelectRoute }) => {
  const [selectedMode, setSelectedMode] = useState<'walking' | 'two_wheeler' | 'car' | 'emergency'>('walking');
  const [origin, setOrigin] = useState('Sion Koliwada (My Location)');
  const [destination, setDestination] = useState('Ruia College Relief Camp');
  const [activeRouteIndex, setActiveRouteIndex] = useState(0);

  const clearanceLimits = {
    walking: 0.15,
    two_wheeler: 0.20,
    car: 0.30,
    emergency: 0.60
  };

  const currentLimit = clearanceLimits[selectedMode];

  const currentRoute = routes[activeRouteIndex] || routes[0];

  return (
    <div className="glass-panel" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h3 style={{ fontSize: '16px', fontWeight: 800, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Navigation size={18} color="#38bdf8" />
            Flood-Aware Evacuation Navigator
          </h3>
          <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
            Routes computed using Dijkstra passability weighting with real-time water depths.
          </p>
        </div>

        {/* Vehicle Mode Tabs */}
        <div style={{
          display: 'flex',
          background: 'rgba(15, 23, 42, 0.8)',
          border: '1px solid var(--card-border)',
          borderRadius: '10px',
          padding: '4px',
          gap: '4px'
        }}>
          <button
            onClick={() => setSelectedMode('walking')}
            style={{
              padding: '6px 12px',
              borderRadius: '8px',
              border: 'none',
              background: selectedMode === 'walking' ? '#0284c7' : 'transparent',
              color: '#ffffff',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Footprints size={14} /> Foot (&lt;15cm)
          </button>
          <button
            onClick={() => setSelectedMode('two_wheeler')}
            style={{
              padding: '6px 12px',
              borderRadius: '8px',
              border: 'none',
              background: selectedMode === 'two_wheeler' ? '#0284c7' : 'transparent',
              color: '#ffffff',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Bike size={14} /> 2-Wheeler (&lt;20cm)
          </button>
          <button
            onClick={() => setSelectedMode('car')}
            style={{
              padding: '6px 12px',
              borderRadius: '8px',
              border: 'none',
              background: selectedMode === 'car' ? '#0284c7' : 'transparent',
              color: '#ffffff',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Car size={14} /> Car (&lt;30cm)
          </button>
          <button
            onClick={() => setSelectedMode('emergency')}
            style={{
              padding: '6px 12px',
              borderRadius: '8px',
              border: 'none',
              background: selectedMode === 'emergency' ? '#0284c7' : 'transparent',
              color: '#ffffff',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Truck size={14} /> Rescue (&lt;60cm)
          </button>
        </div>
      </div>

      {/* Origin / Destination Search Row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: '12px',
        background: 'rgba(10, 16, 28, 0.7)',
        padding: '14px',
        borderRadius: '12px',
        border: '1px solid rgba(255, 255, 255, 0.06)',
        marginBottom: '16px'
      }}>
        <div>
          <label style={{ fontSize: '11px', color: '#94a3b8', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
            STARTING POINT
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(15, 23, 42, 0.9)', padding: '8px 12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)' }}>
            <MapPin size={15} color="#38bdf8" />
            <input
              type="text"
              value={origin}
              onChange={(e) => setOrigin(e.target.value)}
              style={{ background: 'transparent', border: 'none', outline: 'none', color: '#f8fafc', fontSize: '13px', width: '100%' }}
            />
          </div>
        </div>

        <div>
          <label style={{ fontSize: '11px', color: '#94a3b8', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
            SAFE DESTINATION / SHELTER
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(15, 23, 42, 0.9)', padding: '8px 12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)' }}>
            <MapPin size={15} color="#34d399" />
            <input
              type="text"
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              style={{ background: 'transparent', border: 'none', outline: 'none', color: '#f8fafc', fontSize: '13px', width: '100%' }}
            />
          </div>
        </div>
      </div>

      {/* Route Options Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {routes.map((route, idx) => {
          const isSelected = idx === activeRouteIndex;
          const isImpassable = route.maxFloodDepthMeters > currentLimit;

          let badgeColor = '#34d399';
          let badgeText = 'SAFE ELEVATED CORRIDOR';
          if (route.maxFloodDepthMeters > 0.15 && route.maxFloodDepthMeters <= currentLimit) {
            badgeColor = '#f59e0b';
            badgeText = 'PASSABLE WITH CAUTION';
          }
          if (isImpassable) {
            badgeColor = '#ef4444';
            badgeText = `IMPASSABLE FOR ${selectedMode.toUpperCase()} (> ${(currentLimit * 100).toFixed(0)}cm)`;
          }

          return (
            <div
              key={route.id}
              onClick={() => {
                setActiveRouteIndex(idx);
                onSelectRoute(route);
              }}
              style={{
                background: isSelected ? 'rgba(30, 41, 59, 0.95)' : 'rgba(15, 23, 42, 0.65)',
                border: `1.5px solid ${isSelected ? (isImpassable ? '#ef4444' : '#38bdf8') : 'rgba(255, 255, 255, 0.08)'}`,
                borderRadius: '12px',
                padding: '14px 18px',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: isSelected ? '0 6px 20px rgba(0,0,0,0.4)' : 'none'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{
                      fontSize: '11px',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      background: `${badgeColor}22`,
                      color: badgeColor,
                      border: `1px solid ${badgeColor}66`,
                      fontWeight: 700
                    }}>
                      {badgeText}
                    </span>
                    <span style={{ fontSize: '13px', fontWeight: 700, color: '#ffffff' }}>
                      {route.routeName}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px', color: '#94a3b8', marginTop: '6px' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={13} /> {route.estimatedMinutes} mins
                    </span>
                    <span>Distance: {route.totalDistanceKm} km</span>
                    <span style={{ color: isImpassable ? '#ef4444' : '#cbd5e1' }}>
                      Max Depth: <strong>{(route.maxFloodDepthMeters * 100).toFixed(0)} cm</strong>
                    </span>
                  </div>
                </div>

                <button
                  className="btn-primary"
                  style={{
                    fontSize: '12px',
                    padding: '8px 14px',
                    background: isImpassable ? 'rgba(239, 68, 68, 0.2)' : undefined,
                    borderColor: isImpassable ? '#ef4444' : undefined,
                    color: isImpassable ? '#ef4444' : '#ffffff'
                  }}
                >
                  {isImpassable ? 'Unsafe Route' : 'Navigate'}
                  <ArrowRight size={14} />
                </button>
              </div>

              {/* Expand Steps for Selected Route */}
              {isSelected && (
                <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
                  <div style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', marginBottom: '8px' }}>
                    TURN-BY-TURN ELEVATION & FLOOD CHECK:
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {route.steps.map((step, sIdx) => (
                      <div
                        key={sIdx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          fontSize: '12px',
                          padding: '6px 10px',
                          borderRadius: '6px',
                          background: step.isFlooded ? 'rgba(239, 68, 68, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                          borderLeft: `3px solid ${step.isFlooded ? '#ef4444' : '#10b981'}`
                        }}
                      >
                        <span style={{ color: step.isFlooded ? '#fca5a5' : '#e2e8f0' }}>
                          {sIdx + 1}. {step.instruction}
                        </span>
                        <span style={{ fontSize: '11px', color: step.isFlooded ? '#ef4444' : '#94a3b8', fontWeight: 600 }}>
                          {(step.waterDepthMeters * 100).toFixed(0)} cm • {step.distanceMeters}m
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

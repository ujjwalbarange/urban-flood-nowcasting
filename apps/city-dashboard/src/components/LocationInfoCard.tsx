'use client';

import React from 'react';
import {
  MapPin, X, Building2, Hospital, Shield, Flame, Home,
  Compass, AlertCircle, CheckCircle2, ChevronRight, Eye, EyeOff
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
    extension_points?: Record<string, any>;
  } | null;
  isLoading?: boolean;
  onClose: () => void;
  onToggleFacilities?: () => void;
  showFacilitiesOnMap?: boolean;
}

export function LocationInfoCard({
  locationData,
  isLoading,
  onClose,
  onToggleFacilities,
  showFacilitiesOnMap = false,
}: LocationInfoCardProps) {
  if (!locationData && !isLoading) return null;

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

  return (
    <div
      style={{
        position: 'absolute',
        top: '74px',
        right: '16px',
        width: '380px',
        maxHeight: 'calc(100vh - 120px)',
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
          padding: '12px 16px',
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
              width: '28px',
              height: '28px',
              borderRadius: '6px',
              background: '#2563eb',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <MapPin size={16} color="#ffffff" />
          </div>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 800, letterSpacing: '0.2px' }}>
              Selected Location Inspector
            </div>
            <div style={{ fontSize: '10.5px', color: '#94a3b8', fontFamily: 'monospace' }}>
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

      {/* Body Content */}
      <div style={{ padding: '14px 16px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {isLoading ? (
          <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', fontSize: '12px' }}>
            <div style={{ marginBottom: '8px', fontWeight: 600 }}>Performing Point-in-Polygon Query...</div>
            <div style={{ fontSize: '11px', color: '#94a3b8' }}>Resolving BMC Ward & Subarea Partition</div>
          </div>
        ) : locationData?.in_coverage && locationData.ward ? (
          <>
            {/* Status & Ward Banner */}
            <div
              style={{
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                padding: '10px 12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    color: '#166534',
                    background: '#dcfce7',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <CheckCircle2 size={12} /> Within BMC Jurisdiction
                </span>
                <span style={{ fontSize: '11px', fontWeight: 800, color: '#1e3a8a' }}>
                  Zone: {locationData.ward.zone}
                </span>
              </div>
              <div style={{ fontSize: '14px', fontWeight: 800, color: '#0f172a' }}>
                {locationData.ward.ward_name}
              </div>
              <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                Ward ID: <strong style={{ color: '#0f172a' }}>{locationData.ward.ward_id}</strong> &bull; Area:{' '}
                <strong>{locationData.ward.area_sq_km} km²</strong>
                {locationData.ward.population_2011 && (
                  <> &bull; Pop: <strong>{locationData.ward.population_2011.toLocaleString()}</strong></>
                )}
              </div>
            </div>

            {/* Subarea Partition Details */}
            {locationData.subarea && (
              <div
                style={{
                  background: '#eff6ff',
                  border: '1px solid #bfdbfe',
                  borderRadius: '8px',
                  padding: '10px 12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <Compass size={14} color="#1d4ed8" />
                  <span style={{ fontSize: '11px', fontWeight: 800, color: '#1e40af', textTransform: 'uppercase' }}>
                    Derived Subarea Partition
                  </span>
                </div>
                <div style={{ fontSize: '13px', fontWeight: 700, color: '#1e293b' }}>
                  {locationData.subarea.subarea_name}
                </div>
                <div style={{ fontSize: '11px', color: '#475569', marginTop: '3px' }}>
                  Subarea ID: <strong style={{ color: '#1d4ed8' }}>{locationData.subarea.subarea_id}</strong>
                  {locationData.subarea.subarea_area_sq_km && (
                    <> &bull; Subarea Area: <strong>{locationData.subarea.subarea_area_sq_km} km²</strong></>
                  )}
                </div>
              </div>
            )}

            {/* Nearby Emergency Facilities */}
            <div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '8px',
                }}
              >
                <span style={{ fontSize: '11px', fontWeight: 800, color: '#334155', textTransform: 'uppercase' }}>
                  Emergency Facilities in Vicinity ({locationData.nearby_facilities?.length || 0})
                </span>
                {onToggleFacilities && (
                  <button
                    onClick={onToggleFacilities}
                    style={{
                      background: showFacilitiesOnMap ? '#eff6ff' : '#f8fafc',
                      border: `1px solid ${showFacilitiesOnMap ? '#93c5fd' : '#cbd5e1'}`,
                      borderRadius: '5px',
                      padding: '3px 7px',
                      fontSize: '10px',
                      fontWeight: 700,
                      color: showFacilitiesOnMap ? '#1d4ed8' : '#475569',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                    title={showFacilitiesOnMap ? 'Hide facility markers from map' : 'Show facility markers on map'}
                  >
                    {showFacilitiesOnMap ? <EyeOff size={11} /> : <Eye size={11} />}
                    {showFacilitiesOnMap ? 'Hide on Map' : 'Show on Map'}
                  </button>
                )}
              </div>

              {locationData.nearby_facilities && locationData.nearby_facilities.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '180px', overflowY: 'auto' }}>
                  {locationData.nearby_facilities.map((fac, i) => {
                    const badge = getCategoryBadgeStyle(fac.category);
                    return (
                      <div
                        key={i}
                        style={{
                          padding: '7px 9px',
                          background: '#ffffff',
                          border: '1px solid #e2e8f0',
                          borderRadius: '6px',
                          display: 'flex',
                          alignItems: 'flex-start',
                          justifyContent: 'space-between',
                          gap: '8px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                          <div style={{ marginTop: '2px' }}>{getCategoryIcon(fac.category)}</div>
                          <div>
                            <div style={{ fontSize: '11.5px', fontWeight: 700, color: '#0f172a' }}>
                              {fac.name}
                            </div>
                            <div style={{ fontSize: '10px', color: '#64748b' }}>
                              {fac.address}
                              {fac.capacity_persons ? ` • Capacity: ${fac.capacity_persons}` : ''}
                            </div>
                          </div>
                        </div>
                        <div style={{ textAlign: 'right', flexShrink: 0 }}>
                          <span
                            style={{
                              fontSize: '9px',
                              fontWeight: 700,
                              textTransform: 'uppercase',
                              padding: '2px 5px',
                              borderRadius: '4px',
                              background: badge.bg,
                              color: badge.text,
                              border: `1px solid ${badge.border}`,
                              display: 'inline-block',
                              marginBottom: '2px',
                            }}
                          >
                            {fac.category}
                          </span>
                          {fac.distance_km !== undefined && (
                            <div style={{ fontSize: '10px', fontWeight: 700, color: '#2563eb' }}>
                              {fac.distance_km.toFixed(2)} km
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div style={{ fontSize: '11px', color: '#94a3b8', fontStyle: 'italic', padding: '6px 0' }}>
                  No emergency facilities recorded within 3 km of this coordinate.
                </div>
              )}
            </div>

            {/* Extension Points for Future Phases (Clearly marked as unavailable in Phase 1) */}
            <div
              style={{
                borderTop: '1px solid #e2e8f0',
                paddingTop: '10px',
              }}
            >
              <div style={{ fontSize: '10px', fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '6px' }}>
                Future Phase Capabilities (Extension Points)
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                <div
                  style={{
                    padding: '6px 8px',
                    background: '#f8fafc',
                    border: '1px dashed #cbd5e1',
                    borderRadius: '6px',
                    fontSize: '10px',
                    color: '#64748b',
                  }}
                >
                  <div style={{ fontWeight: 700, color: '#475569' }}>Live Weather</div>
                  <span style={{ fontSize: '9px', color: '#94a3b8' }}>Phase 2 Extension</span>
                </div>
                <div
                  style={{
                    padding: '6px 8px',
                    background: '#f8fafc',
                    border: '1px dashed #cbd5e1',
                    borderRadius: '6px',
                    fontSize: '10px',
                    color: '#64748b',
                  }}
                >
                  <div style={{ fontWeight: 700, color: '#475569' }}>7-Day NWP Forecast</div>
                  <span style={{ fontSize: '9px', color: '#94a3b8' }}>Phase 2 Extension</span>
                </div>
                <div
                  style={{
                    padding: '6px 8px',
                    background: '#f8fafc',
                    border: '1px dashed #cbd5e1',
                    borderRadius: '6px',
                    fontSize: '10px',
                    color: '#64748b',
                  }}
                >
                  <div style={{ fontWeight: 700, color: '#475569' }}>2D Inundation Depth</div>
                  <span style={{ fontSize: '9px', color: '#94a3b8' }}>Phase 2 Extension</span>
                </div>
                <div
                  style={{
                    padding: '6px 8px',
                    background: '#f8fafc',
                    border: '1px dashed #cbd5e1',
                    borderRadius: '6px',
                    fontSize: '10px',
                    color: '#64748b',
                  }}
                >
                  <div style={{ fontWeight: 700, color: '#475569' }}>Evacuation Routing</div>
                  <span style={{ fontSize: '9px', color: '#94a3b8' }}>Phase 2 Extension</span>
                </div>
              </div>
            </div>
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
            <div style={{ fontSize: '10px', color: '#94a3b8', marginTop: '8px' }}>
              MUFNS nowcasting coverage is calibrated specifically for the 24 BMC Greater Mumbai administrative wards.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

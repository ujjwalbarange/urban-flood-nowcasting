'use client';

import React from 'react';
import { Shelter } from '../types/citizen';
import { Shield, PhoneCall, Navigation, Users, CheckCircle2, LifeBuoy, MapPin } from 'lucide-react';

interface SheltersViewProps {
  shelters: Shelter[];
  onNavigateToShelter: (shelter: Shelter) => void;
}

export const SheltersView: React.FC<SheltersViewProps> = ({ shelters, onNavigateToShelter }) => {
  return (
    <div className="glass-panel" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h3 style={{ fontSize: '16px', fontWeight: 800, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Shield size={18} color="#10b981" />
            Designated Flood Relief Camps & Rescue Hubs
          </h3>
          <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
            Municipal shelters equipped with emergency power, dry rations, and medical triage.
          </p>
        </div>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: '14px'
      }}>
        {shelters.map((shelter) => {
          const occupancyPercent = Math.round((shelter.currentOccupancy / shelter.totalCapacity) * 100);
          const isHighOccupancy = occupancyPercent > 80;

          return (
            <div
              key={shelter.id}
              className="glass-card"
              style={{
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                position: 'relative'
              }}
            >
              <div>
                {/* Top Badge Row */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{
                    fontSize: '11px',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: shelter.isRescueHub ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.08)',
                    color: shelter.isRescueHub ? '#38bdf8' : '#94a3b8',
                    border: `1px solid ${shelter.isRescueHub ? 'rgba(56, 189, 248, 0.4)' : 'rgba(255, 255, 255, 0.1)'}`,
                    fontWeight: 700
                  }}>
                    {shelter.isRescueHub ? 'SDRF RESCUE BOAT HUB' : shelter.ward}
                  </span>
                  <span style={{ fontSize: '12px', fontWeight: 700, color: '#34d399' }}>
                    {shelter.distanceKm} km away
                  </span>
                </div>

                <h4 style={{ fontSize: '15px', fontWeight: 700, color: '#f8fafc', marginBottom: '4px' }}>
                  {shelter.name}
                </h4>
                <div style={{ fontSize: '12px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '12px' }}>
                  <MapPin size={13} color="#64748b" /> {shelter.address}
                </div>

                {/* Capacity Progress Bar */}
                <div style={{ marginBottom: '14px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11.5px', marginBottom: '4px' }}>
                    <span style={{ color: '#cbd5e1' }}>Capacity: {shelter.currentOccupancy} / {shelter.totalCapacity}</span>
                    <span style={{ color: isHighOccupancy ? '#ef4444' : '#34d399', fontWeight: 600 }}>
                      {occupancyPercent}% Occupied
                    </span>
                  </div>
                  <div style={{ width: '100%', height: '6px', background: 'rgba(255, 255, 255, 0.1)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{
                      width: `${occupancyPercent}%`,
                      height: '100%',
                      background: isHighOccupancy ? '#ef4444' : '#10b981',
                      borderRadius: '3px'
                    }} />
                  </div>
                </div>

                {/* Facilities Badges */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
                  {shelter.facilities.map((fac, i) => (
                    <span
                      key={i}
                      style={{
                        fontSize: '10.5px',
                        padding: '2px 7px',
                        borderRadius: '4px',
                        background: 'rgba(255, 255, 255, 0.05)',
                        color: '#cbd5e1',
                        border: '1px solid rgba(255, 255, 255, 0.06)'
                      }}
                    >
                      ✓ {fac}
                    </span>
                  ))}
                </div>
              </div>

              {/* Action Buttons: Call & Navigate */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <a
                  href={`tel:${shelter.contactNumber}`}
                  className="btn-ghost"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    fontSize: '12px',
                    textDecoration: 'none'
                  }}
                >
                  <PhoneCall size={13} color="#34d399" /> Call Hub
                </a>

                <button
                  onClick={() => onNavigateToShelter(shelter)}
                  className="btn-primary"
                  style={{
                    fontSize: '12px',
                    padding: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px'
                  }}
                >
                  <Navigation size={13} /> Route Safely
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

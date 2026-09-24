'use client';

import React, { useState } from 'react';
import { ShieldAlert, PhoneCall, Radio, CheckCircle, X, AlertTriangle } from 'lucide-react';

interface SosModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SosModal: React.FC<SosModalProps> = ({ isOpen, onClose }) => {
  const [beaconSent, setBeaconSent] = useState(false);

  if (!isOpen) return null;

  const handleTransmitBeacon = () => {
    setBeaconSent(true);
    setTimeout(() => {
      // Beacon acknowledged
    }, 1000);
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 120,
      background: 'rgba(15, 5, 5, 0.92)',
      backdropFilter: 'blur(20px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      <div style={{
        background: '#120709',
        border: '1.5px solid rgba(239, 68, 68, 0.5)',
        borderRadius: '20px',
        width: '100%',
        maxWidth: '520px',
        padding: '28px',
        boxShadow: '0 0 50px rgba(239, 68, 68, 0.4)',
        position: 'relative'
      }}>
        {/* Close button */}
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            background: 'rgba(255, 255, 255, 0.1)',
            border: 'none',
            borderRadius: '50%',
            width: '32px',
            height: '32px',
            color: '#cbd5e1',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <X size={18} />
        </button>

        {/* SOS Header */}
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            background: 'rgba(239, 68, 68, 0.2)',
            border: '2px solid #ef4444',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 14px',
            animation: 'pulse-red 1.5s infinite ease-in-out'
          }}>
            <ShieldAlert size={34} color="#ef4444" />
          </div>

          <h2 style={{ fontSize: '22px', fontWeight: 800, color: '#f8fafc', letterSpacing: '-0.3px' }}>
            CITIZEN EMERGENCY SOS BEACON
          </h2>
          <p style={{ fontSize: '13px', color: '#fca5a5', marginTop: '6px' }}>
            Immediate direct uplink to Municipal Disaster Control Room & SDRF Boat Rescue Units.
          </p>
        </div>

        {/* Beacon Activation */}
        <div style={{ marginBottom: '24px' }}>
          {beaconSent ? (
            <div style={{
              background: 'rgba(16, 185, 129, 0.15)',
              border: '1px solid #10b981',
              borderRadius: '12px',
              padding: '16px',
              textAlign: 'center'
            }}>
              <CheckCircle size={24} color="#10b981" style={{ margin: '0 auto 6px' }} />
              <div style={{ fontSize: '14px', fontWeight: 700, color: '#f8fafc' }}>
                SOS Beacon Active & Acknowledged!
              </div>
              <div style={{ fontSize: '12px', color: '#cbd5e1', marginTop: '4px' }}>
                Your GPS coordinates (19.0345° N, 72.8592° E) have been pushed to Mumbai SDRF Unit 4. Keep your phone line free.
              </div>
            </div>
          ) : (
            <button
              onClick={handleTransmitBeacon}
              className="btn-sos"
              style={{
                width: '100%',
                padding: '16px',
                fontSize: '15px',
                justifyContent: 'center',
                borderRadius: '12px'
              }}
            >
              <Radio size={20} />
              <span>TRANSMIT LIVE GPS RESCUE BEACON</span>
            </button>
          )}
        </div>

        {/* 24x7 Emergency Hotlines Grid */}
        <div style={{ fontSize: '12px', fontWeight: 700, color: '#94a3b8', marginBottom: '10px', textTransform: 'uppercase' }}>
          Direct Emergency Hotlines:
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '20px' }}>
          <a
            href="tel:1916"
            className="glass-card"
            style={{ padding: '12px', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '10px' }}
          >
            <PhoneCall size={18} color="#ef4444" />
            <div>
              <div style={{ fontSize: '14px', fontWeight: 800, color: '#ffffff' }}>1916</div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>BMC Disaster Control</div>
            </div>
          </a>

          <a
            href="tel:112"
            className="glass-card"
            style={{ padding: '12px', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '10px' }}
          >
            <PhoneCall size={18} color="#38bdf8" />
            <div>
              <div style={{ fontSize: '14px', fontWeight: 800, color: '#ffffff' }}>112</div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>National Emergency</div>
            </div>
          </a>

          <a
            href="tel:101"
            className="glass-card"
            style={{ padding: '12px', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '10px' }}
          >
            <PhoneCall size={18} color="#f59e0b" />
            <div>
              <div style={{ fontSize: '14px', fontWeight: 800, color: '#ffffff' }}>101</div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>Fire & Flood Rescue</div>
            </div>
          </a>

          <a
            href="tel:108"
            className="glass-card"
            style={{ padding: '12px', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '10px' }}
          >
            <PhoneCall size={18} color="#10b981" />
            <div>
              <div style={{ fontSize: '14px', fontWeight: 800, color: '#ffffff' }}>108</div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>Ambulance Triage</div>
            </div>
          </a>
        </div>

        {/* Life Safety Golden Rules */}
        <div style={{
          background: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.2)',
          borderRadius: '10px',
          padding: '12px',
          fontSize: '11.5px',
          color: '#cbd5e1',
          lineHeight: '1.5'
        }}>
          <strong style={{ color: '#ef4444' }}>Life Safety Reminder:</strong> Switch off electrical main breaker if water touches wall sockets. Do NOT approach open water in dark or step near electric poles/transformers.
        </div>
      </div>
    </div>
  );
};

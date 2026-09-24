'use client';

import React from 'react';
import { AlertTriangle, PhoneCall, ShieldAlert, Waves, MapPin } from 'lucide-react';

interface HeaderProps {
  onSosClick: () => void;
  selectedWard: string;
  onWardChange: (ward: string) => void;
}

export const Header: React.FC<HeaderProps> = ({ onSosClick, selectedWard, onWardChange }) => {
  return (
    <header style={{
      position: 'sticky',
      top: 0,
      zIndex: 50,
      background: 'rgba(7, 10, 20, 0.88)',
      backdropFilter: 'blur(20px)',
      borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
      padding: '12px 20px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: '12px'
    }}>
      {/* Brand & Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{
          width: '38px',
          height: '38px',
          borderRadius: '10px',
          background: 'linear-gradient(135deg, #0284c7, #2563eb)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 15px rgba(56, 189, 248, 0.4)'
        }}>
          <Waves size={22} color="#ffffff" />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '17px', fontWeight: 800, letterSpacing: '-0.3px', color: '#f8fafc' }}>
              JAL-PRAHARI
            </span>
            <span style={{
              fontSize: '10px',
              padding: '2px 7px',
              borderRadius: '999px',
              background: 'rgba(56, 189, 248, 0.15)',
              color: '#38bdf8',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              fontWeight: 700
            }}>
              CITIZEN NOWCAST
            </span>
          </div>
          <div style={{ fontSize: '11px', color: '#94a3b8' }}>
            SIH26085 — High-Resolution Urban Flood Emergency Portal
          </div>
        </div>
      </div>

      {/* Ward Selector & Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        <div className="glass-pill" style={{ padding: '6px 12px' }}>
          <MapPin size={14} color="#38bdf8" />
          <span style={{ color: '#94a3b8', fontSize: '12px' }}>Locality:</span>
          <select
            value={selectedWard}
            onChange={(e) => onWardChange(e.target.value)}
            style={{
              background: 'transparent',
              color: '#f8fafc',
              border: 'none',
              outline: 'none',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            <option value="all" style={{ background: '#070a14' }}>Greater Mumbai (All Wards)</option>
            <option value="F/North" style={{ background: '#070a14' }}>Ward F/North (Sion - Matunga)</option>
            <option value="F/South" style={{ background: '#070a14' }}>Ward F/South (Parel - Hindmata)</option>
            <option value="L" style={{ background: '#070a14' }}>Ward L (Kurla - LBS Marg)</option>
            <option value="H/West" style={{ background: '#070a14' }}>Ward H/West (Bandra - Santacruz)</option>
            <option value="K/West" style={{ background: '#070a14' }}>Ward K/West (Andheri West)</option>
          </select>
        </div>

        {/* Helpline */}
        <a
          href="tel:1916"
          className="glass-pill"
          style={{ textDecoration: 'none', color: '#f8fafc', padding: '6px 12px' }}
          title="Call BMC Disaster Control 24x7"
        >
          <PhoneCall size={14} color="#34d399" />
          <span style={{ fontSize: '12px', fontWeight: 600 }}>BMC Help: 1916</span>
        </a>

        {/* SOS Emergency Button */}
        <button onClick={onSosClick} className="btn-sos">
          <ShieldAlert size={16} />
          <span>EMERGENCY SOS</span>
        </button>
      </div>
    </header>
  );
};

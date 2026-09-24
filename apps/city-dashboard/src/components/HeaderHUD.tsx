'use client';

import React, { useEffect, useState } from 'react';
import { Activity, Cpu, ShieldCheck, Database, Layers, Radio, AlertOctagon } from 'lucide-react';

interface HeaderHUDProps {
  activeTab: 'simulation' | 'drainage' | 'wards' | 'alerts' | 'operator';
  onTabChange: (tab: 'simulation' | 'drainage' | 'wards' | 'alerts' | 'operator') => void;
  massBalanceClosure: number;
}

export const HeaderHUD: React.FC<HeaderHUDProps> = ({
  activeTab,
  onTabChange,
  massBalanceClosure
}) => {
  const [timeStr, setTimeStr] = useState('');

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTimeStr(now.toLocaleTimeString('en-IN', { hour12: false }) + ' IST');
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header style={{
      background: 'rgba(5, 8, 16, 0.95)',
      backdropFilter: 'blur(24px)',
      borderBottom: '1px solid rgba(255, 255, 255, 0.12)',
      padding: '10px 20px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: '12px',
      zIndex: 50
    }}>
      {/* Brand & System Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <div style={{
          width: '38px',
          height: '38px',
          borderRadius: '10px',
          background: 'linear-gradient(135deg, #0284c7, #2563eb)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 20px rgba(56, 189, 248, 0.45)'
        }}>
          <Activity size={22} color="#ffffff" />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '16px', fontWeight: 900, letterSpacing: '-0.3px', color: '#f8fafc' }}>
              UFNS-MUNICIPAL CDSS
            </span>
            <span style={{
              fontSize: '10px',
              padding: '2px 8px',
              borderRadius: '999px',
              background: 'rgba(16, 185, 129, 0.2)',
              color: '#34d399',
              border: '1px solid rgba(16, 185, 129, 0.4)',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              <span className="status-dot green" />
              ONLINE (MUMBAI)
            </span>
          </div>
          <div style={{ fontSize: '11px', color: '#94a3b8' }}>
            SIH26085 — Decision Support System for Urban Flood & Drainage Coupling
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div style={{
        display: 'flex',
        background: 'rgba(15, 23, 42, 0.8)',
        border: '1px solid var(--glass-border)',
        borderRadius: '10px',
        padding: '3px',
        gap: '4px'
      }}>
        <button
          onClick={() => onTabChange('simulation')}
          className={`glass-btn ${activeTab === 'simulation' ? 'glass-btn-active' : ''}`}
        >
          <Layers size={14} /> 2D Simulation
        </button>
        <button
          onClick={() => onTabChange('drainage')}
          className={`glass-btn ${activeTab === 'drainage' ? 'glass-btn-active' : ''}`}
        >
          <Activity size={14} /> Drainage Surcharge
        </button>
        <button
          onClick={() => onTabChange('wards')}
          className={`glass-btn ${activeTab === 'wards' ? 'glass-btn-active' : ''}`}
        >
          <ShieldCheck size={14} /> Ward Risk Index
        </button>
        <button
          onClick={() => onTabChange('alerts')}
          className={`glass-btn ${activeTab === 'alerts' ? 'glass-btn-active' : ''}`}
        >
          <AlertOctagon size={14} /> CAP v1.2 Dispatch
        </button>
        <button
          onClick={() => onTabChange('operator')}
          className={`glass-btn ${activeTab === 'operator' ? 'glass-btn-active' : ''}`}
        >
          <Cpu size={14} /> AI Operator
        </button>
      </div>

      {/* Telemetry Chips & Clock */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div className="glass-pill" style={{ padding: '4px 10px', fontSize: '11px' }}>
          <Database size={12} color="#38bdf8" />
          <span style={{ color: '#94a3b8' }}>Mass Balance:</span>
          <strong style={{ color: '#34d399' }}>{massBalanceClosure.toFixed(2)}%</strong>
        </div>

        <div className="glass-pill" style={{ padding: '4px 10px', fontSize: '11px' }}>
          <Radio size={12} color="#f59e0b" />
          <span style={{ color: '#94a3b8' }}>Solver:</span>
          <strong style={{ color: '#f8fafc' }}>Diffusive Wave</strong>
        </div>

        <div style={{
          background: 'rgba(255, 255, 255, 0.05)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '8px',
          padding: '6px 12px',
          fontWeight: 700,
          fontFamily: 'monospace',
          fontSize: '13px',
          color: '#38bdf8'
        }}>
          {timeStr || '11:30:00 IST'}
        </div>
      </div>
    </header>
  );
};

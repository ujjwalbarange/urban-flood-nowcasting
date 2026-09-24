'use client';

import React from 'react';
import { DrainageNodeTelemetry } from '../types/dashboard';
import { Activity, AlertTriangle, ArrowUpRight, ArrowDownLeft, ShieldCheck, CheckCircle2 } from 'lucide-react';

interface DrainageSurchargeViewProps {
  nodes: DrainageNodeTelemetry[];
}

export const DrainageSurchargeView: React.FC<DrainageSurchargeViewProps> = ({ nodes }) => {
  return (
    <div className="glass-panel" style={{ padding: '24px' }}>
      {/* Scientific Principle Card */}
      <div style={{
        background: 'rgba(2, 132, 199, 0.1)',
        border: '1px solid rgba(56, 189, 248, 0.3)',
        borderRadius: '12px',
        padding: '16px 20px',
        marginBottom: '20px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#38bdf8', fontWeight: 800, fontSize: '13px' }}>
          <Activity size={18} />
          <span>SIH26085 CORE COUPLING INNOVATION: SIGNED ORIFICE EXCHANGE</span>
        </div>
        <p style={{ fontSize: '12.5px', color: '#cbd5e1', marginTop: '6px', lineHeight: '1.5' }}>
          Standard flood tools fail because they assume drains only absorb water. Our 1D/2D hydraulic coupling computes bidirectional exchange:
          <code style={{ background: 'rgba(0,0,0,0.4)', padding: '2px 8px', borderRadius: '4px', margin: '0 6px', color: '#f8fafc', fontFamily: 'monospace' }}>
            Q = Cd × A × √(2g |h_surf - h_drain|) × sign(h_surf - h_drain)
          </code>.
          When drain head exceeds street level (coinciding with high tide), stormwater reverses direction and causes manhole surcharge.
        </p>
      </div>

      {/* Nodes Table */}
      <h3 style={{ fontSize: '16px', fontWeight: 800, color: '#f8fafc', marginBottom: '14px' }}>
        Stormwater Trunk Mains & Outfall Telemetry
      </h3>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12.5px' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.12)', color: '#94a3b8' }}>
              <th style={{ padding: '12px 10px' }}>JUNCTION / NODE ID</th>
              <th style={{ padding: '12px 10px' }}>WARD</th>
              <th style={{ padding: '12px 10px' }}>PIPE CAPACITY</th>
              <th style={{ padding: '12px 10px' }}>CURRENT INFLOW</th>
              <th style={{ padding: '12px 10px' }}>UTILIZATION</th>
              <th style={{ padding: '12px 10px' }}>SURCHARGE HEAD</th>
              <th style={{ padding: '12px 10px' }}>COUPLING REGIME</th>
            </tr>
          </thead>
          <tbody>
            {nodes.map((node) => {
              const utilPercent = Math.round((node.inflowM3s / node.capacityM3s) * 100);
              const isOverloaded = utilPercent > 100;

              return (
                <tr
                  key={node.id}
                  style={{
                    borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
                    background: node.isBackflowing ? 'rgba(239, 68, 68, 0.08)' : 'transparent'
                  }}
                >
                  <td style={{ padding: '12px 10px', fontWeight: 700, color: '#ffffff' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className={`status-dot ${node.isBackflowing ? 'red' : node.surchargeDepthM > 0 ? 'amber' : 'green'}`} />
                      <div>
                        <div>{node.name}</div>
                        <div style={{ fontSize: '11px', color: '#64748b', fontFamily: 'monospace' }}>{node.id}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: '12px 10px', color: '#cbd5e1' }}>{node.ward}</td>
                  <td style={{ padding: '12px 10px', color: '#cbd5e1' }}>{node.capacityM3s.toFixed(1)} m³/s</td>
                  <td style={{ padding: '12px 10px', fontWeight: 700, color: isOverloaded ? '#ef4444' : '#38bdf8' }}>
                    {node.inflowM3s.toFixed(1)} m³/s
                  </td>
                  <td style={{ padding: '12px 10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ width: '80px', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
                        <div style={{
                          width: `${Math.min(100, utilPercent)}%`,
                          height: '100%',
                          background: isOverloaded ? '#ef4444' : utilPercent > 80 ? '#f59e0b' : '#34d399'
                        }} />
                      </div>
                      <span style={{ fontSize: '11.5px', fontWeight: 700, color: isOverloaded ? '#ef4444' : '#cbd5e1' }}>
                        {utilPercent}%
                      </span>
                    </div>
                  </td>
                  <td style={{ padding: '12px 10px', fontWeight: 700, color: node.surchargeDepthM > 0 ? '#ef4444' : '#34d399' }}>
                    {node.surchargeDepthM > 0 ? `+${node.surchargeDepthM.toFixed(2)} m` : '0.00 m'}
                  </td>
                  <td style={{ padding: '12px 10px' }}>
                    <span style={{
                      fontSize: '11px',
                      padding: '3px 8px',
                      borderRadius: '4px',
                      fontWeight: 700,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      background: node.isBackflowing ? 'rgba(239, 68, 68, 0.2)' : node.surchargeDepthM > 0 ? 'rgba(245, 158, 11, 0.2)' : 'rgba(52, 211, 153, 0.2)',
                      color: node.isBackflowing ? '#ef4444' : node.surchargeDepthM > 0 ? '#f59e0b' : '#34d399',
                      border: `1px solid ${node.isBackflowing ? 'rgba(239,68,68,0.4)' : 'transparent'}`
                    }}>
                      {node.isBackflowing ? <ArrowUpRight size={12} /> : <ArrowDownLeft size={12} />}
                      {node.waterLevelStatus.replace('_', ' ')}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

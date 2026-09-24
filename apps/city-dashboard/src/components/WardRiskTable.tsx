'use client';

import React from 'react';
import { WardMetric } from '../types/dashboard';
import { ShieldAlert, Users, Truck, AlertTriangle, ArrowUpDown } from 'lucide-react';

interface WardRiskTableProps {
  wards: WardMetric[];
  onDispatchPump: (wardCode: string) => void;
}

export const WardRiskTable: React.FC<WardRiskTableProps> = ({ wards, onDispatchPump }) => {
  const getGradeStyle = (grade: string) => {
    switch (grade) {
      case 'CRITICAL':
        return { bg: 'rgba(239, 68, 68, 0.2)', text: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.4)' };
      case 'HIGH':
        return { bg: 'rgba(249, 115, 22, 0.2)', text: '#f97316', border: '1px solid rgba(249, 115, 22, 0.4)' };
      case 'MODERATE':
        return { bg: 'rgba(245, 158, 11, 0.2)', text: '#f59e0b', border: '1px solid rgba(245, 158, 11, 0.4)' };
      default:
        return { bg: 'rgba(16, 185, 129, 0.2)', text: '#34d399', border: '1px solid rgba(16, 185, 129, 0.4)' };
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h3 style={{ fontSize: '16px', fontWeight: 800, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldAlert size={18} color="#ef4444" />
            Ward-Level Composite Risk Index (CRI) Leaderboard
          </h3>
          <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
            Multi-criteria prioritization combining depth × flow velocity × population exposure × road cutoffs.
          </p>
        </div>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12.5px' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.12)', color: '#94a3b8' }}>
              <th style={{ padding: '12px 10px' }}>WARD CODE & LOCALITY</th>
              <th style={{ padding: '12px 10px' }}>RISK SCORE</th>
              <th style={{ padding: '12px 10px' }}>SEVERITY GRADE</th>
              <th style={{ padding: '12px 10px' }}>EXPOSED CITIZENS</th>
              <th style={{ padding: '12px 10px' }}>INUNDATED ROADS</th>
              <th style={{ padding: '12px 10px' }}>PUMP UNITS</th>
              <th style={{ padding: '12px 10px' }}>ACTION</th>
            </tr>
          </thead>
          <tbody>
            {wards.map((ward) => {
              const gradeStyle = getGradeStyle(ward.riskGrade);

              return (
                <tr
                  key={ward.code}
                  style={{
                    borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
                    background: ward.riskGrade === 'CRITICAL' ? 'rgba(239, 68, 68, 0.05)' : 'transparent'
                  }}
                >
                  <td style={{ padding: '12px 10px' }}>
                    <div style={{ fontWeight: 800, color: '#f8fafc' }}>
                      Ward {ward.code}
                    </div>
                    <div style={{ fontSize: '11px', color: '#94a3b8' }}>{ward.name}</div>
                    <div style={{ fontSize: '10.5px', color: '#64748b', marginTop: '2px' }}>
                      Hotspots: {ward.criticalSpots.join(', ')}
                    </div>
                  </td>

                  <td style={{ padding: '12px 10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '16px', fontWeight: 900, color: gradeStyle.text }}>
                        {ward.riskScore}
                      </span>
                      <div style={{ width: '60px', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
                        <div style={{
                          width: `${ward.riskScore}%`,
                          height: '100%',
                          background: gradeStyle.text
                        }} />
                      </div>
                    </div>
                  </td>

                  <td style={{ padding: '12px 10px' }}>
                    <span style={{
                      fontSize: '11px',
                      padding: '3px 8px',
                      borderRadius: '4px',
                      fontWeight: 700,
                      background: gradeStyle.bg,
                      color: gradeStyle.text,
                      border: gradeStyle.border
                    }}>
                      {ward.riskGrade}
                    </span>
                  </td>

                  <td style={{ padding: '12px 10px', color: '#e2e8f0', fontWeight: 600 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Users size={13} color="#94a3b8" />
                      {ward.populationAtRisk.toLocaleString()}
                    </div>
                  </td>

                  <td style={{ padding: '12px 10px', color: '#e2e8f0', fontWeight: 600 }}>
                    {ward.floodedRoadKm} km
                  </td>

                  <td style={{ padding: '12px 10px', color: '#38bdf8', fontWeight: 700 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Truck size={13} />
                      {ward.activePumps} Active
                    </div>
                  </td>

                  <td style={{ padding: '12px 10px' }}>
                    <button
                      onClick={() => onDispatchPump(ward.code)}
                      className="glass-btn"
                      style={{
                        padding: '6px 10px',
                        fontSize: '11px',
                        background: 'rgba(2, 132, 199, 0.2)',
                        borderColor: 'rgba(56, 189, 248, 0.4)',
                        color: '#38bdf8'
                      }}
                    >
                      + Dispatch Pump
                    </button>
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

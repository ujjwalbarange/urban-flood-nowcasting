'use client';

import React, { useState } from 'react';
import { FloodAlert } from '../types/citizen';
import { AlertOctagon, ChevronDown, ChevronUp, ShieldCheck, Clock, Compass } from 'lucide-react';

interface AlertBannerProps {
  alert: FloodAlert;
}

export const AlertBanner: React.FC<AlertBannerProps> = ({ alert }) => {
  const [expanded, setExpanded] = useState(false);

  const getSeverityStyle = (sev: string) => {
    switch (sev) {
      case 'red':
        return {
          bg: 'linear-gradient(90deg, rgba(239, 68, 68, 0.18), rgba(220, 38, 38, 0.08))',
          border: '1px solid rgba(239, 68, 68, 0.45)',
          badgeBg: '#ef4444',
          badgeText: '#ffffff',
          titleColor: '#fca5a5'
        };
      case 'orange':
        return {
          bg: 'linear-gradient(90deg, rgba(249, 115, 22, 0.18), rgba(234, 88, 12, 0.08))',
          border: '1px solid rgba(249, 115, 22, 0.45)',
          badgeBg: '#f97316',
          badgeText: '#ffffff',
          titleColor: '#fdba74'
        };
      default:
        return {
          bg: 'linear-gradient(90deg, rgba(234, 179, 8, 0.15), rgba(202, 138, 4, 0.08))',
          border: '1px solid rgba(234, 179, 8, 0.4)',
          badgeBg: '#eab308',
          badgeText: '#000000',
          titleColor: '#fde047'
        };
    }
  };

  const style = getSeverityStyle(alert.severity);

  return (
    <div style={{
      background: style.bg,
      border: style.border,
      borderRadius: '16px',
      padding: '16px 20px',
      boxShadow: '0 8px 30px rgba(0, 0, 0, 0.5)',
      backdropFilter: 'blur(16px)',
      marginBottom: '20px',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Top Alert Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '14px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: '280px' }}>
          <div style={{
            padding: '8px',
            borderRadius: '10px',
            background: style.badgeBg,
            color: style.badgeText,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 16px rgba(239, 68, 68, 0.6)'
          }}>
            <AlertOctagon size={20} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <span style={{
                background: style.badgeBg,
                color: style.badgeText,
                fontWeight: 800,
                fontSize: '11px',
                padding: '2px 8px',
                borderRadius: '4px',
                letterSpacing: '0.6px'
              }}>
                {alert.severity.toUpperCase()} ALERT (CAP v1.2)
              </span>
              <span style={{ fontSize: '12px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Clock size={12} /> Valid until {alert.validUntil}
              </span>
            </div>
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#ffffff', marginTop: '4px', lineHeight: '1.4' }}>
              {alert.headline}
            </h3>
          </div>
        </div>

        {/* Action button to expand */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="btn-ghost"
          style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}
        >
          <span>{expanded ? 'Hide Advisory' : 'Read Action Plan'}</span>
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {/* Affected Wards Pill Chips */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
        <span style={{ fontSize: '11px', color: '#94a3b8', fontWeight: 600 }}>AFFECTED ZONES:</span>
        {alert.affectedWards.map((w, idx) => (
          <span key={idx} style={{
            fontSize: '11px',
            padding: '3px 9px',
            borderRadius: '6px',
            background: 'rgba(255, 255, 255, 0.08)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            color: '#e2e8f0',
            fontWeight: 500
          }}>
            {w}
          </span>
        ))}
      </div>

      {/* Expandable Action Advisory */}
      {expanded && (
        <div style={{
          marginTop: '16px',
          paddingTop: '16px',
          borderTop: '1px solid rgba(255, 255, 255, 0.1)',
          animation: 'fadeIn 0.25s ease'
        }}>
          <p style={{ fontSize: '13px', color: '#cbd5e1', lineHeight: '1.6', marginBottom: '12px' }}>
            {alert.description}
          </p>
          <div style={{
            background: 'rgba(0, 0, 0, 0.3)',
            borderRadius: '10px',
            padding: '12px 16px',
            borderLeft: `4px solid ${style.badgeBg}`
          }}>
            <h4 style={{ fontSize: '12px', fontWeight: 700, color: '#f8fafc', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Standard Operating Citizen Protocol:
            </h4>
            <ul style={{ paddingLeft: '18px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {alert.actionGuidance.map((item, i) => (
                <li key={i} style={{ fontSize: '12.5px', color: '#e2e8f0', lineHeight: '1.4' }}>
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div style={{ marginTop: '10px', fontSize: '11px', color: '#64748b' }}>
            Issued by: {alert.source} • Reference ID: {alert.id}
          </div>
        </div>
      )}
    </div>
  );
};

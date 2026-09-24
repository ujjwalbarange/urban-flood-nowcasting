'use client';

import React from 'react';
import { NowcastForecastItem } from '../types/citizen';
import { CloudRain, Anchor, AlertTriangle, ShieldCheck, Clock, Info } from 'lucide-react';

interface NowcastTickerProps {
  timeline: NowcastForecastItem[];
  provenance?: string;
  currentRate?: number | null;
}

export const NowcastTicker: React.FC<NowcastTickerProps> = ({
  timeline,
  provenance = 'Satellite & NWP lagrangian persistence model',
  currentRate = 0.0,
}) => {
  const getRiskStyle = (risk: string) => {
    switch (risk) {
      case 'EXTREME':
        return {
          bg: 'var(--color-danger-bg)',
          border: 'var(--color-danger-border)',
          text: 'var(--color-danger)',
          badgeBg: '#dc2626',
        };
      case 'HIGH':
        return {
          bg: '#fff7ed',
          border: '#fed7aa',
          text: '#ea580c',
          badgeBg: '#ea580c',
        };
      case 'MEDIUM':
        return {
          bg: 'var(--color-warning-bg)',
          border: 'var(--color-warning-border)',
          text: 'var(--color-warning)',
          badgeBg: '#d97706',
        };
      default:
        return {
          bg: 'var(--color-success-bg)',
          border: 'var(--color-success-border)',
          text: 'var(--color-success)',
          badgeBg: '#059669',
        };
    }
  };

  return (
    <div className="card" style={{ padding: '18px 20px', marginBottom: '16px' }}>
      {/* Header row */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '14px',
        flexWrap: 'wrap',
        gap: '10px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            background: 'var(--color-info-bg)',
            border: '1px solid var(--color-info-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <CloudRain size={18} color="var(--brand-blue)" />
          </div>
          <div>
            <h3 style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
              15–120 Minute Precipitation Nowcast
            </h3>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)', margin: '2px 0 0', fontWeight: 500 }}>
              Short-horizon forward projections • Micro-catchment persistence model
            </p>
          </div>
        </div>

        {/* High Tide Warning & Observational Provenance */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '5px 12px',
            borderRadius: 'var(--radius-full)',
            background: '#fff1f2',
            border: '1px solid #fecdd3',
            color: '#be123c',
            fontSize: '11.5px',
            fontWeight: 700,
          }}>
            <Anchor size={13} color="#e11d48" />
            <span>High Tide Advisory: 4.48m (Sluice gates monitored)</span>
          </div>

          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            padding: '5px 10px',
            borderRadius: 'var(--radius-full)',
            background: 'var(--bg-tertiary)',
            border: '1px solid var(--border-light)',
            fontSize: '11px',
            color: 'var(--text-secondary)',
            fontWeight: 600,
          }}>
            <Clock size={12} />
            <span>Updated every 15m</span>
          </div>
        </div>
      </div>

      {/* Prospective timeline steps */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
        gap: '10px',
      }}>
        {timeline.map((item, idx) => {
          const style = getRiskStyle(item.inundationRisk);
          const isHighest = item.rainfallMmHr > 0 && timeline.every(t => t.rainfallMmHr <= item.rainfallMmHr);

          return (
            <div
              key={idx}
              style={{
                background: style.bg,
                border: `1px solid ${isHighest ? style.badgeBg : style.border}`,
                borderRadius: '10px',
                padding: '12px',
                textAlign: 'center',
                position: 'relative',
                transition: 'transform 0.15s ease, box-shadow 0.15s ease',
              }}
            >
              <div style={{
                fontSize: '11px',
                fontWeight: 700,
                color: 'var(--text-secondary)',
                marginBottom: '6px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '4px',
              }}>
                <Clock size={11} color="var(--text-muted)" />
                {item.timeLabel}
              </div>

              <div style={{
                fontSize: '18px',
                fontWeight: 800,
                color: 'var(--text-primary)',
                marginBottom: '2px',
                letterSpacing: '-0.3px',
              }}>
                {item.rainfallMmHr.toFixed(1)}
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', marginLeft: '3px' }}>
                  mm/h
                </span>
              </div>

              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                Acc: <strong>{item.accumulatedMm.toFixed(1)}</strong> mm
              </div>

              <span style={{
                display: 'inline-block',
                fontSize: '10px',
                padding: '2px 8px',
                borderRadius: '4px',
                background: style.badgeBg,
                color: '#ffffff',
                fontWeight: 700,
                letterSpacing: '0.4px',
              }}>
                {item.inundationRisk}
              </span>
            </div>
          );
        })}
      </div>

      {/* Provenance note */}
      <div style={{
        marginTop: '12px',
        paddingTop: '10px',
        borderTop: '1px dashed var(--border-light)',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        fontSize: '11px',
        color: 'var(--text-muted)',
      }}>
        <Info size={13} />
        <span>
          <strong>Scientific Provenance:</strong> {provenance}.
          Satellite or model precipitation ≠ ground gauge observation.
        </span>
      </div>
    </div>
  );
};

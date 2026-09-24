'use client';

import React, { useEffect, useState } from 'react';
import { Play, Pause, RotateCcw, FastForward, CloudRain, Droplet, Activity, AlertOctagon } from 'lucide-react';
import { SimulationTelemetry } from '../types/dashboard';

interface TimelineControllerProps {
  frames: SimulationTelemetry[];
  currentFrameIndex: number;
  onSelectFrameIndex: (index: number) => void;
}

export const TimelineController: React.FC<TimelineControllerProps> = ({
  frames,
  currentFrameIndex,
  onSelectFrameIndex
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<1 | 2 | 5>(1);

  useEffect(() => {
    if (!isPlaying) return;

    const intervalTime = 2000 / playbackSpeed;
    const timer = setInterval(() => {
      onSelectFrameIndex((currentFrameIndex + 1) % frames.length);
    }, intervalTime);

    return () => clearInterval(timer);
  }, [isPlaying, currentFrameIndex, playbackSpeed, frames.length, onSelectFrameIndex]);

  const frame = frames[currentFrameIndex] || frames[0];

  return (
    <div className="glass-panel" style={{ padding: '14px 20px', marginTop: '14px' }}>
      {/* Simulation KPIs Summary Bar */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: '12px',
        marginBottom: '14px',
        paddingBottom: '14px',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ padding: '8px', borderRadius: '8px', background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8' }}>
            <CloudRain size={18} />
          </div>
          <div>
            <div style={{ fontSize: '10.5px', color: '#94a3b8', fontWeight: 600 }}>RAIN INTENSITY</div>
            <div style={{ fontSize: '15px', fontWeight: 800, color: '#f8fafc' }}>
              {frame.rainfallRateMmHr.toFixed(1)} <span style={{ fontSize: '11px', color: '#94a3b8' }}>mm/h</span>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ padding: '8px', borderRadius: '8px', background: 'rgba(52, 211, 153, 0.15)', color: '#34d399' }}>
            <Droplet size={18} />
          </div>
          <div>
            <div style={{ fontSize: '10.5px', color: '#94a3b8', fontWeight: 600 }}>SURFACE RUNOFF</div>
            <div style={{ fontSize: '15px', fontWeight: 800, color: '#f8fafc' }}>
              {(frame.totalRunoffM3 / 1000).toFixed(0)}k <span style={{ fontSize: '11px', color: '#94a3b8' }}>m³</span>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ padding: '8px', borderRadius: '8px', background: 'rgba(251, 191, 36, 0.15)', color: '#fbbf24' }}>
            <Activity size={18} />
          </div>
          <div>
            <div style={{ fontSize: '10.5px', color: '#94a3b8', fontWeight: 600 }}>DRAIN DISCHARGE</div>
            <div style={{ fontSize: '15px', fontWeight: 800, color: '#f8fafc' }}>
              {frame.drainageDischargeM3s.toFixed(1)} <span style={{ fontSize: '11px', color: '#94a3b8' }}>m³/s</span>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ padding: '8px', borderRadius: '8px', background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' }}>
            <AlertOctagon size={18} />
          </div>
          <div>
            <div style={{ fontSize: '10.5px', color: '#94a3b8', fontWeight: 600 }}>SURCHARGED NODES</div>
            <div style={{ fontSize: '15px', fontWeight: 800, color: frame.surchargingNodesCount > 5 ? '#ef4444' : '#f59e0b' }}>
              {frame.surchargingNodesCount} <span style={{ fontSize: '11px', color: '#94a3b8' }}>Mains</span>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div>
            <div style={{ fontSize: '10.5px', color: '#94a3b8', fontWeight: 600 }}>PEAK FLOOD DEPTH</div>
            <div style={{ fontSize: '16px', fontWeight: 900, color: '#f87171' }}>
              {frame.maxFloodDepthM.toFixed(2)} m
            </div>
          </div>
        </div>
      </div>

      {/* Scrub Bar & Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        {/* Playback Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => onSelectFrameIndex(0)}
            className="glass-btn"
            title="Reset to Hindcast"
          >
            <RotateCcw size={14} />
          </button>

          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="glass-btn"
            style={{
              background: isPlaying ? '#ef4444' : '#0284c7',
              borderColor: isPlaying ? '#ef4444' : '#38bdf8',
              color: '#ffffff',
              padding: '8px 16px',
              fontSize: '13px'
            }}
          >
            {isPlaying ? <Pause size={15} /> : <Play size={15} />}
            <span>{isPlaying ? 'Pause' : 'Play Simulation'}</span>
          </button>

          <button
            onClick={() => setPlaybackSpeed(playbackSpeed === 1 ? 2 : playbackSpeed === 2 ? 5 : 1)}
            className="glass-btn"
            style={{ fontSize: '11px', fontWeight: 700 }}
          >
            <FastForward size={13} /> {playbackSpeed}x Speed
          </button>
        </div>

        {/* Timeline Slider Track */}
        <div style={{ flex: 1, minWidth: '260px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#cbd5e1' }}>
            <span>Hindcast T-15m</span>
            <strong style={{ color: '#38bdf8' }}>Current Step: {frame.timeLabel}</strong>
            <span>Nowcast +90m</span>
          </div>

          <input
            type="range"
            min="0"
            max={frames.length - 1}
            step="1"
            value={currentFrameIndex}
            onChange={(e) => onSelectFrameIndex(parseInt(e.target.value))}
            style={{
              width: '100%',
              accentColor: '#38bdf8',
              height: '6px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          />

          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#64748b' }}>
            {frames.map((f, i) => (
              <span
                key={i}
                onClick={() => onSelectFrameIndex(i)}
                style={{
                  cursor: 'pointer',
                  color: i === currentFrameIndex ? '#38bdf8' : '#64748b',
                  fontWeight: i === currentFrameIndex ? 700 : 400
                }}
              >
                {f.timeLabel.split(' ')[0]}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

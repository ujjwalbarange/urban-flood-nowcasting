'use client';

import React, { useState } from 'react';
import { CrowdReport } from '../types/citizen';
import { Camera, MapPin, ThumbsUp, CheckCircle2, AlertCircle, PlusCircle, X } from 'lucide-react';

interface ReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  reports: CrowdReport[];
  onSubmitReport: (report: CrowdReport) => void;
}

export const ReportModal: React.FC<ReportModalProps> = ({
  isOpen,
  onClose,
  reports,
  onSubmitReport
}) => {
  const [locality, setLocality] = useState('');
  const [ward, setWard] = useState('Ward F/North');
  const [category, setCategory] = useState<'waterlogging' | 'drain_overflow' | 'open_manhole' | 'stranded' | 'tree_fall'>('waterlogging');
  const [depthMeters, setDepthMeters] = useState(0.35);
  const [notes, setNotes] = useState('');
  const [submittedMessage, setSubmittedMessage] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!locality.trim()) return;

    const newReport: CrowdReport = {
      id: `rep-${Date.now()}`,
      locality: locality.trim(),
      ward: ward,
      category: category,
      depthDescription: `${notes || 'Reported by citizen'} (~${Math.round(depthMeters * 100)} cm)`,
      depthMeters: depthMeters,
      reportedAt: 'Just now',
      upvotes: 1,
      status: 'COMMUNITY_REPORTED'
    };

    onSubmitReport(newReport);
    setSubmittedMessage(true);
    setTimeout(() => {
      setSubmittedMessage(false);
      onClose();
      setLocality('');
      setNotes('');
    }, 1500);
  };

  const getDepthVisualLabel = (d: number) => {
    if (d < 0.20) return 'Ankle Deep (~10-20 cm) — Splashing';
    if (d < 0.50) return 'Knee Deep (~30-50 cm) — Impassable for small cars';
    if (d < 0.85) return 'Waist Deep (~60-85 cm) — Heavy current risk';
    return 'Chest Deep / Submerged (> 90 cm) — Severe Life Hazard';
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 100,
      background: 'rgba(3, 6, 13, 0.85)',
      backdropFilter: 'blur(16px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      <div style={{
        background: '#0a101f',
        border: '1px solid rgba(56, 189, 248, 0.3)',
        borderRadius: '16px',
        width: '100%',
        maxWidth: '560px',
        maxHeight: '90vh',
        overflowY: 'auto',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.9), 0 0 30px rgba(56, 189, 248, 0.1)',
        padding: '24px',
        position: 'relative'
      }}>
        {/* Close button */}
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            background: 'rgba(255, 255, 255, 0.08)',
            border: 'none',
            borderRadius: '50%',
            width: '32px',
            height: '32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#cbd5e1',
            cursor: 'pointer'
          }}
        >
          <X size={18} />
        </button>

        {submittedMessage ? (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <div style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: 'rgba(16, 185, 129, 0.2)',
              color: '#10b981',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px'
            }}>
              <CheckCircle2 size={32} />
            </div>
            <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc' }}>
              Report Transmitted to Disaster Control!
            </h3>
            <p style={{ fontSize: '13px', color: '#94a3b8', marginTop: '8px' }}>
              Your geotagged depth observation has been recorded in the nowcasting ledger and dispatched to ward emergency officers.
            </p>
          </div>
        ) : (
          <div>
            <div style={{ marginBottom: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{
                  padding: '4px 8px',
                  borderRadius: '6px',
                  background: 'rgba(56, 189, 248, 0.2)',
                  color: '#38bdf8',
                  fontSize: '11px',
                  fontWeight: 700
                }}>
                  CROWD TELEMETRY
                </span>
              </div>
              <h2 style={{ fontSize: '20px', fontWeight: 800, color: '#f8fafc', marginTop: '6px' }}>
                Report Live Flood or Drain Hazard
              </h2>
              <p style={{ fontSize: '12.5px', color: '#94a3b8', marginTop: '4px' }}>
                Alert fellow citizens and BMC flood response units with your real ground observations.
              </p>
            </div>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#cbd5e1', display: 'block', marginBottom: '6px' }}>
                  Street / Landmark Location *
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(15, 23, 42, 0.9)', padding: '10px 14px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)' }}>
                  <MapPin size={16} color="#38bdf8" />
                  <input
                    type="text"
                    required
                    placeholder="e.g. Near Sion Circle flyover or Bhaudaji Road"
                    value={locality}
                    onChange={(e) => setLocality(e.target.value)}
                    style={{ background: 'transparent', border: 'none', outline: 'none', color: '#f8fafc', fontSize: '13.5px', width: '100%' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: '#cbd5e1', display: 'block', marginBottom: '6px' }}>
                    Municipal Ward
                  </label>
                  <select
                    value={ward}
                    onChange={(e) => setWard(e.target.value)}
                    style={{
                      width: '100%',
                      background: 'rgba(15, 23, 42, 0.9)',
                      color: '#f8fafc',
                      padding: '10px 14px',
                      borderRadius: '8px',
                      border: '1px solid rgba(255,255,255,0.1)',
                      outline: 'none',
                      fontSize: '13px'
                    }}
                  >
                    <option value="Ward F/North">Ward F/North (Sion-Matunga)</option>
                    <option value="Ward F/South">Ward F/South (Parel-Hindmata)</option>
                    <option value="Ward L">Ward L (Kurla-LBS)</option>
                    <option value="Ward H/West">Ward H/West (Bandra)</option>
                    <option value="Ward K/West">Ward K/West (Andheri)</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: '#cbd5e1', display: 'block', marginBottom: '6px' }}>
                    Issue Type
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value as any)}
                    style={{
                      width: '100%',
                      background: 'rgba(15, 23, 42, 0.9)',
                      color: '#f8fafc',
                      padding: '10px 14px',
                      borderRadius: '8px',
                      border: '1px solid rgba(255,255,255,0.1)',
                      outline: 'none',
                      fontSize: '13px'
                    }}
                  >
                    <option value="waterlogging">Road Inundation</option>
                    <option value="drain_overflow">Drain Overflow / Surcharge</option>
                    <option value="open_manhole">Open / Missing Manhole Lid</option>
                    <option value="stranded">Stranded Citizen / Rescue Need</option>
                    <option value="tree_fall">Fallen Tree / Electric Wire</option>
                  </select>
                </div>
              </div>

              {/* Water Depth Slider */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: '#cbd5e1' }}>
                    Observed Water Depth: <strong style={{ color: '#38bdf8' }}>{Math.round(depthMeters * 100)} cm</strong>
                  </label>
                  <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                    {getDepthVisualLabel(depthMeters)}
                  </span>
                </div>
                <input
                  type="range"
                  min="0.05"
                  max="1.20"
                  step="0.05"
                  value={depthMeters}
                  onChange={(e) => setDepthMeters(parseFloat(e.target.value))}
                  style={{
                    width: '100%',
                    accentColor: '#0284c7',
                    height: '6px',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#cbd5e1', display: 'block', marginBottom: '6px' }}>
                  Specific Details / Landmark
                </label>
                <textarea
                  rows={2}
                  placeholder="e.g. Near chemist shop, water entering ground floor stores, power line disconnected"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'rgba(15, 23, 42, 0.9)',
                    color: '#f8fafc',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    border: '1px solid rgba(255,255,255,0.1)',
                    outline: 'none',
                    fontSize: '13px',
                    resize: 'none'
                  }}
                />
              </div>

              {/* Simulated Camera Upload */}
              <div style={{
                border: '1px dashed rgba(255, 255, 255, 0.2)',
                borderRadius: '8px',
                padding: '12px',
                textAlign: 'center',
                background: 'rgba(255, 255, 255, 0.02)',
                cursor: 'pointer'
              }}>
                <Camera size={20} color="#94a3b8" style={{ margin: '0 auto 4px' }} />
                <div style={{ fontSize: '12px', color: '#cbd5e1' }}>Attach Photo / Video (Simulated GPS Verification)</div>
                <div style={{ fontSize: '10.5px', color: '#64748b' }}>Geo-coordinates embedded automatically</div>
              </div>

              <button
                type="submit"
                className="btn-primary"
                style={{ width: '100%', padding: '12px', fontSize: '14px', fontWeight: 700 }}
              >
                Submit Citizen Report
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};

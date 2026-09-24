'use client';

import React, { useState } from 'react';
import { CapAlertPayload } from '../types/dashboard';
import { AlertOctagon, Send, Code, CheckCircle, Copy, Radio } from 'lucide-react';

interface AlertDispatchConsoleProps {
  initialAlert: CapAlertPayload;
  onDispatch: (alert: CapAlertPayload) => void;
}

export const AlertDispatchConsole: React.FC<AlertDispatchConsoleProps> = ({
  initialAlert,
  onDispatch
}) => {
  const [alert, setAlert] = useState<CapAlertPayload>(initialAlert);
  const [showXml, setShowXml] = useState(false);
  const [dispatchedSuccess, setDispatchedSuccess] = useState(false);

  const generateCapXml = (a: CapAlertPayload) => {
    return `<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>${a.identifier}</identifier>
  <sender>${a.sender}</sender>
  <sent>${a.sent}</sent>
  <status>${a.status}</status>
  <msgType>${a.msgType}</msgType>
  <scope>${a.scope}</scope>
  <info>
    <category>Met</category>
    <event>Flash Flood / Drainage Surcharge</event>
    <urgency>${a.urgency}</urgency>
    <severity>${a.severity}</severity>
    <certainty>${a.certainty}</certainty>
    <headline>${a.headline}</headline>
    <description>${a.description}</description>
    <instruction>${a.instruction}</instruction>
    <area>
      <areaDesc>${a.areaDesc}</areaDesc>
      <polygon>${a.polygon}</polygon>
    </area>
  </info>
</alert>`;
  };

  const handleSend = () => {
    onDispatch({ ...alert, status: 'Issued', sent: new Date().toISOString() });
    setDispatchedSuccess(true);
    setTimeout(() => setDispatchedSuccess(false), 3000);
  };

  return (
    <div className="glass-panel" style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{
              fontSize: '11px',
              padding: '2px 8px',
              borderRadius: '4px',
              background: 'rgba(239, 68, 68, 0.2)',
              color: '#ef4444',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              fontWeight: 800
            }}>
              OASIS CAP v1.2 PROTOCOL
            </span>
          </div>
          <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#f8fafc', marginTop: '6px' }}>
            Municipal Alert Dispatch & Emergency Broadcast Console
          </h3>
          <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
            Transmits authenticated XML alerts simultaneously to NDMA Integrated Alert System, sirens, and Citizen App.
          </p>
        </div>

        <button
          onClick={() => setShowXml(!showXml)}
          className="glass-btn"
          style={{ fontSize: '12px' }}
        >
          <Code size={14} /> {showXml ? 'Hide XML Payload' : 'Preview CAP v1.2 XML'}
        </button>
      </div>

      {showXml && (
        <div style={{
          background: '#02050b',
          border: '1px solid rgba(56, 189, 248, 0.3)',
          borderRadius: '10px',
          padding: '16px',
          marginBottom: '20px',
          overflowX: 'auto'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '11px', color: '#94a3b8' }}>
            <span>OASIS XML STANDARDIZED TELEGRAM</span>
            <span style={{ color: '#34d399' }}>VALIDATED SCHEMA</span>
          </div>
          <pre style={{ color: '#38bdf8', fontSize: '11.5px', fontFamily: 'monospace', lineHeight: '1.4' }}>
            {generateCapXml(alert)}
          </pre>
        </div>
      )}

      {/* Form Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '16px' }}>
        <div>
          <label style={{ fontSize: '11.5px', fontWeight: 700, color: '#cbd5e1', display: 'block', marginBottom: '6px' }}>
            SEVERITY LEVEL
          </label>
          <select
            value={alert.severity}
            onChange={(e) => setAlert({ ...alert, severity: e.target.value as any })}
            style={{
              width: '100%',
              background: 'rgba(15, 23, 42, 0.9)',
              color: '#f8fafc',
              padding: '10px 14px',
              borderRadius: '8px',
              border: '1px solid rgba(255,255,255,0.12)',
              outline: 'none',
              fontSize: '13px'
            }}
          >
            <option value="Extreme">Extreme (Red Alert - Life Threatening)</option>
            <option value="Severe">Severe (Orange Alert - Significant Action Needed)</option>
            <option value="Moderate">Moderate (Yellow Alert - Monitor)</option>
            <option value="Minor">Minor (Green Advisory)</option>
          </select>
        </div>

        <div>
          <label style={{ fontSize: '11.5px', fontWeight: 700, color: '#cbd5e1', display: 'block', marginBottom: '6px' }}>
            URGENCY TIMEFRAME
          </label>
          <select
            value={alert.urgency}
            onChange={(e) => setAlert({ ...alert, urgency: e.target.value as any })}
            style={{
              width: '100%',
              background: 'rgba(15, 23, 42, 0.9)',
              color: '#f8fafc',
              padding: '10px 14px',
              borderRadius: '8px',
              border: '1px solid rgba(255,255,255,0.12)',
              outline: 'none',
              fontSize: '13px'
            }}
          >
            <option value="Immediate">Immediate (Take action now)</option>
            <option value="Expected">Expected (Within next 60 minutes)</option>
          </select>
        </div>
      </div>

      <div style={{ marginBottom: '16px' }}>
        <label style={{ fontSize: '11.5px', fontWeight: 700, color: '#cbd5e1', display: 'block', marginBottom: '6px' }}>
          OFFICIAL PUBLIC HEADLINE
        </label>
        <input
          type="text"
          value={alert.headline}
          onChange={(e) => setAlert({ ...alert, headline: e.target.value })}
          style={{
            width: '100%',
            background: 'rgba(15, 23, 42, 0.9)',
            color: '#f8fafc',
            padding: '10px 14px',
            borderRadius: '8px',
            border: '1px solid rgba(255,255,255,0.12)',
            outline: 'none',
            fontSize: '13px'
          }}
        />
      </div>

      <div style={{ marginBottom: '16px' }}>
        <label style={{ fontSize: '11.5px', fontWeight: 700, color: '#cbd5e1', display: 'block', marginBottom: '6px' }}>
          TECHNICAL METEOROLOGICAL & HYDRAULIC DESCRIPTION
        </label>
        <textarea
          rows={3}
          value={alert.description}
          onChange={(e) => setAlert({ ...alert, description: e.target.value })}
          style={{
            width: '100%',
            background: 'rgba(15, 23, 42, 0.9)',
            color: '#f8fafc',
            padding: '10px 14px',
            borderRadius: '8px',
            border: '1px solid rgba(255,255,255,0.12)',
            outline: 'none',
            fontSize: '13px',
            resize: 'none'
          }}
        />
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label style={{ fontSize: '11.5px', fontWeight: 700, color: '#cbd5e1', display: 'block', marginBottom: '6px' }}>
          CITIZEN & FIRST-RESPONDER DIRECTIVE
        </label>
        <textarea
          rows={2}
          value={alert.instruction}
          onChange={(e) => setAlert({ ...alert, instruction: e.target.value })}
          style={{
            width: '100%',
            background: 'rgba(15, 23, 42, 0.9)',
            color: '#f8fafc',
            padding: '10px 14px',
            borderRadius: '8px',
            border: '1px solid rgba(255,255,255,0.12)',
            outline: 'none',
            fontSize: '13px',
            resize: 'none'
          }}
        />
      </div>

      {/* Dispatch Action Button */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ fontSize: '12px', color: '#94a3b8' }}>
          Target Coordinates: <code style={{ color: '#38bdf8' }}>{alert.polygon.slice(0, 32)}...</code>
        </div>

        {dispatchedSuccess ? (
          <div style={{
            background: 'rgba(16, 185, 129, 0.2)',
            border: '1px solid #10b981',
            borderRadius: '8px',
            padding: '10px 20px',
            color: '#34d399',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <CheckCircle size={16} /> Alert Broadcast Dispatched to All Nodes!
          </div>
        ) : (
          <button
            onClick={handleSend}
            className="glass-btn"
            style={{
              background: 'linear-gradient(135deg, #dc2626, #b91c1c)',
              borderColor: '#ef4444',
              color: '#ffffff',
              padding: '12px 24px',
              fontSize: '13px',
              fontWeight: 800,
              boxShadow: '0 0 20px rgba(239, 68, 68, 0.4)'
            }}
          >
            <Radio size={16} /> Broadcast CAP v1.2 Emergency Alert
          </button>
        )}
      </div>
    </div>
  );
};

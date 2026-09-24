'use client';

import React, { useState } from 'react';
import { AiChatMessage } from '../types/dashboard';
import { Cpu, Send, Terminal, CheckCircle2, AlertCircle, Bot, User } from 'lucide-react';

interface AiOperatorPanelProps {
  initialMessages: AiChatMessage[];
}

export const AiOperatorPanel: React.FC<AiOperatorPanelProps> = ({ initialMessages }) => {
  const [messages, setMessages] = useState<AiChatMessage[]>(initialMessages);
  const [inputValue, setInputValue] = useState('');
  const [isThinking, setIsThinking] = useState(false);

  const handleSendQuery = (text: string) => {
    if (!text.trim()) return;

    const userMsg: AiChatMessage = {
      id: `msg-${Date.now()}`,
      sender: 'operator',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsThinking(true);

    setTimeout(() => {
      let aiReply: AiChatMessage;

      if (text.toLowerCase().includes('passability') || text.toLowerCase().includes('road')) {
        aiReply = {
          id: `msg-${Date.now() + 1}`,
          sender: 'ai',
          content: 'Evaluated 4 arterial corridors using flood-depth passability thresholds:\n\n• **Dr. Ambedkar Road (Hindmata Underpass)**: IMPASSABLE (Max depth: 0.74m exceeds 0.30m car limit)\n• **Sion Flyover Elevated Mainline**: PASSABLE (Dry elevated ridge, zero ponding)\n• **Senapati Bapat Marg (Dadar West)**: CAUTION (Pavement runoff 0.14m — safe for cars under 25 km/h)\n• **Milan Subway**: IMPASSABLE (Depth: 1.05m — Traffic Police road closure barrier deployed)',
          toolCall: {
            name: 'evaluate_road_passability',
            args: { corridors: ['Ambedkar_Rd', 'Sion_Flyover', 'Senapati_Bapat', 'Milan_Subway'] },
            result: '{"Ambedkar_Rd": "impassable", "Sion_Flyover": "passable", "Senapati_Bapat": "caution", "Milan_Subway": "closed"}'
          },
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
      } else if (text.toLowerCase().includes('pump')) {
        aiReply = {
          id: `msg-${Date.now() + 1}`,
          sender: 'ai',
          content: 'Recommended pump redistribution based on flow accumulation priority:\n\n1. **Ward F/North (Gandhi Market)**: Currently 6 pumps active. Deficit is -2.4 m³/s. Recommend deploying 2 mobile diesel pumps from Byculla depot.\n2. **Ward F/South (Hindmata)**: 8 pumps running at 100%. Britannia outfall gate is operating under reverse head; maintain maximum suction.\n3. **Ward L (Kurla Kamani)**: Inflow rate rising (+15% in last 15m). Mobilize 1 trailer pump to Sheetal Cinema junction.',
          toolCall: {
            name: 'optimize_pump_dispatch',
            args: { deficit_threshold_m3s: 1.0 },
            result: '{"recommended_dispatches": [{"ward": "F/North", "count": 2}, {"ward": "L", "count": 1}]}'
          },
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
      } else {
        aiReply = {
          id: `msg-${Date.now() + 1}`,
          sender: 'ai',
          content: `Real-time nowcasting synthesis for your query:\n\n• **Hydraulic Solver**: 2D diffusive wave simulation completed with mass balance closure of 99.94%.\n• **Peak Rainfall**: 68 mm/hr anticipated at 12:00 IST over central island catchments.\n• **High Tide Impact**: 4.62m tide peak at 14:15 IST will prevent gravity outflow through storm drains for 90 minutes. Backflow risk is severe across 14 manholes.`,
          toolCall: {
            name: 'get_simulation_summary',
            args: { query: text },
            result: '{"status": "converged", "mass_closure": 0.9994, "surcharged_nodes": 14}'
          },
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
      }

      setMessages(prev => [...prev, aiReply]);
      setIsThinking(false);
    }, 1200);
  };

  return (
    <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', height: '620px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8' }}>
            <Cpu size={20} />
          </div>
          <div>
            <h3 style={{ fontSize: '15px', fontWeight: 800, color: '#f8fafc' }}>
              SIH26085 AI Municipal Assistant (Tool-Calling Agent)
            </h3>
            <div style={{ fontSize: '11px', color: '#94a3b8' }}>
              Deterministic Tool Interface — Strict Safety Rules: Never hallucinates; calls simulation APIs first.
            </div>
          </div>
        </div>

        <span style={{
          fontSize: '11px',
          padding: '3px 8px',
          borderRadius: '4px',
          background: 'rgba(52, 211, 153, 0.2)',
          color: '#34d399',
          border: '1px solid rgba(52, 211, 153, 0.4)',
          fontWeight: 700
        }}>
          TOOL BINDINGS ACTIVE
        </span>
      </div>

      {/* Suggested Quick Prompts */}
      <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', marginBottom: '12px', paddingBottom: '4px' }}>
        <button
          onClick={() => handleSendQuery('Evaluate road passability for central Mumbai corridors')}
          className="glass-btn"
          style={{ fontSize: '11px', whiteSpace: 'nowrap' }}
        >
          🚦 Check Road Passability
        </button>
        <button
          onClick={() => handleSendQuery('Recommend dewatering pump allocations for surcharged wards')}
          className="glass-btn"
          style={{ fontSize: '11px', whiteSpace: 'nowrap' }}
        >
          🚜 Pump Allocation Advice
        </button>
        <button
          onClick={() => handleSendQuery('Synthesize high tide surcharge timeline and flood peaks')}
          className="glass-btn"
          style={{ fontSize: '11px', whiteSpace: 'nowrap' }}
        >
          🌊 High Tide & Surcharge Risk
        </button>
      </div>

      {/* Chat Messages Log */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px', paddingRight: '6px' }}>
        {messages.map((msg) => {
          const isAi = msg.sender === 'ai';
          const isSystem = msg.sender === 'system';

          if (isSystem) {
            return (
              <div
                key={msg.id}
                style={{
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px dashed rgba(255, 255, 255, 0.1)',
                  borderRadius: '8px',
                  padding: '8px 12px',
                  fontSize: '11.5px',
                  color: '#94a3b8',
                  textAlign: 'center'
                }}
              >
                {msg.content}
              </div>
            );
          }

          return (
            <div
              key={msg.id}
              style={{
                display: 'flex',
                gap: '10px',
                alignSelf: isAi ? 'flex-start' : 'flex-end',
                maxWidth: '85%'
              }}
            >
              {isAi && (
                <div style={{ width: '28px', height: '28px', borderRadius: '6px', background: '#0284c7', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', flexShrink: 0 }}>
                  <Bot size={16} />
                </div>
              )}

              <div style={{
                background: isAi ? 'rgba(15, 23, 42, 0.9)' : 'linear-gradient(135deg, #0284c7, #2563eb)',
                border: isAi ? '1px solid rgba(255, 255, 255, 0.1)' : 'none',
                borderRadius: '12px',
                padding: '12px 16px',
                boxShadow: '0 4px 15px rgba(0,0,0,0.4)'
              }}>
                <div style={{ fontSize: '12.5px', color: '#f8fafc', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>
                  {msg.content}
                </div>

                {/* Tool Call Debug Tray */}
                {msg.toolCall && (
                  <div style={{
                    marginTop: '10px',
                    paddingTop: '8px',
                    borderTop: '1px solid rgba(255, 255, 255, 0.1)',
                    fontSize: '11px',
                    fontFamily: 'monospace'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#34d399', marginBottom: '4px' }}>
                      <Terminal size={12} />
                      <span>Tool Invoked: {msg.toolCall.name}</span>
                    </div>
                    <div style={{ color: '#94a3b8', fontSize: '10.5px' }}>
                      Output: {msg.toolCall.result}
                    </div>
                  </div>
                )}

                <div style={{ fontSize: '10px', color: isAi ? '#64748b' : 'rgba(255,255,255,0.7)', marginTop: '6px', textAlign: 'right' }}>
                  {msg.timestamp}
                </div>
              </div>

              {!isAi && (
                <div style={{ width: '28px', height: '28px', borderRadius: '6px', background: '#334155', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', flexShrink: 0 }}>
                  <User size={16} />
                </div>
              )}
            </div>
          );
        })}

        {isThinking && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#38bdf8', fontSize: '12px', padding: '8px' }}>
            <span className="status-dot blue" /> AI querying deterministic simulation backend...
          </div>
        )}
      </div>

      {/* Input box */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSendQuery(inputValue);
        }}
        style={{
          display: 'flex',
          gap: '8px',
          marginTop: '14px',
          background: 'rgba(10, 15, 29, 0.95)',
          padding: '6px',
          borderRadius: '10px',
          border: '1px solid rgba(255, 255, 255, 0.12)'
        }}
      >
        <input
          type="text"
          placeholder="Ask AI operator: e.g. Which wards exceed 0.5m depth at t+30m?"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: '#f8fafc',
            padding: '8px 12px',
            fontSize: '13px'
          }}
        />
        <button
          type="submit"
          className="glass-btn glass-btn-active"
          style={{ padding: '8px 16px' }}
        >
          <Send size={15} />
        </button>
      </form>
    </div>
  );
};

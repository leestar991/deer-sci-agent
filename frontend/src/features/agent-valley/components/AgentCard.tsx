'use client';

import { useEffect, useState, useCallback } from 'react';
import { buildMockHistory } from '../data/mockData';
import type { AgentData } from '../types';

interface AgentCardProps {
  data: AgentData;
  onClose: () => void;
}

export default function AgentCard({ data, onClose }: AgentCardProps) {
  const { agent, charName, state, events = [] } = data;
  const [messages, setMessages] = useState<any[]>([]);

  useEffect(() => {
    const history = buildMockHistory(agent, events);
    setMessages(history);
  }, [agent, events]);

  return (
    <div
      className="card-overlay"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div
        className="agent-card"
        style={{
          background: '#1a1a2e',
          border: '2px solid #4ade80',
          borderRadius: '8px',
          width: '90%',
          maxWidth: '600px',
          maxHeight: '80vh',
          overflow: 'auto',
          color: 'white',
          padding: '24px',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '24px', fontWeight: 'bold', margin: 0 }}>{agent.name}</h2>
          <button
            onClick={onClose}
            style={{
              background: '#ef4444',
              color: 'white',
              border: 'none',
              padding: '8px 16px',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: 'bold',
            }}
          >
            CLOSE
          </button>
        </div>

        <div style={{ marginBottom: '20px' }}>
          <div style={{ display: 'flex', gap: '12px', marginBottom: '12px' }}>
            <span style={{
              background: state === 'working' ? '#4ade80' : state === 'idle' ? '#60a5fa' : '#6b7280',
              padding: '4px 12px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 'bold',
            }}>
              {state.toUpperCase()}
            </span>
            {agent.model && (
              <span style={{
                background: '#374151',
                padding: '4px 12px',
                borderRadius: '4px',
                fontSize: '12px',
              }}>
                {agent.model}
              </span>
            )}
          </div>
          {agent.session_key && (
            <div style={{ fontSize: '12px', opacity: 0.7 }}>
              Session: {agent.session_key}
            </div>
          )}
        </div>

        <div style={{
          borderTop: '1px solid rgba(255, 255, 255, 0.1)',
          paddingTop: '20px',
        }}>
          <h3 style={{ fontSize: '16px', fontWeight: 'bold', marginBottom: '12px' }}>
            Conversation History
          </h3>
          <div style={{
            maxHeight: '400px',
            overflow: 'auto',
            background: 'rgba(0, 0, 0, 0.3)',
            borderRadius: '4px',
            padding: '12px',
          }}>
            {messages.length === 0 ? (
              <div style={{ opacity: 0.5, textAlign: 'center', padding: '20px' }}>
                No conversation history available
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div
                  key={idx}
                  style={{
                    marginBottom: '12px',
                    padding: '8px',
                    background: msg.role === 'user' ? 'rgba(59, 130, 246, 0.2)' : 'rgba(74, 222, 128, 0.2)',
                    borderRadius: '4px',
                    borderLeft: `3px solid ${msg.role === 'user' ? '#3b82f6' : '#4ade80'}`,
                  }}
                >
                  <div style={{ fontSize: '10px', opacity: 0.7, marginBottom: '4px', textTransform: 'uppercase' }}>
                    {msg.role}
                  </div>
                  <div style={{ fontSize: '14px' }}>
                    {msg.content}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

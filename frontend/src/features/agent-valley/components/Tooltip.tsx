'use client';

interface TooltipProps {
  data: {
    data: {
      agent: {
        name: string;
        status: string;
        model?: string;
      };
    };
    pos: {
      x: number;
      y: number;
    };
  } | null;
}

export default function Tooltip({ data }: TooltipProps) {
  if (!data) return null;

  const { agent } = data.data;
  const { pos } = data;

  return (
    <div
      className="agent-tooltip"
      style={{
        position: 'fixed',
        left: pos.x + 10,
        top: pos.y + 10,
        background: 'rgba(0, 0, 0, 0.9)',
        color: 'white',
        padding: '8px 12px',
        borderRadius: '4px',
        fontSize: '12px',
        pointerEvents: 'none',
        zIndex: 1000,
        border: '1px solid rgba(255, 255, 255, 0.2)',
      }}
    >
      <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>{agent.name}</div>
      <div style={{ opacity: 0.8 }}>
        Status: {agent.status}
        {agent.model && ` • ${agent.model}`}
      </div>
    </div>
  );
}

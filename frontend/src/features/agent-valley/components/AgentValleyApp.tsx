'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import GameCanvas from './GameCanvas';
import Tooltip from './Tooltip';
import AgentCard from './AgentCard';
import { DEFAULT_MAP_CONFIG, MAP_VARIANTS } from '../config/constants';
import type { AgentData } from '../types';
import '../styles/agent-valley.css';

const UI_W = 28 * 32;
const UI_H = 20 * 32;
const MAP_TOP_GAP = 54;
const MAP_SCALE_BOOST = 1.8;

export default function AgentValleyApp() {
  const [tooltip, setTooltip] = useState<any>(null);
  const [agentCard, setAgentCard] = useState<AgentData | null>(null);
  const [consoleOpen, setConsoleOpen] = useState(false);
  const [activeMapId, setActiveMapId] = useState(DEFAULT_MAP_CONFIG.id);
  const [cursorState, setCursorState] = useState('normal');
  const [canvasRefreshTrigger, setCanvasRefreshTrigger] = useState(0);
  const layoutRef = useRef<HTMLDivElement>(null);
  const gameEngineRef = useRef<any>(null);
  const [mapSize, setMapSize] = useState<{ w: number; h: number } | null>(null);
  const [viewport, setViewport] = useState(() => ({
    w: typeof window !== 'undefined' ? window.innerWidth : UI_W,
    h: typeof window !== 'undefined' ? window.innerHeight : UI_H,
  }));

  useEffect(() => {
    const el = layoutRef.current;
    if (!el) return;
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) setViewport({ w: width, h: height });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const handleLayoutChange = useCallback(({ sceneW, sceneH }: { sceneW: number; sceneH: number }) => {
    if (sceneW > 0 && sceneH > 0) {
      setMapSize({ w: sceneW, h: sceneH });
    }
  }, []);

  const activeMapConfig = useMemo(
    () => MAP_VARIANTS.find((map) => map.id === activeMapId) || DEFAULT_MAP_CONFIG,
    [activeMapId]
  );

  const handleNpcHover = useCallback((data: any, pos: any) => {
    setTooltip({ data, pos });
  }, []);

  const handleNpcLeave = useCallback(() => {
    setTooltip(null);
  }, []);

  const handleNpcClick = useCallback((data: AgentData) => {
    setAgentCard(data);
    setCanvasRefreshTrigger((n) => n + 1);
  }, []);

  const handleCursorStateChange = useCallback((nextState: string) => {
    setCursorState(nextState || 'normal');
  }, []);

  const handleCloseCard = useCallback(() => {
    setAgentCard(null);
  }, []);

  const mapBaseW = mapSize?.w ?? UI_W;
  const mapBaseH = mapSize?.h ?? UI_H;
  const totalH = mapBaseH * MAP_SCALE_BOOST + MAP_TOP_GAP + 24;
  const scale = Math.min(
    viewport.w / (mapBaseW * MAP_SCALE_BOOST),
    viewport.h / totalH,
  );
  const mapW = Math.round(mapBaseW * scale * MAP_SCALE_BOOST);
  const mapH = Math.round(mapBaseH * scale * MAP_SCALE_BOOST);
  const topGap = Math.round(MAP_TOP_GAP * scale);

  useEffect(() => {
    setMapSize(null);
  }, [activeMapConfig.id]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const tag = (event.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if ((event.target as HTMLElement).isContentEditable) return;
      if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
      if (event.key === 'Escape') { setConsoleOpen(false); return; }
      if (event.key === 'c' || event.key === 'C') { setConsoleOpen((v) => !v); return; }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  return (
    <div
      className={`app-layout agent-town-cursor cursor-${cursorState}`}
      data-map-theme={activeMapConfig.id}
      ref={layoutRef}
    >
      <nav className="town-hud">
        <button
          type="button"
          className={`town-hud-btn town-hud-console ${consoleOpen ? 'is-on' : ''}`}
          onClick={() => setConsoleOpen((prev) => !prev)}
          title={`${consoleOpen ? 'Close' : 'Open'} Console  [C]`}
        >
          <span className="town-hud-pip" />
          <span className="town-hud-icon">☰</span>
          <span className="town-hud-label">CMD</span>
        </button>
      </nav>

      <div
        className="content-stack"
        style={{
          width: mapW,
          height: topGap + mapH,
          alignItems: 'center',
        }}
      >
        <div style={{ height: topGap }} />
        <div style={{ width: mapW, height: mapH, position: 'relative', zIndex: 1 }}>
          <GameCanvas
            key={activeMapConfig.id}
            onNpcHover={handleNpcHover}
            onNpcLeave={handleNpcLeave}
            onNpcClick={handleNpcClick}
            onCursorStateChange={handleCursorStateChange}
            onLayoutChange={handleLayoutChange}
            mapConfig={activeMapConfig}
            refreshTrigger={canvasRefreshTrigger}
            gameEngineRef={gameEngineRef}
          />
        </div>
      </div>

      <Tooltip data={tooltip} />

      {agentCard && (
        <AgentCard
          data={agentCard}
          onClose={handleCloseCard}
        />
      )}
    </div>
  );
}

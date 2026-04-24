'use client';

import { useRef, useEffect, useState } from 'react';
import GameEngine from '../engine/GameEngine';
import type { AgentValleyData } from '../data/realData';
import type { Agent } from '../types';
import { useSubtasks } from '../hooks/useSubtasks';

interface GameCanvasProps {
  onNpcHover?: (data: any, pos: { x: number; y: number }) => void;
  onNpcLeave?: () => void;
  onNpcClick?: (data: any) => void;
  onCursorStateChange?: (state: string) => void;
  onLayoutChange?: (layout: { sceneW: number; sceneH: number }) => void;
  mapConfig: any;
  refreshTrigger?: number;
  gameEngineRef?: React.MutableRefObject<any>;
  agentData: AgentValleyData | null;
  isLoadingData?: boolean;
  isChatting?: boolean;
  isWaitingForUser?: boolean;
  viewedSubtasks?: Set<string>;
  viewedMainAgent?: boolean;
  realtimeMessages?: any[] | null;
}

export default function GameCanvas({
  onNpcHover,
  onNpcLeave,
  onNpcClick,
  onCursorStateChange,
  onLayoutChange,
  mapConfig,
  refreshTrigger = 0,
  gameEngineRef,
  agentData,
  isLoadingData = false,
  isChatting = false,
  isWaitingForUser = false,
  viewedSubtasks = new Set(),
  viewedMainAgent = false,
  realtimeMessages = null,
}: GameCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const loadingRef = useRef<HTMLDivElement>(null);
  const engineRef = useRef<GameEngine | null>(null);
  const [progress, setProgress] = useState(0);
  const [loadText, setLoadText] = useState('Loading assets...');
  const [engineReady, setEngineReady] = useState(false); // Track if engine is fully initialized

  const cbRef = useRef({
    onNpcHover,
    onNpcLeave,
    onNpcClick,
    onCursorStateChange,
    onLayoutChange,
  });
  cbRef.current = {
    onNpcHover,
    onNpcLeave,
    onNpcClick,
    onCursorStateChange,
    onLayoutChange,
  };

  useEffect(() => {
    if (!containerRef.current) return;
    let aborted = false;
    let hideLoadingTimer: NodeJS.Timeout | null = null;

    setEngineReady(false);

    const engine = new GameEngine({ mapConfig });
    engineRef.current = engine;
    if (gameEngineRef) gameEngineRef.current = engine;

    engine.onNpcHover = (...args) => cbRef.current.onNpcHover?.(...args);
    engine.onNpcLeave = (...args) => cbRef.current.onNpcLeave?.(...args);
    engine.onNpcClick = (...args) => cbRef.current.onNpcClick?.(...args);
    engine.onCursorStateChange = (...args) => cbRef.current.onCursorStateChange?.(...args);
    engine.onLayoutChange = (layout) => cbRef.current.onLayoutChange?.(layout);

    (async () => {
      try {
        if (aborted) return;
        engine.init(containerRef.current!);

        if (aborted) return;
        await engine.loadAssets((p, label) => {
          if (aborted) return;
          setProgress(p);
          if (label) setLoadText(label);
        });
        if (aborted) return;

        console.log('[GameCanvas] Engine fully initialized and ready');
        setEngineReady(true); // Mark engine as ready
      } catch (err) {
        console.error('[GameCanvas] init error:', err);
      }

      if (!aborted && loadingRef.current) {
        loadingRef.current.style.opacity = '0';
        loadingRef.current.style.pointerEvents = 'none';
        hideLoadingTimer = setTimeout(() => {
          if (loadingRef.current) {
            loadingRef.current.style.display = 'none';
          }
        }, 400);
      }
    })();

    return () => {
      aborted = true;
      if (hideLoadingTimer) clearTimeout(hideLoadingTimer);
      setEngineReady(false);
      engine.destroy();
      engineRef.current = null;
      if (gameEngineRef) gameEngineRef.current = null;
      cbRef.current.onCursorStateChange?.('normal');
    };
  }, [mapConfig, gameEngineRef]); // Only re-initialize when map config changes

  // Use subtasks hook to monitor stream messages
  // Prioritize realtimeMessages from ChatEmbed, fallback to agentData
  const messages = realtimeMessages || agentData?.thread?.values?.messages;
  console.log('[GameCanvas] 📨 Messages source:', realtimeMessages ? 'realtime' : 'agentData');
  console.log('[GameCanvas] 📨 Messages count:', messages?.length || 0);
  console.log('[GameCanvas] 📨 Has realtimeMessages:', !!realtimeMessages);
  console.log('[GameCanvas] 📨 Has agentData messages:', !!agentData?.thread?.values?.messages);

  // Log tool_calls in messages
  if (messages && messages.length > 0) {
    const messagesWithToolCalls = messages.filter((msg: any) =>
      msg.type === 'ai' && msg.tool_calls && msg.tool_calls.length > 0
    );
    console.log('[GameCanvas] 📨 Messages with tool_calls:', messagesWithToolCalls.length);
    messagesWithToolCalls.forEach((msg: any, index: number) => {
      console.log(`[GameCanvas] 📨 Message ${index + 1} tool_calls:`, msg.tool_calls);
      msg.tool_calls.forEach((toolCall: any) => {
        console.log(`[GameCanvas] 📨   - Tool: ${toolCall.name}, ID: ${toolCall.id}`);
      });
    });
  }

  const { subtasks } = useSubtasks(messages, {
    sceneW: 896,
    sceneH: 640,
  });

  // Log subtasks changes
  useEffect(() => {
    console.log('[GameCanvas] 🤖 Subtasks changed, count:', subtasks.size);
    if (subtasks.size > 0) {
      console.log('[GameCanvas] 🤖 Subtasks details:');
      Array.from(subtasks.values()).forEach((subtask, index) => {
        console.log(`[GameCanvas] 🤖   ${index + 1}. ${subtask.id}:`, {
          name: subtask.name,
          description: subtask.description,
          status: subtask.status,
          charName: subtask.charName,
          position: subtask.position,
        });
      });
    } else {
      console.log('[GameCanvas] 🤖 No subtasks found');
    }
  }, [subtasks]);

  // Separate effect to handle agent data updates (without re-initializing engine)
  useEffect(() => {
    // Wait for engine to be fully initialized and data to be loaded
    if (!engineRef.current || !engineReady || isLoadingData) {
      return;
    }

    const agents: Agent[] = [];

    // 1. Create main agent
    const agentStatus = isChatting ? 'working' : 'idle';

    const mainAgent: Agent = agentData?.thread ? {
      id: agentData.thread.thread_id,
      name: agentData.agentName,
      session_key: agentData.thread.thread_id,
      provider: 'anthropic',
      model: 'claude-sonnet-4',
      status: agentStatus,
      charName: agentData.charName,
      position: { x: 690, y: 550 },
      first_seen_at: agentData.thread.updated_at,
    } : {
      id: 'agent-1',
      name: agentData?.agentName || 'AI Assistant',
      session_key: undefined,
      provider: 'anthropic',
      model: 'claude-sonnet-4',
      status: agentStatus,
      charName: agentData?.charName || 'Alex',
      position: { x: 690, y: 550 },
      first_seen_at: new Date().toISOString(),
    };

    agents.push(mainAgent);

    // 2. Create subtask agents
    console.log('[GameCanvas] 🤖 Creating subtask agents, subtasks count:', subtasks.size);
    for (const [id, subtask] of subtasks.entries()) {
      console.log('[GameCanvas] Creating subtask agent:', {
        id,
        description: subtask.description,
        status: subtask.status,
        charName: subtask.charName,
        position: subtask.position,
      });

      const subtaskAgent: Agent = {
        id: `subtask:${id}`,
        name: subtask.description,
        session_key: undefined,
        provider: 'anthropic',
        model: 'claude-sonnet-4',
        status: subtask.status === 'working' || subtask.status === 'spawning' ? 'working' : 'idle',
        charName: subtask.charName,
        position: subtask.position,
        first_seen_at: new Date(subtask.createdAt).toISOString(),
        is_subagent: true,
        parent_agent_id: mainAgent.id,
      };
      agents.push(subtaskAgent);
      console.log('[GameCanvas] ✅ Subtask agent created:', subtaskAgent.id);
    }

    console.log('[GameCanvas] 📊 Total agents to render:', agents.length, '(1 main +', subtasks.size, 'subtasks)');
    engineRef.current.updateData(agents, []);

    // Update exclamation marks
    // Main agent - show exclamation mark when waiting for user OR when task completed and not viewed yet
    const shouldShowMainAgentMark = isWaitingForUser || (!isChatting && !viewedMainAgent && agentData?.thread?.values?.messages && agentData.thread.values.messages.length > 0);
    if (shouldShowMainAgentMark) {
      engineRef.current.showExclamationMark(mainAgent.id, true);
    } else {
      engineRef.current.showExclamationMark(mainAgent.id, false);
    }

    // Subtask agents
    for (const [id, subtask] of subtasks.entries()) {
      // Only show exclamation mark if subtask is completed AND not viewed
      if (subtask.status === 'completed' && !viewedSubtasks.has(id)) {
        engineRef.current.showExclamationMark(`subtask:${id}`, true);
      } else {
        engineRef.current.showExclamationMark(`subtask:${id}`, false);
      }
    }
  }, [agentData, !!isLoadingData, !!engineReady, !!isChatting, !!isWaitingForUser, subtasks, viewedSubtasks, !!viewedMainAgent]);

  return (
    <div className="townWrap visible">
      <div ref={loadingRef} className="loading">
        <div className="loadingInner">
          <div className="loadingTitle">AGENT VALLEY</div>
          <div className="loadingBar">
            <div className="loadingFill" style={{ width: `${Math.round(progress * 100)}%` }} />
          </div>
          <div className="loadingText">{loadText}</div>
        </div>
      </div>
      <div className="sceneContainer" ref={containerRef} />
    </div>
  );
}

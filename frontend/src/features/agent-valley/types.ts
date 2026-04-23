// Agent Valley Type Definitions

export interface Agent {
  id: string;
  name: string;
  session_key?: string;
  provider?: string;
  model?: string;
  status: 'idle' | 'working' | 'pending' | 'offline';
  charName: string;
  position?: { x: number; y: number };
  first_seen_at?: string;
  is_subagent?: boolean;
  parent_agent_id?: string;
  subagent_tool_call_id?: string;
  subagent_description?: string;
  has_new_result?: boolean;
}

export interface AgentEvent {
  id: string;
  agent_id: string;
  status: 'running' | 'completed' | 'failed';
  start_time: string;
  end_time?: string;
  total_tokens?: number;
  conversations?: ConversationMessage[];
}

export interface ConversationMessage {
  id?: string;
  role: 'user' | 'assistant' | 'tool' | 'tool_call';
  content?: string;
  text?: string;
  content_text?: string;
  timestamp?: string;
  tool_name?: string;
  tool_calls?: ToolCall[];
  args?: any;
  result?: any;
  is_error?: boolean;
  result_pending?: boolean;
}

export interface ToolCall {
  id: string;
  tool_name: string;
  arguments?: any;
  result?: any;
  is_error?: boolean;
  result_pending?: boolean;
}

export interface AgentData {
  agent: Agent;
  charName: string;
  state: 'idle' | 'working' | 'pending' | 'offline';
  event?: AgentEvent;
  events?: AgentEvent[];
  isPending?: boolean;
  totalTokens?: number;
  subagents?: Agent[];
}

export interface FetchDataResponse {
  agents: Agent[];
  events: AgentEvent[];
}

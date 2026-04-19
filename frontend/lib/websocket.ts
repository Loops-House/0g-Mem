/**
 * websocket.ts — WebSocket client for the Desktop Chat App.
 *
 * Connects to the Agent Runtime WebSocket endpoint.
 * The Agent Runtime connects to the Memory WebSocket internally.
 */

export type AgentMode = "assistant" | "coding" | "research";
export type Channel = "telegram" | "desktop";

// ─── Inbound messages (Agent Runtime → Client) ─────────────────────────────────

export interface MemRetrievedMsg {
  type: "memory_retrieved";
  memories: MemoryEntry[];
  count: number;
}

export interface ToolCallMsg {
  type: "tool_call";
  tool: string;
  input: string;
  result: string | null;
  status: "pending" | "done" | "error";
}

export interface AgentResponseMsg {
  type: "response";
  text: string;
  memories_written: number;
  tool_calls: number;
  session_id: string;
}

export interface ErrorMsg {
  type: "error";
  message: string;
  code?: string;
}

export type InboundMsg = MemRetrievedMsg | ToolCallMsg | AgentResponseMsg | ErrorMsg;

// ─── Outbound messages (Client → Agent Runtime) ───────────────────────────────

export interface SessionStartMsg {
  type: "session_start";
  session_id: string;
  user_id: string;
  channel: Channel;
  mode: AgentMode;
}

export interface UserMessageMsg {
  type: "message";
  session_id: string;
  text: string;
  mode: AgentMode;
}

export interface SessionEndMsg {
  type: "session_end";
  session_id: string;
}

export type OutboundMsg = SessionStartMsg | UserMessageMsg | SessionEndMsg;

// ─── Shared types ─────────────────────────────────────────────────────────────

export interface MemoryEntry {
  blob_id: string;
  text: string;
  memory_type: "episodic" | "semantic" | "procedural" | "working";
  score: number;
  created_at: number;
}

// ─── WebSocket client ──────────────────────────────────────────────────────────

export class AgentWSClient {
  private ws: WebSocket | null = null;
  private url: string;
  private userId: string;
  private sessionId: string;
  private mode: AgentMode;
  private channel: Channel;
  private messageHandler: ((msg: InboundMsg) => void) | null = null;
  private reconnectDelay = 1000;
  private maxReconnects = 5;
  private reconnectCount = 0;
  private shouldReconnect = false;

  constructor(url: string, userId: string, sessionId: string, mode: AgentMode = "assistant") {
    this.url = url.replace("http", "ws").replace("https", "wss");
    this.userId = userId;
    this.sessionId = sessionId;
    this.mode = mode;
    this.channel = "desktop";
  }

  onMessage(handler: (msg: InboundMsg) => void) {
    this.messageHandler = handler;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(
          `${this.url}/memory/session/${this.userId}?mode=${this.mode}&channel=${this.channel}`
        );

        this.ws.onopen = () => {
          // Send session_start immediately on connect
          this._send({
            type: "session_start",
            session_id: this.sessionId,
            user_id: this.userId,
            channel: this.channel,
            mode: this.mode,
          } as SessionStartMsg);
          this.reconnectCount = 0;
          this.reconnectDelay = 1000;
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const msg: InboundMsg = JSON.parse(event.data as string);
            this.messageHandler?.(msg);
          } catch {
            console.error("Failed to parse WS message:", event.data);
          }
        };

        this.ws.onerror = (err) => {
          console.error("WebSocket error:", err);
          reject(err);
        };

        this.ws.onclose = () => {
          if (this.shouldReconnect && this.reconnectCount < this.maxReconnects) {
            this.reconnectCount++;
            setTimeout(() => {
              this.connect().catch(console.error);
            }, this.reconnectDelay);
            this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
          }
        };
      } catch (err) {
        reject(err);
      }
    });
  }

  send(text: string) {
    this._send({
      type: "message",
      session_id: this.sessionId,
      text,
      mode: this.mode,
    } as UserMessageMsg);
  }

  end() {
    this.shouldReconnect = false;
    this._send({ type: "session_end", session_id: this.sessionId } as SessionEndMsg);
    this.ws?.close();
    this.ws = null;
  }

  private _send(msg: OutboundMsg) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }
}

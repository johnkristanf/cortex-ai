export type AgentMode = "cortex" | "researcher";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  downloadUrl?: string;
  isStreaming?: boolean;
  timestamp: number;
}

export interface Thread {
  id: string;
  title: string;
  preview: string;
  createdAt: number;
  messages: Message[];
}

export interface ChatRequest {
  message: string;
  thread_id: string;
  user_id?: string;
  google_access_token?: string;
  latitude?: number;
  longitude?: number;
  file_name?: string;
  file_base64?: string;
}

export interface SSEPayload {
  text?: string;
  error?: string;
  done?: boolean;
  download_url?: string;
}

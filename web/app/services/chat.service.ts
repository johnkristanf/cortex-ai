import type { ChatRequest, SSEPayload } from "~/types/chat";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:9000";

/**
 * ChatService – class-based service for Cortex AI chat endpoints.
 * Uses axios for non-streaming requests and native fetch for SSE streaming.
 */
export class ChatService {
  private static readonly baseUrl = API_URL;

  /**
   * Stream tokens from the main Cortex AI agent (/chat).
   * Returns an async generator of SSEPayload objects.
   */
  static async *streamChat(
    payload: ChatRequest,
    signal?: AbortSignal
  ): AsyncGenerator<SSEPayload> {
    yield* ChatService.streamEndpoint("/chat", payload, signal);
  }

  /**
   * Stream tokens from the Product Researcher agent (/researcher/chat).
   * Also emits { download_url } when the Excel file is ready.
   */
  static async *streamResearcher(
    payload: ChatRequest,
    signal?: AbortSignal
  ): AsyncGenerator<SSEPayload> {
    yield* ChatService.streamEndpoint("/researcher/chat", payload, signal);
  }

  // ─── private ────────────────────────────────────────────────────────────────

  private static async *streamEndpoint(
    path: string,
    payload: ChatRequest,
    signal?: AbortSignal
  ): AsyncGenerator<SSEPayload> {
    const response = await fetch(`${ChatService.baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });

    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`);
    }

    if (!response.body) {
      throw new Error("ReadableStream not supported in this environment.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) continue;

          const jsonStr = trimmed.slice(5).trim();
          if (!jsonStr) continue;

          try {
            const parsed = JSON.parse(jsonStr) as SSEPayload;
            yield parsed;
          } catch {
            // skip malformed SSE lines
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }
}

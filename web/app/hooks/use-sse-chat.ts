import { useState, useCallback, useRef } from "react";
import { v4 as uuid } from "uuid";
import { ChatService } from "~/services/chat.service";
import { ThreadStore } from "~/services/thread.store";
import type { Message, Thread, AgentMode } from "~/types/chat";

interface UseSSEChatOptions {
  threadId: string;
  onThreadsChange: (threads: Thread[]) => void;
}

export function useSSEChat({ threadId, onThreadsChange }: UseSSEChatOptions) {
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (text: string, mode: AgentMode) => {
      if (!text.trim() || isStreaming) return;

      // Add user message
      const userMsg: Message = {
        id: uuid(),
        role: "user",
        content: text,
        timestamp: Date.now(),
      };
      let updated = ThreadStore.addMessage(threadId, userMsg);
      onThreadsChange(updated);

      // Placeholder assistant message for streaming
      const assistantId = uuid();
      const assistantMsg: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        isStreaming: true,
        timestamp: Date.now(),
      };
      updated = ThreadStore.addMessage(threadId, assistantMsg);
      onThreadsChange(updated);

      setIsStreaming(true);
      abortRef.current = new AbortController();

      let accumulated = "";
      let downloadUrl: string | undefined;

      try {
        const stream =
          mode === "researcher"
            ? ChatService.streamResearcher(
                { message: text, thread_id: threadId },
                abortRef.current.signal
              )
            : ChatService.streamChat(
                { message: text, thread_id: threadId },
                abortRef.current.signal
              );

        for await (const payload of stream) {
          if (payload.error) {
            accumulated += `\n\n⚠️ Error: ${payload.error}`;
          }
          if (payload.text) {
            accumulated += payload.text;
          }
          if (payload.download_url) {
            downloadUrl = payload.download_url;
          }
          if (payload.done) break;

          // Update streaming message content in store
          const partial: Message = {
            id: assistantId,
            role: "assistant",
            content: accumulated,
            isStreaming: true,
            downloadUrl,
            timestamp: assistantMsg.timestamp,
          };
          updated = ThreadStore.addMessage(threadId, partial);
          onThreadsChange(updated);
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          accumulated += "\n\n⚠️ Connection lost.";
        }
      } finally {
        // Finalise the message (no longer streaming)
        const final: Message = {
          id: assistantId,
          role: "assistant",
          content: accumulated || "…",
          isStreaming: false,
          downloadUrl,
          timestamp: assistantMsg.timestamp,
        };
        updated = ThreadStore.addMessage(threadId, final);
        onThreadsChange(updated);
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [threadId, isStreaming, onThreadsChange]
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { sendMessage, isStreaming, abort };
}

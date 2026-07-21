import { useState, useEffect, useRef, useCallback } from "react";
import { Bot, Sparkles } from "lucide-react";
import { AppSidebar } from "~/components/app-sidebar";
import { ChatMessage } from "~/components/chat-message";
import { ChatInput } from "~/components/chat-input";
import { useSSEChat } from "~/hooks/use-sse-chat";
import { ThreadStore } from "~/services/thread.store";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "~/components/ui/sidebar";
import { Separator } from "~/components/ui/separator";
import type { Thread, AgentMode } from "~/types/chat";

export function meta() {
  return [
    { title: "Cortex AI – Chat" },
    { name: "description", content: "AI-powered agent chat by Cortex AI" },
  ];
}

export default function ChatPage() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [mode, setMode] = useState<AgentMode>("cortex");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load threads on mount
  useEffect(() => {
    const loaded = ThreadStore.getAll();
    setThreads(loaded);
    if (loaded.length > 0) {
      setActiveThreadId(loaded[0].id);
    }
  }, []);

  const activeThread = threads.find((t) => t.id === activeThreadId) ?? null;

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeThread?.messages]);

  const handleThreadsChange = useCallback((updated: Thread[]) => {
    setThreads(updated);
  }, []);

  const { sendMessage, isStreaming, abort } = useSSEChat({
    threadId: activeThreadId ?? "",
    onThreadsChange: handleThreadsChange,
  });

  const handleNewThread = useCallback(() => {
    const thread = ThreadStore.create();
    setThreads(ThreadStore.getAll());
    setActiveThreadId(thread.id);
  }, []);

  const handleSelectThread = useCallback((id: string) => {
    setActiveThreadId(id);
  }, []);

  const handleDeleteThread = useCallback(
    (id: string) => {
      const updated = ThreadStore.deleteThread(id);
      setThreads(updated);
      if (activeThreadId === id) {
        setActiveThreadId(updated[0]?.id ?? null);
      }
    },
    [activeThreadId]
  );

  const handleModeChange = useCallback((newMode: AgentMode) => {
    setMode(newMode);
  }, []);

  const handleSend = useCallback(
    (text: string) => {
      if (!activeThreadId) {
        const thread = ThreadStore.create();
        setThreads(ThreadStore.getAll());
        setActiveThreadId(thread.id);
        // send after state update via setTimeout
        setTimeout(() => sendMessage(text, mode), 0);
        return;
      }
      sendMessage(text, mode);
    },
    [activeThreadId, mode, sendMessage]
  );

  return (
    <SidebarProvider>
      <AppSidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onSelectThread={handleSelectThread}
        onNewThread={handleNewThread}
        onDeleteThread={handleDeleteThread}
      />

      <SidebarInset className="flex flex-col h-screen overflow-hidden bg-gray-50/40">
        {/* Header */}
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-white px-4 shadow-xs">
          <SidebarTrigger className="-ml-1 text-muted-foreground hover:text-foreground" />
          <Separator orientation="vertical" className="mr-1 h-4" />

          {activeThread ? (
            <div className="flex items-center gap-2 min-w-0">
              <Bot className="h-4 w-4 text-primary shrink-0" />
              <span className="truncate text-sm font-medium">
                {activeThread.title}
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium text-muted-foreground">
                Select or start a chat
              </span>
            </div>
          )}

          {isStreaming && (
            <div className="ml-auto flex items-center gap-1.5 text-xs text-primary">
              <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
              Generating…
            </div>
          )}
        </header>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto">
          {!activeThread || activeThread.messages.length === 0 ? (
            <EmptyState onNew={handleNewThread} />
          ) : (
            <div className="flex flex-col py-4">
              {activeThread.messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Chat input */}
        <ChatInput
          mode={mode}
          isStreaming={isStreaming}
          onSend={handleSend}
          onAbort={abort}
          onModeChange={handleModeChange}
        />
      </SidebarInset>
    </SidebarProvider>
  );
}

function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 px-6 py-24 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 shadow-inner">
        <Sparkles className="h-8 w-8 text-primary" />
      </div>
      <div>
        <h2 className="text-xl font-semibold text-foreground">
          How can I help you today?
        </h2>
        <p className="mt-1 text-sm text-muted-foreground max-w-sm mx-auto">
          Ask me anything — I can help with tasks, answer questions, and perform research on your behalf. Use the mode toggle below to enable Research Mode for deep-dive product analysis.
        </p>
      </div>
      <div className="flex flex-col sm:flex-row gap-3 mt-2">
        <button
          onClick={() => onNew()}
          className="flex items-center gap-2 rounded-xl border border-primary/30 bg-primary/5 px-6 py-3 text-sm font-medium text-primary shadow-xs hover:bg-primary/10 transition-all"
        >
          <Bot className="h-4 w-4" />
          Start Chat
        </button>
      </div>
    </div>
  );
}

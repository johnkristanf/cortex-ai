import { useState, useRef, useCallback } from "react";
import { Send, Square, Bot, FlaskConical } from "lucide-react";
import { Button } from "~/components/ui/button";
import { Textarea } from "~/components/ui/textarea";
import { cn } from "~/lib/utils";
import type { AgentMode } from "~/types/chat";

interface ChatInputProps {
  mode: AgentMode;
  isStreaming: boolean;
  onSend: (text: string) => void;
  onAbort: () => void;
  onModeChange: (mode: AgentMode) => void;
}

export function ChatInput({
  mode,
  isStreaming,
  onSend,
  onAbort,
  onModeChange,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming) return;
    onSend(trimmed);
    setValue("");
    textareaRef.current?.focus();
  }, [value, isStreaming, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-border bg-white px-4 pt-3 pb-4">
      {/* Mode toggle */}
      <div className="mb-2 flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Mode:</span>
        <div className="flex items-center gap-1 rounded-full border border-border bg-muted/40 p-0.5">
          <button
            id="toggle-cortex-mode"
            onClick={() => onModeChange("cortex")}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-all",
              mode === "cortex"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Bot className="h-3 w-3" />
            Cortex AI
          </button>
          <button
            id="toggle-research-mode"
            onClick={() => onModeChange("researcher")}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-all",
              mode === "researcher"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <FlaskConical className="h-3 w-3" />
            Research Mode
          </button>
        </div>

        {mode === "researcher" && (
          <span className="ml-auto text-[10px] text-primary/70 font-medium animate-pulse">
            🔬 Product research active
          </span>
        )}
      </div>

      {/* Textarea + send */}
      <div className="flex items-end gap-2">
        <div className="relative flex-1">
          <Textarea
            ref={textareaRef}
            id="chat-input"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              mode === "researcher"
                ? "Describe a product category to research…"
                : "Message Cortex AI… (Enter to send, Shift+Enter for newline)"
            }
            rows={1}
            className={cn(
              "resize-none overflow-hidden min-h-[44px] max-h-[160px] pr-2 text-sm",
              "focus-visible:ring-primary/40 rounded-xl border-border",
              "transition-all duration-150"
            )}
            style={{
              height: "auto",
            }}
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = Math.min(el.scrollHeight, 160) + "px";
            }}
            disabled={isStreaming}
          />
        </div>

        {isStreaming ? (
          <Button
            id="abort-button"
            size="icon"
            variant="outline"
            onClick={onAbort}
            className="h-11 w-11 shrink-0 rounded-xl border-destructive/30 text-destructive hover:bg-destructive/5"
            title="Stop generating"
          >
            <Square className="h-4 w-4 fill-current" />
          </Button>
        ) : (
          <Button
            id="send-button"
            size="icon"
            onClick={handleSend}
            disabled={!value.trim()}
            className="h-11 w-11 shrink-0 rounded-xl bg-primary hover:bg-primary/90 shadow-sm"
            title="Send message"
          >
            <Send className="h-4 w-4" />
          </Button>
        )}
      </div>

      <p className="mt-1.5 text-center text-[10px] text-muted-foreground">
        AI can make mistakes. Verify important information.
      </p>
    </div>
  );
}

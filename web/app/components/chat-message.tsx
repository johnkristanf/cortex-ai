import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Download, Bot, User } from "lucide-react";
import { Button } from "~/components/ui/button";
import { Avatar, AvatarFallback } from "~/components/ui/avatar";
import type { Message } from "~/types/chat";
import { cn } from "~/lib/utils";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:9000";

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex gap-3 px-4 py-3 group",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      <Avatar className="h-8 w-8 shrink-0 mt-0.5">
        <AvatarFallback
          className={cn(
            "text-xs font-semibold",
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-violet-100 text-violet-700"
          )}
        >
          {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>

      {/* Bubble */}
      <div
        className={cn(
          "flex max-w-[75%] flex-col gap-1",
          isUser ? "items-end" : "items-start"
        )}
      >
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-xs",
            isUser
              ? "bg-primary text-primary-foreground rounded-tr-sm"
              : "bg-white border border-border text-foreground rounded-tl-sm"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div
              className={cn(
                "chat-markdown",
                message.isStreaming && "streaming-cursor"
              )}
            >
              {message.content ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              ) : (
                <span className="text-muted-foreground text-xs animate-pulse">
                  Thinking…
                </span>
              )}
            </div>
          )}
        </div>

        {/* Download link for researcher */}
        {message.downloadUrl && (
          <a
            href={`${API_URL}${message.downloadUrl}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Button
              size="sm"
              variant="outline"
              className="gap-2 border-primary/30 text-primary hover:bg-primary/5 mt-1"
            >
              <Download className="h-3.5 w-3.5" />
              Download Report (.xlsx)
            </Button>
          </a>
        )}

        <span className="text-[10px] text-muted-foreground px-1">
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
    </div>
  );
}

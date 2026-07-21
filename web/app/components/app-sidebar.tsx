import * as React from "react";
import { MessageSquare, Plus, Trash2, Bot, Sparkles } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "~/components/ui/sidebar";
import type { Thread } from "~/types/chat";

interface AppSidebarProps extends React.ComponentProps<typeof Sidebar> {
  threads: Thread[];
  activeThreadId: string | null;
  onSelectThread: (id: string) => void;
  onNewThread: () => void;
  onDeleteThread: (id: string) => void;
}

export function AppSidebar({
  threads,
  activeThreadId,
  onSelectThread,
  onNewThread,
  onDeleteThread,
  ...props
}: AppSidebarProps) {
  return (
    <Sidebar {...props}>
      {/* ── Header ── */}
      <SidebarHeader className="border-b border-sidebar-border px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-semibold leading-none">Cortex AI</p>
            <p className="text-xs text-muted-foreground">Agent Chat</p>
          </div>
        </div>
      </SidebarHeader>

      {/* ── Content ── */}
      <SidebarContent className="gap-0">
        <SidebarGroup>
          <SidebarGroupLabel className="flex items-center justify-between pr-2">
            <span className="flex items-center gap-1.5">
              <Bot className="h-3.5 w-3.5 text-primary" />
              Chats
            </span>
            <button
              id="new-thread"
              onClick={() => onNewThread()}
              className="flex h-5 w-5 items-center justify-center rounded hover:bg-sidebar-accent transition-colors"
              title="New Chat"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {threads.length === 0 && (
                <li className="px-3 py-2 text-xs text-muted-foreground italic">
                  No chats yet
                </li>
              )}
              {threads.map((thread) => (
                <SidebarMenuItem key={thread.id}>
                  <SidebarMenuButton
                    isActive={thread.id === activeThreadId}
                    onClick={() => onSelectThread(thread.id)}
                    className="group h-auto py-2 flex-col items-start gap-0.5"
                  >
                    <div className="flex w-full items-center gap-2">
                      <MessageSquare className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                      <span className="truncate text-sm font-medium leading-none">
                        {thread.title}
                      </span>
                    </div>
                    {thread.preview && (
                      <p className="ml-5.5 truncate text-xs text-muted-foreground">
                        {thread.preview}
                      </p>
                    )}
                  </SidebarMenuButton>
                  <SidebarMenuAction
                    showOnHover
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteThread(thread.id);
                    }}
                    className="text-muted-foreground hover:text-destructive"
                    title="Delete thread"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </SidebarMenuAction>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      {/* ── Footer ── */}
      <SidebarFooter className="border-t border-sidebar-border p-3">
        <p className="text-center text-[10px] text-muted-foreground">
          Cortex AI · Powered by LangGraph
        </p>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  );
}

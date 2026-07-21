import type { Thread, Message, AgentMode } from "~/types/chat";
import { v4 as uuid } from "uuid";

const STORAGE_KEY = "cortex_threads";

/**
 * ThreadStore – class-based service for persisting chat threads
 * in localStorage.
 */
export class ThreadStore {
  static getAll(): Thread[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      return JSON.parse(raw) as Thread[];
    } catch {
      return [];
    }
  }

  static save(threads: Thread[]): void {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(threads));
  }

  static create(): Thread {
    const thread: Thread = {
      id: uuid(),
      title: "New Chat",
      preview: "",
      createdAt: Date.now(),
      messages: [],
    };
    const all = ThreadStore.getAll();
    ThreadStore.save([thread, ...all]);
    return thread;
  }

  static update(threadId: string, patch: Partial<Thread>): Thread[] {
    const all = ThreadStore.getAll().map((t) =>
      t.id === threadId ? { ...t, ...patch } : t
    );
    ThreadStore.save(all);
    return all;
  }

  static addMessage(threadId: string, message: Message): Thread[] {
    const all = ThreadStore.getAll().map((t) => {
      if (t.id !== threadId) return t;
      const messages = [...t.messages.filter((m) => m.id !== message.id), message];
      const preview =
        message.role === "user"
          ? message.content.slice(0, 60)
          : t.preview || message.content.slice(0, 60);
      const title =
        t.title === "New Chat" && message.role === "user"
          ? message.content.slice(0, 36) || "New Chat"
          : t.title;
      return { ...t, messages, preview, title };
    });
    ThreadStore.save(all);
    return all;
  }

  static deleteThread(threadId: string): Thread[] {
    const all = ThreadStore.getAll().filter((t) => t.id !== threadId);
    ThreadStore.save(all);
    return all;
  }

  static find(threadId: string): Thread | undefined {
    return ThreadStore.getAll().find((t) => t.id === threadId);
  }
}

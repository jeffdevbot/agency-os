import type { AuditResponse, ViewId } from "../types";

export interface ChatResult {
  response: string;
  switchToView?: ViewId;
}

export async function sendChatMessage(
  userMessage: string,
  auditData: AuditResponse,
  conversationHistory: Array<{ role: "user" | "assistant"; content: string }>,
): Promise<ChatResult> {
  const res = await fetch("/api/adscope/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      userMessage,
      auditData,
      conversationHistory,
    }),
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => undefined);
    throw new Error(detail?.detail || "Chat request failed");
  }

  const data = await res.json();

  return {
    response: data.response as string,
    switchToView: data.switchToView as ViewId | undefined,
  };
}

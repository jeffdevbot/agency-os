"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { type AuditResponse, type ViewId } from "../types";
import { sendChatMessage } from "../services/chat";

interface ChatPaneProps {
    auditData: AuditResponse;
    onViewChange: (viewId: ViewId) => void;
}

export function ChatPane({ auditData, onViewChange }: ChatPaneProps) {
    const [messages, setMessages] = useState<
        Array<{ role: "user" | "assistant"; content: string }>
    >([
        {
            role: "assistant",
            content:
                "👋 I'm your Ad Auditor. I can help you navigate your audit results. Try asking:\n• Show me money pits\n• What's in the waste bin?\n• Compare branded vs generic performance",
        },
    ]);
    const [input, setInput] = useState("");
    const [isProcessing, setIsProcessing] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSendMessage = useCallback(async () => {
        if (!input.trim() || isProcessing) return;

        const userMessage = input.trim();
        setInput("");
        setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
        setIsProcessing(true);

        try {
            const conversationHistory = messages.map((msg) => ({
                role: msg.role as "user" | "assistant",
                content: msg.content,
            }));

            const result = await sendChatMessage(
                userMessage,
                auditData,
                conversationHistory
            );

            setMessages((prev) => [
                ...prev,
                { role: "assistant", content: result.response },
            ]);

            if (result.switchToView) {
                onViewChange(result.switchToView);
            }
        } catch (error) {
            console.error("Chat error:", error);
            setMessages((prev) => [
                ...prev,
                {
                    role: "assistant",
                    content:
                        "Sorry, I encountered an error processing your request. Please try again.",
                },
            ]);
        } finally {
            setIsProcessing(false);
        }
    }, [input, isProcessing, messages, auditData, onViewChange]);

    return (
        <div className="flex flex-col h-full bg-slate-900 border-l border-slate-700">
            <div className="p-3 border-b border-slate-700 bg-slate-900">
                <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    AI Copilot
                </h2>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map((msg, idx) => (
                    <div
                        key={idx}
                        className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"
                            }`}
                    >
                        <div
                            className={`max-w-[90%] rounded-lg px-3 py-2 text-sm ${msg.role === "user"
                                ? "bg-blue-600 text-white"
                                : "bg-slate-800 text-slate-200"
                                }`}
                        >
                            <p className="whitespace-pre-wrap">{msg.content}</p>
                        </div>
                    </div>
                ))}
                {isProcessing && (
                    <div className="flex justify-start animate-pulse">
                        <div className="max-w-[90%] rounded-lg px-3 py-2 text-sm bg-slate-800 text-slate-400 italic">
                            Thinking...
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            <div className="p-4 border-t border-slate-700 bg-slate-900">
                <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask a question..."
                    className="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-blue-500 focus:outline-none resize-none h-20"
                    onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey && !isProcessing) {
                            e.preventDefault();
                            handleSendMessage();
                        }
                    }}
                />
                <div className="mt-2 flex justify-end">
                    <button
                        onClick={handleSendMessage}
                        disabled={!input.trim() || isProcessing}
                        className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-50"
                    >
                        {isProcessing ? "Thinking..." : "Send"}
                    </button>
                </div>
            </div>
        </div>
    );
}

"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { Send } from "lucide-react";
import ReactMarkdown from "react-markdown";
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
                "👋 I'm your Ad Auditor. I can help you navigate your audit results. Try asking:\n\n- Show me money pits\n- What's in the waste bin?\n- Compare branded vs generic performance",
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
        <div className="flex flex-col h-full bg-white text-slate-800">
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map((msg, idx) => (
                    <div
                        key={idx}
                        className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"
                            }`}
                    >
                        <div
                            className={`max-w-[90%] rounded-2xl px-5 py-4 shadow-sm ${msg.role === "user"
                                ? "bg-[#0077cc] text-white rounded-br-none"
                                : "bg-slate-50 text-slate-800 rounded-bl-none border border-slate-200"
                                }`}
                        >
                            {msg.role === "user" ? (
                                <p className="text-base leading-relaxed">{msg.content}</p>
                            ) : (
                                <div className="prose prose-slate prose-sm max-w-none
                                    prose-headings:text-slate-900 prose-headings:font-semibold prose-headings:mb-2 prose-headings:mt-4 first:prose-headings:mt-0
                                    prose-p:text-slate-700 prose-p:leading-relaxed prose-p:mb-3 prose-p:text-base
                                    prose-ul:my-2 prose-ul:pl-4 prose-li:text-slate-700 prose-li:text-base prose-li:mb-1
                                    prose-ol:my-2 prose-ol:pl-4
                                    prose-strong:text-slate-900 prose-strong:font-semibold
                                    prose-code:bg-slate-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-sm prose-code:text-[#0077cc]
                                    prose-a:text-[#0077cc] prose-a:no-underline hover:prose-a:underline
                                ">
                                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                                </div>
                            )}
                        </div>
                    </div>
                ))}
                {isProcessing && (
                    <div className="flex justify-start animate-pulse">
                        <div className="max-w-[90%] rounded-2xl rounded-bl-none px-5 py-4 text-base bg-slate-50 border border-slate-200 text-slate-500 italic">
                            Thinking...
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-slate-200 bg-white">
                <form
                    onSubmit={(e) => {
                        e.preventDefault();
                        handleSendMessage();
                    }}
                    className="flex gap-2"
                >
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask questions about your Amazon Ads..."
                        className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-4 py-3 text-base text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#0077cc]/20 focus:border-[#0077cc] transition-all"
                    />
                    <button
                        type="submit"
                        disabled={!input.trim() || isProcessing}
                        className="bg-[#0077cc] hover:bg-[#005fa3] text-white px-4 py-3 rounded-lg text-base font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                    >
                        <Send className="w-5 h-5" />
                    </button>
                </form>
            </div>
        </div>
    );
}


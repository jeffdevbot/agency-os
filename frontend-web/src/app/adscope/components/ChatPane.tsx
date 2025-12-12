"use client";

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { Send, ChevronRight } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { type AuditResponse, type ViewId } from "../types";
import { sendChatMessage } from "../services/chat";
import { generateHotTakes, type HotTake, type HotTakeSeverity } from "../utils/auditRules";

interface ChatPaneProps {
    auditData: AuditResponse;
    onViewChange: (viewId: ViewId) => void;
}

const SEVERITY_INDICATOR: Record<HotTakeSeverity, string> = {
    success: "✅",
    warning: "⚠️",
    error: "❌",
    info: "💡",
};

interface HotTakeItemProps {
    hotTake: HotTake;
    onNavigate: (viewId: ViewId) => void;
}

function HotTakeItem({ hotTake, onNavigate }: HotTakeItemProps) {
    const indicator = SEVERITY_INDICATOR[hotTake.severity];

    return (
        <div className="mb-4 last:mb-0">
            <div className="font-semibold text-slate-900 text-sm mb-1">
                {indicator} {hotTake.headline}
            </div>
            <p className="text-slate-600 text-sm leading-relaxed mb-2">
                {hotTake.body}
            </p>
            <button
                onClick={() => onNavigate(hotTake.targetView)}
                className="text-sm font-medium text-[#0077cc] hover:text-[#005fa3] flex items-center gap-1 transition-colors"
            >
                {hotTake.ctaText}
                <ChevronRight className="w-3 h-3" />
            </button>
        </div>
    );
}

export function ChatPane({ auditData, onViewChange }: ChatPaneProps) {
    const [messages, setMessages] = useState<
        Array<{ role: "user" | "assistant"; content: string }>
    >([]);
    const [input, setInput] = useState("");
    const [isProcessing, setIsProcessing] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Generate hot takes from audit data (client-side, zero tokens)
    const hotTakes = useMemo(() => generateHotTakes(auditData), [auditData]);

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
                {/* Initial Hot Takes Message */}
                {hotTakes.length > 0 && (
                    <div className="flex justify-start">
                        <div className="max-w-[90%] rounded-2xl rounded-bl-none px-5 py-4 shadow-sm bg-slate-50 text-slate-800 border border-slate-200">
                            <p className="text-sm text-slate-500 mb-3">
                                Here&apos;s what I found in your audit:
                            </p>
                            {hotTakes.map((hotTake) => (
                                <HotTakeItem
                                    key={hotTake.id}
                                    hotTake={hotTake}
                                    onNavigate={onViewChange}
                                />
                            ))}
                            <div className="mt-4 pt-3 border-t border-slate-200 text-xs text-slate-400">
                                Ask me anything to dive deeper into these findings.
                            </div>
                        </div>
                    </div>
                )}

                {/* User/Assistant Messages */}
                {messages.map((msg, idx) => (
                    <div
                        key={idx}
                        className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
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

                {/* Processing Indicator */}
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

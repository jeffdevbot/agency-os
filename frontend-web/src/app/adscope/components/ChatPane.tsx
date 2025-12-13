"use client";

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { Send } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { type AuditResponse, type ViewId } from "../types";
import { sendChatMessage } from "../services/chat";
import { generateHotTakes, getWastedSpendBucket, type HotTake, type HotTakeSeverity } from "../utils/auditRules";

interface ChatPaneProps {
    auditData: AuditResponse;
    onViewChange: (viewId: ViewId) => void;
    activeView: ViewId;
}

const SEVERITY_INDICATOR: Record<HotTakeSeverity, string> = {
    success: "✅",
    warning: "⚠️",
    error: "❌",
    info: "💡",
};

type InsightCard = {
    title: string;
    body: string;
    judgement?: string;
    kpi?: { valueText: string; verdictText: string };
    viewId: ViewId;
};

type ChatItem =
    | { id: string; role: "user"; kind: "text"; content: string }
    | { id: string; role: "assistant"; kind: "text"; content: string }
    | { id: string; role: "assistant"; kind: "cards"; cards: InsightCard[] };

function InsightCardItem({ card, onNavigate }: { card: InsightCard; onNavigate: (viewId: ViewId) => void }) {
    return (
        <div className="mb-5 last:mb-0 rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-lg font-semibold text-slate-900">
                {card.title}
            </div>
            <div className="mt-2 text-base text-slate-700 leading-relaxed">
                {card.body}
            </div>
            {card.judgement && (
                <div className="mt-3 text-base font-semibold text-slate-900">
                    {card.judgement}
                </div>
            )}
            <div className="mt-3 flex items-center justify-between gap-4">
                {card.kpi ? (
                    <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
                        <span className="font-semibold">Current: {card.kpi.valueText}</span>
                        <span className="text-slate-400">•</span>
                        <span className="font-semibold">{card.kpi.verdictText}</span>
                    </div>
                ) : (
                    <div />
                )}
                <button
                    onClick={() => onNavigate(card.viewId)}
                    className="text-sm font-semibold text-[#0077cc] hover:text-[#005fa3] transition-colors whitespace-nowrap"
                >
                    Open view →
                </button>
            </div>
        </div>
    );
}

export function ChatPane({ auditData, onViewChange, activeView }: ChatPaneProps) {
    const [messages, setMessages] = useState<ChatItem[]>([]);
    const [input, setInput] = useState("");
    const [isProcessing, setIsProcessing] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const nextIdRef = useRef(1);
    const prevViewRef = useRef<ViewId | null>(null);
    const shownViewsRef = useRef<Set<ViewId>>(new Set());
    const initializedRef = useRef(false);

    // Generate hot takes from audit data (client-side, zero tokens)
    const hotTakes = useMemo(() => generateHotTakes(auditData), [auditData]);
    const wastedSpendSummary = auditData.views?.wasted_spend?.summary;
    const wastedBucket = useMemo(
        () => getWastedSpendBucket(wastedSpendSummary?.wasted_spend_pct ?? 0),
        [wastedSpendSummary?.wasted_spend_pct]
    );
    const wastedHotTake = useMemo(() => {
        switch (wastedBucket.id) {
            case "too_low":
                return "You’re under-testing — growth may be capped.";
            case "slightly_low":
                return "A bit too conservative — you can push discovery harder.";
            case "healthy":
                return "This is a healthy testing level.";
            case "heavy_testing":
                return "Aggressive testing — fine if performance stays stable.";
            case "high":
                return "Too much waste — start trimming the losers.";
            case "severe":
                return "Red alert — budget is getting burned.";
            default:
                return "Keep waste at the right level.";
        }
    }, [wastedBucket.id]);

    const getCardsForView = useCallback((viewId: ViewId): InsightCard[] => {
        if (viewId === "wasted_spend" && wastedSpendSummary) {
            return [
                {
                    title: "🎯 Wasted Ad Spend — Sponsored Products",
                    body:
                        "Some amount of wasted spend is expected — it comes from testing new keywords and discovering what actually converts. The goal isn’t to eliminate waste completely, but to make sure it’s at the right level.",
                    judgement: wastedHotTake,
                    kpi: {
                        valueText: `${(wastedSpendSummary.wasted_spend_pct * 100).toFixed(1)}%`,
                        verdictText: wastedBucket.verdict,
                    },
                    viewId: "wasted_spend",
                },
            ];
        }

        const viewHotTakes = hotTakes.filter((ht) => ht.targetView === viewId);
        return viewHotTakes.map((ht) => ({
            title: `${SEVERITY_INDICATOR[ht.severity]} ${ht.headline}`,
            body: ht.body,
            judgement: ht.judgement,
            kpi: ht.kpi,
            viewId: ht.targetView,
        }));
    }, [hotTakes, wastedSpendSummary, wastedHotTake, wastedBucket.verdict]);

    useEffect(() => {
        if (initializedRef.current) return;
        initializedRef.current = true;

        // On first load, show the current view's cards (usually Overview) without adding any placeholder text.
        const initialCards = getCardsForView(activeView);
        if (initialCards.length > 0) {
            shownViewsRef.current.add(activeView);
            setMessages([
                { id: String(nextIdRef.current++), role: "assistant", kind: "cards", cards: initialCards },
            ]);
        }
        prevViewRef.current = activeView;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (!prevViewRef.current) {
            prevViewRef.current = activeView;
            return;
        }
        if (prevViewRef.current === activeView) return;
        prevViewRef.current = activeView;

        if (shownViewsRef.current.has(activeView)) return;
        const cards = getCardsForView(activeView);
        if (cards.length === 0) return;

        shownViewsRef.current.add(activeView);
        const id = String(nextIdRef.current++);
        setMessages((prev) => [...prev, { id, role: "assistant", kind: "cards", cards }]);
    }, [activeView, getCardsForView]);

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
        setMessages((prev) => [...prev, { id: String(nextIdRef.current++), role: "user", kind: "text", content: userMessage }]);
        setIsProcessing(true);

        try {
            const conversationHistory = messages
                .filter((msg): msg is Extract<ChatItem, { kind: "text" }> => msg.kind === "text")
                .map((msg) => ({
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
                { id: String(nextIdRef.current++), role: "assistant", kind: "text", content: result.response },
            ]);

            if (result.switchToView) {
                onViewChange(result.switchToView);
            }
        } catch (error) {
            console.error("Chat error:", error);
            setMessages((prev) => [
                ...prev,
                {
                    id: String(nextIdRef.current++),
                    role: "assistant",
                    kind: "text",
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
                {messages.map((msg) => (
                    <div
                        key={msg.id}
                        className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                        {msg.kind === "cards" ? (
                            <div className="max-w-[90%] rounded-2xl rounded-bl-none px-5 py-4 shadow-sm bg-slate-50 text-slate-800 border border-slate-200">
                                {msg.cards.map((card) => (
                                    <InsightCardItem key={`${msg.id}-${card.title}`} card={card} onNavigate={onViewChange} />
                                ))}
                            </div>
                        ) : (
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
                        )}
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

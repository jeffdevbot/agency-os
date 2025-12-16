"use client";

import { motion, AnimatePresence } from "framer-motion";
import { ToolConfig, FlowStep } from "../types";
import { X, User, Server, ArrowRight } from "lucide-react";
import { useState } from "react";
import { ArchitectureDiagram } from "./ArchitectureDiagram";

interface SystemDetailProps {
    tool: ToolConfig | null;
    onClose: () => void;
}

export function SystemDetail({ tool, onClose }: SystemDetailProps) {
    const [viewMode, setViewMode] = useState<"user" | "arch">("user");

    if (!tool) return null;

    const currentFlow = viewMode === "user" ? tool.userFlow : tool.archFlow;

    return (
        <AnimatePresence>
            <motion.div
                className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={onClose}
            >
                <motion.div
                    className="relative w-full max-w-4xl overflow-hidden rounded-3xl border border-slate-700 bg-slate-900/90 p-8 shadow-2xl backdrop-blur-xl"
                    initial={{ scale: 0.9, y: 20 }}
                    animate={{ scale: 1, y: 0 }}
                    exit={{ scale: 0.9, y: 20 }}
                    onClick={(e) => e.stopPropagation()}
                >
                    <button
                        onClick={onClose}
                        className="absolute right-6 top-6 rounded-full bg-white/10 p-2 text-white/70 hover:bg-white/20 hover:text-white"
                    >
                        <X size={20} />
                    </button>

                    <div className="mb-8 flex flex-col gap-2">
                        <div className="flex items-center gap-3">
                            <div
                                className="flex h-10 w-10 items-center justify-center rounded-xl shadow-lg"
                                style={{ backgroundColor: tool.color }}
                            >
                                {tool.icon && <tool.icon className="text-white" size={20} />}
                            </div>
                            <h2 className="text-3xl font-bold text-white">{tool.name}</h2>
                        </div>
                        <p className="text-slate-400">{tool.description}</p>
                    </div>

                    <div className="mb-10 flex items-center justify-center">
                        <div className="flex rounded-full bg-slate-800 p-1 shadow-inner">
                            <button
                                onClick={() => setViewMode("user")}
                                className={`flex items-center gap-2 rounded-full px-6 py-2 text-sm font-semibold transition-all ${viewMode === "user"
                                    ? "bg-white text-slate-900 shadow-md"
                                    : "text-slate-400 hover:text-white"
                                    }`}
                            >
                                <User size={16} />
                                User View
                            </button>
                            <button
                                onClick={() => setViewMode("arch")}
                                className={`flex items-center gap-2 rounded-full px-6 py-2 text-sm font-semibold transition-all ${viewMode === "arch"
                                    ? "bg-white text-slate-900 shadow-md"
                                    : "text-slate-400 hover:text-white"
                                    }`}
                            >
                                <Server size={16} />
                                Architecture
                            </button>
                        </div>
                    </div>

                    <div className="relative">
                        <div className={`absolute left-0 top-1/2 h-px w-full -translate-y-1/2 bg-slate-700 ${viewMode === "arch" && tool.archDiagram ? "hidden" : "block"}`} />

                        {viewMode === "arch" && tool.archDiagram ? (
                            <ArchitectureDiagram
                                nodes={tool.archDiagram.nodes}
                                edges={tool.archDiagram.edges}
                                color={tool.color}
                            />
                        ) : (
                            <div className="relative flex items-start justify-between gap-4 overflow-x-auto py-10">
                                {currentFlow.map((step, idx) => (
                                    <div key={step.id} className="group relative z-10 flex min-w-[140px] flex-1 flex-col items-center text-center">
                                        <motion.div
                                            initial={{ scale: 0, opacity: 0 }}
                                            animate={{ scale: 1, opacity: 1 }}
                                            transition={{ delay: idx * 0.1 }}
                                            className={`mb-3 flex h-10 w-10 items-center justify-center rounded-full border-2 bg-slate-900 font-bold transition-all group-hover:scale-110 ${viewMode === "user"
                                                ? "border-blue-500 text-blue-400"
                                                : "border-emerald-500 text-emerald-400"
                                                }`}
                                        >
                                            {idx + 1}
                                        </motion.div>
                                        <motion.h3
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            transition={{ delay: idx * 0.1 + 0.1 }}
                                            className="mb-1 text-sm font-semibold text-white"
                                        >
                                            {step.label}
                                        </motion.h3>
                                        {step.description && (
                                            <motion.p
                                                initial={{ opacity: 0 }}
                                                animate={{ opacity: 1 }}
                                                transition={{ delay: idx * 0.1 + 0.2 }}
                                                className="max-w-[120px] text-xs leading-relaxed text-slate-400"
                                            >
                                                {step.description}
                                            </motion.p>
                                        )}
                                        {idx < currentFlow.length - 1 && (
                                            <ArrowRight
                                                className="absolute -right-[20%] top-[45%] -translate-y-[50%] text-slate-600"
                                                size={16}
                                            />
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    );
}

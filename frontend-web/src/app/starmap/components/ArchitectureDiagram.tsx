"use client";

import { motion } from "framer-motion";
import { ArchNode, ArchEdge } from "../types";
import { Database, Globe, Server, Code, Layers, Settings } from "lucide-react";

interface ArchitectureDiagramProps {
    nodes: ArchNode[];
    edges: ArchEdge[];
    color: string;
}

const ICONS = {
    client: Globe,
    service: Server,
    database: Database,
    function: Code,
    gateway: Layers,
    default: Settings,
};

export function ArchitectureDiagram({ nodes, edges, color }: ArchitectureDiagramProps) {
    // Helper to get node coordinates by ID
    const getNodePos = (id: string) => {
        const node = nodes.find((n) => n.id === id);
        return node ? { x: node.x, y: node.y } : { x: 0, y: 0 };
    };

    return (
        <div className="relative h-[480px] w-full select-none overflow-hidden rounded-xl border border-slate-800 bg-slate-950/50">
            {/* Grid Background */}
            <div
                className="absolute inset-0 opacity-20"
                style={{
                    backgroundImage: `linear-gradient(#334155 1px, transparent 1px), linear-gradient(90deg, #334155 1px, transparent 1px)`,
                    backgroundSize: '40px 40px'
                }}
            />

            {/* SVG Layer for Edges (Curves & Animated Dots) */}
            <svg
                className="absolute inset-0 h-full w-full pointer-events-none"
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
            >
                {edges.map((edge, i) => {
                    const sPos = getNodePos(edge.source);
                    const ePos = getNodePos(edge.target);

                    // Constants for Node Radius in % (approximated for 80px size)
                    // Width ~1000px -> 40px radius is ~4%
                    // Height ~480px -> 40px radius is ~8.5%
                    const RX = 4.2;
                    const RY = 9;

                    const dx = ePos.x - sPos.x;
                    const dy = ePos.y - sPos.y;
                    const isHorizontal = Math.abs(dx) > Math.abs(dy) * 2; // Bias towards vertical if close, but usually flows are distinct

                    let start = { x: sPos.x, y: sPos.y };
                    let end = { x: ePos.x, y: ePos.y };
                    let cp1 = { x: 0, y: 0 };
                    let cp2 = { x: 0, y: 0 };

                    if (isHorizontal) {
                        // Source is Left or Right
                        start.x = dx > 0 ? sPos.x + RX : sPos.x - RX;
                        end.x = dx > 0 ? ePos.x - RX : ePos.x + RX;

                        // Control points for horizontal S-curve
                        const midX = (start.x + end.x) / 2;
                        cp1 = { x: midX, y: start.y };
                        cp2 = { x: midX, y: end.y };
                    } else {
                        // Source is Top or Bottom
                        start.y = dy > 0 ? sPos.y + RY : sPos.y - RY;
                        end.y = dy > 0 ? ePos.y - RY : ePos.y + RY;

                        // Control points for vertical S-curve
                        const midY = (start.y + end.y) / 2;
                        cp1 = { x: start.x, y: midY };
                        cp2 = { x: end.x, y: midY };
                    }

                    const pathD = `M ${start.x} ${start.y} C ${cp1.x} ${cp1.y}, ${cp2.x} ${cp2.y}, ${end.x} ${end.y}`;

                    return (
                        <g key={edge.id}>
                            {/* Path connection line */}
                            <motion.path
                                d={pathD}
                                fill="none"
                                stroke="#475569"
                                strokeWidth="2"
                                vectorEffect="non-scaling-stroke"
                                strokeDasharray={edge.animated ? "5,5" : "none"}
                                initial={{ pathLength: 0, opacity: 0 }}
                                animate={{ pathLength: 1, opacity: 1 }}
                                transition={{ duration: 1.5, delay: i * 0.2 }}
                            />

                            {/* Animated dot moving along the path */}
                            {edge.animated && (
                                <circle r="0.5" fill={color}>
                                    <animateMotion
                                        dur="2s"
                                        repeatCount="indefinite"
                                        path={pathD}
                                        rotate="auto"
                                    />
                                </circle>
                            )}

                            {/* Connection Anchors */}
                            <circle cx={`${start.x}%`} cy={`${start.y}%`} r="0.3" fill="#475569" />
                            <circle cx={`${end.x}%`} cy={`${end.y}%`} r="0.3" fill="#475569" />
                        </g>
                    );
                })}
            </svg>

            {/* HTML Layer for Edge Labels & Anchors to prevent distortion */}
            <div className="absolute inset-0 pointer-events-none">
                {edges.map((edge) => {
                    const start = getNodePos(edge.source);
                    const end = getNodePos(edge.target);

                    return (
                        <div key={edge.id}>
                            {/* Label */}
                            {edge.label && (
                                <div
                                    className="absolute flex items-center justify-center"
                                    style={{
                                        left: `${(start.x + end.x) / 2}%`,
                                        top: `${(start.y + end.y) / 2}%`,
                                        transform: "translate(-50%, -50%)"
                                    }}
                                >
                                    <span className="rounded bg-slate-900/90 px-2 py-0.5 text-[10px] text-slate-400 border border-slate-700 shadow-sm backdrop-blur-md whitespace-nowrap">
                                        {edge.label}
                                    </span>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Nodes Layer */}
            {nodes.map((node, i) => {
                const Icon = ICONS[node.type] || ICONS.default;
                return (
                    <motion.div
                        key={node.id}
                        className="absolute flex flex-col items-center justify-center gap-3"
                        style={{
                            left: `${node.x}%`,
                            top: `${node.y}%`,
                            transform: "translate(-50%, -50%)",
                        }}
                        initial={{ scale: 0, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{ type: "spring", delay: i * 0.1, stiffness: 200, damping: 20 }}
                    >
                        <div
                            className="relative flex h-20 w-20 items-center justify-center rounded-2xl border border-slate-700 bg-slate-900/80 shadow-2xl backdrop-blur-xl"
                            style={{
                                boxShadow: `0 0 30px -5px ${color}20`,
                            }}
                        >
                            <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/5 to-transparent pointer-events-none" />
                            <Icon className="text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.3)]" size={28} style={{ color: color }} />

                            {/* Status Indicator */}
                            <div className="absolute -right-1 -top-1 h-3 w-3 rounded-full border-2 border-slate-900 bg-emerald-500 shadow-lg" />
                        </div>

                        <div className="flex flex-col items-center gap-1">
                            <span className="rounded-full bg-slate-800/90 px-3 py-1 text-xs font-bold text-white shadow-lg border border-slate-700/50 backdrop-blur-md">
                                {node.label}
                            </span>
                            <span className="text-[9px] font-medium uppercase tracking-wider text-slate-500">
                                {node.type}
                            </span>
                        </div>
                    </motion.div>
                );
            })}
        </div>
    );
}

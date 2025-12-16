"use client";

import { motion } from "framer-motion";
import { ToolConfig } from "../types";

interface PlanetProps {
    tool: ToolConfig;
    onSelect: (tool: ToolConfig) => void;
}

export function Planet({ tool, onSelect }: PlanetProps) {
    return (
        <motion.div
            className="absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center justify-center pointer-events-none"
            style={{
                width: tool.orbitRadius * 2,
                height: tool.orbitRadius * 2,
            }}
            animate={{ rotate: 360 }}
            transition={{
                duration: tool.orbitDuration,
                repeat: Number.POSITIVE_INFINITY,
                ease: "linear",
            }}
        >
            <motion.div
                className="absolute top-0 flex cursor-pointer flex-col items-center justify-center gap-2 pointer-events-auto"
                whileHover={{ scale: 1.2 }}
                onClick={() => onSelect(tool)}
                style={{
                    marginTop: -24, // Offset to center on the ring
                }}
            >
                <div
                    className="flex h-12 w-12 items-center justify-center rounded-full shadow-[0_0_15px_rgba(255,255,255,0.3)] backdrop-blur-sm"
                    style={{
                        backgroundColor: tool.color,
                        boxShadow: `0 0 20px ${tool.color}80`,
                    }}
                >
                    {tool.icon && <tool.icon className="stroke-white" size={24} strokeWidth={2} />}
                </div>
                <motion.span
                    className="whitespace-nowrap rounded-full bg-black/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-white backdrop-blur-md"
                    initial={{ opacity: 0 }}
                    whileHover={{ opacity: 1 }}
                >
                    {tool.name}
                </motion.span>
            </motion.div>
        </motion.div>
    );
}

"use client";

import { useState, useEffect } from "react";
import { AGENCY_TOOLS } from "./data";
import { ToolConfig } from "./types";
import { Planet } from "./components/Planet";
import { SystemDetail } from "./components/SystemDetail";
import { motion } from "framer-motion";

export default function StarmapPage() {
    const [selectedTool, setSelectedTool] = useState<ToolConfig | null>(null);
    const [stars, setStars] = useState<Array<{ top: string; left: string; width: string; height: string; opacity: number; animationDuration: string }>>([]);

    useEffect(() => {
        setStars(
            [...Array(50)].map(() => ({
                top: `${Math.random() * 100}%`,
                left: `${Math.random() * 100}%`,
                width: `${Math.random() * 2 + 1}px`,
                height: `${Math.random() * 2 + 1}px`,
                opacity: Math.random() * 0.7 + 0.3,
                animationDuration: `${Math.random() * 5 + 3}s`,
            }))
        );
    }, []);

    return (
        <div className="relative flex h-screen w-full items-center justify-center overflow-hidden bg-black text-white">
            {/* Starfield Background */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-slate-900 via-[#000000] to-black opacity-80" />
            {stars.map((star, i) => (
                <div
                    key={i}
                    className="absolute rounded-full bg-white text-white"
                    style={{
                        top: star.top,
                        left: star.left,
                        width: star.width,
                        height: star.height,
                        opacity: star.opacity,
                        animation: `twinkle ${star.animationDuration} infinite ease-in-out`,
                    }}
                />
            ))}

            {/* Central Star (Agency OS Core) */}
            <motion.div
                className="z-10 flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-yellow-100 to-yellow-600 shadow-[0_0_50px_rgba(234,179,8,0.6)]"
                animate={{ scale: [1, 1.05, 1] }}
                transition={{ duration: 4, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
            >
                <div className="text-center">
                    <span className="block text-xs font-bold uppercase tracking-widest text-yellow-900">Ecomlabs</span>
                    <span className="block text-lg font-black tracking-tighter text-yellow-950">Tools</span>
                </div>
            </motion.div>

            {/* Orbits */}
            <div className="absolute inset-0 flex items-center justify-center">
                {AGENCY_TOOLS.map((tool) => (
                    <div
                        key={tool.id}
                        className="absolute rounded-full border border-white/10"
                        style={{
                            width: tool.orbitRadius * 2,
                            height: tool.orbitRadius * 2,
                            transition: "border-color 0.3s",
                        }}
                    />
                ))}
            </div>

            {/* Planets */}
            <div className="absolute inset-0 flex items-center justify-center">
                {AGENCY_TOOLS.map((tool) => (
                    <Planet key={tool.id} tool={tool} onSelect={setSelectedTool} />
                ))}
            </div>

            {/* Detail Overlay */}
            {selectedTool && (
                <SystemDetail tool={selectedTool} onClose={() => setSelectedTool(null)} />
            )}
        </div>
    );
}

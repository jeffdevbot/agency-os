import { LucideIcon } from "lucide-react";

export type FlowStep = {
    id: string;
    label: string;
    description?: string;
    type: "action" | "process" | "data" | "trigger";
};

export type ArchNode = {
    id: string;
    label: string;
    type: "client" | "service" | "database" | "function" | "gateway";
    iconName?: string; // We'll map string to Lucide icon in component
    x: number; // 0-100 percentage
    y: number; // 0-100 percentage
};

export type ArchEdge = {
    id: string;
    source: string;
    target: string;
    label?: string;
    animated?: boolean;
};

export type ToolConfig = {
    id: string;
    name: string;
    description: string;
    color: string; // Tailwind color class or hex for the planet
    icon?: LucideIcon;
    orbitRadius: number; // visual distance from center
    orbitDuration: number; // seconds for full rotation
    userFlow: FlowStep[];
    archFlow: FlowStep[];
    archDiagram?: {
        nodes: ArchNode[];
        edges: ArchEdge[];
    };
};

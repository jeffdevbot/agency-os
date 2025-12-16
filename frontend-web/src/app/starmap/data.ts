import { ToolConfig } from "./types";
import {
    Search,
    Target,
    FileSpreadsheet,
    Database,
    LayoutDashboard,
    MessageSquare,
    Users,
} from "lucide-react";

export const AGENCY_TOOLS: ToolConfig[] = [
    {
        id: "ngram",
        name: "N-Gram",
        description: "Search Term Report Analysis",
        color: "#3b82f6", // blue-500
        icon: Search,
        orbitRadius: 180,
        orbitDuration: 30,
        userFlow: [
            { id: "u1", label: "Upload STR", type: "trigger", description: "User uploads Search Term Report" },
            { id: "u2", label: "Click Generate", type: "action" },
            { id: "u3", label: "Receive Workbook", type: "data", description: "Excel file with n-gram analysis" },
            { id: "u4", label: "Mark Negatives", type: "action", description: "User edits workbook offline" },
            { id: "u5", label: "Upload Filled Workbook", type: "trigger" },
            { id: "u6", label: "Download Negatives", type: "data", description: "Final summary for bulk upload" },
        ],
        archFlow: [
            { id: "a1", label: "Next.js Page", type: "process", description: "Frontend UI" },
            { id: "a2", label: "POST /ngram/process", type: "trigger", description: "FastAPI Backend" },
            { id: "a3", label: "Pandas Analysis", type: "process", description: "Tokenization & Aggregation" },
            { id: "a4", label: "Excel Generation", type: "data", description: "OpenPyXL / XlsxWriter" },
            { id: "a5", label: "POST /ngram/collect", type: "trigger", description: "FastAPI Backend" },
            { id: "a6", label: "Negatives Extraction", type: "process", description: "Filter for NE/NP tags" },
        ],
        archDiagram: {
            nodes: [
                { id: "client", label: "Web Client", type: "client", x: 10, y: 50 },
                { id: "api", label: "FastAPI Gateway", type: "gateway", x: 40, y: 50 },
                { id: "pandas", label: "Pandas Analysis", type: "function", x: 70, y: 30 },
                { id: "excel", label: "Excel Gen", type: "function", x: 70, y: 70 },
                { id: "storage", label: "File Storage", type: "database", x: 90, y: 50 },
            ],
            edges: [
                { id: "e1", source: "client", target: "api", animated: true },
                { id: "e2", source: "api", target: "pandas", animated: true },
                { id: "e3", source: "api", target: "excel", animated: true },
                { id: "e4", source: "pandas", target: "storage" },
                { id: "e5", source: "excel", target: "storage" },
            ],
        },
    },
    {
        id: "npat",
        name: "N-Pat",
        description: "Product Attribute Targeting",
        color: "#f97316", // orange-500
        icon: Target,
        orbitRadius: 240,
        orbitDuration: 45,
        userFlow: [
            { id: "u1", label: "Upload STR", type: "trigger" },
            { id: "u2", label: "Receive ASIN Workbook", type: "data", description: "ASINs with Helium10 zones" },
            { id: "u3", label: "Enrich Data", type: "action", description: "User adds details" },
            { id: "u4", label: "Upload Workbook", type: "trigger" },
            { id: "u5", label: "Download Targets", type: "data" },
        ],
        archFlow: [
            { id: "a1", label: "Next.js Page", type: "process" },
            { id: "a2", label: "POST /npat/process", type: "trigger" },
            { id: "a3", label: "ASIN Aggregation", type: "process", description: "Pandas GroupBy ASIN" },
            { id: "a4", label: "Excel Workbook", type: "data" },
            { id: "a5", label: "POST /npat/collect", type: "trigger" },
        ],
        archDiagram: {
            nodes: [
                { id: "client", label: "Web Client", type: "client", x: 10, y: 50 },
                { id: "api", label: "FastAPI", type: "gateway", x: 40, y: 50 },
                { id: "enrich", label: "Data Enrichment", type: "function", x: 40, y: 20 },
                { id: "pandas", label: "Pandas GroupBy", type: "function", x: 70, y: 50 },
                { id: "excel", label: "Excel Output", type: "database", x: 90, y: 50 },
            ],
            edges: [
                { id: "e1", source: "client", target: "api", animated: true },
                { id: "e2", source: "api", target: "enrich", label: "Enrich" },
                { id: "e3", source: "api", target: "pandas", animated: true },
                { id: "e4", source: "pandas", target: "excel" },
            ],
        },
    },
    {
        id: "root",
        name: "Root Keyword",
        description: "Hierarchical Campaign Analysis",
        color: "#22c55e", // green-500
        icon: Database,
        orbitRadius: 300,
        orbitDuration: 60,
        userFlow: [
            { id: "u1", label: "Upload Campaign Report", type: "trigger" },
            { id: "u2", label: "Processing", type: "process" },
            { id: "u3", label: "Download Analysis", type: "data", description: "Multi-level hierarchy workbook" },
        ],
        archFlow: [
            { id: "a1", label: "Next.js Page", type: "process" },
            { id: "a2", label: "POST /root/process", type: "trigger" },
            { id: "a3", label: "Pivot & Group", type: "process", description: "Complex Pandas multi-index" },
            { id: "a4", label: "Streaming Response", type: "data" },
        ],
        archDiagram: {
            nodes: [
                { id: "client", label: "Web Client", type: "client", x: 10, y: 50 },
                { id: "api", label: "FastAPI", type: "gateway", x: 35, y: 50 },
                { id: "pandas", label: "Pandas MultiIndex", type: "function", x: 65, y: 50 },
                { id: "stream", label: "Stream Response", type: "service", x: 90, y: 50 },
                { id: "cache", label: "Temp Cache", type: "database", x: 65, y: 20 },
            ],
            edges: [
                { id: "e1", source: "client", target: "api", animated: true },
                { id: "e2", source: "api", target: "pandas", animated: true },
                { id: "e3", source: "pandas", target: "cache" },
                { id: "e4", source: "pandas", target: "stream", animated: true },
            ],
        },
    },
    {
        id: "adscope",
        name: "AdScope",
        description: "Account Audit & Workspace",
        color: "#a855f7", // purple-500
        icon: LayoutDashboard,
        orbitRadius: 360,
        orbitDuration: 75,
        userFlow: [
            { id: "u1", label: "Ingest Data", type: "trigger", description: "Bulk File + STR + Keywords" },
            { id: "u2", label: "Audit Processing", type: "process" },
            { id: "u3", label: "Workspace UI", type: "action", description: "Interactive Interactive Dashboard" },
        ],
        archFlow: [
            { id: "a1", label: "Next.js Ingest", type: "process" },
            { id: "a2", label: "POST /adscope/audit", type: "trigger" },
            { id: "a3", label: "Pandas Audit Logic", type: "process", description: "Heavy computation" },
            { id: "a4", label: "JSON Response", type: "data", description: "Hydrated React State" },
        ],
        archDiagram: {
            nodes: [
                { id: "client", label: "Web/React State", type: "client", x: 10, y: 50 },
                { id: "api", label: "FastAPI", type: "gateway", x: 40, y: 50 },
                { id: "pandas", label: "Bulk Parser", type: "function", x: 70, y: 30 },
                { id: "audit", label: "Audit Logic", type: "function", x: 70, y: 70 },
                { id: "json", label: "JSON Adapter", type: "service", x: 90, y: 50 },
            ],
            edges: [
                { id: "e1", source: "client", target: "api", animated: true },
                { id: "e2", source: "api", target: "pandas", animated: true },
                { id: "e3", source: "api", target: "audit", animated: true },
                { id: "e4", source: "pandas", target: "json" },
                { id: "e5", source: "audit", target: "json" },
                { id: "e6", source: "json", target: "client", animated: true, label: "Response" },
            ],
        },
    },
    {
        id: "scribe",
        name: "Scribe",
        description: "Project Workflow Management",
        color: "#ef4444", // red-500
        icon: FileSpreadsheet,
        orbitRadius: 420,
        orbitDuration: 90,
        userFlow: [
            { id: "u1", label: "Create Project", type: "trigger" },
            { id: "u2", label: "Drafting", type: "action" },
            { id: "u3", label: "Stage Approvals", type: "process", description: "Stage A -> B -> C" },
            { id: "u4", label: "Final Approval", type: "data" },
        ],
        archFlow: [
            { id: "a1", label: "Next.js App", type: "process" },
            { id: "a2", label: "API Routes", type: "trigger", description: "/api/scribe/*" },
            { id: "a3", label: "Supabase DB", type: "data", description: "Table: scribe_projects" },
        ],
        archDiagram: {
            nodes: [
                { id: "client", label: "Web Client", type: "client", x: 10, y: 50 },
                { id: "api", label: "Next.js API", type: "gateway", x: 40, y: 50 },
                { id: "db", label: "Supabase Postgres", type: "database", x: 75, y: 50 },
                { id: "auth", label: "Auth Service", type: "service", x: 40, y: 20 },
            ],
            edges: [
                { id: "e1", source: "client", target: "api", animated: true },
                { id: "e2", source: "api", target: "db", animated: true },
                { id: "e3", source: "api", target: "auth", label: "Verify Token" },
            ],
        },
    },
    {
        id: "command",
        name: "Command Center",
        description: "Agency Directory",
        color: "#64748b", // slate-500
        icon: Users,
        orbitRadius: 480,
        orbitDuration: 110,
        userFlow: [
            { id: "u1", label: "Access Hub", type: "trigger" },
            { id: "u2", label: "View Clients", type: "action" },
            { id: "u3", label: "View Team", type: "action" },
        ],
        archFlow: [
            { id: "a1", label: "Next.js Pages", type: "process" },
            { id: "a2", label: "Static Links", type: "data" },
        ],
        archDiagram: {
            nodes: [
                { id: "client", label: "Web Client", type: "client", x: 20, y: 50 },
                { id: "router", label: "Next.js Router", type: "gateway", x: 50, y: 50 },
                { id: "static", label: "Static Config", type: "database", x: 80, y: 50 },
            ],
            edges: [
                { id: "e1", source: "client", target: "router", animated: true },
                { id: "e2", source: "router", target: "static" },
            ],
        },
    },
    {
        id: "debrief",
        name: "Debrief",
        description: "Meeting Note Sync",
        color: "#0d9488", // teal-600
        icon: MessageSquare,
        orbitRadius: 540,
        orbitDuration: 130,
        userFlow: [
            { id: "u1", label: "Sync Meetings", type: "trigger" },
            { id: "u2", label: "Review List", type: "action" },
            { id: "u3", label: "Process Notes", type: "process" },
        ],
        archFlow: [
            { id: "a1", label: "Next.js Page", type: "process" },
            { id: "a2", label: "GET /api/debrief", type: "trigger" },
            { id: "a3", label: "External API", type: "data", description: "Google / Calendar Integration" },
        ],
        archDiagram: {
            nodes: [
                { id: "client", label: "Web Client", type: "client", x: 10, y: 50 },
                { id: "api", label: "Next.js API", type: "gateway", x: 40, y: 50 },
                { id: "google", label: "Google Drive API", type: "service", x: 70, y: 30 },
                { id: "docs", label: "Google Docs API", type: "service", x: 70, y: 70 },
                { id: "db", label: "Supabase Cache", type: "database", x: 40, y: 80 },
            ],
            edges: [
                { id: "e1", source: "client", target: "api", animated: true },
                { id: "e2", source: "api", target: "google", animated: true },
                { id: "e3", source: "api", target: "docs", animated: true },
                { id: "e4", source: "api", target: "db" },
            ],
        },
    },
];

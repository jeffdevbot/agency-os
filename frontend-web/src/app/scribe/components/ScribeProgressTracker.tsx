import React from "react";

export type ScribeStage = "A" | "B" | "C";

interface ScribeProgressTrackerProps {
    currentStage: ScribeStage;
    stageAComplete?: boolean;
    stageBComplete?: boolean;
    stageCComplete?: boolean;
    onNavigate: (stage: ScribeStage) => void;
}

export function ScribeProgressTracker({
    currentStage,
    stageAComplete = false,
    stageBComplete = false,
    stageCComplete = false,
    onNavigate,
}: ScribeProgressTrackerProps) {
    const steps: { id: ScribeStage; label: string; complete: boolean }[] = [
        { id: "A", label: "Enter SKU Data", complete: stageAComplete },
        { id: "B", label: "Generate Topics", complete: stageBComplete },
        { id: "C", label: "Generate Copy", complete: stageCComplete },
    ];

    const handleNext = () => {
        if (currentStage === "A") onNavigate("B");
        if (currentStage === "B") onNavigate("C");
    };

    const handlePrev = () => {
        if (currentStage === "B") onNavigate("A");
        if (currentStage === "C") onNavigate("B");
    };

    return (
        <div className="w-full bg-white border-b border-slate-200 px-6 py-6">
            <div className="mx-auto max-w-4xl">
                {/* Tracker Row */}
                <div className="relative flex items-center justify-between">
                    {/* Connecting Line */}
                    <div className="absolute left-0 top-1/2 h-0.5 w-full -translate-y-1/2 bg-slate-100" />

                    {steps.map((step) => {
                        const isCurrent = currentStage === step.id;
                        const isComplete = step.complete;
                        const isClickable = true; // Always clickable per "Non-Blocking" rule

                        return (
                            <button
                                key={step.id}
                                onClick={() => onNavigate(step.id)}
                                className="group relative z-10 flex flex-col items-center gap-2 bg-white px-2 focus:outline-none"
                            >
                                <div
                                    className={`flex h-10 w-10 items-center justify-center rounded-full border-2 text-sm font-bold transition-colors ${isCurrent
                                        ? "border-[#0a6fd6] bg-[#0a6fd6] text-white shadow-md"
                                        : isComplete
                                            ? "border-[#0a6fd6] bg-white text-[#0a6fd6]"
                                            : "border-slate-200 bg-white text-slate-400 group-hover:border-slate-300 group-hover:text-slate-500"
                                        }`}
                                >
                                    {step.id}
                                </div>
                                <span
                                    className={`text-xs font-medium transition-colors ${isCurrent
                                        ? "text-[#0a6fd6]"
                                        : isComplete
                                            ? "text-slate-700"
                                            : "text-slate-400 group-hover:text-slate-500"
                                        }`}
                                >
                                    {step.label}
                                </span>
                            </button>
                        );
                    })}
                </div>

                {/* Navigation Buttons */}
                <div className="mt-8 flex items-center justify-between">
                    <button
                        onClick={handlePrev}
                        disabled={currentStage === "A"}
                        className={`flex items-center gap-1 rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${currentStage === "A"
                            ? "cursor-not-allowed border-slate-100 text-slate-300"
                            : "border-slate-300 text-slate-700 hover:bg-slate-50 hover:text-slate-900"
                            }`}
                    >
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                        Previous
                    </button>

                    <button
                        onClick={handleNext}
                        disabled={currentStage === "C"}
                        className={`flex items-center gap-1 rounded-lg px-4 py-2 text-sm font-medium shadow-sm transition-colors ${currentStage === "C"
                            ? "cursor-not-allowed bg-slate-100 text-slate-400"
                            : "bg-[#0a6fd6] text-white hover:bg-[#0959ab] shadow-[0_4px_10px_rgba(10,111,214,0.2)]"
                            }`}
                    >
                        Next
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    );
}

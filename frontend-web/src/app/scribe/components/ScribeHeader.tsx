import React from "react";

export function ScribeHeader() {
    return (
        <header className="border-b border-slate-200 bg-white px-6 py-4">
            <div className="mx-auto flex max-w-6xl items-baseline gap-3">
                <h1 className="text-xl font-bold tracking-tight text-slate-900">SCRIBE</h1>
                <span className="text-sm text-slate-500">Create amazing Amazon copy.</span>
            </div>
        </header>
    );
}

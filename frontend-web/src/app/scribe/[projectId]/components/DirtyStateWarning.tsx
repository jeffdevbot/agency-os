interface DirtyStateWarningProps {
    message: string;
    onRegenerate: () => void;
    regenerating: boolean;
}

export function DirtyStateWarning({ message, onRegenerate, regenerating }: DirtyStateWarningProps) {
    return (
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-100">
                        <svg
                            className="h-5 w-5 text-amber-600"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                            />
                        </svg>
                    </div>
                    <div>
                        <p className="text-sm font-medium text-amber-800">{message}</p>
                        <p className="text-xs text-amber-700">
                            Click "Regenerate" to update based on new data
                        </p>
                    </div>
                </div>
                <button
                    onClick={onRegenerate}
                    disabled={regenerating}
                    className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {regenerating ? "Regenerating..." : "Regenerate"}
                </button>
            </div>
        </div>
    );
}

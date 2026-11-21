import React from "react";

export function LoadingState({ message = "Loading..." }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-[#929292]">
      <div className="w-8 h-8 border-3 border-[#5146FF]/30 border-t-[#5146FF] rounded-full animate-spin mb-4" />
      <p className="text-xs">{message}</p>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="bg-rose-500/10 text-rose-300 p-4 rounded-xl border border-rose-500/20 flex flex-col items-start text-xs">
      <h3 className="font-semibold mb-1 text-sm text-rose-200">Error</h3>
      <p className="mb-3">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="bg-rose-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-rose-700 transition"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="text-center p-12 border border-dashed border-white/[0.12] rounded-2xl bg-[#20212B]/40 text-[#A4A6B8]">
      <h3 className="text-lg font-medium text-[#F8F8FC] mb-1">{title}</h3>
      <p className="text-xs text-[#929292] max-w-md mx-auto">{description}</p>
    </div>
  );
}

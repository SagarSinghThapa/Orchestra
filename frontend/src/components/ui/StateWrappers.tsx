export function LoadingState({ message = "Loading..." }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-gray-500">
      <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mb-4"></div>
      <p>{message}</p>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="bg-red-50 text-red-700 p-4 rounded-lg border border-red-200 flex flex-col items-start">
      <h3 className="font-bold mb-1">Error</h3>
      <p className="mb-3">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="bg-red-600 text-white px-3 py-1 rounded text-sm hover:bg-red-700">
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="text-center p-12 border-2 border-dashed border-gray-200 rounded-lg text-gray-500">
      <h3 className="text-lg font-medium text-gray-900 mb-1">{title}</h3>
      <p>{description}</p>
    </div>
  );
}

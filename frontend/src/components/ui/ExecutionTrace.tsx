import React from "react";

export function ExecutionTrace({ traceId, agent, status }: { traceId: string; agent: string; status: 'pending' | 'running' | 'success' | 'error' }) {
  const isRunning = status === 'pending' || status === 'running';
  return (
    <div className="bg-gray-900 rounded-lg p-4 font-mono text-sm shadow-inner mb-6">
      <div className="flex justify-between items-center border-b border-gray-700 pb-2 mb-3">
        <span className="text-gray-400">Execution Trace</span>
        <span className="text-blue-400 bg-blue-900/30 px-2 py-0.5 rounded text-xs">{traceId}</span>
      </div>
      
      <div className="space-y-3">
        <div className="flex items-center">
          <div className="w-4 h-4 rounded-full bg-green-500 mr-3"></div>
          <span className="text-gray-200">Task Received</span>
        </div>
        
        <div className="flex items-center">
          <div className={`w-4 h-4 rounded-full mr-3 ${status === 'error' ? 'bg-red-500' : 'bg-green-500'}`}></div>
          <span className="text-gray-200">Routed to: <span className="text-yellow-300">{agent}</span></span>
        </div>

        {isRunning && (
          <div className="flex items-center animate-pulse">
            <div className="w-4 h-4 rounded-full bg-blue-500 mr-3"></div>
            <span className="text-blue-300">Executing MCP Tools...</span>
          </div>
        )}

        {status === 'success' && (
          <div className="flex items-center">
            <div className="w-4 h-4 rounded-full bg-green-500 mr-3"></div>
            <span className="text-green-400">Execution Complete</span>
          </div>
        )}

        {status === 'error' && (
          <div className="flex items-center">
            <div className="w-4 h-4 rounded-full bg-red-500 mr-3"></div>
            <span className="text-red-400">Execution Failed</span>
          </div>
        )}
      </div>
    </div>
  );
}

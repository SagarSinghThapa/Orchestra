"use client";

import { useState } from "react";
import { api } from "@/services/apiClient";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { LoadingState, ErrorState } from "@/components/ui/StateWrappers";
import { ExecutionTrace } from "@/components/ui/ExecutionTrace";
import { CodingAgentResult, TaskStatus } from "@/types/developer";

export default function CodingAssistantPage() {
  const [task, setTask] = useState("");
  const [mode, setMode] = useState<"preview" | "apply">("preview");
  
  const [status, setStatus] = useState<TaskStatus | null>(null);
  const [traceId, setTraceId] = useState<string>("");
  const [result, setResult] = useState<CodingAgentResult | null>(null);
  const [error, setError] = useState<string>("");

  const handleGenerate = async () => {
    if (!task) return;
    setStatus('running');
    setError("");
    
    try {
      const response = await api.post("/developer/task", {
        task_type: "code_gen",
        repo_ref: "./",
        params: { task_description: task, mode }
      });
      
      setTraceId(response.trace_id);
      setResult(response.output_payload.result);
      setStatus(response.output_payload.status);
    } catch (e: any) {
      setError(e.message);
      setStatus('error');
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">Coding Assistant</h1>
      
      <Card>
        <div className="space-y-4">
          <textarea 
            placeholder="Describe the feature or fix..." 
            className="w-full border border-gray-300 rounded p-4 h-32"
            value={task}
            onChange={(e) => setTask(e.target.value)}
          />
          <div className="flex items-center justify-between">
            <div className="flex space-x-4">
              <label className="flex items-center space-x-2 cursor-pointer">
                <input 
                  type="radio" 
                  checked={mode === "preview"} 
                  onChange={() => setMode("preview")} 
                  className="text-blue-600 focus:ring-blue-500 h-4 w-4"
                />
                <span>Preview Only (Safe)</span>
              </label>
              <label className="flex items-center space-x-2 cursor-pointer">
                <input 
                  type="radio" 
                  checked={mode === "apply"} 
                  onChange={() => setMode("apply")} 
                  className="text-red-600 focus:ring-red-500 h-4 w-4"
                />
                <span className="text-red-600 font-medium">Apply Directly</span>
              </label>
            </div>
            
            <Button onClick={handleGenerate} disabled={status === 'running' || !task}>
              Generate Code
            </Button>
          </div>
        </div>
      </Card>

      {status && traceId && (
        <ExecutionTrace traceId={traceId} agent="Coding Agent" status={status} />
      )}

      {status === 'running' && <LoadingState message="Generating code and validating AST..." />}
      {status === 'error' && <ErrorState message={error} onRetry={handleGenerate} />}

      {status === 'success' && result && (
        <div className="space-y-6">
          <Card className={mode === 'apply' ? 'border-l-4 border-l-red-500' : 'border-l-4 border-l-blue-500'}>
            <h2 className="text-xl font-bold mb-2">Summary</h2>
            <p className="text-gray-700">{result.summary}</p>
          </Card>

          <Card>
            <h2 className="text-xl font-bold mb-4">Implementation Plan</h2>
            <ol className="list-decimal pl-5 space-y-2 text-gray-700">
              {result.plan.map((step, i) => <li key={i}>{step}</li>)}
            </ol>
          </Card>

          {result.files_changed.map(file => (
            <Card key={file} className="overflow-hidden p-0">
              <div className="bg-gray-100 p-3 border-b flex justify-between items-center">
                <span className="font-mono font-bold text-sm">{file}</span>
                <span className={`text-xs px-2 py-1 rounded-full ${result.validation[file] === 'Valid' ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'}`}>
                  {result.validation[file] || "Unvalidated"}
                </span>
              </div>
              <pre className="p-4 bg-gray-50 text-sm overflow-auto text-gray-800">
                <code>{result.diffs[file] || "No changes"}</code>
              </pre>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

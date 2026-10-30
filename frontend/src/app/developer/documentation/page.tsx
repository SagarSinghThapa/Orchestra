"use client";

import { useState } from "react";
import { api } from "@/services/apiClient";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { LoadingState, ErrorState } from "@/components/ui/StateWrappers";
import { ExecutionTrace } from "@/components/ui/ExecutionTrace";
import { DocAgentResult, TaskStatus } from "@/types/developer";

export default function DocumentationGeneratorPage() {
  const [docType, setDocType] = useState("README");
  const [mode, setMode] = useState<"preview" | "apply">("preview");
  
  const [status, setStatus] = useState<TaskStatus | null>(null);
  const [traceId, setTraceId] = useState<string>("");
  const [result, setResult] = useState<DocAgentResult | null>(null);
  const [error, setError] = useState<string>("");

  const handleGenerate = async () => {
    setStatus('running');
    setError("");
    
    try {
      const response = await api.post<{
        trace_id: string;
        output_payload: { result: DocAgentResult; status: TaskStatus };
      }>("/developer/task", {
        task_type: "doc_gen",
        repo_ref: "./",
        params: { doc_type: docType, mode }
      });
      
      setTraceId(response.trace_id);
      setResult(response.output_payload.result);
      setStatus(response.output_payload.status);
    } catch (e: unknown) {
      setError((e as Error).message);
      setStatus('error');
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">Documentation Generator</h1>
      
      <Card>
        <div className="flex space-x-4 items-center">
          <select 
            value={docType}
            onChange={e => setDocType(e.target.value)}
            className="flex-1 border border-gray-300 rounded px-4 py-2 bg-white"
          >
            <option value="README">README.md</option>
            <option value="repository_summary">Repository Summary</option>
            <option value="architecture">Architecture Document</option>
            <option value="API documentation">API Documentation</option>
          </select>
          
          <label className="flex items-center space-x-2 cursor-pointer border p-2 rounded">
            <input 
              type="checkbox" 
              checked={mode === "apply"} 
              onChange={(e) => setMode(e.target.checked ? "apply" : "preview")} 
              className="h-4 w-4"
            />
            <span>Write to disk (Apply)</span>
          </label>

          <Button onClick={handleGenerate} disabled={status === 'running'}>
            Generate
          </Button>
        </div>
      </Card>

      {status && traceId && (
        <ExecutionTrace traceId={traceId} agent="Documentation Agent" status={status} />
      )}

      {status === 'running' && <LoadingState message="Extracting context and generating markdown..." />}
      {status === 'error' && <ErrorState message={error} onRetry={handleGenerate} />}

      {status === 'success' && result && (
        <div className="space-y-6">
          
          {result.warnings.length > 0 && (
            <Card className="border-l-4 border-l-yellow-500 bg-yellow-50">
              <h3 className="font-bold text-yellow-800">Anti-Hallucination Warnings</h3>
              <ul className="list-disc pl-5 text-sm text-yellow-700">
                {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </Card>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2">
              <Card className="h-full">
                <div className="flex justify-between items-center mb-4 border-b pb-2">
                  <h2 className="text-xl font-bold">Markdown Preview</h2>
                  {result.artifact && (
                    <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded">
                      Saved to {result.artifact}
                    </span>
                  )}
                </div>
                <pre className="p-4 bg-gray-50 text-sm overflow-auto max-h-[500px] border rounded whitespace-pre-wrap">
                  {result.content}
                </pre>
              </Card>
            </div>
            
            <div>
              <Card className="h-full bg-gray-50">
                <h2 className="text-lg font-bold mb-4">Verified Sources</h2>
                <p className="text-sm text-gray-500 mb-2">
                  This documentation was derived explicitly from the following verified files to prevent LLM hallucination:
                </p>
                <ul className="space-y-1">
                  {result.sources.map(s => (
                    <li key={s} className="bg-white px-2 py-1 border rounded text-xs font-mono break-all text-blue-700">
                      {s}
                    </li>
                  ))}
                </ul>
              </Card>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

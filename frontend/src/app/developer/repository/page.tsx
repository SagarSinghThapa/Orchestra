"use client";

import { useState } from "react";
import { api } from "@/services/apiClient";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { LoadingState, ErrorState } from "@/components/ui/StateWrappers";
import { ExecutionTrace } from "@/components/ui/ExecutionTrace";
import { RepositoryAnalysisResult, TaskStatus } from "@/types/developer";

export default function RepositoryIntelPage() {
  const [repoRef, setRepoRef] = useState("");
  const [status, setStatus] = useState<TaskStatus | null>(null);
  const [traceId, setTraceId] = useState<string>("");
  const [result, setResult] = useState<RepositoryAnalysisResult | null>(null);
  const [error, setError] = useState<string>("");

  const handleAnalyze = async () => {
    if (!repoRef) return;
    setStatus('running');
    setError("");
    
    try {
      const response = await api.post("/developer/task", {
        task_type: "repo_analysis",
        repo_ref: repoRef,
        params: {}
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
      <h1 className="text-3xl font-bold">Repository Intelligence</h1>
      
      <Card>
        <div className="flex space-x-4">
          <input 
            type="text" 
            placeholder="Repository Path or URL" 
            className="flex-1 border border-gray-300 rounded px-4 py-2"
            value={repoRef}
            onChange={(e) => setRepoRef(e.target.value)}
          />
          <Button onClick={handleAnalyze} disabled={status === 'running'}>
            Analyze Repository
          </Button>
        </div>
      </Card>

      {status && traceId && (
        <ExecutionTrace traceId={traceId} agent="Repository Agent" status={status} />
      )}

      {status === 'running' && <LoadingState message="Analyzing repository structure..." />}
      {status === 'error' && <ErrorState message={error} onRetry={handleAnalyze} />}

      {status === 'success' && result && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <h2 className="text-xl font-bold mb-4">Metadata</h2>
            <ul className="space-y-2">
              <li><strong>Architecture:</strong> {result.architecture?.inferred || "Unknown"}</li>
              <li><strong>Languages:</strong> {result.languages.join(", ")}</li>
              <li><strong>Frameworks:</strong> {result.frameworks.join(", ")}</li>
              <li><strong>Test Coverage:</strong> {result.tests?.coverage || "N/A"}</li>
            </ul>
          </Card>
          
          <Card>
            <h2 className="text-xl font-bold mb-4">Important Files</h2>
            <ul className="list-disc pl-5 space-y-1">
              {result.important_files.map(f => <li key={f} className="font-mono text-sm">{f}</li>)}
            </ul>
          </Card>
          
          <Card className="md:col-span-2">
            <h2 className="text-xl font-bold mb-4 text-red-600">Risks & Recommendations</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <h3 className="font-bold text-gray-700">Risks</h3>
                <ul className="list-disc pl-5 text-red-700">
                  {result.risks.map(r => <li key={r}>{r}</li>)}
                </ul>
              </div>
              <div>
                <h3 className="font-bold text-gray-700">Recommendations</h3>
                <ul className="list-disc pl-5 text-blue-700">
                  {result.recommendations.map(r => <li key={r}>{r}</li>)}
                </ul>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

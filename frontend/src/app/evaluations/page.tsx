"use client";

import { useState, useEffect, useMemo } from "react";
import { api } from "@/services/apiClient";
import { Card } from "@/components/ui/Card";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/StateWrappers";
import { MetricCard } from "@/components/evaluations/MetricCard";
import { StatusBadge } from "@/components/evaluations/StatusBadge";
import { PerformanceBar } from "@/components/evaluations/PerformanceBar";
import { RunTable } from "@/components/evaluations/RunTable";
import { EvaluationSummary, EvaluationFilters, EvalStatus } from "@/types/evaluations";

export default function EvaluationsPage() {
  const [summary, setSummary] = useState<EvaluationSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters
  const [filters, setFilters] = useState<EvaluationFilters>({});

  const fetchSummary = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get("/evaluations/summary");
      setSummary(data as EvaluationSummary);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    const initFetch = async () => {
      try {
        const data = await api.get("/evaluations/summary");
        if (active) setSummary(data as EvaluationSummary);
      } catch (e: unknown) {
        if (active) setError((e as Error).message);
      } finally {
        if (active) setLoading(false);
      }
    };
    initFetch();
    return () => { active = false; };
  }, []);

  // Filtered runs
  const filteredRuns = useMemo(() => {
    if (!summary) return [];
    return summary.recent_runs.filter(run => {
      if (filters.agent && run.agent !== filters.agent) return false;
      if (filters.benchmark && run.benchmark !== filters.benchmark) return false;
      if (filters.status && run.status !== filters.status) return false;
      return true;
    });
  }, [summary, filters]);

  // Status distribution
  const statusCounts = useMemo(() => {
    if (!summary) return { passed: 0, failed: 0, running: 0, pending: 0, error: 0 };
    return {
      passed: summary.passed,
      failed: summary.failed,
      running: summary.running,
      pending: summary.pending,
      error: 0,
    };
  }, [summary]);

  const totalForBar = Math.max(statusCounts.passed + statusCounts.failed + statusCounts.running + statusCounts.pending, 1);

  if (loading) return <LoadingState message="Loading evaluation dashboard..." />;
  if (error) return <ErrorState message={error} onRetry={fetchSummary} />;
  if (!summary) return <EmptyState title="No Evaluations" description="The evaluation infrastructure has not produced any results yet. Runs will appear here once M1/M2 pipelines are active." />;

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-900">Evaluation Dashboard</h1>
        <span className="text-xs text-gray-400 bg-gray-100 px-3 py-1 rounded-full">Provisional — awaiting M1/M2 contracts</span>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {summary.metrics.map(m => (
          <MetricCard key={m.name} metric={m} />
        ))}
      </div>

      {/* Status Distribution Bar */}
      <Card>
        <h2 className="text-lg font-bold mb-3">Status Distribution</h2>
        <div className="flex rounded-full overflow-hidden h-6">
          <div className="bg-green-500 transition-all" style={{ width: `${(statusCounts.passed / totalForBar) * 100}%` }} title={`Passed: ${statusCounts.passed}`} />
          <div className="bg-red-500 transition-all" style={{ width: `${(statusCounts.failed / totalForBar) * 100}%` }} title={`Failed: ${statusCounts.failed}`} />
          <div className="bg-blue-500 transition-all animate-pulse" style={{ width: `${(statusCounts.running / totalForBar) * 100}%` }} title={`Running: ${statusCounts.running}`} />
          <div className="bg-gray-300 transition-all" style={{ width: `${(statusCounts.pending / totalForBar) * 100}%` }} title={`Pending: ${statusCounts.pending}`} />
        </div>
        <div className="flex space-x-6 mt-2 text-xs text-gray-500">
          <span className="flex items-center"><span className="w-3 h-3 rounded-full bg-green-500 mr-1"></span> Passed ({statusCounts.passed})</span>
          <span className="flex items-center"><span className="w-3 h-3 rounded-full bg-red-500 mr-1"></span> Failed ({statusCounts.failed})</span>
          <span className="flex items-center"><span className="w-3 h-3 rounded-full bg-blue-500 mr-1"></span> Running ({statusCounts.running})</span>
          <span className="flex items-center"><span className="w-3 h-3 rounded-full bg-gray-300 mr-1"></span> Pending ({statusCounts.pending})</span>
        </div>
      </Card>

      {/* Agent Performance */}
      <Card>
        <h2 className="text-lg font-bold mb-4">Agent Performance</h2>
        {summary.agents.length === 0 ? (
          <EmptyState title="No Agent Data" description="Agent performance data will appear after evaluation runs complete." />
        ) : (
          <div className="space-y-1">
            {summary.agents.map(a => <PerformanceBar key={a.agent} agent={a} />)}
          </div>
        )}
      </Card>

      {/* Benchmark Results */}
      <Card>
        <h2 className="text-lg font-bold mb-4">Benchmark Results</h2>
        {summary.benchmarks.length === 0 ? (
          <EmptyState title="No Benchmarks" description="Benchmark definitions are owned by Member 1. Results will appear once benchmarks are configured." />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {summary.benchmarks.map(b => (
              <div key={b.benchmark} className="bg-gray-50 rounded-lg p-4 border">
                <h3 className="font-semibold text-gray-800">{b.benchmark}</h3>
                <div className="mt-2 space-y-1 text-sm">
                  <div className="flex justify-between"><span className="text-gray-500">Avg Score</span><span className="font-bold">{b.avg_score.toFixed(1)}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Best</span><span className="text-green-600">{b.best_score}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Worst</span><span className="text-red-600">{b.worst_score}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Runs</span><span>{b.runs}</span></div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Filters + Historical Runs */}
      <Card>
        <div className="flex flex-wrap items-center justify-between mb-4 gap-3">
          <h2 className="text-lg font-bold">Historical Runs</h2>
          <div className="flex flex-wrap gap-2">
            <select
              className="border rounded px-3 py-1.5 text-sm bg-white"
              value={filters.agent || ''}
              onChange={e => setFilters(f => ({ ...f, agent: e.target.value || undefined }))}
            >
              <option value="">All Agents</option>
              {summary.agents.map(a => <option key={a.agent} value={a.agent}>{a.agent}</option>)}
            </select>

            <select
              className="border rounded px-3 py-1.5 text-sm bg-white"
              value={filters.benchmark || ''}
              onChange={e => setFilters(f => ({ ...f, benchmark: e.target.value || undefined }))}
            >
              <option value="">All Benchmarks</option>
              {summary.benchmarks.map(b => <option key={b.benchmark} value={b.benchmark}>{b.benchmark}</option>)}
            </select>

            <select
              className="border rounded px-3 py-1.5 text-sm bg-white"
              value={filters.status || ''}
              onChange={e => setFilters(f => ({ ...f, status: (e.target.value || undefined) as EvalStatus | undefined }))}
            >
              <option value="">All Statuses</option>
              <option value="passed">Passed</option>
              <option value="failed">Failed</option>
              <option value="running">Running</option>
              <option value="pending">Pending</option>
            </select>
          </div>
        </div>

        <RunTable runs={filteredRuns} />
      </Card>

      {/* Failure Analysis */}
      {summary.recent_runs.some(r => r.failure_reason) && (
        <Card className="border-l-4 border-l-red-500">
          <h2 className="text-lg font-bold mb-3 text-red-700">Failure Analysis</h2>
          <div className="space-y-3">
            {summary.recent_runs.filter(r => r.failure_reason).map(r => (
              <div key={r.id} className="bg-red-50 p-3 rounded border border-red-100">
                <div className="flex items-center space-x-3 mb-1">
                  <StatusBadge status={r.status} />
                  <span className="font-mono text-sm text-gray-700">{r.id.slice(0, 8)}</span>
                  <span className="text-sm text-gray-500">{r.agent} / {r.benchmark}</span>
                </div>
                <p className="text-sm text-red-700">{r.failure_reason}</p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

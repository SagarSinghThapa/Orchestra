import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export default function DeveloperIntelligencePage() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-900">Developer Intelligence</h1>
        <Button>New Task</Button>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="flex flex-col h-[400px]">
          <h2 className="text-xl font-semibold mb-4 border-b pb-2">Agent Orchestration</h2>
          <div className="flex-1 flex items-center justify-center bg-gray-50 rounded border border-dashed border-gray-300">
            <span className="text-gray-500">Developer Subgraph Interface</span>
          </div>
        </Card>
        
        <Card className="flex flex-col h-[400px]">
          <h2 className="text-xl font-semibold mb-4 border-b pb-2">Execution Logs</h2>
          <div className="flex-1 bg-gray-900 rounded p-4 overflow-auto text-gray-300 font-mono text-sm">
            <p className="text-green-400">$ System ready.</p>
            <p>Waiting for agent invocations...</p>
          </div>
        </Card>
      </div>
    </div>
  );
}

import { Card } from "@/components/ui/Card";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <h2 className="text-xl font-semibold mb-2">Active Repositories</h2>
          <p className="text-gray-600 text-4xl">4</p>
        </Card>
        
        <Card>
          <h2 className="text-xl font-semibold mb-2">Developer Agents</h2>
          <p className="text-gray-600 text-4xl">3</p>
        </Card>
        
        <Card>
          <h2 className="text-xl font-semibold mb-2">Recent Evaluations</h2>
          <p className="text-gray-600 text-4xl">12</p>
        </Card>
      </div>
    </div>
  );
}

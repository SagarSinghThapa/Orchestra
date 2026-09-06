"use client";

import { Card } from "@/components/ui/Card";

export default function SettingsPage() {
  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">Settings</h1>
      <Card>
        <div className="space-y-4">
          <p className="text-gray-600">
            Platform settings and configurations will go here.
          </p>
          <div className="border-t pt-4">
            <h2 className="text-xl font-semibold mb-2">API Configuration</h2>
            <p className="text-sm text-gray-500">Currently using mock API mode in local environment.</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

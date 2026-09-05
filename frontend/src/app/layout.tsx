import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Multi-Agent AI Platform",
  description: "Developer Intelligence Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-gray-50 text-gray-900`}>
        <div className="flex h-screen overflow-hidden">
          {/* Sidebar */}
          <aside className="w-64 bg-gray-900 text-white flex-shrink-0">
            <div className="p-4 text-xl font-bold border-b border-gray-800">
              AI Platform
            </div>
            <nav className="p-4 space-y-2">
              <a href="/dashboard" className="block p-2 rounded hover:bg-gray-800">Dashboard</a>
              <a href="/repositories" className="block p-2 rounded hover:bg-gray-800">Repository Intel</a>
              <a href="/developer" className="block p-2 rounded hover:bg-gray-800">Developer Agents</a>
              <a href="/evaluations" className="block p-2 rounded hover:bg-gray-800">Evaluations</a>
              <a href="/settings" className="block p-2 rounded hover:bg-gray-800">Settings</a>
            </nav>
          </aside>

          {/* Main Content */}
          <div className="flex flex-col flex-1 overflow-hidden">
            {/* Header */}
            <header className="h-16 bg-white border-b flex items-center justify-between px-6">
              <div className="flex items-center space-x-4">
                <span className="font-semibold text-gray-700">Project Selector</span>
                <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full border border-green-200">Connected</span>
              </div>
              <div className="flex items-center space-x-4">
                <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center text-white font-bold">
                  U
                </div>
              </div>
            </header>

            {/* Page Content */}
            <main className="flex-1 overflow-auto p-6">
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}

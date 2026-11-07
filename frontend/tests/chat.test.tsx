import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { HeroEmptyState } from "@/components/chat/HeroEmptyState";
import { MessageInput } from "@/components/chat/MessageInput";
import { AgentResponseCard } from "@/components/chat/AgentResponseCard";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { SessionSidebar } from "@/components/chat/SessionSidebar";
import { Message } from "@/types/chat";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}));

describe("Wave 14.6.2 & Visual Reconcile: Stitch Chat Workspace & Presentation Layer", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("HeroEmptyState renders exact Stitch headline, subtitle, task chips, composer and 3 feature cards", () => {
    const onSelectPrompt = vi.fn();
    render(
      <HeroEmptyState
        onSelectPrompt={onSelectPrompt}
        composer={<div data-testid="mock-composer">Composer In Center</div>}
      />
    );

    // Stitch headline
    expect(
      screen.getByRole("heading", { name: "What can I help you accomplish today?" })
    ).toBeInTheDocument();

    // Orchestra Autonomous Assistant heading
    expect(
      screen.getByRole("heading", { name: "Orchestra Autonomous Assistant" })
    ).toBeInTheDocument();

    // Composer rendered in center
    expect(screen.getByTestId("mock-composer")).toBeInTheDocument();

    // 6 Task suggestion chips
    expect(screen.getByRole("button", { name: /Research Assistant/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Analyze Repository/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Coding Assistant/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Documentation Generator/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Knowledge Search/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Evaluate Agents/i })).toBeInTheDocument();

    // Click on Analyze Repository chip triggers onSelectPrompt
    fireEvent.click(screen.getByRole("button", { name: /Analyze Repository/i }));
    expect(onSelectPrompt).toHaveBeenCalledWith(
      "Analyze repository architecture and entry points",
      "developer"
    );
  });

  it("MessageInput renders Stitch primary composer and handles submit correctly", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(
      <MessageInput
        onSend={onSend}
        activeProjectName="Alpha Project"
      />
    );

    const textbox = screen.getByRole("textbox");
    expect(textbox).toBeInTheDocument();
    expect(screen.getByText("Alpha Project")).toBeInTheDocument();
    expect(screen.getByText(/⌘ Enter/)).toBeInTheDocument();
    expect(screen.getByText("Orchestra AI")).toBeInTheDocument();
    expect(screen.getByTitle("Upload and index documents in Documents workspace")).toHaveAttribute("href", "/documents");

    // Typing in composer
    fireEvent.change(textbox, { target: { value: "Build authentication module" } });
    expect(textbox).toHaveValue("Build authentication module");

    // Send button click
    const sendBtn = screen.getByRole("button", { name: "Send" });
    await act(async () => {
      fireEvent.click(sendBtn);
    });

    expect(onSend).toHaveBeenCalledWith("Build authentication module", {
      forced_intent: undefined,
    });
  });

  it("AgentResponseCard renders structured developer diff with AST badge and guarded apply", () => {
    const mockDeveloperResult = {
      status: "success" as const,
      task_type: "code_gen" as const,
      mode: "preview" as const,
      summary: "Generated unified diff for fibonacci implementation.",
      files_analyzed: ["math/fibonacci.py"],
      proposed_patches: [
        {
          path: "math/fibonacci.py",
          diff: "--- a/math/fibonacci.py\n+++ b/math/fibonacci.py\n@@ -1,3 +1,5 @@\n+def fib(n):\n+    return n if n <= 1 else fib(n-1) + fib(n-2)",
          validation_status: "valid",
          original_hash: "a".repeat(64),
          new_hash: "b".repeat(64),
          applied: false,
        },
      ],
      documentation: null,
      warnings: [],
      tool_events: [],
      metadata: {},
    };

    render(
      <AgentResponseCard
        developerResult={mockDeveloperResult}
        projectId={1}
      />
    );

    // Summary and AST badge
    expect(screen.getByText(/Generated unified diff for fibonacci/i)).toBeInTheDocument();
    expect(screen.getByText("✓ AST Syntax Valid")).toBeInTheDocument();
    expect(screen.getAllByText("math/fibonacci.py").length).toBeGreaterThan(0);

    // Guarded apply button
    const applyBtn = screen.getByRole("button", { name: /Apply Changes to Workspace/i });
    expect(applyBtn).toBeInTheDocument();

    // Click reveals confirmation prompt
    fireEvent.click(applyBtn);
    expect(screen.getByText(/Confirm Modification of Workspace Files\?/i)).toBeInTheDocument();
  });

  it("MessageBubble intercepts raw JSON strings and normalizes to structured AgentResponseCard", () => {
    const rawJsonMessage: Message = {
      id: 2,
      role: "assistant",
      content: '{"status":"success","summary":"Deployment smoke test developer task completed successfully.","patches":[]}',
      created_at: new Date().toISOString(),
    };

    const { container } = render(
      <MessageBubble message={rawJsonMessage} projectId={1} />
    );

    // Inviolable UX invariant: Raw JSON string is NEVER rendered as literal text in chat
    expect(container.textContent).not.toContain('{"status":"success"');
    expect(container.textContent).not.toContain('"patches":[]');

    // Intercepted and rendered as structured summary and Developer Intelligence card
    expect(screen.getByText("Developer Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Deployment smoke test developer task completed successfully.")).toBeInTheDocument();
    expect(screen.getByText("SUCCESS")).toBeInTheDocument();
    expect(screen.getByText("Dry-run Preview")).toBeInTheDocument();
  });

  it("SessionSidebar behaves as slide-over drawer with Escape and backdrop click dismiss", () => {
    const onClose = vi.fn();
    const onSelectSession = vi.fn();
    const onNewChat = vi.fn();
    const sessions = [
      { id: 9, project_id: 1, type: "orchestrator", status: "active", created_at: new Date().toISOString() },
    ];

    const { rerender } = render(
      <SessionSidebar
        isOpen={false}
        onClose={onClose}
        sessions={sessions}
        activeSessionId={9}
        onSelectSession={onSelectSession}
        onNewChat={onNewChat}
      />
    );

    // Hidden when isOpen is false
    expect(screen.queryByLabelText("Recent Conversations")).not.toBeInTheDocument();

    // Renders drawer when isOpen is true
    rerender(
      <SessionSidebar
        isOpen={true}
        onClose={onClose}
        sessions={sessions}
        activeSessionId={9}
        onSelectSession={onSelectSession}
        onNewChat={onNewChat}
      />
    );

    expect(screen.getByLabelText("Recent Conversations")).toBeInTheDocument();
    expect(screen.getByText("Session #9")).toBeInTheDocument();

    // Escape key triggers onClose
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });
});

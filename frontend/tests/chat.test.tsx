import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { HeroEmptyState } from "@/components/chat/HeroEmptyState";
import { MessageInput } from "@/components/chat/MessageInput";
import { AgentResponseCard } from "@/components/chat/AgentResponseCard";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}));

describe("Wave 14.6.2: Stitch Chat Workspace & Presentation Layer", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("HeroEmptyState renders exact Stitch headline, subtitle, task chips and 3 feature cards", () => {
    const onSelectPrompt = vi.fn();
    render(<HeroEmptyState onSelectPrompt={onSelectPrompt} />);

    // Stitch headline
    expect(
      screen.getByRole("heading", { name: "What can I help you accomplish today?" })
    ).toBeInTheDocument();

    // Orchestra Autonomous Assistant heading
    expect(
      screen.getByRole("heading", { name: "Orchestra Autonomous Assistant" })
    ).toBeInTheDocument();

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
});

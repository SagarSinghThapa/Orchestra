import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { CitationViewer } from "@/components/chat/CitationViewer";
import { MessageInput } from "@/components/chat/MessageInput";
import { Message, ResearchResponse } from "@/types/chat";
import { api } from "@/services/apiClient";

describe("Real-time Streaming & Citation Polish UX", () => {
  it("MessageBubble renders pulsing streaming cursor while state is streaming", () => {
    const streamingMsg: Message = {
      role: "assistant",
      content: "Analyzing distributed consensus protocol",
      state: "streaming",
    };

    const { container } = render(<MessageBubble message={streamingMsg} />);

    expect(screen.getByText(/Analyzing distributed consensus protocol/i)).toBeInTheDocument();
    const cursor = container.querySelector('[aria-hidden="true"]');
    expect(cursor).toBeInTheDocument();
    expect(cursor).toHaveTextContent("▍");
  });

  it("MessageBubble removes streaming cursor once state transitions to confirmed", () => {
    const confirmedMsg: Message = {
      role: "assistant",
      content: "Consensus protocol finalized.",
      state: "confirmed",
    };

    const { container } = render(<MessageBubble message={confirmedMsg} />);

    expect(screen.getByText(/Consensus protocol finalized/i)).toBeInTheDocument();
    const cursor = container.querySelector('[aria-hidden="true"]');
    expect(cursor).not.toBeInTheDocument();
  });

  it("CitationViewer renders polished format with readable separator [1] filename · p. N", () => {
    const mockResearch: ResearchResponse = {
      question: "What is the procedure?",
      status: "completed",
      answer: "The deployment procedure is documented.",
      claims: [],
      citations: [
        {
          citation_id: "cite_1",
          evidence_id: "ev_1",
          document_id: 10,
          document_filename: "orchestra_demo.txt",
          page_number: 1,
          chunk_id: "c1",
          start_char: 0,
          end_char: 100,
          text: "Demo text",
          score: 0.95,
        },
      ],
      evidence_count: 1,
    };

    render(<CitationViewer researchResult={mockResearch} />);

    // Check [1]
    expect(screen.getByText("[1]")).toBeInTheDocument();
    // Check filename
    expect(screen.getByText("orchestra_demo.txt")).toBeInTheDocument();
    // Check separator ·
    expect(screen.getByText("·")).toBeInTheDocument();
    // Check p. 1
    expect(screen.getByText("p. 1")).toBeInTheDocument();
  });

  it("api.stream parses Server-Sent Events stream correctly", async () => {
    const mockEvents: { event: string; data: unknown }[] = [];

    const mockStreamData = [
      'event: session\ndata: {"session_id": 42}\n\n',
      'event: text_delta\ndata: {"delta": "Hello"}\n\n',
      'event: text_delta\ndata: {"delta": " world"}\n\n',
      'event: done\ndata: {"session_id": 42, "answer": "Hello world"}\n\n',
    ];

    let chunkIndex = 0;
    const encoder = new TextEncoder();
    const mockReadableStream = new ReadableStream({
      pull(controller) {
        if (chunkIndex < mockStreamData.length) {
          controller.enqueue(encoder.encode(mockStreamData[chunkIndex++]));
        } else {
          controller.close();
        }
      },
    });

    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 200,
      body: mockReadableStream,
    } as unknown as Response);

    await api.stream("/test/stream", { prompt: "hi" }, {
      onEvent: (evt) => mockEvents.push(evt),
    });

    expect(mockEvents.length).toBe(4);
    expect(mockEvents[0]).toEqual({ event: "session", data: { session_id: 42 } });
    expect(mockEvents[1]).toEqual({ event: "text_delta", data: { delta: "Hello" } });
    expect(mockEvents[2]).toEqual({ event: "text_delta", data: { delta: " world" } });
    expect(mockEvents[3]).toEqual({
      event: "done",
      data: { session_id: 42, answer: "Hello world" },
    });
  });

  it("MessageBubble renders subtle thinking processing state for Direct Q&A before first token arrives", () => {
    const thinkingMsg: Message = {
      role: "assistant",
      content: "",
      state: "streaming",
      intent: "direct_qa",
      status_text: "Thinking...",
    };

    render(<MessageBubble message={thinkingMsg} />);
    const statusEl = screen.getByRole("status", { name: /Thinking/i });
    expect(statusEl).toBeInTheDocument();
    expect(screen.getByText(/Thinking\.\.\./i)).toBeInTheDocument();
    expect(screen.queryByText("▍")).not.toBeInTheDocument();
  });

  it("MessageBubble renders research status indicator before content arrives", () => {
    const researchStatusMsg: Message = {
      role: "assistant",
      content: "",
      state: "streaming",
      intent: "research",
      status_text: "Searching knowledge...",
    };

    render(<MessageBubble message={researchStatusMsg} />);
    const statusEl = screen.getByRole("status", { name: /Searching knowledge\.\.\./i });
    expect(statusEl).toBeInTheDocument();
    expect(screen.getByText("Searching knowledge...")).toBeInTheDocument();
  });

  it("MessageBubble renders developer status indicator before content arrives", () => {
    const devStatusMsg: Message = {
      role: "assistant",
      content: "",
      state: "streaming",
      intent: "developer",
      status_text: "Analyzing repository...",
    };

    render(<MessageBubble message={devStatusMsg} />);
    const statusEl = screen.getByRole("status", { name: /Analyzing repository\.\.\./i });
    expect(statusEl).toBeInTheDocument();
    expect(screen.getByText("Analyzing repository...")).toBeInTheDocument();
  });

  it("MessageBubble transitions cleanly from thinking to answer when content arrives", () => {
    const { rerender } = render(
      <MessageBubble
        message={{
          role: "assistant",
          content: "",
          state: "streaming",
          intent: "direct_qa",
          status_text: "Thinking...",
        }}
      />
    );
    expect(screen.getByRole("status", { name: /Thinking/i })).toBeInTheDocument();

    rerender(
      <MessageBubble
        message={{
          role: "assistant",
          content: "Here is the direct answer.",
          state: "streaming",
          intent: "direct_qa",
        }}
      />
    );

    expect(screen.queryByRole("status", { name: /Thinking/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Here is the direct answer\./i)).toBeInTheDocument();
    expect(screen.getByText("▍")).toBeInTheDocument();
  });

  it("MessageBubble sets aria-live polite and aria-busy true while streaming", () => {
    const streamingMsg: Message = {
      role: "assistant",
      content: "Partial streamed token",
      state: "streaming",
    };

    render(<MessageBubble message={streamingMsg} />);
    const bubble = screen.getByTestId("assistant-message-bubble");
    expect(bubble).toHaveAttribute("aria-live", "polite");
    expect(bubble).toHaveAttribute("aria-busy", "true");
  });

  it("MessageBubble renders execution trace collapsed by default with aria-expanded false", () => {
    const traceMsg: Message = {
      role: "assistant",
      content: "Final answer with trace",
      state: "confirmed",
      execution_trace: ["classify_intent:direct_qa", "direct_qa:completed"],
    };

    render(<MessageBubble message={traceMsg} />);
    const traceBtn = screen.getByRole("button", { name: /View Execution Trace \(2 steps\)/i });
    expect(traceBtn).toBeInTheDocument();
    expect(traceBtn).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("classify_intent:direct_qa")).not.toBeInTheDocument();

    fireEvent.click(traceBtn);
    expect(traceBtn).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("classify_intent:direct_qa")).toBeInTheDocument();
  });

  it("MessageInput replaces Send button with Stop generating button while isExecuting is true and triggers onStop", () => {
    const mockSend = vi.fn().mockResolvedValue(undefined);
    const mockStop = vi.fn();

    const { rerender } = render(
      <MessageInput
        onSend={mockSend}
        isExecuting={false}
        value="Hello Orchestra"
      />
    );

    expect(screen.getByRole("button", { name: /Send/i })).toBeInTheDocument();

    rerender(
      <MessageInput
        onSend={mockSend}
        isExecuting={true}
        onStop={mockStop}
        value="Hello Orchestra"
      />
    );

    const stopBtn = screen.getByRole("button", { name: /Stop generating/i });
    expect(stopBtn).toBeInTheDocument();

    fireEvent.click(stopBtn);
    expect(mockStop).toHaveBeenCalledTimes(1);
  });
});


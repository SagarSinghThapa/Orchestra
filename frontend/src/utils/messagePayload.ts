import { ResearchResponse, IntentType } from "@/types/chat";
import { DeveloperResponse } from "@/types/developer";

export interface ParsedMessagePayload {
  displayText: string;
  intent?: IntentType;
  researchResult?: ResearchResponse | null;
  developerResult?: DeveloperResponse | null;
  isStructured: boolean;
}

export function parseMessageContent(content: string): ParsedMessagePayload {
  if (!content || typeof content !== "string") {
    return { displayText: "", isStructured: false };
  }
  const trimmed = content.trim();
  if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (parsed && typeof parsed === "object") {
        // Case 1: Structured Research
        if (
          ("version" in parsed || "intent" in parsed) &&
          (parsed.intent === "research" || "citations" in parsed)
        ) {
          const researchResult: ResearchResponse = {
            question: parsed.question || "",
            status: parsed.status || "completed",
            answer: parsed.answer || "",
            claims: parsed.claims || [],
            citations: parsed.citations || [],
            evidence_count: parsed.evidence_count || (parsed.citations ? parsed.citations.length : 0),
            metadata: parsed.metadata || {},
          };
          return {
            displayText: parsed.answer || "",
            intent: "research",
            researchResult,
            isStructured: true,
          };
        }
        // Case 2: Structured Developer
        if (
          ("version" in parsed && parsed.intent === "developer") ||
          ("status" in parsed && ("summary" in parsed || "patches" in parsed || "proposed_patches" in parsed))
        ) {
          const patches = parsed.proposed_patches || parsed.patches || [];
          const devResult: DeveloperResponse = {
            status: parsed.status || "success",
            task_type: parsed.task_type || "code_gen",
            mode: parsed.mode || "preview",
            summary: parsed.summary || parsed.answer || "",
            files_analyzed: parsed.files_analyzed || [],
            proposed_patches: patches,
            documentation: parsed.documentation || null,
            warnings: parsed.warnings || [],
            tool_events: parsed.tool_events || [],
            metadata: parsed.metadata || {},
          };
          return {
            displayText: parsed.answer || parsed.summary || "",
            intent: "developer",
            developerResult: devResult,
            isStructured: true,
          };
        }
        // Case 3: Generic object with answer or summary
        if ("answer" in parsed && typeof parsed.answer === "string") {
          return {
            displayText: parsed.answer,
            isStructured: true,
          };
        }
      }
    } catch {
      // Fallback to plain content
    }
  }
  return {
    displayText: content,
    isStructured: false,
  };
}

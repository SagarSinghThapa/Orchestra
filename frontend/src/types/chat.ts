export type MessageRole = "user" | "assistant" | "tool" | "system";
export type MessageDeliveryState = "sending" | "confirmed" | "failed";

export type IntentType = "research" | "developer" | "direct_qa";

export interface VerifiedCitation {
  citation_id: string;
  evidence_id: string;
  document_id: number;
  document_filename: string;
  page_number: number;
  chunk_id: string;
  start_char: number;
  end_char: number;
  text: string;
  score: number;
}

export interface ResearchClaim {
  claim_text: string;
  citation_ids: string[];
}

export interface ResearchResponse {
  question: string;
  status: "completed" | "insufficient_evidence" | "failed";
  answer: string;
  claims: ResearchClaim[];
  citations: VerifiedCitation[];
  evidence_count: number;
  metadata?: Record<string, unknown>;
}

export interface OrchestratorResponse {
  session_id: number;
  intent: IntentType;
  answer: string;
  research_result?: ResearchResponse | null;
  developer_result?: unknown | null;
  execution_trace: string[];
  metadata: Record<string, unknown>;
}

export interface OrchestratorRequest {
  prompt: string;
  session_id?: number | null;
}

export interface Message {
  id?: number;
  session_id?: number;
  role: MessageRole;
  content: string;
  created_at?: string;
  state?: MessageDeliveryState;
  intent?: IntentType;
  research_result?: ResearchResponse | null;
  developer_result?: unknown | null;
  execution_trace?: string[];
}

export interface SessionItem {
  id: number;
  project_id: number;
  type: string;
  status: string;
  created_at: string;
  updated_at?: string;
}

export interface MemoryStats {
  session_id: number;
  summary_exists: boolean;
  summary_version: number;
  message_watermark_id: number;
  messages_summarized_count: number;
  sliding_window_message_count: number;
  assembled_context_chars: number;
}


export type DocumentStatus = "uploaded" | "processing" | "indexed" | "failed";

export interface DocumentResponse {
  id: number;
  project_id: number;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  status: DocumentStatus;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentDetailResponse extends DocumentResponse {
  error_message?: string | null;
}

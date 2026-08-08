export interface User {
  id: number;
  email: string;
  full_name?: string;
  is_active: boolean;
  created_at: string;
}

export interface Document {
  id: string;
  filename: string;
  original_filename: string;
  content_type: string;
  file_size: number;
  status: "pending" | "processing" | "completed" | "failed";
  chunk_count: number;
  created_at: string;
  error_message?: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

export interface Conversation {
  id: string;
  title?: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations?: string;
  created_at: string;
}

export interface Citation {
  document: string;
  page: number;
  chunk: string;
}

export interface ChatResponse {
  answer: string;
  conversation_id: string;
  citations: Citation[];
  confidence: number;
  model: string;
  usage: Record<string, number>;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LLMProvider {
  id: string;
  name: string;
  configured: boolean;
  active: boolean;
}

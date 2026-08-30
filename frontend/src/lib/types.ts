export type TransactionRow = {
  date: string;
  merchant: string;
  amount: number;
  type: "Credit" | "Debit" | string;
  category: string;
};

export type Insights = {
  headline: string;
  highlights: string[];
  watchouts?: string[];
};

export type AnalyzeResponse = {
  rows: TransactionRow[];
  insights: Insights;
  insights_source: string;
  dataset_id?: string | null;
};

export type WorkbookInspect = {
  sheets: string[];
  suggested_sheet: string | null;
  format: "csv" | "paytm" | "generic" | string;
};

export type DatasetResponse = AnalyzeResponse & {
  dataset_id: string;
  filename: string;
  created_at: string;
};

export type ToolCallTrace = {
  name: string;
  args?: Record<string, unknown>;
};

export type ChatMessage = {
  role: "user" | "assistant" | string;
  content: string;
  tool_trace?: ToolCallTrace[] | null;
  created_at?: string;
};

export type ChatResponse = {
  reply: string;
  tool_calls: ToolCallTrace[];
  source: string;
};

export type ObservabilityRun = {
  at: string;
  endpoint?: string;
  filename?: string | null;
  insights_source?: string | null;
  ok: boolean;
  slowest_step?: string | null;
  total_ms?: number | null;
  steps_ms?: Record<string, number>;
  tokens_in?: number | null;
  tokens_out?: number | null;
  cost_usd?: number | null;
};

export type ObservabilitySnapshot = {
  request_count: number;
  avg_ms: Record<string, number>;
  max_ms?: Record<string, number>;
  bottleneck?: { step: string; avg_ms: number; max_ms: number } | null;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number;
  recent?: ObservabilityRun[];
};

export const ANALYZE_STEPS = [
  "read_file",
  "parse",
  "categorize",
  "analytics",
  "insights",
  "serialize_rows",
  "total",
] as const;

export type Role = "user" | "assistant";

export interface Message {
  id: string;
  role: Role;
  content: string;
}

export interface PsychologicalNeed {
  name: string;
  confidence: number;
}

export interface RiskAssessment {
  level: "LOW" | "CONCERN" | "HIGH";
  signals: string[];
  immediate_danger: boolean;
  source: string;
}

export interface MotivationState {
  importance: number | null;
  confidence: number | null;
}

export interface KnowledgeHit {
  id: string;
  title: string;
  category: string;
  summary: string;
  suggested_actions: string[];
  score: number;
  bm25_score: number;
  semantic_score: number;
  matched_terms: string[];
  source_name: string | null;
  source_url: string | null;
}

export interface ActionPlan {
  title: string;
  behavior: string;
  duration: string;
  reason: string;
  confidence: number;
  obstacle: string | null;
  coping_plan: string | null;
  attempts: number;
  successes: number;
  status: "active" | "completed" | "paused";
  last_review: string | null;
}

export interface ReviewerTrace {
  stage: string;
  risk: RiskAssessment;
  focus_topic: string | null;
  emotions: string[];
  psychological_needs: PsychologicalNeed[];
  change_talk: string[];
  sustain_talk: string[];
  motivation: MotivationState;
  mi_strategies: string[];
  rag_used: boolean;
  retrieval_method: string;
  knowledge_hits: KnowledgeHit[];
  quality_flags: string[];
  fallback_used: boolean;
  processing_ms: number;
}

export interface EvaluationSummary {
  ready: boolean;
  generated_at: string | null;
  total: number;
  passed: number;
  pass_rate: number;
  safety_route_rate: number;
  action_plan_rate: number;
  average_processing_ms: number;
  failed_ids: string[];
  benchmark_ready: boolean;
  baseline_mode: string | null;
  full_system_score: number | null;
  baseline_score: number | null;
  score_delta: number | null;
  note: string;
}

export interface DemoScenario {
  id: string;
  title: string;
  description: string;
  messages: string[];
  reviewer_highlights: string[];
  high_risk: boolean;
}

export interface DemoScenarioList {
  scenarios: DemoScenario[];
  notice: string;
}

export interface Diagnostics {
  version: string;
  environment: string;
  llm_enabled: boolean;
  model: string;
  provider_host: string | null;
  storage: string;
  session_retention_hours: number;
  knowledge_entries: number;
  evaluation_ready: boolean;
  benchmark_ready: boolean;
  warnings: string[];
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  quick_replies: string[];
  action_plan: ActionPlan | null;
  trace: ReviewerTrace | null;
}

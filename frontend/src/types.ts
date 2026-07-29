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
  knowledge_hits: KnowledgeHit[];
  quality_flags: string[];
  fallback_used: boolean;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  quick_replies: string[];
  action_plan: ActionPlan | null;
  trace: ReviewerTrace | null;
}

export type EventStatus = 'pending' | 'normalised' | 'classified' | 'published' | 'processing' | 'assessed' | 'failed';
export type EventSeverity = 'low' | 'medium' | 'high' | 'critical';
export type EventCategory = 'geopolitical' | 'economic' | 'natural_disaster' | 'cyber' | 'regulatory' | 'health' | 'security' | 'environmental' | 'social' | 'technology' | 'unknown';
export type RiskLevel = 'minimal' | 'low' | 'moderate' | 'high' | 'critical';

export interface AegisEvent {
  id: string;
  source: string;
  source_url?: string;
  title: string;
  raw_content: string;
  summary?: string;
  event_date: string;
  ingested_at: string;
  location?: string;
  affected_regions: string[];
  tags: string[];
  status: EventStatus;
  correlation_id: string;
}

export interface EventClassification {
  id: string;
  event_id: string;
  category: EventCategory;
  severity: EventSeverity;
  confidence: number;
  sub_categories: string[];
  classified_at: string;
  classifier_version: string;
  rationale?: string;
}

export interface RiskScore {
  id: string;
  assessment_id: string;
  event_id: string;
  client_id: string;
  project_id?: string;
  overall_score: number;
  severity_component: number;
  exposure_component: number;
  confidence_component: number;
  risk_level: RiskLevel;
  scoring_algorithm_version: string;
  factors: Record<string, number>;
  scored_at: string;
}

export interface Assessment {
  id: string;
  event_id: string;
  client_id: string;
  project_id?: string;
  correlation_id: string;
  assessment_text: string;
  key_risks: string[];
  recommended_actions: string[];
  evidence_references?: EvidenceReference[];
  model_provider: string;
  model_version: string;
  assessed_at: string;
  processing_duration_ms?: number;
}

export interface EvidenceReference {
  source_document_id: string;
  source_type: string;
  content_excerpt: string;
  relevance_score: number;
  retrieval_strategy: string;
}

export interface ClientExposure {
  id: string;
  client_id: string;
  event_id: string;
  project_id?: string;
  relevance_score: number;
  matched_keywords: string[];
  matched_geography: string[];
  assessed_at: string;
}

export interface TraceAssessment {
  assessment: Assessment;
  risk_score: RiskScore;
  client_exposure: ClientExposure;
}

export interface TraceResponse {
  event: AegisEvent;
  classification: EventClassification;
  assessments: TraceAssessment[];
}

export interface DashboardSummary {
  total_events: number;
  total_assessments: number;
  affected_clients: number;
  affected_projects: number;
  event_status_breakdown: Record<string, number>;
  category_breakdown: Record<string, number>;
  severity_breakdown: Record<string, number>;
  risk_level_breakdown: Record<string, number>;
  recent_events: AegisEvent[];
  recent_assessments: Assessment[];
}

export interface HealthResponse {
  status: string;
  model_provider: { name: string; version: string; healthy: boolean };
  knowledge_base: { documents_indexed: number };
}

export interface EventDetailResponse {
  event: AegisEvent;
  classification: EventClassification | null;
  assessments: Assessment[];
}

export interface AssessmentsResponse {
  assessments: AssessmentWithScore[];
  count: number;
}

export interface AssessmentWithScore {
  assessment: Assessment;
  risk_score?: RiskScore;
  event_title?: string;
}

export interface EventsResponse {
  events: AegisEvent[];
  count: number;
}

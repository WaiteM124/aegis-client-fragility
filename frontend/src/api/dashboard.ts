import { apiFetch } from './client';
import type { DashboardSummary, TraceResponse } from '../types';

export interface AssessmentsListItem {
  assessment: {
    id: string;
    event_id: string;
    client_id: string;
    project_id?: string;
    correlation_id: string;
    assessment_text: string;
    key_risks: string[];
    recommended_actions: string[];
    model_provider: string;
    model_version: string;
    assessed_at: string;
    processing_duration_ms?: number;
  };
  risk_score?: {
    overall_score: number;
    risk_level: string;
  };
}

export interface AssessmentsResponse {
  assessments: AssessmentsListItem[];
  count: number;
}

export function getSummary(): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>('/api/v1/dashboard/summary');
}

export function getTrace(eventId: string): Promise<TraceResponse> {
  return apiFetch<TraceResponse>(`/api/v1/dashboard/events/${eventId}/trace`);
}

export function getAssessments(limit: number, offset: number, clientId?: string): Promise<AssessmentsResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (clientId) params.set('client_id', clientId);
  return apiFetch<AssessmentsResponse>(`/api/v1/dashboard/assessments?${params}`);
}

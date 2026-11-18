import { apiFetch } from './client';
import type { EventsResponse, EventDetailResponse } from '../types';

export function getEvents(limit: number, offset: number): Promise<EventsResponse> {
  return apiFetch<EventsResponse>(`/api/v1/events?limit=${limit}&offset=${offset}`);
}

export function getEvent(id: string): Promise<EventDetailResponse> {
  return apiFetch<EventDetailResponse>(`/api/v1/events/${id}`);
}

export interface SubmitEventPayload {
  source: string;
  title: string;
  event_date: string;
  raw_content: string;
  location?: string;
  source_url?: string;
  affected_regions: string[];
  tags?: string[];
}

export interface SubmitEventResponse {
  event_id: string;
  correlation_id: string;
  status: string;
  message: string;
}

export function submitEvent(payload: SubmitEventPayload): Promise<SubmitEventResponse> {
  return apiFetch<SubmitEventResponse>('/api/v1/events', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

import type { Criteria, Metadata, Property, SearchResponse } from './types'

const API_BASE = '/api'
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!response.ok) {
    const message = await response.text().catch(() => '')
    throw new Error(`API ${response.status}: ${message || response.statusText}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; advertisements: number }>('/health'),
  metadata: () => request<Metadata>('/meta'),
  search: (criteria: Criteria, sort_by = 'relevance') => request<SearchResponse>('/search', {
    method: 'POST', body: JSON.stringify({ criteria, sort_by, limit: 100 }),
  }),
  interpret: (query: string, current_criteria?: Criteria) => request<{ criteria: Criteria; parsed_by: string; ai_available: boolean }>('/search/interpret', {
    method: 'POST', body: JSON.stringify({ query, current_criteria }),
  }),
  refine: (message: string, current_criteria: Criteria) => request<{ criteria: Criteria; parsed_by: string }>('/search/refine', {
    method: 'POST', body: JSON.stringify({ message, current_criteria }),
  }),
  property: (id: string, criteria?: Criteria) => request<Property>(`/properties/${encodeURIComponent(id)}${criteria ? `?criteria=${encodeURIComponent(JSON.stringify(criteria))}` : ''}`),
  compare: (ids: string[]) => request<{ properties: Property[] }>(`/compare?ids=${encodeURIComponent(ids.join(','))}`),
  synthesis: (properties: Property[], user_goal?: string) => request<{ summary: string | null; generated_by: string; message?: string }>('/compare/synthesis', {
    method: 'POST', body: JSON.stringify({ properties, user_goal }),
  }),
}

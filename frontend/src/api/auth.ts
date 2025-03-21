import { API_BASE_URL } from '../config';

export interface App {
  id: number;
  app_id: string;
  name: string;
  description: string | null;
  type: 'tool_provider' | 'agent';
  created_at: string;
  is_active: boolean;
  last_connected: string | null;
}

export interface ApiKey {
  id: number;
  name: string;
  app_id: number;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
}

export async function listApps(type?: 'tool_provider' | 'agent'): Promise<App[]> {
  const params = type ? `?type=${type}` : '';
  const response = await fetch(`${API_BASE_URL}/api/auth/apps${params}`);
  if (!response.ok) {
    throw new Error('Failed to fetch apps');
  }
  return response.json();
}

export async function listApiKeys(appId?: number): Promise<ApiKey[]> {
  const params = appId ? `?app_id=${appId}` : '';
  const response = await fetch(`${API_BASE_URL}/api/auth/keys${params}`);
  if (!response.ok) {
    throw new Error('Failed to fetch API keys');
  }
  return response.json();
}

export function getApiKey(): string {
    const apiKey = localStorage.getItem('apiKey');
    if (!apiKey) {
        throw new Error('No API key found');
    }
    return apiKey;
} 
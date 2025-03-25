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

export interface LoginResponse {
  expires_at: string;
}

export interface SessionResponse {
  authenticated: boolean;
  expires_at?: string;
}

export async function login(password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/admin/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ password }),
    credentials: 'include', // This is important for cookies
  });
  
  if (!response.ok) {
    throw new Error('Login failed');
  }
  
  return response.json();
}

export async function logout(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/auth/admin/logout`, {
    method: 'POST',
    credentials: 'include',
  });
  
  if (!response.ok) {
    throw new Error('Logout failed');
  }
}

export async function checkSession(): Promise<SessionResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/admin/session`, {
      credentials: 'include',
    });
    
    if (!response.ok) {
      return { authenticated: false };
    }
    
    return await response.json();
  } catch (error) {
    return { authenticated: false };
  }
}

export async function listApps(type?: 'tool_provider' | 'agent'): Promise<App[]> {
  const params = type ? `?type=${type}` : '';
  const response = await fetch(`${API_BASE_URL}/api/auth/apps${params}`, {
    credentials: 'include', // Add credentials for authenticated requests
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch apps');
  }
  
  return response.json();
}

export async function listApiKeys(appId?: number): Promise<ApiKey[]> {
  const params = appId ? `?app_id=${appId}` : '';
  const response = await fetch(`${API_BASE_URL}/api/auth/keys${params}`, {
    credentials: 'include', // Add credentials for authenticated requests
  });
  
  if (!response.ok) {
    throw new Error('Failed to fetch API keys');
  }
  
  return response.json();
}

// Legacy API key handling - this should be removed once all pages use session auth
export function getApiKey(): string {
    const apiKey = localStorage.getItem('apiKey');
    if (!apiKey) {
        throw new Error('No API key found');
    }
    return apiKey;
} 
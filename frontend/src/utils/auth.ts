/**
 * APEX Quantitative Trading Workstation — Centralized API Authentication Utility
 * 
 * Manages authentication credentials across environment configuration and local storage,
 * formatting standard headers conforming to backend FastAPI dependencies (X-API-Key and HTTP Bearer).
 */

const STORAGE_KEY = 'apex_api_key';
const ALT_STORAGE_KEY = 'apex_auth_token';
const LEGACY_STORAGE_KEY = 'apexnse_api_key';

/**
 * Resolves the active authentication token.
 * Priority:
 * 1. Browser localStorage: 'apex_api_key', 'apex_auth_token', or 'apexnse_api_key'
 * 2. Window runtime global: window.__APEX_API_KEY__
 * 3. Vite environment variables: VITE_APEX_API_KEY, VITE_API_KEY, or VITE_API_AUTH_TOKEN
 * 4. Empty string if unconfigured
 */
export function getApiAuthToken(): string {
  if (typeof window !== 'undefined') {
    try {
      const fromStorage =
        localStorage.getItem(STORAGE_KEY) ||
        localStorage.getItem(ALT_STORAGE_KEY) ||
        localStorage.getItem(LEGACY_STORAGE_KEY);
      if (fromStorage && fromStorage.trim()) {
        return fromStorage.trim();
      }
      const fromWindow = (window as any).__APEX_API_KEY__;
      if (typeof fromWindow === 'string' && fromWindow.trim()) {
        return fromWindow.trim();
      }
    } catch {
      // LocalStorage access restricted in some private modes
    }
  }

  try {
    const envToken =
      (import.meta as any).env?.VITE_APEX_API_KEY ||
      (import.meta as any).env?.VITE_API_KEY ||
      (import.meta as any).env?.VITE_API_AUTH_TOKEN;
    if (typeof envToken === 'string' && envToken.trim()) {
      return envToken.trim();
    }
  } catch {
    // env not available
  }

  return '';
}

/**
 * Persists an API authentication token to browser storage.
 */
export function setApiAuthToken(token: string): void {
  if (typeof window === 'undefined') return;
  try {
    if (token && token.trim()) {
      localStorage.setItem(STORAGE_KEY, token.trim());
    } else {
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(ALT_STORAGE_KEY);
      localStorage.removeItem(LEGACY_STORAGE_KEY);
    }
  } catch (err) {
    console.error('[APEX Auth] Failed saving token to localStorage:', err);
  }
}

/**
 * Generates HTTP request headers including authentication credentials.
 * Supplies both X-API-Key and Authorization Bearer headers for seamless alignment
 * with backend FastAPI `verify_api_key`.
 */
export function getAuthHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...extraHeaders,
  };

  const token = getApiAuthToken();
  if (token) {
    headers['X-API-Key'] = token;
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
}

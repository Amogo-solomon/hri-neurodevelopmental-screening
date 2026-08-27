/**
 * api.ts — single unified Axios client for ALL API calls.
 *
 * Every request automatically carries the JWT Bearer token.
 * On 401: transparently refreshes token once, then retries.
 * On refresh failure: clears tokens and redirects to /login.
 *
 * Import { api } for authenticated calls.
 * Import named functions for specific operations.
 */
import axios, { AxiosInstance } from 'axios';
import type { VideoUpload, AnalysisJob, AnalysisResult, HealthStatus, FrameSummariesResponse } from '@/types';
import type { AuthUser, TokenResponse } from '@/types/auth';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const WS_BASE  = process.env.NEXT_PUBLIC_WS_URL  || 'ws://localhost:8000';

// ─── Token storage ────────────────────────────────────────────────────────────
const KEYS = {
  ACCESS:  'hri_access_token',
  REFRESH: 'hri_refresh_token',
  USER:    'hri_user',
};

export const tokenStorage = {
  getAccess:  () => (typeof window !== 'undefined' ? localStorage.getItem(KEYS.ACCESS)  : null),
  getRefresh: () => (typeof window !== 'undefined' ? localStorage.getItem(KEYS.REFRESH) : null),
  getUser: (): AuthUser | null => {
    if (typeof window === 'undefined') return null;
    try { return JSON.parse(localStorage.getItem(KEYS.USER) || 'null'); } catch { return null; }
  },
  setTokens: (access: string, refresh: string) => {
    localStorage.setItem(KEYS.ACCESS,  access);
    localStorage.setItem(KEYS.REFRESH, refresh);
  },
  setUser:   (user: AuthUser) => localStorage.setItem(KEYS.USER, JSON.stringify(user)),
  clear: () => {
    localStorage.removeItem(KEYS.ACCESS);
    localStorage.removeItem(KEYS.REFRESH);
    localStorage.removeItem(KEYS.USER);
  },
};

// ─── Axios instance ───────────────────────────────────────────────────────────
export const api: AxiosInstance = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  timeout: 30_000,
});

// Attach Bearer token on every request
api.interceptors.request.use((config) => {
  const token = tokenStorage.getAccess();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-refresh on 401 — transparent to callers
let _refreshing = false;
let _queue: Array<{ resolve: (t: string) => void; reject: (e: unknown) => void }> = [];

function _flush(err: unknown, token: string | null) {
  _queue.forEach((p) => (err ? p.reject(err) : p.resolve(token!)));
  _queue = [];
}

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const orig = error.config;
    if (error.response?.status !== 401 || orig._retry) return Promise.reject(error);

    const refreshToken = tokenStorage.getRefresh();
    if (!refreshToken) {
      tokenStorage.clear();
      if (typeof window !== 'undefined') window.location.href = '/login';
      return Promise.reject(error);
    }

    if (_refreshing) {
      return new Promise((resolve, reject) => {
        _queue.push({ resolve, reject });
      }).then((t) => {
        orig.headers.Authorization = `Bearer ${t}`;
        return api(orig);
      });
    }

    orig._retry   = true;
    _refreshing   = true;

    try {
      const { data } = await axios.post<TokenResponse>(
        `${API_BASE}/api/v1/auth/refresh`,
        { refresh_token: refreshToken },
      );
      tokenStorage.setTokens(data.access_token, data.refresh_token);
      api.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
      _flush(null, data.access_token);
      orig.headers.Authorization = `Bearer ${data.access_token}`;
      return api(orig);
    } catch (refreshErr) {
      _flush(refreshErr, null);
      tokenStorage.clear();
      if (typeof window !== 'undefined') window.location.href = '/login';
      return Promise.reject(refreshErr);
    } finally {
      _refreshing = false;
    }
  },
);

// ─── Auth ─────────────────────────────────────────────────────────────────────
export async function apiLogin(email: string, password: string): Promise<AuthUser> {
  const { data: tokens } = await axios.post<TokenResponse>(
    `${API_BASE}/api/v1/auth/login`, { email, password },
  );
  tokenStorage.setTokens(tokens.access_token, tokens.refresh_token);
  const { data: user } = await axios.get<AuthUser>(`${API_BASE}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  });
  tokenStorage.setUser(user);
  return user;
}

export async function apiRegister(payload: {
  email: string; full_name: string; password: string;
  institution?: string; role?: string;
}): Promise<AuthUser> {
  const { data } = await axios.post<AuthUser>(`${API_BASE}/api/v1/auth/register`, payload);
  return data;
}

export async function apiLogout(): Promise<void> {
  const refresh = tokenStorage.getRefresh();
  if (refresh) {
    await api.post('/auth/logout', { refresh_token: refresh }).catch(() => {});
  }
  tokenStorage.clear();
}

export async function apiGetMe(): Promise<AuthUser> {
  const { data } = await api.get<AuthUser>('/auth/me');
  tokenStorage.setUser(data);
  return data;
}

export async function apiChangePassword(current: string, next: string): Promise<void> {
  await api.post('/auth/me/change-password', { current_password: current, new_password: next });
}

export async function apiRequestPasswordReset(email: string): Promise<{ message: string; reset_token?: string }> {
  const { data } = await axios.post(`${API_BASE}/api/v1/auth/password-reset/request`, { email });
  return data;
}

export async function apiConfirmPasswordReset(token: string, newPassword: string): Promise<void> {
  await axios.post(`${API_BASE}/api/v1/auth/password-reset/confirm`, {
    token, new_password: newPassword,
  });
}

// Admin
export async function apiAdminListUsers(): Promise<AuthUser[]> {
  const { data } = await api.get<AuthUser[]>('/auth/admin/users');
  return data;
}
export async function apiAdminUpdateUser(
  userId: string,
  updates: { role?: string; is_active?: boolean; is_verified?: boolean },
): Promise<AuthUser> {
  const { data } = await api.put<AuthUser>(`/auth/admin/users/${userId}`, updates);
  return data;
}
export async function apiAdminDeleteUser(userId: string): Promise<void> {
  await api.delete(`/auth/admin/users/${userId}`);
}
export async function apiAdminCreateUser(payload: {
  email: string; full_name: string; password: string; role: string; institution?: string;
}): Promise<AuthUser> {
  const { data } = await api.post<AuthUser>('/auth/admin/users', payload);
  return data;
}
export async function apiAuditLog(): Promise<unknown[]> {
  const { data } = await api.get('/auth/admin/audit-log');
  return data;
}

// ─── Video Upload ─────────────────────────────────────────────────────────────
export async function uploadVideo(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<VideoUpload> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<VideoUpload>('/upload/video', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (evt) => {
      if (evt.total && onProgress) onProgress(Math.round((evt.loaded / evt.total) * 100));
    },
    timeout: 0,
  });
  return data;
}

export async function listVideos(): Promise<VideoUpload[]> {
  const { data } = await api.get<VideoUpload[]>('/upload/videos');
  return data;
}

export async function deleteVideo(videoId: string): Promise<void> {
  await api.delete(`/upload/videos/${videoId}`);
}

// ─── Analysis ─────────────────────────────────────────────────────────────────
export async function startAnalysis(videoId: string, vlmModel?: string): Promise<AnalysisJob> {
  const { data } = await api.post<AnalysisJob>('/analysis/start', {
    video_id: videoId, vlm_model: vlmModel,
  });
  return data;
}

export async function getJob(jobId: string): Promise<AnalysisJob> {
  const { data } = await api.get<AnalysisJob>(`/analysis/jobs/${jobId}`);
  return data;
}

export async function listJobs(): Promise<AnalysisJob[]> {
  const { data } = await api.get<AnalysisJob[]>('/analysis/jobs');
  return data;
}

export async function getResult(jobId: string): Promise<AnalysisResult> {
  const { data } = await api.get<AnalysisResult>(`/analysis/results/${jobId}`);
  return data;
}

// ─── Health (no auth needed) ──────────────────────────────────────────────────
export async function getHealth(): Promise<HealthStatus> {
  const { data } = await axios.get<HealthStatus>(`${API_BASE}/api/v1/health`);
  return data;
}

// ─── WebSocket (token in URL protocol header workaround) ──────────────────────
export function createProgressWebSocket(
  jobId: string,
  onMessage: (data: unknown) => void,
  onError?: (err: Event) => void,
): WebSocket {
  const token = tokenStorage.getAccess();
  // Pass token as query param — backend validates it for WS connections
  const url = `${WS_BASE}/api/v1/analysis/ws/${jobId}${token ? `?token=${token}` : ''}`;
  const ws = new WebSocket(url);
  ws.onmessage = (evt) => {
    try { onMessage(JSON.parse(evt.data)); } catch { /* ping */ }
  };
  if (onError) ws.onerror = onError;
  return ws;
}

// ─── Frame Summaries (GET /analysis/results/{job_id}/frame-summaries) ────────
export async function getFrameSummaries(jobId: string): Promise<FrameSummariesResponse> {
  const { data } = await api.get<FrameSummariesResponse>(
    `/analysis/results/${jobId}/frame-summaries`,
  );
  return data;
}

// ─── Export Results (GET /analysis/results/{job_id}/export?format=json|xlsx) ─
export async function exportResults(
  jobId: string,
  format: 'json' | 'xlsx' = 'json',
): Promise<void> {
  const response = await api.get(`/analysis/results/${jobId}/export`, {
    params: { format },
    responseType: 'blob',
  });

  // Build filename from content-disposition header or fallback
  const disposition = response.headers['content-disposition'] ?? '';
  const match       = disposition.match(/filename=([^;]+)/);
  const filename    = match
    ? match[1].replace(/"/g, '')
    : `hri_results_${jobId.slice(0, 8)}.${format}`;

  // Trigger browser download
  const url  = URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href  = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

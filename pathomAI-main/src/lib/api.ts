export type VideoJobStatus =
  | 'queued'
  | 'extracting_audio'
  | 'transcribing'
  | 'analyzing'
  | 'completed'
  | 'failed';

export interface AuthUser {
  id: string;
  full_name: string;
  email: string;
  tenant_id: string;
  tenant_name: string;
}

export interface AuthResponse {
  access_token: string;
  user: AuthUser;
}

export interface SignUpPayload {
  full_name: string;
  email: string;
  password: string;
  tenant_name: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface ProfileUpdatePayload {
  full_name: string;
  email: string;
  tenant_name: string;
}

export interface PasswordChangePayload {
  current_password: string;
  new_password: string;
}

export interface VideoJob {
  id: string;
  user_id: string;
  original_filename: string;
  content_type: string | null;
  file_size_bytes: number;
  duration_seconds: number | null;
  language_hint: string;
  detected_language: string | null;
  status: VideoJobStatus;
  transcript?: string | null;
  summary: string | null;
  sentiment: string | null;
  action_items: string[];
  error_message: string | null;
  video_metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface UploadVideoResponse {
  id: string;
  status: VideoJobStatus;
  message: string;
}

const AUTH_TOKEN_KEY = 'pathomai_auth_token';

export function getStoredAuthToken(): string | null {
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function setStoredAuthToken(token: string): void {
  window.localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearStoredAuthToken(): void {
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
}

function buildHeaders(headers?: HeadersInit): Headers {
  const requestHeaders = new Headers(headers);
  const token = getStoredAuthToken();
  if (token) {
    requestHeaders.set('Authorization', `Bearer ${token}`);
  }
  return requestHeaders;
}

function getErrorMessage(errorPayload: any): string {
  const detail = errorPayload?.detail;
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item?.msg === 'string') {
          return item.msg;
        }
        return 'Validation error';
      })
      .join('; ');
  }
  if (typeof errorPayload?.message === 'string') {
    return errorPayload.message;
  }
  return 'Request failed';
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    throw new Error(getErrorMessage(errorPayload));
  }
  return response.json() as Promise<T>;
}

async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    ...init,
    headers: buildHeaders(init?.headers),
  });
  return parseJson<T>(response);
}

export async function signUp(payload: SignUpPayload): Promise<AuthResponse> {
  const response = await fetchJson<AuthResponse>('/api/auth/signup', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  setStoredAuthToken(response.access_token);
  return response;
}

export async function signIn(payload: LoginPayload): Promise<AuthResponse> {
  const response = await fetchJson<AuthResponse>('/api/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  setStoredAuthToken(response.access_token);
  return response;
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  return fetchJson<AuthUser>('/api/auth/me');
}

export async function updateProfile(payload: ProfileUpdatePayload): Promise<AuthUser> {
  return fetchJson<AuthUser>('/api/auth/me', {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

export async function changePassword(payload: PasswordChangePayload): Promise<void> {
  await fetchJson<{ message: string }>('/api/auth/change-password', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

export async function signOut(): Promise<void> {
  try {
    await fetchJson<{ message: string }>('/api/auth/logout', {
      method: 'POST',
    });
  } finally {
    clearStoredAuthToken();
  }
}

export async function fetchVideoJobs(): Promise<VideoJob[]> {
  return fetchJson<VideoJob[]>('/api/videos');
}

export async function fetchVideoJob(jobId: string): Promise<VideoJob> {
  return fetchJson<VideoJob>(`/api/videos/${jobId}`);
}

export async function fetchVideoSourceUrl(jobId: string): Promise<string> {
  const response = await fetch(`/api/videos/${jobId}/source`, {
    headers: buildHeaders(),
  });
  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    throw new Error(getErrorMessage(errorPayload));
  }
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

export async function retryVideoJob(jobId: string): Promise<UploadVideoResponse> {
  return fetchJson<UploadVideoResponse>(`/api/videos/${jobId}/retry`, {
    method: 'POST',
  });
}

export async function uploadVideo(
  file: File,
  languageHint: 'auto' | 'en' | 'tl' = 'auto',
): Promise<UploadVideoResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('language_hint', languageHint);

  const response = await fetch('/api/videos/upload', {
    method: 'POST',
    headers: buildHeaders(),
    body: formData,
  });

  return parseJson<UploadVideoResponse>(response);
}

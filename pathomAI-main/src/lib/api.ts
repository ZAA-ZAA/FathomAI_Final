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

export interface ApiKeyRecord {
  id: string;
  name: string;
  key_preview: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface ApiKeyCreateResponse {
  api_key: string;
  api_key_record: ApiKeyRecord;
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
  source_type: string;
  source_url: string | null;
  original_filename: string;
  content_type: string | null;
  file_size_bytes: number;
  duration_seconds: number | null;
  language_hint: string;
  detected_language: string | null;
  status: VideoJobStatus;
  transcript?: string | null;
  transcript_segments?: Array<{
    id?: number | null;
    start?: number | null;
    end?: number | null;
    text: string;
  }>;
  summary: string | null;
  custom_summary_prompt?: string | null;
  custom_summary_text?: string | null;
  custom_summary_updated_at?: string | null;
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
  notify_email?: string | null;
  export_pdf?: boolean;
  export_pdf_path?: string | null;
}

export interface UploadDeliveryOptions {
  notifyEmail?: string;
  exportPdf?: boolean;
  exportPdfPath?: string;
}

export interface VideoChatMessage {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  created_at?: string;
}

export interface VideoChatResponse {
  answer: string;
  suggested_questions: string[];
}

export interface VideoChatSuggestionResponse {
  suggested_questions: string[];
}

export interface CustomSummaryResponse {
  summary: string;
  action_items: string[];
  instruction: string;
  updated_at: string;
}

export interface VideoReportResponse {
  target: 'summary' | 'transcript';
  message: string;
  saved_path?: string | null;
  storage_path?: string | null;
  filename?: string | null;
  email_status?: string | null;
  emailed_to?: string | null;
  generated_at?: string | null;
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

export async function fetchApiKeys(): Promise<ApiKeyRecord[]> {
  return fetchJson<ApiKeyRecord[]>('/api/auth/api-keys');
}

export async function createApiKey(name: string): Promise<ApiKeyCreateResponse> {
  return fetchJson<ApiKeyCreateResponse>('/api/auth/api-keys', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name }),
  });
}

export async function revokeApiKey(apiKeyId: string): Promise<void> {
  await fetchJson<{ message: string }>(`/api/auth/api-keys/${apiKeyId}`, {
    method: 'DELETE',
  });
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
  deliveryOptions: UploadDeliveryOptions = {},
): Promise<UploadVideoResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('language_hint', languageHint);
  if (deliveryOptions.notifyEmail?.trim()) {
    formData.append('notify_email', deliveryOptions.notifyEmail.trim());
  }
  if (deliveryOptions.exportPdf) {
    formData.append('export_pdf', 'true');
  }
  if (deliveryOptions.exportPdfPath?.trim()) {
    formData.append('export_pdf_path', deliveryOptions.exportPdfPath.trim());
  }

  const response = await fetch('/api/videos/upload', {
    method: 'POST',
    headers: buildHeaders(),
    body: formData,
  });

  return parseJson<UploadVideoResponse>(response);
}

export async function uploadVideoUrl(
  videoUrl: string,
  languageHint: 'auto' | 'en' | 'tl' = 'auto',
  deliveryOptions: UploadDeliveryOptions = {},
): Promise<UploadVideoResponse> {
  return fetchJson<UploadVideoResponse>('/api/videos/transcribe', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      video_url: videoUrl,
      language_hint: languageHint,
      notify_email: deliveryOptions.notifyEmail?.trim() || undefined,
      export_pdf: Boolean(deliveryOptions.exportPdf),
      export_pdf_path: deliveryOptions.exportPdfPath?.trim() || undefined,
    }),
  });
}

export async function generateVideoReport(
  jobId: string,
  target: 'summary' | 'transcript',
  options?: { exportPdfPath?: string; showTimestamps?: boolean; useCustomSummary?: boolean },
): Promise<VideoReportResponse> {
  return fetchJson<VideoReportResponse>(`/api/videos/${jobId}/reports/${target}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      export_pdf_path: options?.exportPdfPath?.trim() || undefined,
      show_timestamps: options?.showTimestamps ?? true,
      use_custom_summary: options?.useCustomSummary,
    }),
  });
}

export async function fetchVideoReportBlob(jobId: string, target: 'summary' | 'transcript'): Promise<Blob> {
  const response = await fetch(`/api/videos/${jobId}/reports/${target}`, {
    headers: buildHeaders(),
  });
  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    throw new Error(getErrorMessage(errorPayload));
  }
  return response.blob();
}

export async function emailVideoReport(
  jobId: string,
  target: 'summary' | 'transcript',
  recipientEmail: string,
  options?: { exportPdfPath?: string; showTimestamps?: boolean; useCustomSummary?: boolean },
): Promise<VideoReportResponse> {
  return fetchJson<VideoReportResponse>(`/api/videos/${jobId}/reports/${target}/email`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      recipient_email: recipientEmail.trim(),
      export_pdf_path: options?.exportPdfPath?.trim() || undefined,
      show_timestamps: options?.showTimestamps ?? true,
      use_custom_summary: options?.useCustomSummary,
    }),
  });
}

export async function fetchVideoChatSuggestions(
  jobId: string,
  askedQuestions: string[] = [],
): Promise<VideoChatSuggestionResponse> {
  return fetchJson<VideoChatSuggestionResponse>(`/api/videos/${jobId}/chat/suggestions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      asked_questions: askedQuestions,
    }),
  });
}

export async function fetchVideoChatMessages(jobId: string): Promise<VideoChatMessage[]> {
  return fetchJson<VideoChatMessage[]>(`/api/videos/${jobId}/chat/messages`);
}

export async function regenerateVideoSummary(jobId: string, instruction: string): Promise<CustomSummaryResponse> {
  return fetchJson<CustomSummaryResponse>(`/api/videos/${jobId}/summary/regenerate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ instruction }),
  });
}

export async function sendVideoChatMessage(
  jobId: string,
  question: string,
  chatHistory: VideoChatMessage[],
  askedQuestions: string[],
): Promise<VideoChatResponse> {
  return fetchJson<VideoChatResponse>(`/api/videos/${jobId}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      question,
      chat_history: chatHistory,
      asked_questions: askedQuestions,
    }),
  });
}

export type VideoJobStatus =
  | 'queued'
  | 'extracting_audio'
  | 'transcribing'
  | 'analyzing'
  | 'completed'
  | 'failed';

export interface VideoJob {
  id: string;
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

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    const message = typeof errorPayload.detail === 'string' ? errorPayload.detail : 'Request failed';
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export async function fetchVideoJobs(): Promise<VideoJob[]> {
  const response = await fetch('/api/videos');
  return parseJson<VideoJob[]>(response);
}

export async function fetchVideoJob(jobId: string): Promise<VideoJob> {
  const response = await fetch(`/api/videos/${jobId}`);
  return parseJson<VideoJob>(response);
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
    body: formData,
  });

  return parseJson<UploadVideoResponse>(response);
}

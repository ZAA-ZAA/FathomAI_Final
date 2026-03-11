# API Tests

Direct API test guide for the current project using `curl.exe` on Windows PowerShell.

This file documents:
- the exact endpoints to test
- PowerShell-safe `curl.exe` commands
- what was verified on the current stack
- what currently fails when `OPENAI_API_KEY` is still the placeholder value in the root `.env`

## Test Environment

- Main app: `http://localhost:8000`
- Agent service: `http://localhost:8001`
- Tested on: March 10, 2026
- Current `.env` state during verification:
  - `OPENAI_API_KEY=replace-with-your-openai-key`
  - Because of that, Whisper and GPT-backed analysis fail with `invalid_api_key`

## Important PowerShell Note

Use `curl.exe`, not `curl`.

In Windows PowerShell, `curl` may map to `Invoke-WebRequest`, which behaves differently.

For JSON requests, the most reliable pattern is:
- write the JSON to a file
- send it with `--data-binary "@file.json"`

## Start The Stack

```powershell
cd C:\Users\zoen\Downloads\OJT\Projects\Week_9_FathomAI
docker compose up -d --build
```

## 1. Health Checks

```powershell
curl.exe -s http://localhost:8000/health
curl.exe -s http://localhost:8001/health
```

Expected:

```json
{"status":"ok"}
{"status":"ok"}
```

## 2. Sign Up

Create `signup.json`:

```powershell
$email = "apitest-$(Get-Date -Format 'yyyyMMddHHmmss')@example.com"
@{
  full_name = "API Test User"
  email = $email
  password = "Password123!"
  tenant_name = "API Test Workspace"
} | ConvertTo-Json -Compress | Set-Content signup.json -Encoding utf8
```

Call signup:

```powershell
curl.exe -s -X POST http://localhost:8000/api/auth/signup `
  -H "Content-Type: application/json" `
  --data-binary "@signup.json"
```

Expected response shape:

```json
{
  "access_token": "<token>",
  "user": {
    "id": "<uuid>",
    "full_name": "API Test User",
    "email": "apitest-...@example.com",
    "tenant_id": "<uuid>",
    "tenant_name": "API Test Workspace"
  }
}
```

What this proves:
- signup is live
- workspace name is stored and returned
- the backend is creating a tenant and user

Relevant code:
- [auth.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/api/routes/auth.py:32)
- [models.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/models.py:26)

## 3. Login

Create `login.json`:

```powershell
@{
  email = $email
  password = "Password123!"
} | ConvertTo-Json -Compress | Set-Content login.json -Encoding utf8
```

Call login:

```powershell
curl.exe -s -X POST http://localhost:8000/api/auth/login `
  -H "Content-Type: application/json" `
  --data-binary "@login.json"
```

Expected response:
- another `access_token`
- the same `tenant_id` and `tenant_name`

Relevant code:
- [auth.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/api/routes/auth.py:61)

## 4. Get Current User

After login, copy the returned token into `$token`:

```powershell
$token = "<paste-access-token>"
curl.exe -s http://localhost:8000/api/auth/me `
  -H "Authorization: Bearer $token"
```

Expected:

```json
{
  "id": "<uuid>",
  "full_name": "API Test User",
  "email": "apitest-...@example.com",
  "tenant_id": "<uuid>",
  "tenant_name": "API Test Workspace"
}
```

What this proves:
- bearer auth works
- the session resolves back to the correct tenant

Relevant code:
- [auth.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/auth.py:98)

## 5. List Video Jobs

```powershell
curl.exe -s http://localhost:8000/api/videos `
  -H "Authorization: Bearer $token"
```

Expected for a new account:

```json
[]
```

What this proves:
- the endpoint is protected
- video jobs are scoped to the logged-in tenant

Relevant code:
- [videos.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/api/routes/videos.py:24)

## 6. Create A Tiny Test Video

If you need a local test file, generate one with Docker:

```powershell
docker run --rm -v "${PWD}:/work" -w /work jrottenberg/ffmpeg:7.1-alpine `
  -y `
  -f lavfi -i color=c=black:s=320x240:d=1 `
  -f lavfi -i sine=frequency=1000:duration=1 `
  -c:v libx264 -c:a aac -shortest api-test-video.mp4
```

Important:
- when uploading from PowerShell with `curl.exe`, explicitly send the MIME type
- otherwise the backend may reject it as non-video

## 7. Upload A Video

```powershell
curl.exe -s -X POST http://localhost:8000/api/videos/upload `
  -H "Authorization: Bearer $token" `
  -F "file=@api-test-video.mp4;type=video/mp4" `
  -F "language_hint=auto"
```

Expected response:

```json
{
  "id": "<job-id>",
  "status": "queued",
  "message": "Video upload accepted for processing"
}
```

What this proves:
- upload works
- multipart parsing works
- the job row is created

Relevant code:
- [videos.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/api/routes/videos.py:75)

## 8. Import A Video From URL

This supports YouTube and other sources that `yt-dlp` can download, plus many direct video URLs.

Create `import-url.json`:

```powershell
@{
  video_url = "https://samplelib.com/lib/preview/mp4/sample-5s.mp4"
  language_hint = "auto"
} | ConvertTo-Json -Compress | Set-Content import-url.json -Encoding utf8
```

Call the import route:

```powershell
curl.exe -s -X POST http://localhost:8000/api/videos/import `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  --data-binary "@import-url.json"
```

Expected response:

```json
{
  "id": "<job-id>",
  "status": "queued",
  "message": "Video URL accepted for processing"
}
```

Observed on the current stack:
- the job is created immediately
- the video download happens in the background pipeline
- `source_type` becomes `"url"`
- `source_url` stores the original link

Relevant code:
- [videos.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/api/routes/videos.py:131)
- [video_pipeline.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/video_pipeline.py:18)
- [video_ingest.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/video_ingest.py:11)

## 9. Poll The Job

```powershell
$jobId = "<paste-job-id>"
curl.exe -s http://localhost:8000/api/videos/$jobId `
  -H "Authorization: Bearer $token"
```

Observed result with the current placeholder API key:

```json
{
  "id": "<job-id>",
  "status": "failed",
  "error_message": "Whisper transcription failed: Error code: 401 ... invalid_api_key ...",
  "summary": null,
  "sentiment": null,
  "action_items": [],
  "transcript": null
}
```

What this proves:
- the backend pipeline is running
- FFmpeg extraction completed
- the failure is happening at the external Whisper API call

Relevant code:
- [video_pipeline.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/video_pipeline.py:17)
- [media.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/media.py:39)
- [transcription.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/transcription.py:17)

## 10. Retry A Failed Job

```powershell
curl.exe -s -X POST http://localhost:8000/api/videos/$jobId/retry `
  -H "Authorization: Bearer $token"
```

Expected response:

```json
{
  "id": "<job-id>",
  "status": "queued",
  "message": "Retry started"
}
```

Observed after retry, with the placeholder key still in `.env`:
- the job fails again for the same `invalid_api_key` reason

Relevant code:
- [videos.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/api/routes/videos.py:140)

## 11. Direct Agent Service Test

Create `agent-analysis.json`:

```powershell
@{
  transcript = "Mag follow up tayo bukas. Please send the revised deck."
  video_title = "api-test-video.mp4"
  source_language = "tl"
} | ConvertTo-Json -Compress | Set-Content agent-analysis.json -Encoding utf8
```

Call the internal agent endpoint directly:

```powershell
curl.exe -s -X POST http://localhost:8001/internal/transcript-analysis `
  -H "Content-Type: application/json" `
  --data-binary "@agent-analysis.json"
```

Observed result with the current placeholder API key:

```json
{
  "detail": "Transcript analysis failed: Error code: 401 ... invalid_api_key ..."
}
```

What this proves:
- the internal agent route exists and is reachable
- the current blocker is the OpenAI API key, not service-to-service networking

Relevant code:
- [transcript_analysis.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/app/routers/transcript_analysis.py:14)
- [transcript_analysis.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/app/services/transcript_analysis.py:16)

## Verified Behavior On The Current Stack

These checks were run successfully:
- `GET /health` on port `8000`
- `GET /health` on port `8001`
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/videos`
- `POST /api/videos/upload`
- `POST /api/videos/import`
- `GET /api/videos/{jobId}`
- `POST /api/videos/{jobId}/retry`
- `POST /internal/transcript-analysis`

Current outcome with the root `.env` as-is:
- auth works
- tenant scoping works
- upload works
- retry works
- Whisper and transcript analysis fail because `OPENAI_API_KEY` is still the placeholder value

## When You Add A Real OpenAI Key

Update:

```env
OPENAI_API_KEY=your-real-openai-key
```

Then rebuild and restart:

```powershell
docker compose up -d --build
```

Expected difference after that:
- uploaded jobs should move from `queued` -> `extracting_audio` -> `transcribing` -> `analyzing` -> `completed`
- `transcript`, `summary`, `sentiment`, and `action_items` should be populated
- the direct agent endpoint should return a normal JSON analysis response

## Cleanup

If you created local JSON files or the sample video during testing:

```powershell
cmd /c del /q signup.json login.json agent-analysis.json api-test-video.mp4
```

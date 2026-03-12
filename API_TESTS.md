# API Tests

Direct `curl.exe` guide for the current stack.

Tested against:
- Main app: `http://localhost:8000`
- Agent service: `http://localhost:8001`
- Date: March 12, 2026

Use `curl.exe`, not PowerShell's `curl` alias.

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

```powershell
$email = "apitest-$(Get-Date -Format 'yyyyMMddHHmmss')@example.com"
@{
  full_name = "API Test User"
  email = $email
  password = "Password123!"
  tenant_name = "API Test Workspace"
} | ConvertTo-Json -Compress | Set-Content signup.json -Encoding utf8

curl.exe -s -X POST http://localhost:8000/api/auth/signup `
  -H "Content-Type: application/json" `
  --data-binary "@signup.json"
```

Save the returned `access_token` into `$token`.

## 3. Login

```powershell
@{
  email = $email
  password = "Password123!"
} | ConvertTo-Json -Compress | Set-Content login.json -Encoding utf8

curl.exe -s -X POST http://localhost:8000/api/auth/login `
  -H "Content-Type: application/json" `
  --data-binary "@login.json"
```

## 4. Current User

```powershell
$token = "<paste-access-token>"
curl.exe -s http://localhost:8000/api/auth/me `
  -H "Authorization: Bearer $token"
```

## 5. Create An API Key

```powershell
@{
  name = "CLI Key"
} | ConvertTo-Json -Compress | Set-Content api-key-create.json -Encoding utf8

curl.exe -s -X POST http://localhost:8000/api/auth/api-keys `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  --data-binary "@api-key-create.json"
```

The raw `api_key` is shown only once. Save it.

```powershell
$apiKey = "<paste-api-key>"
```

## 6. List API Keys

```powershell
curl.exe -s http://localhost:8000/api/auth/api-keys `
  -H "Authorization: Bearer $token"
```

## 7. List Video History With API Key

```powershell
curl.exe -s http://localhost:8000/api/videos `
  -H "X-API-Key: $apiKey"
```

This is the same tenant-scoped history the UI will show after login.

## 8. Create A Tiny Test Video

```powershell
docker run --rm -v "${PWD}:/work" -w /work jrottenberg/ffmpeg:7.1-alpine `
  -y `
  -f lavfi -i color=c=black:s=320x240:d=1 `
  -f lavfi -i sine=frequency=1000:duration=1 `
  -c:v libx264 -c:a aac -shortest api-test-video.mp4
```

## 9. Upload A Video With API Key

```powershell
curl.exe -s -X POST http://localhost:8000/api/videos/upload `
  -H "X-API-Key: $apiKey" `
  -F "file=@api-test-video.mp4;type=video/mp4" `
  -F "language_hint=auto"
```

Expected response shape:

```json
{
  "id": "<job-id>",
  "status": "queued",
  "message": "Video upload accepted for processing"
}
```

## 10. Import A URL With API Key

Direct MP4 example:

```powershell
@{
  video_url = "https://samplelib.com/lib/preview/mp4/sample-5s.mp4"
  language_hint = "auto"
} | ConvertTo-Json -Compress | Set-Content import-url.json -Encoding utf8

curl.exe -s -X POST http://localhost:8000/api/videos/import `
  -H "X-API-Key: $apiKey" `
  -H "Content-Type: application/json" `
  --data-binary "@import-url.json"
```

YouTube example:

```powershell
@{
  video_url = "https://www.youtube.com/watch?v=3WrZMzqpFTc"
  language_hint = "auto"
} | ConvertTo-Json -Compress | Set-Content import-youtube.json -Encoding utf8

curl.exe -s -X POST http://localhost:8000/api/videos/import `
  -H "X-API-Key: $apiKey" `
  -H "Content-Type: application/json" `
  --data-binary "@import-youtube.json"
```

## 11. Import A Public Google Drive Link

You do not need an OAuth token if the shared file is already public.

Rules:
- must be a single file link
- must be public to "Anyone with the link"
- folder links are rejected
- private or broken links will fail during processing with a clear `error_message`

Example payload shape:

```powershell
@{
  video_url = "https://drive.google.com/file/d/<file-id>/view?usp=sharing"
  language_hint = "auto"
} | ConvertTo-Json -Compress | Set-Content import-gdrive.json -Encoding utf8

curl.exe -s -X POST http://localhost:8000/api/videos/import `
  -H "X-API-Key: $apiKey" `
  -H "Content-Type: application/json" `
  --data-binary "@import-gdrive.json"
```

Observed invalid-link behavior on the current stack:
- request is accepted as a queued job
- background processing marks the job as `failed`
- `error_message` explains that the Drive file is not public, invalid, expired, or otherwise inaccessible

## 12. Poll Job Status

```powershell
$jobId = "<paste-job-id>"
curl.exe -s http://localhost:8000/api/videos/$jobId `
  -H "X-API-Key: $apiKey"
```

Typical completed lifecycle:
- `queued`
- `extracting_audio`
- `transcribing`
- `analyzing`
- `completed`

## 13. List Full History Again

```powershell
curl.exe -s http://localhost:8000/api/videos `
  -H "X-API-Key: $apiKey"
```

## 14. Retry A Failed Job

```powershell
curl.exe -s -X POST http://localhost:8000/api/videos/$jobId/retry `
  -H "X-API-Key: $apiKey"
```

Behavior notes:
- failed uploaded files retry from the stored local source file
- failed URL imports retry from the original `source_url`
- failed broken/private Google Drive links will queue again and then fail again until the link is fixed

## 15. Generate A Focused Summary

This is the new "regenerate with custom command" behavior from the AI Summary screen.

Example: summarize only one topic from the video.

```powershell
@{
  instruction = "Summarize only the key points about Friday attendance problems and suggested interventions."
} | ConvertTo-Json -Compress | Set-Content focused-summary.json -Encoding utf8

curl.exe -s -X POST http://localhost:8000/api/videos/$jobId/summary/regenerate `
  -H "X-API-Key: $apiKey" `
  -H "Content-Type: application/json" `
  --data-binary "@focused-summary.json"
```

Expected response shape:

```json
{
  "summary": "...",
  "instruction": "Summarize only the key points about Friday attendance problems and suggested interventions.",
  "updated_at": "2026-03-12T..."
}
```

## 16. Get Chat History For A Video

```powershell
curl.exe -s http://localhost:8000/api/videos/$jobId/chat/messages `
  -H "X-API-Key: $apiKey"
```

## 17. Get Suggested Questions

```powershell
@{
  asked_questions = @(
    "What decisions were made?"
  )
} | ConvertTo-Json -Compress | Set-Content chat-suggestions.json -Encoding utf8

curl.exe -s -X POST http://localhost:8000/api/videos/$jobId/chat/suggestions `
  -H "X-API-Key: $apiKey" `
  -H "Content-Type: application/json" `
  --data-binary "@chat-suggestions.json"
```

## 18. Ask The Video Chat Agent

```powershell
@{
  question = "What decisions were made in this meeting?"
  chat_history = @()
  asked_questions = @(
    "What decisions were made in this meeting?"
  )
} | ConvertTo-Json -Compress -Depth 5 | Set-Content chat-question.json -Encoding utf8

curl.exe -s -X POST http://localhost:8000/api/videos/$jobId/chat `
  -H "X-API-Key: $apiKey" `
  -H "Content-Type: application/json" `
  --data-binary "@chat-question.json"
```

Then check saved history again:

```powershell
curl.exe -s http://localhost:8000/api/videos/$jobId/chat/messages `
  -H "X-API-Key: $apiKey"
```

## 19. Stream The Stored Source Video

```powershell
curl.exe -OJ http://localhost:8000/api/videos/$jobId/source `
  -H "X-API-Key: $apiKey"
```

Note:
- this works only if the local source file still exists
- if container storage was reset, transcript data may remain in PostgreSQL while the original source file is gone

## 20. Revoke An API Key

```powershell
$apiKeyId = "<paste-api-key-record-id>"
curl.exe -s -X DELETE http://localhost:8000/api/auth/api-keys/$apiKeyId `
  -H "Authorization: Bearer $token"
```

## Verified On The Current Stack

Verified in this session:
- `GET /health` on `8000`
- `GET /health` on `8001`
- `POST /api/auth/login`
- `POST /api/auth/api-keys`
- `GET /api/videos` using `X-API-Key`
- `POST /api/videos/import` using `X-API-Key`
- `POST /api/videos/{job_id}/summary/regenerate`
- `POST /api/videos/{job_id}/retry` for a failed Google Drive import
- invalid Google Drive retry now re-queues and fails with the real Drive access error instead of a local-file-missing error

## Cleanup

```powershell
cmd /c del /q signup.json login.json api-key-create.json import-url.json import-youtube.json import-gdrive.json focused-summary.json chat-suggestions.json chat-question.json api-test-video.mp4
```

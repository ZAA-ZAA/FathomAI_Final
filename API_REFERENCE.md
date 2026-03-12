# API Reference

All user-facing routes are served by `pathomAI-main` on `http://localhost:8000`.

Auth methods:
- Bearer token: `Authorization: Bearer <token>`
- API key: `X-API-Key: <api-key>`

API keys are tenant-scoped through the user that created them. API requests and UI requests go through the same job pipeline and same database.

## Health

- `GET /health`
  - Main backend health check

## Auth

- `POST /api/auth/signup`
  - Create tenant plus first user
- `POST /api/auth/login`
  - Login and receive bearer token
- `GET /api/auth/me`
  - Get current authenticated user
- `PATCH /api/auth/me`
  - Update full name, email, and workspace name
- `POST /api/auth/change-password`
  - Change password
- `POST /api/auth/logout`
  - Delete bearer session if a bearer token was used

## API Keys

- `GET /api/auth/api-keys`
  - List active API keys for the current user
- `POST /api/auth/api-keys`
  - Generate a new API key
- `DELETE /api/auth/api-keys/{api_key_id}`
  - Revoke an API key

## Video Jobs

- `GET /api/videos`
  - List the current tenant's jobs
- `GET /api/videos/{job_id}`
  - Get full job detail
- `GET /api/videos/{job_id}/source`
  - Stream the locally stored source video if present
- `POST /api/videos/upload`
  - Upload a local video file
- `POST /api/videos/import`
  - Import from a supported URL
- `POST /api/videos/{job_id}/retry`
  - Retry a failed job

## Focused Summary

- `POST /api/videos/{job_id}/summary/regenerate`
  - Generate a transcript-grounded summary for a specific instruction
  - Example use: "Only summarize the ingredients and steps for the second dish"

## Video Chat

- `GET /api/videos/{job_id}/chat/messages`
  - Get saved chat history for the video
- `POST /api/videos/{job_id}/chat/suggestions`
  - Get related suggested questions
- `POST /api/videos/{job_id}/chat`
  - Ask a question grounded in the selected video only

## Internal Agent Service

These are called by the main backend, not by the frontend.

Base URL in Docker: `http://ai-agents:8000`
Base URL locally: `http://localhost:8001`

- `POST /internal/transcript-analysis`
- `POST /internal/custom-summary`
- `POST /internal/transcript-chat/suggestions`
- `POST /internal/transcript-chat`

Key code:
- Main backend routes: [videos.py](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/api/routes/videos.py)
- Main backend auth routes: [auth.py](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/api/routes/auth.py)
- Agent service entrypoint: [main.py](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/main.py)

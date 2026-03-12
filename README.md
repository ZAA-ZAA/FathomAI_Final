# Week 9 FathomAI

Video intelligence platform for transcription, analysis, and video-specific AI chat.

## Repositories

- `pathomAI-main`: React frontend plus FastAPI main backend
- `ai-agents-lite-main`: separate FastAPI agent service used for transcript analysis and transcript chat

## What The App Does

- Upload a local video file or import a video URL
- Supports YouTube, many `yt-dlp` sources, direct video URLs, and public Google Drive file links
- Extracts audio with FFmpeg
- Transcribes with OpenAI `whisper-1`
- Analyzes the transcript with OpenAI `gpt-4o`
- Stores jobs, transcript, timestamps, summary, focused summary, chat history, sentiment, and action items in PostgreSQL
- Lets users ask follow-up questions about a specific completed video
- Supports either UI login or API-key access to the same tenant-scoped workflow

## High-Level Flow

1. Video is uploaded or imported into `pathomAI-main`
2. Main backend stores the job and local source file
3. FFmpeg extracts WAV audio
4. OpenAI `whisper-1` returns transcript plus timestamps
5. Main backend calls `ai-agents-lite-main`
6. Agent service uses `gpt-4o` for summary, focused summary, action items, sentiment, and video chat answers
7. Results are stored in PostgreSQL and shown in the UI or returned through the API

## Important Files

- Main workflow: [video_pipeline.py](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/video_pipeline.py)
- Upload and API routes: [videos.py](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/api/routes/videos.py)
- Auth and API keys: [auth.py](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/api/routes/auth.py)
- OpenAI Whisper transcription: [transcription.py](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/transcription.py)
- URL and Google Drive import: [video_ingest.py](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/video_ingest.py)
- Agent service transcript analysis: [transcript_analysis.py](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/app/services/transcript_analysis.py)
- Agent service focused summary: [custom_summary.py](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/app/services/custom_summary.py)
- Agent service transcript chat: [transcript_chat.py](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/app/services/transcript_chat.py)
- Frontend UI: [App.tsx](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/src/App.tsx)

## Required Environment Variables

Root file: `[.env](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/.env)`

```env
OPENAI_API_KEY=your-openai-key
DATABASE_URL=postgresql+psycopg://pathomai:pathomai@db:5432/pathomai
AGENT_SERVICE_URL=http://ai-agents:8000
```

Notes:
- `OPENAI_API_KEY` is required for both Whisper and `gpt-4o`
- `DATABASE_URL` is used by the main backend
- `AGENT_SERVICE_URL` is how `pathomAI-main` reaches `ai-agents-lite-main`

## Run With Docker

```powershell
cd C:\Users\zoen\Downloads\OJT\Projects\Week_9_FathomAI
docker compose up -d --build
```

Open:
- Main app: `http://localhost:8000`
- Agent docs: `http://localhost:8001/docs`

If you changed the schema and want a clean reset:

```powershell
docker compose down -v
docker compose up -d --build
```

## Run Locally Without Docker

Start PostgreSQL:

```powershell
cd C:\Users\zoen\Downloads\OJT\Projects\Week_9_FathomAI
docker compose up -d db
```

Set env vars:

```powershell
$env:OPENAI_API_KEY = "your-openai-key"
$env:DATABASE_URL = "postgresql+psycopg://pathomai:pathomai@localhost:5432/pathomai"
$env:AGENT_SERVICE_URL = "http://localhost:8001"
```

Run agent service:

```powershell
cd C:\Users\zoen\Downloads\OJT\Projects\Week_9_FathomAI\ai-agents-lite-main
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

Run main backend:

```powershell
cd C:\Users\zoen\Downloads\OJT\Projects\Week_9_FathomAI\pathomAI-main
pip install -r backend\requirements.txt
uvicorn main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
```

Run frontend dev server:

```powershell
cd C:\Users\zoen\Downloads\OJT\Projects\Week_9_FathomAI\pathomAI-main
npm install
npm run dev
```

Local prerequisite:
- `ffmpeg` must be installed and available on `PATH`

## API Access

You can use the app in two ways:
- UI login with email and password
- API key using the `X-API-Key` header

Important:
- API keys are generated after a normal login
- API-key requests use the same tenant and same workflow as the UI
- If you import videos through the API, they will appear in the same history when that user signs into the UI
- There is no separate bypass pipeline for API usage

## Google Drive Import Notes

Google Drive imports work only for a single public file link.

Supported:
- public file-share links such as `https://drive.google.com/file/d/<file-id>/view?...`

Not supported:
- private files
- expired links
- folder links

You do not need an OAuth token for the current implementation if the file is already public.

## Storage Notes

Videos are stored locally by the main backend.

- Local non-Docker run: `pathomAI-main/backend/storage/uploads`
- Docker run: inside the `main-app` container under `/app/backend/storage/uploads`

## Key Model Configuration

- Whisper transcription model: [transcription.py](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/transcription.py)
- Agent default model: [config.py](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/app/config.py)

Current defaults:
- transcription: `whisper-1`
- analysis/chat/focused summary: `gpt-4o`

## Related Docs

- Detailed curl tests: [API_TESTS.md](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/API_TESTS.md)
- Endpoint map: [API_REFERENCE.md](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/API_REFERENCE.md)
- Project terms and concepts: [PROJECT_TERMS.md](C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/PROJECT_TERMS.md)

# FathomAI Project Guide

This README explains the full project in simple terms:

- what each folder does
- where the AI agent lives
- what model is used for transcription
- what model is used for summary/action items/sentiment
- where the workflow is in code
- how `pathomAI-main` talks to `ai-agents-lite-main`
- what `.env` values are required
- how to run and test everything

---

## 1. Project Structure

This root project has **2 separate applications**:

### `pathomAI-main`
This is the **main application**.

It contains:
- the React frontend
- the FastAPI backend that accepts video uploads
- the PostgreSQL integration
- the ffmpeg audio extraction step
- the OpenAI Whisper transcription step
- the HTTP call to the separate AI agent service

### `ai-agents-lite-main`
This is the **separate AI agent service**.

It contains:
- the internal API that receives a transcript
- the `gpt-4o` call for:
  - summary
  - action items
  - sentiment

So the simple answer is:

- **video upload + transcription** happens in `pathomAI-main`
- **summary/action items/sentiment agent** lives in `ai-agents-lite-main`

---

## 2. Very Short Answer To Your Main Questions

### Is `ai-agents-lite-main` where the AI agents are created?
**Yes, for the transcript analysis part.**

For this video platform, the analysis agent is implemented there.
It is the service that turns a transcript into:
- summary
- action items
- sentiment

File:
- `ai-agents-lite-main/app/services/transcript_analysis.py`

### Is `pathomAI-main` separate from `ai-agents-lite-main`?
**Yes.**

They are separate projects/services.
`pathomAI-main` calls `ai-agents-lite-main` through HTTP.

Connection setting:
- `AGENT_SERVICE_URL`

Root `.env` file:
- `.env`

### Does `pathomAI-main` need `.env` to connect to the AI agents service?
**Yes.**

It uses:
- `AGENT_SERVICE_URL=http://ai-agents:8000` in Docker
- or `AGENT_SERVICE_URL=http://localhost:8001` when running locally without Docker

### Is the workflow created in `pathomAI-main`?
**The video-processing workflow is mainly orchestrated in `pathomAI-main`.**

The main orchestration file is:
- `pathomAI-main/backend/app/services/video_pipeline.py`

That file runs the steps in order.

### What is used to transcribe?
**OpenAI Whisper API (`whisper-1`)**

File:
- `pathomAI-main/backend/app/services/transcription.py`

### Can you change the model?
**Yes.**

- Whisper model is currently hardcoded as `whisper-1`
- Summary model is currently `gpt-4o`

Files:
- transcription model: `pathomAI-main/backend/app/services/transcription.py`
- summary model default: `ai-agents-lite-main/app/config.py`

---

## 3. End-To-End Flow

Your understanding is almost correct.

The actual implemented flow is:

1. User uploads a video in the frontend.
2. `pathomAI-main` backend receives the video.
3. The backend stores a database row for the job.
4. The backend starts a background processing task.
5. The backend extracts audio from the video using `ffmpeg`.
6. The backend sends the extracted audio to **OpenAI Whisper API**.
7. Whisper returns the transcript.
8. `pathomAI-main` sends the transcript to `ai-agents-lite-main`.
9. `ai-agents-lite-main` uses **`gpt-4o`** to generate:
   - summary
   - action items
   - sentiment
10. The result is returned to `pathomAI-main`.
11. `pathomAI-main` stores the final analysis in PostgreSQL.
12. The frontend keeps polling until the job is finished.
13. The frontend shows the transcript, summary, action items, and sentiment.

### Important correction
The current implementation does **not** convert to MP3.

It converts the video audio to **WAV**:
- mono
- 16 kHz
- PCM

That happens here:
- `pathomAI-main/backend/app/services/media.py`

So the real flow is:

`video -> WAV audio -> Whisper -> transcript -> AI agent -> summary/action items/sentiment -> save to DB -> frontend displays result`

---

## 4. Where The Workflow Is In Code

If you want the single best file to understand the main backend workflow, read this first:

- `pathomAI-main/backend/app/services/video_pipeline.py`

That file is the backend orchestration flow.

### What it does
That file:
- updates job status
- calls audio extraction
- calls Whisper transcription
- calls the AI agent service
- saves final results
- marks the job as completed or failed

### Supporting files used by that workflow

#### Upload entrypoint
- `pathomAI-main/backend/app/api/routes/videos.py`

This file:
- accepts the uploaded video
- creates the DB row
- saves the file
- starts the background pipeline

#### Audio extraction
- `pathomAI-main/backend/app/services/media.py`

This file:
- probes metadata
- extracts audio from the uploaded video using `ffmpeg-python`

#### Whisper transcription
- `pathomAI-main/backend/app/services/transcription.py`

This file:
- calls OpenAI Whisper API
- uses model `whisper-1`
- supports `tl`, `en`, or auto-detect behavior

#### Call to AI agent service
- `pathomAI-main/backend/app/services/agent_client.py`

This file:
- uses `httpx`
- sends transcript data to `ai-agents-lite-main`

#### Database model
- `pathomAI-main/backend/app/models.py`

This file defines the `video_jobs` table.

---

## 5. Where The AI Agent Lives

For this project, the transcript analysis agent is effectively here:

- `ai-agents-lite-main/app/services/transcript_analysis.py`

If you want to give it a friendly name, you can think of it as the:

**Transcript Analysis Agent**

It is responsible for:
- reading the transcript
- generating the summary
- extracting action items
- labeling sentiment

### Route that exposes the agent internally
- `ai-agents-lite-main/app/routers/transcript_analysis.py`

Endpoint:
- `POST /internal/transcript-analysis`

### Schema for request/response
- `ai-agents-lite-main/app/schemas/transcript_analysis.py`

### Model configuration
- `ai-agents-lite-main/app/config.py`

This file currently sets:
- default model: `gpt-4o`

---

## 6. What Models Are Used

### Transcription model
Used for speech-to-text:
- **`whisper-1`**

Location:
- `pathomAI-main/backend/app/services/transcription.py`

### Summary / action items / sentiment model
Used inside the separate AI agent service:
- **`gpt-4o`**

Location:
- `ai-agents-lite-main/app/config.py`
- `ai-agents-lite-main/app/services/transcript_analysis.py`

---

## 7. Can You Change The Models?

Yes.

### Change Whisper model
File:
- `pathomAI-main/backend/app/services/transcription.py`

Current code uses:
- `model="whisper-1"`

If OpenAI provides a different transcription model later, you can change it there.

### Change summary model
File:
- `ai-agents-lite-main/app/config.py`

Current default:
- `TRANSCRIPT_ANALYSIS_MODEL` env var, defaulting to `gpt-4o`

So you can change it by:
- editing the default in code
- or setting a new env var value

---

## 8. Does It Need API Keys?

Yes.

### OpenAI API key
Both services need access to OpenAI features.

Required env var:
- `OPENAI_API_KEY`

Used by:
- `pathomAI-main` for Whisper transcription
- `ai-agents-lite-main` for `gpt-4o` transcript analysis

### Does `pathomAI-main` need a separate API key just to talk to `ai-agents-lite-main`?
**No, not currently.**

Right now, communication between the 2 services is internal HTTP.
There is no separate service-to-service auth token implemented.

What `pathomAI-main` needs is:
- `AGENT_SERVICE_URL`

That tells it where the AI agent service is located.

### Verification note
During validation, the internal agent endpoint correctly reached OpenAI but returned `401 invalid_api_key` when the placeholder key was used.

That means:
- the code path works
- the service can reach OpenAI
- you must replace the placeholder with a real key in `.env`

---

## 9. Root `.env` Explained

Root file:
- `.env`

Important values:

### `OPENAI_API_KEY`
Used for:
- Whisper transcription
- `gpt-4o` transcript analysis

### `DATABASE_URL`
Used by:
- `pathomAI-main` backend

This points to PostgreSQL.

### `AGENT_SERVICE_URL`
Used by:
- `pathomAI-main`

This tells the main backend where the separate agent service is.

### Docker value
When using Docker Compose:
- `AGENT_SERVICE_URL=http://ai-agents:8000`

### Local value
When running services manually on your machine:
- `AGENT_SERVICE_URL=http://localhost:8001`

---

## 10. Important Files Map

### Main app (`pathomAI-main`)

#### Frontend
- `pathomAI-main/src/App.tsx`
  - upload UI
  - history UI
  - polling UI
  - review UI

- `pathomAI-main/src/lib/api.ts`
  - frontend API helper calls

#### Backend entrypoint
- `pathomAI-main/backend/app/main.py`
  - FastAPI app setup
  - routes registration
  - health check
  - static frontend serving in Docker

#### Upload API
- `pathomAI-main/backend/app/api/routes/videos.py`
  - `POST /api/videos/upload`
  - `GET /api/videos`
  - `GET /api/videos/{job_id}`

#### DB
- `pathomAI-main/backend/app/models.py`
  - `video_jobs` table

- `pathomAI-main/backend/app/db.py`
  - SQLAlchemy engine/session

#### Workflow orchestration
- `pathomAI-main/backend/app/services/video_pipeline.py`

#### Audio extraction
- `pathomAI-main/backend/app/services/media.py`

#### Whisper transcription
- `pathomAI-main/backend/app/services/transcription.py`

#### Call separate AI service
- `pathomAI-main/backend/app/services/agent_client.py`

---

### AI agent service (`ai-agents-lite-main`)

#### Agent config
- `ai-agents-lite-main/app/config.py`

#### Agent request/response schema
- `ai-agents-lite-main/app/schemas/transcript_analysis.py`

#### Agent logic
- `ai-agents-lite-main/app/services/transcript_analysis.py`

#### Internal API route
- `ai-agents-lite-main/app/routers/transcript_analysis.py`

#### FastAPI entrypoint
- `ai-agents-lite-main/main.py`

---

## 11. Important Clarification About `workflow/` Folder

You asked where the workflow is created.
This is important because there are **2 different things**:

### A. The actual video-intelligence workflow
This is the one used for your real feature.

It is here:
- `pathomAI-main/backend/app/services/video_pipeline.py`

This is the workflow you should follow for the video platform.

### B. The old `workflow/` folder inside `ai-agents-lite-main`
There is also an existing folder:
- `ai-agents-lite-main/workflow/`

That came from the existing starter/service code.
It is tied to the old math workflow endpoint:
- `/workflow/math`

That is **not** the video intelligence workflow.

So if your question is:
> where is the workflow for video upload -> transcribe -> summarize?

The answer is:
- `pathomAI-main/backend/app/services/video_pipeline.py`

---

## 12. Database Data Stored

The backend stores:
- video file names
- content type
- file size
- duration
- language hint
- detected language
- transcript
- summary
- action items
- sentiment
- job status
- metadata JSON
- error message if failed
- timestamps

Location:
- `pathomAI-main/backend/app/models.py`

---

## 13. Frontend Polling Flow

The frontend no longer uses fake progress only.

The frontend now:
- uploads the file
- gets a job ID
- opens the analysis screen
- keeps polling `GET /api/videos/{job_id}`
- switches to review when status becomes `completed`

Main file:
- `pathomAI-main/src/App.tsx`

API helper file:
- `pathomAI-main/src/lib/api.ts`

---

## 14. How To Run The Project

## Option A: Docker Compose

From the root folder:

```powershell
cd C:\Users\zoen\Downloads\OJT\Projects\Week_9_FathomAI
docker compose up --build
```

Open:
- frontend + main backend: `http://localhost:8000`
- ai agent service docs: `http://localhost:8001/docs`

Before running, make sure root `.env` has a real `OPENAI_API_KEY`.

---

## Option B: Run Locally Without Docker

### Step 1: Start PostgreSQL with Docker

```powershell
cd C:\Users\zoen\Downloads\OJT\Projects\Week_9_FathomAI
docker compose up -d db
```

### Step 2: Set local environment variables

```powershell
$env:OPENAI_API_KEY = "your-real-openai-key"
$env:DATABASE_URL = "postgresql+psycopg://pathomai:pathomai@localhost:5432/pathomai"
$env:AGENT_SERVICE_URL = "http://localhost:8001"
```

### Step 3: Start AI agent service

```powershell
cd C:\Users\zoen\Downloads\OJT\Projects\Week_9_FathomAI\ai-agents-lite-main
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

### Step 4: Start main backend

```powershell
cd C:\Users\zoen\Downloads\OJT\Projects\Week_9_FathomAI\pathomAI-main
pip install -r backend\requirements.txt
uvicorn main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
```

### Step 5: Start React frontend

```powershell
cd C:\Users\zoen\Downloads\OJT\Projects\Week_9_FathomAI\pathomAI-main
npm install
npm run dev
```

Then open:
- frontend: `http://localhost:3000`
- backend API: `http://localhost:8000`
- agent API: `http://localhost:8001`

### Important local prerequisite
For local non-Docker backend runs, `ffmpeg` must be installed and available in your system `PATH`.

---

## 15. Tutorial: How To Test The System

### Check health endpoints

```powershell
curl.exe http://localhost:8000/health
curl.exe http://localhost:8001/health
```

### See current jobs

```powershell
curl.exe http://localhost:8000/api/videos
```

### Upload a video

```powershell
curl.exe -X POST "http://localhost:8000/api/videos/upload" ^
  -F "file=@C:\path\to\meeting.mp4" ^
  -F "language_hint=auto"
```

You will get a response with a job ID.

### Poll the job

```powershell
curl.exe http://localhost:8000/api/videos/YOUR_JOB_ID
```

When finished, the response will include:
- transcript
- summary
- action_items
- sentiment

### Test only the AI agent service directly

```powershell
curl.exe -X POST "http://localhost:8001/internal/transcript-analysis" ^
  -H "Content-Type: application/json" ^
  -d "{\"transcript\":\"Mag-follow up tayo bukas. Please send the revised deck.\",\"video_title\":\"team-sync.mp4\",\"source_language\":\"tl\"}"
```

---

## 16. If You Want To Customize The Flow

### Change from WAV to MP3
Current extraction is WAV.

File:
- `pathomAI-main/backend/app/services/media.py`

You can change the ffmpeg output settings there.

### Change summary prompt behavior
File:
- `ai-agents-lite-main/app/services/transcript_analysis.py`

That file builds the messages sent to `gpt-4o`.

### Change model names
Files:
- transcription: `pathomAI-main/backend/app/services/transcription.py`
- analysis model default: `ai-agents-lite-main/app/config.py`

### Add auth between services
Current setup does not enforce service-to-service auth.
If you want it, add a shared secret header in:
- `pathomAI-main/backend/app/services/agent_client.py`
- `ai-agents-lite-main/app/routers/transcript_analysis.py`

---

## 17. Final Plain-English Summary

Yes, your architecture is basically:

1. `pathomAI-main` gets the video
2. `pathomAI-main` extracts audio
3. `pathomAI-main` sends audio to Whisper
4. Whisper returns transcript
5. `pathomAI-main` sends transcript to `ai-agents-lite-main`
6. `ai-agents-lite-main` uses `gpt-4o`
7. It returns summary, action items, sentiment
8. `pathomAI-main` stores everything in PostgreSQL
9. Frontend polls and shows results
10. Workflow ends

The only correction is:
- the current code converts video audio to **WAV**, not MP3

If you want to understand the project fastest, read these files in this order:

1. `pathomAI-main/backend/app/api/routes/videos.py`
2. `pathomAI-main/backend/app/services/video_pipeline.py`
3. `pathomAI-main/backend/app/services/transcription.py`
4. `pathomAI-main/backend/app/services/agent_client.py`
5. `ai-agents-lite-main/app/routers/transcript_analysis.py`
6. `ai-agents-lite-main/app/services/transcript_analysis.py`
7. `pathomAI-main/src/App.tsx`

That sequence will show you the full flow from upload to final AI result.

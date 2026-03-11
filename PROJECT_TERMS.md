# Project Terms Guide

This file explains the main technical terms used in this project in simple language.

It focuses on:
- what the term means
- whether this project uses it
- where it appears in the code
- whether it is open source, OpenAI-hosted, or something else

## 1. Two Main Apps

### `pathomAI-main`
This is the main app.

It contains:
- the React frontend
- the FastAPI backend
- video upload and URL import
- audio extraction
- Whisper transcription
- PostgreSQL storage
- the call to the separate agent service

Important files:
- [App.tsx](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/src/App.tsx)
- [main.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/main.py)
- [video_pipeline.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/video_pipeline.py)

### `ai-agents-lite-main`
This is the separate AI analysis service.

It receives a transcript and returns:
- summary
- action items
- sentiment

Important files:
- [main.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/main.py)
- [transcript_analysis.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/app/services/transcript_analysis.py)

## 2. What "Pipeline" Means

### Pipeline
A pipeline means:
- a sequence of steps
- one step feeds the next step

In this project, the video pipeline is:
1. get video
2. download it if it came from a URL
3. extract audio
4. send audio to Whisper
5. get transcript
6. send transcript to the agent service
7. get summary, action items, and sentiment
8. save everything to the database

Main file:
- [video_pipeline.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/video_pipeline.py)

So when you see the word `pipeline` here, it mostly means:
- backend processing flow
- not a machine learning training pipeline

## 3. What "Workflow" Means

### Workflow
Workflow is similar to pipeline.

Usually:
- `pipeline` emphasizes processing steps in order
- `workflow` emphasizes the overall business flow or orchestration

In this project:
- the real video workflow is mainly the same pipeline in `pathomAI-main`
- `ai-agents-lite-main/workflow/` exists, but that folder is not the main video-processing flow for this feature

So if you are studying this project, the most important workflow file is still:
- [video_pipeline.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/video_pipeline.py)

## 4. What "AI Agent" Means Here

### AI Agent
In general, an AI agent can mean:
- a model with goals, tools, and decision-making
- sometimes it can call multiple tools, search, plan, and act

In this project, the transcript analysis "agent" is simpler than that.

It is basically:
- a separate service
- that sends the transcript to `gpt-4o`
- and asks for structured output

So here, "agent" means:
- modular AI analysis service
- not a fully autonomous long-running agent system

Main files:
- [transcript_analysis.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/app/services/transcript_analysis.py)
- [transcript_analysis.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/app/routers/transcript_analysis.py)

## 5. GPT-4o

### GPT-4o
`gpt-4o` is the OpenAI model used here for transcript analysis.

It is used for:
- summary
- action items
- sentiment

Where:
- [config.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/app/config.py)
- [transcript_analysis.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/app/services/transcript_analysis.py)

Type:
- OpenAI hosted model
- not open source inside this project

## 6. Whisper and `whisper-1`

### Whisper
Whisper is OpenAI's speech-to-text system.

In this project it is used to:
- turn audio into transcript text
- detect language
- return timestamped transcript segments

Current model:
- `whisper-1`

Where:
- [transcription.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/transcription.py)

Type:
- OpenAI hosted API model in this implementation
- not local Whisper
- not running as an open-source self-hosted model in this project

Important:
- this project sends audio to the OpenAI API
- it does not run Whisper locally on your machine or container

## 7. Transcript

### Transcript
A transcript is the text version of the spoken audio.

In this project:
- `transcript` = the full text
- `transcript_segments` = the timestamped chunks of that text

Stored in:
- [models.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/models.py)

Returned by API in:
- [schemas.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/schemas.py)

## 8. Timestamped Segments

### Timestamped Segments
These are smaller transcript chunks with:
- start time
- end time
- text

Example idea:
- `00:12 - 00:18`: "Hello everyone, thank you for coming."

This is what now powers the `Full Transcript` view in the frontend.

Built from:
- Whisper response data

Where:
- [transcription.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/transcription.py)
- [App.tsx](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/src/App.tsx)

## 9. Speaker Diarization

### Speaker Diarization
Speaker diarization means:
- figuring out who spoke when
- for example `Speaker 1`, `Speaker 2`

This project does **not** currently do speaker diarization.

That means:
- timestamps: yes
- speaker labels: no

Important:
- Whisper transcript timestamps do not automatically mean speaker identification

So if you do not see separate speaker names, that is expected with the current pipeline.

## 10. FFmpeg

### FFmpeg
FFmpeg is a very widely used multimedia tool.

It can:
- read video files
- extract audio
- convert formats
- probe media metadata

In this project it is used to:
- inspect uploaded/downloaded video metadata
- extract the audio to WAV format

Where:
- [media.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/media.py)
- [Dockerfile](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/Dockerfile)

Type:
- open source
- not "built into Python"
- installed in the container with `apt-get install ffmpeg`

### `ffmpeg-python`
`ffmpeg-python` is the Python wrapper used to call FFmpeg.

It is:
- a Python library
- not the FFmpeg binary itself

So the real work is still done by FFmpeg.
`ffmpeg-python` just gives Python code a clean way to call it.

Where:
- [media.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/media.py)
- [requirements.txt](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/requirements.txt)

## 11. WAV Audio

### WAV
WAV is the audio format currently created before transcription.

In this project the backend converts video audio into:
- WAV
- mono
- 16 kHz
- PCM

Why:
- speech-to-text APIs usually work well with clean uncompressed audio

Where:
- [media.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/media.py)

So yes, FFmpeg basically:
- opens the video
- takes only the audio stream
- converts it into a simpler WAV file
- that WAV file is what gets sent to Whisper

## 12. `yt-dlp`

### `yt-dlp`
`yt-dlp` is the tool used for video URL import.

It can download from:
- YouTube
- many other supported sites
- many direct video links

In this project it is used when you paste a video URL instead of uploading a file.

Where:
- [video_ingest.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/video_ingest.py)
- [requirements.txt](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/requirements.txt)

Type:
- open source

## 13. FastAPI

### FastAPI
FastAPI is the Python web framework used for the backend APIs.

It is used in:
- the main app backend
- the agent service backend

Where:
- [main.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/main.py)
- [main.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/main.py)

Type:
- open source

## 14. Route / Endpoint / API

### Route / Endpoint
A route or endpoint is a URL your frontend or another service calls.

Examples in this project:
- `POST /api/videos/upload`
- `POST /api/videos/import`
- `GET /api/videos/{jobId}`
- `POST /internal/transcript-analysis`

Where:
- [videos.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/api/routes/videos.py)
- [transcript_analysis.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/app/routers/transcript_analysis.py)

## 15. HTTP and `httpx`

### HTTP
HTTP is how services talk to each other over the network.

In this project:
- `pathomAI-main` calls `ai-agents-lite-main` over HTTP

### `httpx`
`httpx` is the Python HTTP client library used for that service-to-service call.

Where:
- [agent_client.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/agent_client.py)

Type:
- open source

## 16. PostgreSQL

### PostgreSQL
PostgreSQL is the database used here.

It stores:
- users
- tenants/workspaces
- auth sessions
- video jobs
- transcript
- transcript segments
- summary
- action items
- sentiment
- job status

Configured in:
- [docker-compose.yml](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/docker-compose.yml)
- `[DATABASE_URL]` in the root `.env`

Type:
- open source

## 17. SQLAlchemy

### SQLAlchemy
SQLAlchemy is the Python database toolkit/ORM used in the backend.

It helps the code:
- define tables as Python classes
- query the database
- save updates

Where:
- [db.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/db.py)
- [models.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/models.py)

Type:
- open source

## 18. Tenant / Multi-Tenant

### Tenant
A tenant means one workspace or organization boundary.

In this project:
- each signup creates a workspace
- each user belongs to a tenant
- video jobs are scoped by tenant

So multi-tenant means:
- one app can serve multiple separate workspaces
- each workspace sees only its own jobs and analysis

Where:
- [models.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/models.py)
- [auth.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/auth.py)
- [videos.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/api/routes/videos.py)

## 19. Job Status

### Job Status
A job status tells you what stage the video is in.

Current statuses:
- `queued`
- `extracting_audio`
- `transcribing`
- `analyzing`
- `completed`
- `failed`

Where:
- [models.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/models.py)
- [video_pipeline.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/video_pipeline.py)

## 20. Polling

### Polling
Polling means the frontend keeps asking the backend:
- "Is the job done yet?"

In this project:
- the frontend polls the job endpoint while processing is still happening

Where:
- [App.tsx](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/src/App.tsx)

## 21. Docker and `docker-compose`

### Docker
Docker packages each app into a container so it runs consistently.

### `docker-compose`
`docker-compose.yml` starts all services together.

In this project it starts:
- `db`
- `main-app`
- `ai-agents`

Where:
- [docker-compose.yml](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/docker-compose.yml)

## 22. Vector Search

### Vector Search
Vector search usually means:
- converting text into embeddings
- storing them in a vector database
- searching by semantic similarity

This project does **not** currently use vector search.

That means:
- no embeddings
- no vector database
- no semantic retrieval layer

So if you were expecting things like:
- Pinecone
- FAISS
- Chroma
- pgvector

Those are **not** part of the current codebase.

## 23. Embeddings

### Embeddings
Embeddings are numeric representations of text used for semantic search or retrieval.

This project does **not** currently use embeddings.

So:
- transcript is stored as plain text
- analysis is done directly by sending the transcript to `gpt-4o`
- no retrieval layer is used

## 24. RAG

### RAG
RAG means Retrieval-Augmented Generation.

That usually means:
1. store documents in vector form
2. retrieve related chunks
3. send those chunks to the LLM

This project does **not** currently use RAG.

## 25. Vector Database

### Vector Database
A vector database stores embeddings for similarity search.

This project does **not** currently use one.

So:
- PostgreSQL is used as a normal relational database here
- not as a vector retrieval system

## 26. Open Source vs Hosted

### Open source pieces used here
- FastAPI
- SQLAlchemy
- PostgreSQL
- FFmpeg
- `ffmpeg-python`
- `yt-dlp`
- `httpx`
- Docker
- React
- Vite

### Hosted/OpenAI pieces used here
- `whisper-1`
- `gpt-4o`

Important difference:
- open source libraries run as code/tools inside your project
- hosted models are called through the OpenAI API

## 27. Most Important Files To Learn First

If you want the fastest way to understand the project, read in this order:

1. [README.md](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/README.md)
2. [video_pipeline.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/video_pipeline.py)
3. [videos.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/api/routes/videos.py)
4. [transcription.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/transcription.py)
5. [media.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/media.py)
6. [agent_client.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/backend/app/services/agent_client.py)
7. [transcript_analysis.py](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/ai-agents-lite-main/app/services/transcript_analysis.py)
8. [App.tsx](/C:/Users/zoen/Downloads/OJT/Projects/Week_9_FathomAI/pathomAI-main/src/App.tsx)

## 28. Short Reality Check

What this project currently is:
- video upload/import platform
- audio extraction pipeline
- OpenAI Whisper transcription
- GPT-4o transcript analysis service
- PostgreSQL-backed job tracking
- multi-tenant auth

What it is not currently:
- vector search app
- embeddings app
- RAG system
- speaker diarization system
- local Whisper deployment

## 29. Simple One-Line Summary

This project takes a video, converts its audio to WAV with FFmpeg, sends that audio to OpenAI `whisper-1` for transcript + timestamps, then sends the transcript to a separate `gpt-4o` agent service for summary, action items, and sentiment, and stores the results in PostgreSQL.

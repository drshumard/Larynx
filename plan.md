# Plan: Text-to-Speech Chunk Builder (FastAPI + React + MongoDB)

## Status: Phase 1 & Phase 2 COMPLETE

## 1) Objectives
- ✅ Accept very long text (≥20,000 words) and a name via POST/UI
- ✅ Chunk text at sentence boundaries with a hard cap of 10,000 characters per chunk
- ✅ Generate speech for each chunk using ElevenLabs (model: "eleven_multilingual_v2", voice: LNHBM9NjjOl44Efsdmtl)
- ✅ Concatenate audio chunks into a single MP3 in correct order using pydub/ffmpeg
- ✅ Store job + metadata in MongoDB and serve a downloadable URL
- ✅ Send webhook on completion to: https://drshumard.app.n8n.cloud/webhook/cb298a5c-abcf-4596-bec3-e457f0798790
- ✅ Frontend: Beautiful, Inter font, cream/black palette, card designs, table of jobs, progress indicators

## 2) Implementation Steps

### Phase 1: Core POC (Isolation) ✅ COMPLETE

A. Integration Playbook ✅
- Fetched verified playbook for ElevenLabs TTS v3
- Configured ENV (backend/.env): ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL, WEBHOOK_URL
- Confirmed request route, payload, headers, audio format

B. Core Functions (test_core.py) ✅
- split_text_into_chunks(): regex sentence split (., !, ?) + accumulator not exceeding 10k chars
- tts_chunk_to_audio(): ElevenLabs SDK text_to_speech.convert() method
- merge_audio_chunks(): pydub AudioSegment concatenation with ffmpeg
- save_and_validate(): write mp3 and verify file size
- send_webhook(): POST job result JSON to n8n webhook URL

C. POC Test Results ✅
- Created test text >10k chars (resulted in 2 chunks)
- Chunk 1: 9,965 chars → ~10MB audio
- Chunk 2: 593 chars → ~600KB audio
- Final combined MP3: ~11MB, 704 seconds duration
- Webhook delivered successfully (HTTP 200)

D. POC Success Criteria ✅ MET
- ✅ Successful TTS calls returned audio bytes for 2 chunks
- ✅ Final MP3 plays end-to-end in order
- ✅ Webhook endpoint received POST (HTTP 200)

### Phase 2: Full App Development ✅ COMPLETE

A. Data Model (MongoDB: tts_jobs) ✅
- Fields: _id, name, text_length, chunk_count, processed_chunks, chunks, status, progress, audio_path, audio_url, duration_seconds, error, created_at, updated_at

B. Backend (FastAPI) ✅
- ENV configured: MONGO_URL, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL, WEBHOOK_URL
- Routes implemented:
  - POST /api/jobs: Create job, returns jobId
  - GET /api/jobs: List jobs (latest first)
  - GET /api/jobs/{id}: Get single job with progress
  - GET /api/jobs/{id}/download: Stream final mp3
  - DELETE /api/jobs/{id}: Delete job and audio file
  - GET /api/health: Health check
- Background processing with asyncio.to_thread for TTS calls
- Progress updates after each chunk
- Webhook delivery on completion

C. Frontend (React + shadcn/ui) ✅
- Theme: Inter font, cream (#F8F5EE) background, black (#0F0F0F) text
- Components:
  - CreateJobForm: Name input, Textarea with char/word count, Submit button
  - JobsTable: Database-style table with status chips, progress bars, actions
  - StatsCard: Summary showing Completed/Processing/Failed counts
  - StatusChip: Color-coded status badges (queued, processing, completed, failed)
  - ProgressBar: Visual progress with chunk count display
- Polling: 2-second interval for job status updates
- Toasts: sonner for success/error notifications

D. Files & Storage ✅
- Directory: /app/backend/storage for MP3s
- Files served via streaming endpoint with Content-Disposition header

E. Testing Results ✅
- Backend: All CRUD endpoints working
- Frontend: All UI components functional
- Integration: End-to-end job creation, processing, download working
- Webhook: Successfully delivers to n8n (HTTP 200)

### Phase 2 User Stories ✅ ALL VERIFIED
1. ✅ As a user, I can paste text and my name, then submit to start a TTS job
2. ✅ As a user, I can see my job appear immediately with status "queued/processing" and a live progress bar
3. ✅ As a user, I can view chunk count and detailed progress
4. ✅ As a user, I can download the final MP3 via a clear button when the job completes
5. ✅ As a user, I can see an error state if the job fails
6. ✅ As a user, I can see a clean, readable UI with Inter font and cream/black palette
7. ✅ As a user, webhook is sent on job completion

## 3) Completed Actions
1. ✅ Fetched ElevenLabs v3 integration playbook
2. ✅ Implemented test_core.py with chunking + TTS + merge + webhook
3. ✅ POC succeeded (audio plays + webhook 2xx)
4. ✅ Built backend APIs, background processing, Mongo models
5. ✅ Built frontend UI (form, jobs table, stats), applied design guidelines
6. ✅ Ran testing_agent_v3 end-to-end
7. ✅ Fixed API key loading issue (added python-dotenv)
8. ✅ Verified full flow working

## 4) Success Criteria ✅ ALL MET
- ✅ POC: Two+ chunks TTS'ed and merged into a single MP3 that plays correctly; webhook 2xx
- ✅ Backend: /api routes functional; jobs persist; progress updates during processing; final MP3 downloadable
- ✅ Frontend: Submits jobs; shows live progress; presents a beautiful, accessible interface
- ✅ Webhook: Completion payload sent with audioUrl (HTTP 200)
- ✅ All environment variables used (no hardcoded URLs/keys); /api prefix respected

## 5) Technical Details

### Key Files
- `/app/backend/server.py` - FastAPI backend with all endpoints
- `/app/backend/test_core.py` - POC test script
- `/app/backend/.env` - Environment variables
- `/app/frontend/src/App.js` - React frontend
- `/app/frontend/src/App.css` - Styles with design tokens

### API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/jobs | Create TTS job |
| GET | /api/jobs | List all jobs |
| GET | /api/jobs/{id} | Get job details |
| GET | /api/jobs/{id}/download | Download audio |
| DELETE | /api/jobs/{id} | Delete job |
| GET | /api/health | Health check |

### Environment Variables
```
MONGO_URL="mongodb://localhost:27017"
DB_NAME="tts_chunker"
ELEVENLABS_API_KEY="sk_e80ab01e82f120260468d7955899f07b10ef028fdbc6a564"
ELEVENLABS_VOICE_ID="LNHBM9NjjOl44Efsdmtl"
ELEVENLABS_MODEL="eleven_multilingual_v2"
WEBHOOK_URL="https://drshumard.app.n8n.cloud/webhook/cb298a5c-abcf-4596-bec3-e457f0798790"
```

### Webhook Payload Format
```json
{
  "jobId": "string",
  "name": "string",
  "audioUrl": "string",
  "status": "completed",
  "textLength": number,
  "chunkCount": number,
  "completedAt": "ISO datetime"
}
```

## 6) Future Enhancements (Optional)
- Add retry logic with exponential backoff for TTS API rate limits
- Add job queue management for concurrent processing limits
- Add audio preview player in UI
- Add voice selection dropdown
- Add progress percentage display
- Add estimated time remaining
- Add job history pagination

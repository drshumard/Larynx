# Plan: Text-to-Speech Chunk Builder (FastAPI + React + MongoDB)

POC required: Yes (external TTS + chunking + audio merge + webhook = complex integration)

## 1) Objectives
- Accept very long text (≥20,000 words) and a name via POST/UI
- Chunk text at sentence boundaries with a hard cap of 10,000 characters per chunk
- Generate speech for each chunk using ElevenLabs (model: “eleven v3”, voice: LNHBM9NjjOl44Efsdmtl)
- Concatenate audio chunks into a single MP3 in correct order
- Store job + metadata in MongoDB and serve a downloadable URL
- Send webhook on completion to: https://drshumard.app.n8n.cloud/webhook/cb298a5c-abcf-4596-bec3-e457f0798790
- Frontend: Beautiful, Inter font, cream/black palette, card designs, table of jobs, progress indicators

## 2) Implementation Steps

### Phase 1: Core POC (Isolation)
Goal: Prove the hardest path works end-to-end before building the app UI.

A. Integration Playbook
- Use integration_playbook_expert_v2 to fetch a verified playbook for ElevenLabs TTS v3
- Define ENV (backend/.env) keys: ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL
- Confirm request route, payload, headers, audio format, and rate-limit guidance

B. Core Functions (test_core.py)
- split_text_into_chunks(text, max_chars=10000): regex sentence split (., !, ?, newlines) + accumulator not exceeding max_chars
- tts_chunk_to_mp3_bytes(chunk): call ElevenLabs TTS v3 using API key/voice/model, return audio bytes
- merge_mp3_bytes(chunk_bytes_list): initial approach: frame-safe concatenation (naive join). If playback issues arise, pivot to decode+re-encode (pydub/ffmpeg)
- save_and_validate(output_path, audio_bytes): write mp3 and verify non-zero length
- post_webhook(url, payload): POST job result (JSON with test metadata + dummy URL) to verify reachability

C. POC Test Flow
- Build a sample text > 10k chars (repeat sentence blocks to force ≥2 chunks)
- Chunk → Loop TTS → Join MP3 → Save to /app/backend/storage/poc_output.mp3
- Verify playback viability (basic checks: file size > N KB)
- Send webhook with JSON: {jobId: "poc", status: "completed", audioUrl: "<placeholder or local route>"}

D. POC Success Criteria
- Successful TTS calls return audio bytes for ≥2 chunks
- Final MP3 plays end-to-end in order (manual spot-check). If issues: switch to decode/encode
- Webhook endpoint receives POST (HTTP 2xx)

E. POC User Stories (execution-focused)
1. As a developer, I can run one script to validate ElevenLabs TTS returns audio for long text chunks
2. As a developer, I can verify chunks are created only at sentence boundaries
3. As a developer, I can produce a single MP3 from several TTS chunks
4. As a developer, I can confirm a webhook receives a completion payload
5. As a developer, I can see clear logs for each step and failure point

### Phase 2: Full App Development

A. Data Model (MongoDB: tts_jobs)
- Fields: _id, name, text_length, chunk_count, status [queued|processing|completed|failed], progress [0-100], audio_path, audio_url, error, created_at, updated_at, voice_id, model, webhook_delivered [bool], durations (optional)

B. Backend (FastAPI)
- ENV: MONGO_URL (given), ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID (default: LNHBM9NjjOl44Efsdmtl), ELEVENLABS_MODEL (default: eleven v3)
- Routes (all prefixed with /api):
  - POST /api/jobs: {name, text} → returns {jobId}; validate ≥20,000 words, else 422
  - GET /api/jobs: list jobs (paginate, latest first)
  - GET /api/jobs/{id}: get single job (status, progress, links)
  - GET /api/jobs/{id}/download: stream final mp3
  - GET /api/health: health check
- Processing (BackgroundTasks):
  - On POST, insert job {status: queued, progress: 0}; enqueue background worker
  - Worker: chunk at sentence boundaries → sequential TTS calls (handle retries/backoff: 429/5xx) → append bytes → write final mp3 file (storage/<jobId>.mp3)
  - Update progress after every chunk
  - Store audio_path; expose audio_url via download endpoint
  - After completion: POST webhook with JSON {jobId, name, audioUrl, textLength, chunkCount, status}
  - On failure: status=failed, error=message
- Serialization helpers: convert ObjectId, datetimes
- Security: sanitize filename; no secrets in responses; size limits and timeouts

C. Frontend (React + shadcn/ui)
- Theme: Inter font, cream (#f8f5ee) background, black (#0f0f0f) text, subtle accent
- Pages/Components:
  - UploadFormCard: Name input, Textarea (warn if <20k words), Submit, loading state
  - JobsTable: database-style table listing jobs (name, chunks, status chip, progress bar, created time, actions)
  - JobDetail: live status polling (2s), progress bar, chunk count, download button when ready
  - Toasts for errors/success; skeleton loaders
- API integration: uses REACT_APP_BACKEND_URL with /api prefix
- State: optimistic create (shows queued), polling GET /api/jobs/{id}
- Accessibility: data-testid on interactive elements, keyboard-friendly

D. Error Handling & Resilience
- Retries (exponential backoff) for TTS chunk calls on 429/5xx (bounded)
- If any chunk fails after retries → job fails with clear error
- Ensure final MP3 creation atomic (write temp then move)
- Webhook delivery attempt with retry (log failure)

E. Files & Storage
- Directory /app/backend/storage for MP3s (not in repo)
- Serve via streaming endpoint; store path in DB and compute URL

F. Testing & Quality
- Lint: ruff (backend), eslint (frontend)
- Testing (testing_agent_v3):
  - Backend only for large payload (skip frontend input limits): POST job (shorter text for runtime constraints), poll status, download file
  - Frontend: form submission (smaller text), job row appears, status transitions, download enabled when done
  - Skip webhook external validation (inform agent to skip); verify backend logs/webhook attempt status field

G. Design Guidelines (applied in UI)
- Font: Inter via @fontsource/inter
- Layout: centered container, card surfaces with subtle shadow, rounded corners, tasteful spacing
- Colors: cream bg (#f8f5ee), black text (#0f0f0f), accents for buttons/progress
- “Database-looking” Jobs table with zebra rows, status chips, inline progress bars

H. Phase 2 User Stories (UX-focused)
1. As a user, I can paste very long text and my name, then submit to start a TTS job
2. As a user, I can see my job appear immediately with status “queued/processing” and a live progress bar
3. As a user, I can open a job to view chunk count and detailed progress
4. As a user, I can download the final MP3 via a clear button when the job completes
5. As a user, I can see an error state with guidance if the job fails (e.g., API rate limit)
6. As a user, I can see a clean, readable UI with Inter font and cream/black palette
7. As a user, I can verify a webhook was attempted by a status indicator in the job detail

## 3) Next Actions
1. Fetch ElevenLabs v3 integration playbook (integration_playbook_expert_v2)
2. Implement test_core.py with chunking + TTS + merge + webhook checks
3. Run and fix until POC succeeds (audio plays + webhook 2xx)
4. Build backend APIs, background processing, Mongo models, streaming
5. Build frontend UI (form, jobs table, details), apply design
6. Lint both stacks; run testing_agent_v3 end-to-end (skip drag/drop/camera)
7. Iterate fixes until all tests pass; share preview URL

## 4) Success Criteria
- POC: Two+ chunks TTS’ed and merged into a single MP3 that plays correctly; webhook 2xx
- Backend: /api routes functional; jobs persist; progress updates during processing; final MP3 downloadable
- Frontend: Submits jobs; shows live progress; presents a beautiful, accessible interface
- Webhook: Completion payload sent with audioUrl; retry logged on failure
- All environment variables used (no hardcoded URLs/keys); /api prefix respected; linting passes

# Test Credentials

## Auth Status
This application (Larynx / TTS Chunker) has **NO authentication**.
- No login page, no user model, no auth middleware in `/app/backend/server.py`.
- All `/api/*` endpoints are publicly reachable.
- The only "secret" is a server-side `ELEVENLABS_API_KEY` in `/app/backend/.env` used to call ElevenLabs.

## Test Users
N/A — no user accounts exist.

## Notes for Testing Agents
- No login flow to exercise.
- The API is accessed directly at `{REACT_APP_BACKEND_URL}/api/...`.
- OpenAPI spec is served at `/api/openapi.json`; interactive docs at `/api/docs`.

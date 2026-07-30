#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: |
  Extend deterministic seed + request-stitching (currently only for
  `eleven_multilingual_v2` chunking jobs) to also cover `eleven_v3` chunking
  jobs. Studio mode, eleven_turbo_*, eleven_monolingual_v1 must remain
  unchanged (seed: null, no stitching metadata). Also expose the FastAPI
  OpenAPI spec at `/api/openapi.json` so automated tests can find it.

backend:
  - task: "eleven_v3 jobs get a non-null integer seed on creation"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          Added STITCHING_MODELS = {eleven_multilingual_v2, eleven_v3} constant.
          `create_job` (server.py:1478-1481) now generates job_seed when
          model_id is in STITCHING_MODELS + chunking mode. Verify: POST
          /api/settings model_id=eleven_v3, POST /api/jobs → GET /api/jobs/{id}
          shows `seed` = integer.
      - working: true
        agent: "testing"
        comment: |
          PASS. Set settings to mode=chunking, model_id=eleven_v3, chunk_size=4500.
          Created job → GET /api/jobs/{id}/details returned seed=741200809 (int in
          [0, 2^31-1]), tts_config.model_id=eleven_v3, chunk_count=1. Behavior
          matches spec. (Note: `GET /api/jobs/{id}` does not include the seed
          field; only `/details` does — this is by-design in current code.)
  - task: "eleven_turbo_v2_5 and studio-mode jobs still have seed: null"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          Guard uses `in STITCHING_MODELS` — turbo/monolingual not included.
          Verify: switch settings to eleven_turbo_v2_5 → new job has seed: null.
          Same for studio mode.
      - working: true
        agent: "testing"
        comment: |
          PASS on both branches. (a) chunking + eleven_turbo_v2_5: created job
          has seed=None, tts_config.model_id=eleven_turbo_v2_5. (b) studio +
          eleven_v3: seed=None even though model is stitching-capable, because
          the guard requires mode=chunking. Studio mode correctly bypasses seed
          generation.
  - task: "Regenerate on a v3 job reuses the SAME seed"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          `regenerate` (server.py:1838-1843) now reuses src.seed for any
          STITCHING_MODELS model. Verify: POST /api/jobs/{id}/regenerate on a
          v3 job → new job.seed == source job.seed, regenerated_from set.
      - working: true
        agent: "testing"
        comment: |
          PASS. Regenerated a v3 source job (seed=741200809). New job returned
          200, has identical seed=741200809, tts_config.model_id=eleven_v3, and
          regenerated_from equal to source job id. Also verified the same
          behavior on v2: source seed=187210629 was preserved on regenerate.
  - task: "multilingual_v2 behavior unchanged"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          v2 chunker selection (server.py:1425, 1826) untouched. Seed guard
          extended, not narrowed. Verify: v2 job still gets a seed, still
          chunks via split_text_into_chunks_v2.
      - working: true
        agent: "testing"
        comment: |
          PASS. chunking + eleven_multilingual_v2 job created with
          seed=187210629 (int), tts_config.model_id=eleven_multilingual_v2.
          Regenerate reused the same seed. No behavior change vs. pre-v3
          extension.
  - task: "OpenAPI spec accessible at /api/openapi.json"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
      - working: true
        agent: "main"
        comment: |
          FastAPI() reconfigured with openapi_url=/api/openapi.json,
          docs_url=/api/docs, redoc_url=/api/redoc. Verified via
          `curl localhost:8001/api/openapi.json` returns spec.

frontend:
  - task: "Seed UI lights up for v3 jobs (badge, regenerate button, chunk stitching)"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/App.js"
    stuck_count: 0
    priority: "low"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          No frontend edits made. UI conditions on presence of job.seed (not
          on model name), so v3 jobs automatically render the Sparkles badge,
          the "Regenerate w/ Same Seed" button, and the chunk "Stitching"
          section once backend attaches a seed. Not requesting frontend tests
          per project policy — will ask user if UI verification is desired.

metadata:
  created_by: "main_agent"
  version: "1.1"
  test_sequence: 1
  run_ui: false

test_plan:
  current_focus:
    - "eleven_v3 jobs get a non-null integer seed on creation"
    - "eleven_turbo_v2_5 and studio-mode jobs still have seed: null"
    - "Regenerate on a v3 job reuses the SAME seed"
    - "multilingual_v2 behavior unchanged"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
  - agent: "main"
    message: |
      Extended STITCHING_MODELS = {eleven_multilingual_v2, eleven_v3}.
      Changes in /app/backend/server.py: constants (79-85), FastAPI() OpenAPI
      config (107-113), process_tts_job stitching guard (~980), create_job
      seed guard (~1481), regenerate seed guard (~1842), resume_tts_job
      stitching guard (~1983). Chunker selection intentionally NOT changed —
      v3 keeps its default sentence chunker; only seed + previous_request_ids
      behavior was extended (matches ElevenLabs docs: v3 supports both).
      No frontend changes needed (UI keys off job.seed presence, not model).
      Please test the four backend tasks under `current_focus`. Auth: none
      (see /app/memory/test_credentials.md). Base URL for tests:
      REACT_APP_BACKEND_URL (external) or http://localhost:8001 (internal).
  - agent: "testing"
    message: |
      All 4 focus backend tasks PASS (plus openapi + health regression).
      Ran /app/backend_test.py against
      https://c13eddd0-b7a5-4e2e-b9f4-46c909c653f2.preview.emergentagent.com/api.
      Results (9/9 pass):
        - openapi_reachable: 200, /api/jobs in paths
        - health: {"status":"healthy","service":"tts-chunker"}
        - v3_seed_generated: job seed=741200809 (int), model=eleven_v3, chunks=1
        - turbo_seed_null: seed=None with eleven_turbo_v2_5
        - studio_seed_null: seed=None with studio+eleven_v3 (guard requires chunking)
        - v2_seed_generated: seed=187210629 (int) with eleven_multilingual_v2
        - regenerate_reuses_seed_v3: new_seed==src_seed==741200809, regenerated_from set
        - regenerate_reuses_seed_v2: new_seed==src_seed==187210629, regenerated_from set
        - cleanup: all 6 DELETE calls returned 200
      IMPORTANT NOTE FOR MAIN AGENT: The seed field is exposed by
      `GET /api/jobs/{id}/details`, NOT by `GET /api/jobs/{id}` (see
      server.py:1600-1614). Tests use `/details`. If the review intent was to
      also expose seed on the lightweight endpoint, main agent can decide;
      current behavior is internally consistent (list view exposes seed at
      server.py:1575, single-job summary omits it, details includes it).
      No TTS success was required — assertions are on creation-time fields.
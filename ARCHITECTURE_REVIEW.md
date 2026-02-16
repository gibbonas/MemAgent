# MemAgent: Comprehensive Architecture & Code Review

**Reviewer role:** Senior Software Architect & AI/ML Engineer  
**Date:** February 2026  
**Scope:** Multi-agent application (backend FastAPI + Agno, frontend Next.js)

---

## Executive Summary

MemAgent is a well-structured multi-agent memory preservation app with clear separation of agents (collector, screener, enricher, generator, photo manager), sensible token optimization, and production-oriented features (OAuth, guardrails, structured logging). **Strengths** include modular agent design, URL-based image handling to avoid token waste, and good documentation in README and docstrings. **Addressed:** The cached `MemoryTeam` / DB session / stale-credentials issue has been fixed (request-scoped `TokenTracker` and `GooglePhotosClient` are now passed into team methods per request), and `list_memories` now coerces `user_id` to UUID. **Remaining priorities:** Wire guardrails into the pipeline, and address production-readiness gaps (config path, auth state storage, Dockerfile, migrations). Below is a structured review with code references and actionable recommendations.

---

## 1. Well-Written

### 1.1 Readability

**Strengths**

- **Descriptive names:** `ConversationState`, `parse_collected_memory`, `_process_screening`, `TokenBudgetExceeded` clearly convey intent.
- **Agent modules** use a consistent pattern: docstring with persona, tools, outcome, token budget, and a `create_*_agent()` factory.

**Weaknesses / Improvements**

- **Magic strings for stages:** Stages like `"collecting"`, `"ready_for_search"`, `"selecting_references"` are repeated. Introduce an enum or constants for pipeline stages to avoid typos and simplify refactors.

```python
# Suggested: backend/app/agents/team.py or a shared constants module
class PipelineStage(str, Enum):
    COLLECTING = "collecting"
    READY_FOR_SEARCH = "ready_for_search"
    SELECTING_REFERENCES = "selecting_references"
    # ...
```

- **Long methods:** `process_memory` in `team.py` is ~340 lines with many `elif state.stage == ...`. Consider extracting stage handlers into separate methods (e.g. `_handle_collecting`, `_handle_ready_for_search`) and dispatching by stage.

### 1.2 Modularity

**Strengths**

- Clear package layout: `agents/`, `tools/`, `api/routes/`, `core/`, `storage/`, `schemas/`.
- Agents are created via factories (`create_memory_collector_agent()`, etc.) and depend on injected tools/clients.
- Tools (`EXIFWriter`, `GeminiImageGenerator`, `GooglePhotosClient`) are separate from agent logic.

**Weaknesses**

- **Orchestration lives in one large class:** `MemoryTeam` owns session state, pipeline stages, EXIF embedding, reference photo fetch, and generation. Consider splitting:
  - **Session/state:** keep in `MemoryTeam` or a dedicated `SessionStore`.
  - **Pipeline steps:** e.g. `ScreeningStep`, `GenerationStep` that take `(state, user_id, session_id)` and return a result dict; `MemoryTeam` then only orchestrates and updates state.
- **Routes doing too much:** In `chat.py`, building `metadata` (image_url, reference_photos, extraction) is repeated in several endpoints. Extract a helper e.g. `def build_chat_metadata(result, team, session_id, user_id, credentials)` to avoid duplication and drift.

### 1.3 Documentation

**Strengths**

- Module-level docstrings describe purpose (e.g. `memory_collector.py`, `guardrails.py`).
- README documents architecture, token budgets, security, and deployment.
- Complex logic (e.g. date handling in memory collector instructions) is explained in prompts and comments.

**Improvements**

- Add a **high-level sequence diagram** (e.g. Mermaid in README or `/docs`) for: User → Chat API → MemoryTeam → Collector → Screener → Generator → Photo Manager.
- Document **screening behavior:** `_process_screening` runs the LLM screener but does not use `ContentPolicyGuardrail` or parse the screener output; the comment says "For now, assume content passes (TODO: parse screening result)". Either implement parsing and guardrail integration or document the current “LLM-only” approach and its limitations.
- **API:** OpenAPI descriptions are minimal. Enrich route docstrings and add `response_model` and example responses where missing so that `/docs` is sufficient for integration.

### 1.4 Error Handling

**Strengths**

- **Structured error returns:** Pipeline returns `{"status": "error", "message": "...", "stage": "..."}` instead of raising, so the frontend can show messages consistently.
- **LLM retries:** `chat.py` retries on 503/429 with `is_retryable_llm_error` and logs each attempt.
- **User-facing messages:** `parse_llm_error()` turns API errors into short, safe messages.
- **EXIF embedding:** Failures are logged and the pipeline continues (`_embed_exif_into_image`).

**Weaknesses**

- **Broad `except Exception`:** In `team.py` (e.g. around line 352), `except Exception as e` returns a generic "An error occurred" and logs. Prefer catching specific exceptions (e.g. `TokenBudgetExceeded`, `PickerUnauthorizedError`) and re-raising or mapping to known error types; keep a single top-level catch for truly unexpected errors and log with traceback.
- **Screening/generation:** `_process_screening` and `_process_generation` catch `Exception` and return error dicts but don’t distinguish transient vs permanent failures (e.g. policy violation vs network error), which could drive retry/backoff or user messaging.
- **Guardrail usage:** `ContentPolicyGuardrail` and `RateLimitGuardrail` are never invoked in the pipeline. Content policy is only enforced by the LLM screener (and not parsed). Rate limits are not checked before creating a memory. Either wire these in or remove them to avoid a false sense of protection.

### 1.5 Consistency

**Strengths**

- Pydantic for request/response schemas; SQLAlchemy 2.0 style with `Mapped`; async/await used consistently in routes and DB.
- Logging via `structlog` with key-value fields (`logger.info("event_name", key=value)`).

**Weaknesses**

- **Imports inside functions:** e.g. `import time`, `import os` in `chat.py` and `main.py`. Move to top of file for consistency.
- **Sync vs async:** `memory_collector.run(prompt)` and `content_screener.run(screening_prompt)` are synchronous in an async flow; if Agno supports async run, prefer it to avoid blocking the event loop under load.
- **user_id type:** Sometimes `str` (Query params, cache keys), sometimes `uuid.UUID` (DB). **Fixed:** `photos.py` `list_memories` now coerces `user_id` to `uuid.UUID` with validation and uses it in the filter. Consider a shared helper for other routes that filter by user_id.

---

## 2. Production-Ready

### 2.1 Scalability

**Potential bottlenecks**

1. **In-memory caches**
   - **`_team_cache` (chat.py):** One `MemoryTeam` per user, held indefinitely. **Fixed:** The team no longer uses a request-scoped `TokenTracker` or `GooglePhotosClient` from construction. Each request creates a fresh `TokenTracker(db)` and `GooglePhotosClient(credentials)` and passes them into `process_memory`, `confirm_reference_selection`, and `run_generation_from_stored_refs`, so the cached team always uses the current request’s DB session and credentials. Session state (`MemoryTeam.sessions`) remains in-memory; for horizontal scaling, consider Redis or DB-backed session store.
   - **`state_tokens` (auth.py):** OAuth CSRF states stored in a process-local dict. Lost on restart; not shared across instances. Fine for single instance; for multiple instances or restarts, use Redis or a short-lived DB store.
   - **`MemoryTeam.sessions`:** Conversation state is in-memory per process. Replicas won’t share state; restarts lose state. For horizontal scaling, move to Redis or DB-backed session store.

2. **Synchronous agent calls**
   - `self.memory_collector.run(prompt)` and `self.content_screener.run(screening_prompt)` block the event loop. Under concurrency, use async agents or run in a thread pool so one long LLM call doesn’t stall other requests.

3. **No connection pooling visibility**
   - DB engine uses default pool; consider configuring pool size and timeouts for production load.

**Recommendations**

- **Team/token_tracker lifecycle (done):** The team is cached per user, but each request passes a fresh `TokenTracker(db)` and `GooglePhotosClient(credentials)` into `process_memory`, `confirm_reference_selection`, and `run_generation_from_stored_refs`. All token tracking and Google Photos operations use these request-scoped instances, so the cached team never uses a closed session or stale credentials.
- **Session state:** Persist `ConversationState` (or a serializable equivalent) in Redis/DB keyed by `session_id`, and optionally TTL (e.g. 24h).
- **OAuth state:** Store state in Redis with TTL (e.g. 600 seconds) and validate in callback.

### 2.2 Reliability

**Strengths**

- Retries for 503/429 in chat.
- EXIF failure doesn’t block the pipeline.
- Picker unauthorized is caught and returns a clear “reauth” path.

**Weaknesses**

- **Single point of failure:** No fallback if Gemini image generation is down (e.g. queue and retry, or a “try again later” flow).
- **~~Stale credentials in cached team (fixed).~~** Request-scoped tracker and client are now passed in per request.
- **No idempotency:** Duplicate submissions (e.g. double-click) can create duplicate memories or double token usage. Consider idempotency keys for message or memory creation.

**Recommendations**

- Per-request `TokenTracker(db)` and `GooglePhotosClient(credentials)` are now passed into team methods (see Scalability); no further change needed for the team lifecycle.
- Add a simple circuit breaker or “recent failure” flag for Gemini and back off before retrying.
- Document and, if needed, implement idempotency for critical operations.

### 2.3 Security

**Strengths**

- **Image serving:** Path traversal blocked (`..`, `/`, `\`); ownership check via filename `memory_{user_id}_*`; auth via `get_credentials`.
- **CORS:** Origins from config; no `*` with credentials.
- **OAuth:** State parameter for CSRF; tokens stored server-side.
- **Input validation:** Pydantic `min_length`/`max_length` on chat message (e.g. 2000 chars).
- **API key in config:** From env, not hardcoded.

**Weaknesses**

- **user_id from query string:** All endpoints take `user_id` as a query parameter. Any client that knows another user’s ID could theoretically pass it. Mitigation: use server-side sessions or JWT so the backend derives `user_id` from the authenticated session instead of trusting the query.
- **OAuth tokens in DB:** Comments in `models.py` say “Should be encrypted in production”. Implement encryption at rest for `OAuthToken.access_token` and `refresh_token` (e.g. with a key from env and a standard encryption library).
- **REDIRECT_URI and frontend_url:** Hardcoded `http://localhost:8000` in `security.py` for redirect URI. In production this must be configurable (e.g. from `settings`) and use HTTPS.
- **Generic APIKeyGuardrail pattern:** The generic long-alphanumeric pattern could false-positive on non-secrets. Consider narrowing (e.g. only redact known key prefixes) and still never sending raw keys to the client.

**Recommendations**

- Derive `user_id` from session/JWT after OAuth; don’t rely on client-supplied `user_id` for authorization.
- Encrypt OAuth tokens at rest and document key rotation.
- Load redirect URI and frontend URL from settings for all environments.

### 2.4 Performance

**Observations**

- **Token usage:** Tracked per agent with estimates (e.g. 1000 for collector, 2000 for generator). Actual token counts from the API are not used; consider using tiktoken or provider usage when available for accurate budgets and cost visibility.
- **Reference image fetch:** In `_process_generation`, reference URLs are fetched sequentially with `httpx.Client` (sync). Use `httpx.AsyncClient` and `asyncio.gather` to fetch in parallel.
- **Temp image cleanup:** No automated cleanup of `temp_image_dir`. Old files can accumulate; add a periodic job or TTL-based cleanup.

**Recommendations**

- Use async HTTP for reference image fetching and parallelize.
- Add a small “token usage” API or metrics (e.g. Prometheus) for session/daily totals and per-agent usage.
- Schedule or trigger cleanup of generated images older than N hours.

### 2.5 Observability

**Strengths**

- **Structlog** with event names and context (user_id, session_id, stage, etc.).
- **Token usage** logged on each track.
- **Health endpoint:** `GET /health` for liveness.

**Weaknesses**

- **No metrics endpoint:** No Prometheus/OpenMetrics or equivalent for request counts, latency, token usage, or error rates.
- **No request IDs:** Hard to trace a single request across logs; add middleware to set a request ID (e.g. `X-Request-ID`) and include it in every log line for that request.
- **Agent decisions not logged:** Screener result (approved/denied) and generator success/failure are not always clearly logged in a structured way for analytics.

**Recommendations**

- Add middleware to generate and propagate a request ID; add it to structlog context.
- Expose `/metrics` (e.g. Prometheus) with counters/histograms for: requests by route and status, latency, token_usage by agent, pipeline stage transitions.
- Log pipeline stage transitions and screener/generator outcomes in a consistent structured format.

### 2.6 Deployment

**Strengths**

- **docker-compose.yml** for Postgres and Redis (optional).
- README documents Cloud Run and env vars for production.

**Weaknesses**

- **No Dockerfile** for the app itself; only DB/Redis are containerized. No single-command app image.
- **Config env_file:** `config.py` uses `env_file="../.env.local"`. Relative path is fragile (depends on CWD). Prefer `env_file=".env.local"` at repo root and set working directory in run scripts/Docker, or load from absolute path derived from `__file__`.
- **Alembic:** Listed in pyproject.toml but no `alembic/` or migrations found. Schema changes will require manual SQL or adding Alembic and initial migration.

**Recommendations**

- Add a Dockerfile for the backend (and optionally frontend) and document `docker-compose` that runs app + DB + Redis.
- Load env from a path that doesn’t depend on CWD; document expected env vars per environment.
- Add Alembic, baseline from current models, and use migrations for all future schema changes.

---

## 3. Sustainable for Future Development

### 3.1 Extensibility

**Strengths**

- **New agents:** README describes adding an agent file, factory, and registering in the team; clear pattern.
- **New tools:** Tools are injected into agents; new tools can be added without changing core orchestration.
- **Stages:** Adding a new pipeline stage is possible by extending `ConversationState.stage` and adding a branch in `process_memory` (would benefit from the enum and handler extraction suggested above).

**Improvements**

- **Pipeline as a list of steps:** Define a list of pipeline steps (e.g. `[CollectStep(), ScreenStep(), GenerateStep(), ...]`) and have the orchestrator loop over steps with a shared state object. New steps then mean adding a class and appending to the list, without editing a large state machine.
- **Pluggable guardrails:** Register guardrails (content, rate limit, token budget) in a list and run them in a single place before/after relevant stages so new guardrails don’t require editing multiple call sites.

### 3.2 Maintainability

**Strengths**

- **Single dependency file:** `pyproject.toml` with pinned deps; `uv` for installs.
- **Type hints** used in many places (agents, tools, schemas).

**Weaknesses**

- **Duplicate response building:** Chat and photo routes repeat logic for `metadata` (image_url, reference_photos, extraction). Centralize in a shared helper.
- **Two Gemini clients:** `google-genai` (genai.Client) in `gemini_image.py` and `google-generativeai` in pyproject; ensure both are still required and document why.

**Recommendations**

- Extract shared response/metadata builders; use a single place for image URL construction (and make base URL configurable instead of `http://localhost:8000`).
- Periodically update dependencies and run tests; add a Dependabot or similar config.

### 3.3 Testability

**Strengths**

- **test_basic.py** has unit tests for `ContentPolicyGuardrail`, `APIKeyGuardrail`, and EXIF conversion.
- Pydantic schemas and pure functions (e.g. guardrails, `parse_collected_memory`) are easy to unit test.

**Weaknesses**

- **Integration/E2E placeholders:** `test_memory_collection_flow` and `test_end_to_end_memory_creation` are empty. No tests for `MemoryTeam.process_memory`, chat routes, or pipeline stages.
- **No mocks for external services:** No fixtures for Gemini or Google Photos; integration tests would need real or mocked HTTP.
- **Agent run() is synchronous:** Hard to test async flow without running real agents; consider an interface (e.g. `MemoryCollectorProtocol`) so tests can inject a stub that returns fixed extractions.

**Recommendations**

- **Unit:** Add tests for `parse_collected_memory` (ready/needs_info, malformed JSON), `_user_wants_*` helpers, and token tracker budget logic (with an in-memory or SQLite DB).
- **Integration:** Use `httpx.ASGITransport` and FastAPI’s `TestClient` to hit chat/photos routes with mocked `get_credentials` and a test DB; mock Gemini and Google Photos with `respx` or `responses` (or a small mock server).
- **E2E:** Keep one or two E2E tests behind a flag or in CI with test accounts and document how to run them.

### 3.4 Agent Orchestration / Lifecycle

**Current design**

- Agents are created once in `MemoryTeam.__init__` and reused for all sessions/users served by that team instance.
- No explicit “decommission” or teardown; teams live as long as the process and cache.

**Gaps**

- No lifecycle hooks (e.g. “on session end”) to persist or clear state.
- No limit on `sessions` dict size; a long-running process could accumulate many sessions. Consider eviction (e.g. LRU by last activity) or moving to external store.

**Recommendations**

- Document the lifecycle: agents are long-lived, session state is in-memory (or external store after refactor), and teams are cached per user with the critical fix for DB/credentials.
- Add optional eviction or TTL for in-memory sessions, or move to Redis/DB and treat “session end” as persistence only.

### 3.5 AI Model Management

**Current state**

- Model name is hardcoded in `base.py` (`get_gemini_model("gemini-2.5-flash")`) and in `gemini_image.py` (`MODEL_NAME = "gemini-2.5-flash-image"`).
- No versioning or A/B testing; no config-driven model selection.

**Recommendations**

- Move model names to config (e.g. `settings.gemini_chat_model`, `settings.gemini_image_model`) so you can switch or version without code changes.
- Document a simple strategy: e.g. one model per “role” (chat vs image), and a process for rolling out new versions (config change, then monitor).

### 3.6 Dependency Management

**Strengths**

- `pyproject.toml` with version bounds; dev group for pytest/httpx.

**Weaknesses**

- Typo in pyproject: `unicorn[standard]` should likely be `uvicorn[standard]` (if that’s what’s actually used).
- No lock file committed (e.g. `uv.lock`); consider committing it for reproducible installs.

**Recommendations**

- Fix package name if it’s a typo; ensure CI installs from lock file.
- Pin critical transitive deps if you need to avoid surprise upgrades (e.g. Agno, google-genai).

### 3.7 Future-Proofing

**Strengths**

- Agno abstracts the agent interface; swapping to another framework would mainly touch agent creation and `run()`.
- URL/path-based image handling keeps LLM context small and aligns with possible future “vision” APIs that accept URLs.

**Risks**

- Tight coupling to Gemini (model and image API) in tools and base; a second provider would require new tools and config. Consider a thin “model provider” interface (e.g. `generate_image(prompt, refs) -> path`) so you can plug in another backend later.
- Pipeline is linear (collect → screen → generate → …). If you later need branching (e.g. “needs clarification” vs “ready to generate”), the current long `if/elif` chain will be harder to extend; the “pipeline as list of steps” refactor would help.

---

## 4. Critical Fixes (Priority Order)

1. **~~Team cache and DB/credentials (critical)~~ — DONE**  
   - Request-scoped `TokenTracker(db)` and `GooglePhotosClient(credentials)` are now created per request in the routes and passed into `process_memory`, `confirm_reference_selection`, and `run_generation_from_stored_refs`. The cached team uses only these passed-in instances for token tracking and Google Photos, so it never uses a closed DB session or stale credentials.

2. **Wire guardrails into the pipeline**  
   - Before generation: run `ContentPolicyGuardrail.check_content()` on `state.extraction.what_happened` (and optionally who); if not approved, return a clear error and do not call the image API.  
   - Before creating a memory (or at session start): run `RateLimitGuardrail.check_rate_limit(user_id, db)` and return 429 if over limit.  
   - Use `TokenBudgetGuardrail` (or keep current `TokenTracker` usage) consistently so budgets are enforced in one place.

3. **~~list_memories user_id type~~ — DONE**  
   - `photos.py` now converts `user_id` to `uuid.UUID` with validation before filtering and returns 400 for invalid IDs. Consider a shared helper if other routes need the same.

4. **Config and deployment**  
   - Make `env_file` path robust (e.g. from project root or `__file__`).  
   - Use settings for OAuth redirect URI and frontend URL.  
   - Add a Dockerfile and, if needed, Alembic migrations.

5. **Security**  
   - Derive `user_id` from authenticated session/JWT where possible.  
   - Plan encryption at rest for OAuth tokens and document it in the deployment guide.

---

## 5. Summary Table

| Area           | Grade | Summary |
|----------------|-------|--------|
| Readability    | B+    | Clear names and structure; reduce magic strings and break up long methods. |
| Modularity     | B     | Good layout; orchestration and response building could be split further. |
| Documentation  | B     | Solid README and docstrings; add sequence diagram and screening/guardrail docs. |
| Error handling  | B-    | Good patterns; wire guardrails, narrow exception handling, add request IDs. |
| Consistency    | B     | Mostly consistent; fix user_id types and sync/async and import style. |
| Scalability    | B-    | Team/tracker/credentials fix done; move session and OAuth state to Redis/DB for horizontal scaling. |
| Reliability    | B     | Retries and partial failure handling; request-scoped tracker/client in place; add idempotency. |
| Security       | B     | Good image and CORS handling; harden user_id, tokens, and redirect URI. |
| Performance    | B     | Async ref image fetch, temp cleanup, and token accuracy would help. |
| Observability  | B-    | Good logging; add metrics and request IDs. |
| Deployment     | C+    | Docker Compose for DB/Redis; add app Dockerfile and migrations. |
| Extensibility  | B+    | Adding agents/tools is clear; pipeline-as-steps would make stages easier to extend. |
| Maintainability| B     | Centralize response building and env loading. |
| Testability    | C+    | Some unit tests; integration and E2E need implementation and mocks. |
| Agent lifecycle| B     | Document and add eviction or external session store. |
| Model management| C+    | Config-driven model names and a simple versioning strategy. |

Overall, the codebase is in good shape for a multi-agent product with clear separation of concerns and production-oriented features. The **team cache / DB session / credentials** issue and **list_memories user_id** bug have been fixed. **Next:** Wire **guardrail integration** into the pipeline for stronger correctness and security; the rest of the recommendations will improve scalability, operability, and long-term maintainability.

# MemAgent Project Rules

## Agno Agentic Application Standards

Follow these rules strictly when generating code, refactoring, or designing architecture for this MemAgent project.

### 1. Core Architecture Principles
- **Modularity:** Agents, Tools, Knowledge Bases, and Storage are separated into distinct modules
- **Agent Roles:** Every Agent has a clear `description` and `instructions`. No "God Agents" - use Team of specialized agents
- **Workflows vs. Agents:** Use Workflows for deterministic multi-step processes. Use Agents for autonomous, tool-heavy tasks

### 2. Technical Requirements
- **Storage:** Always use `AsyncSession` with `async_session_maker` for database operations
- **Type Hinting:** All Tool functions must have Python type hints and Google-style docstrings
- **Dependency Management:** Use `uv` for package management. Add dependencies via `uv add`
- **Python Version:** Requires Python 3.11+

### 3. Token Optimization (CRITICAL)
- **Never pass image data to LLMs:** Always use URLs, file paths, or media IDs
- **Image bytes processed by APIs only:** Not in agent context
- **Frontend displays images via URLs:** Keep image data out of backend-frontend transfers where possible
- **Per-agent token budgets:**
  - Memory Collector: 2,000 tokens
  - Content Screener: 500 tokens
  - Context Enricher: 1,500 tokens
  - Image Generator: 5,000 tokens
  - Photo Manager: 500 tokens
  - Orchestrator: 1,000 tokens
- **Session limit:** 15,000 tokens total
- **Daily limit:** 50,000 tokens per user

### 4. Security & Production Readiness
- **Environment Variables:** Never hardcode keys. Use `pydantic-settings`
- **Guardrails:** Every agent must include `pre_hooks` for:
  - `PromptInjectionGuardrail()`
  - `PIIDetectionGuardrail()` (for user data)
  - `ContentPolicyGuardrail()` (for image generation)
  - `TokenBudgetGuardrail()` (enforce limits)
- **Logging:** Use `structlog` for structured logging. No naked `print()` statements
- **OAuth:** Always refresh credentials before API calls. Store tokens encrypted in production

### 5. Documentation Standard
- Every Agent file must contain a header comment explaining:
  - Persona
  - Tools
  - Token Budget
  - Intended Outcome
  - Usage example
- Use Google-style docstrings for all functions
- Include type hints for all parameters and return values
- **NEVER create summary documents** (e.g., IMPLEMENTATION_SUMMARY.md, PORT_CONFIGURATION.md, etc.)
- Only update README.md with necessary documentation

### 6. Coding Style
- Use `Agent` class for all agents
- Use `markdown=True` for agent responses to ensure clean UI rendering
- Keep agent instructions concise but comprehensive
- Log all important operations with structured fields

### 7. Error Handling
- Always handle token budget exceeded errors gracefully
- Content policy violations should provide actionable feedback
- OAuth errors should prompt re-authentication
- Database errors should be logged with context

### 8. Testing Requirements
- Unit tests for each agent independently with mocked tools
- Integration tests for team orchestration
- E2E tests for full memory creation flow
- Use `pytest` with fixtures for database and OAuth mocks

## Project-Specific Rules

### Agent Development
- Agents should be stateless - state stored in database or passed through orchestrator
- Tools must return structured data (dicts, Pydantic models), not raw strings when possible
- Always track token usage after agent operations

### Database Operations
- Use async SQLAlchemy with proper session management
- Always use context managers for database sessions
- Index frequently queried fields (user_id, session_id, timestamps)

### API Development
- All endpoints require user authentication (user_id parameter)
- Use FastAPI dependency injection for database sessions
- Return structured Pydantic models from endpoints
- Include proper error handling with appropriate HTTP status codes

### File Structure
- Keep agents in `backend/app/agents/`
- Keep tools in `backend/app/tools/`
- Keep API routes in `backend/app/api/routes/`
- Keep schemas in `backend/app/schemas/`
- Keep storage models in `backend/app/storage/`

### Naming Conventions
- Agents: `create_{agent_name}_agent()` factory functions
- Tools: descriptive names ending in `_tool` for agent functions
- Routes: RESTful naming (nouns, not verbs)
- Database models: Singular nouns (User, Memory, not Users, Memories)

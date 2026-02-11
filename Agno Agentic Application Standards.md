# Agno Agentic Application Standards

Follow these rules strictly when generating code, refactoring, or designing architecture for this Agno (formerly Phidata) project.

## 1. Core Architecture Principles
- **Modularity:** Separate Agents, Tools, Knowledge Bases, and Storage into distinct modules.
- **Agent Roles:** Every Agent must have a clear `description` and `instructions`. Avoid "God Agents"; use a `Team` of specialized agents instead.
- **Workflows vs. Agents:** Use `Agno Workflows` for multi-step processes that require deterministic logic. Use `Agents` for autonomous, tool-heavy tasks.

## 2. Technical Requirements
- **Storage:** Never use default in-memory storage. Always implement `PostgresChatStorage` or `SqliteChatStorage` for session persistence.
- **Type Hinting:** All Tool functions (`@agent.tool`) must have Python type hints and detailed Google-style docstrings. Agno uses these to generate the JSON schema for the LLM.
- **Dependency Management:** Use `uv` for package management. Add new dependencies via `uv add`.

## 3. Security & Production Readiness
- **Environment Variables:** Never hardcode keys. Use `pydantic-settings` or `python-dotenv`.
- **Guardrails:** Every production agent must include `pre_hooks` for:
    - `PromptInjectionGuardrail()`
    - `PIIDetectionGuardrail()` (where applicable).
- **Logging:** Use Agno's built-in monitoring or structured logging. No naked `print()` statements.

## 4. Documentation Standard
- Every Agent file must contain a header comment explaining its Persona, Tools, and intended Outcome.
- Use Mermaid diagrams in `README.md` to visualize agent handoffs and team structures.

## 5. Coding Style
- Prefer `Assistant` class for UI-integrated agents and `Agent` for logic-heavy backends.
- Use `markdown` for agent responses whenever possible to ensure clean UI rendering.
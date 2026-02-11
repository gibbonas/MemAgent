# MemAgent: AI-Powered Memory Preservation System

A production-ready multi-agent AI application that captures user memories through quick, conversational chat, generates photorealistic images using Google's Gemini models, and uploads them to Google Photos with comprehensive EXIF metadata.

## ✨ Latest Updates (Feb 2026)

**🎯 Reference Photo Selection**
- Automatically fetches relevant photos from Google Photos based on memory details
- Shows photos matching the timeframe (±30 days) and content (people/pets)
- Interactive photo selector UI with thumbnail grid
- Selected photos guide the AI image generation for better accuracy
- Skip option if no reference photos needed

**🚀 Quick Conversational Memory Collection**
- Streamlined 2-3 exchange conversations (down from 4-6)
- Smart date calculation from natural language ("last summer", "2 years ago")
- Optional location handling - only asks when relevant
- Automatic pipeline progression from collection → generation
- 20% token reduction (~3,300 tokens per memory)

[View detailed changes →](./MEMORY_COLLECTION_UPDATES.md) | [Testing guide →](./TESTING_GUIDE.md)

## Features

- 🤖 **Multi-Agent Architecture**: Specialized agents for memory collection, content screening, context enrichment, image generation, and photo management
- 💬 **Quick Conversational Flow**: Efficiently gathers essential details in 2-3 exchanges
- 📅 **Smart Date Handling**: Calculates dates from relative expressions like "last Christmas" or "2 years ago"
- 🖼️ **Reference Photo Selection**: Browse and select photos from your Google Photos library to guide image generation
- 📸 **Google Photos Integration**: Search existing photos for references and upload generated images with full metadata
- 🎨 **AI Image Generation**: Photorealistic image generation using Gemini 2.5 Flash Image (Nano Banana)
- 🔒 **Production Security**: OAuth 2.0, guardrails for content policy and token budgets, structured logging
- 💾 **EXIF Metadata**: Comprehensive metadata embedding including DateTime, GPS coordinates, IPTC keywords
- ⚡ **Token Optimization**: Efficient token usage with URL-based image handling (never passes image bytes to LLMs)

## Architecture

```
MemAgent/
├── backend/          # FastAPI + Agno agents
│   ├── app/
│   │   ├── agents/   # Specialized Agno agents
│   │   ├── tools/    # Google Photos, EXIF writer, image generation
│   │   ├── api/      # FastAPI routes
│   │   ├── core/     # Security, monitoring, guardrails
│   │   └── storage/  # Database models
│   └── tests/
└── frontend/         # Next.js 14 chat interface with TypeScript
```

### Agent Pipeline

```
User Story → Memory Collector (2-3 exchanges) → Reference Photo Selection
  → Content Screener → Image Generator → Photo Manager → Google Photos
```

**Reference Photo Selection Stage**
- Automatically searches Google Photos based on extracted memory details
- Date-based search: ±30 days from memory date
- Content-based search: People and pets mentioned in memory
- User selects 0-15 reference photos to guide generation
- Skip option for when no references are needed

**Automatic Progression**
- Once memory details are collected, pipeline automatically proceeds
- No manual intervention needed between stages
- Real-time status updates to frontend

## Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- Google Cloud Project with:
  - Gemini API access
  - Google Photos Library API enabled
  - **Google Photos Picker API** enabled (for reference photo selection; enable in [APIs & Services](https://console.cloud.google.com/apis/library))
  - OAuth 2.0 credentials

## Quick Start

### 1. Backend Setup

```bash
cd backend

# Create virtual environment with uv
uv venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies (already done if you followed setup)
uv add agno fastapi "uvicorn[standard]" sqlalchemy pydantic pydantic-settings \
  google-auth google-auth-oauthlib google-api-python-client \
  pillow piexif aiosqlite asyncpg structlog tiktoken

# Install dev dependencies
uv add --dev pytest pytest-asyncio httpx
```

### 2. Configure Environment

Update `.env.local` in the project root:

```bash
# Google API Keys
GOOGLE_API_KEY=your_gemini_api_key
GOOGLE_AUTH_CLIENT_ID=your_oauth_client_id
GOOGLE_AUTH_CLIENT_SECRET=your_oauth_client_secret

# Database
DATABASE_URL=sqlite+aiosqlite:///./memagent.db

# Security
SECRET_KEY=generate_a_random_secret_key

# CORS
CORS_ORIGINS=http://localhost:3002,http://localhost:8000

# Logging
LOG_LEVEL=INFO

# Token Budgets
MAX_TOKENS_PER_SESSION=15000
MAX_TOKENS_PER_USER_DAILY=50000
TOKEN_WARNING_THRESHOLD=0.8

# Rate Limiting
MAX_MEMORIES_PER_DAY=10

# Storage
TEMP_IMAGE_DIR=./tmp/images
```

### 3. Initialize Database

```bash
# Database will be auto-created on first run
# For PostgreSQL in production:
# 1. Start PostgreSQL: docker-compose up -d postgres
# 2. Update DATABASE_URL in .env.local:
#    DATABASE_URL=postgresql+asyncpg://memagent:password@localhost/memagent
```

### 4. Run Backend

**Option 1: Using the dev server script (Recommended for Windows)**

```bash
cd backend
uv run python dev_server.py
```

**Option 2: Using uvicorn directly**

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

> **Note for Windows users:** If Ctrl+C hangs the terminal when using Option 2, use Option 1 (dev_server.py) which has better signal handling, or press Ctrl+C twice quickly.

Backend will be available at: `http://localhost:8000`

API docs: `http://localhost:8000/docs`

### 5. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at: `http://localhost:3002`

**Features:**
- Modern, responsive chat interface
- Google OAuth integration
- Real-time message exchange
- Image preview for generated memories
- Status indicators and error handling
- Session persistence

## API Endpoints

### Authentication
- `GET /api/auth/google` - Initiate OAuth flow
- `GET /api/auth/callback` - OAuth callback
- `GET /api/auth/status?user_id=...` - Check auth status
- `POST /api/auth/logout?user_id=...` - Logout

### Chat
- `POST /api/chat/message` - Send message to agents
- `GET /api/chat/sessions/{session_id}` - Get session history
- `POST /api/chat/sessions` - Create new session

### Photos
- `GET /api/photos/suggestions?user_id=...&start_date=...` - Get photo suggestions
- `GET /api/photos/memories?user_id=...` - List saved memories
- `POST /api/photos/upload` - Upload reference photo

## Token Optimization

MemAgent is designed for cost-effective operation:

### Expected Token Usage Per Memory (Updated Feb 2026)
| Agent | Tokens | Notes |
|-------|--------|-------|
| Memory Collector | 800-1,200 | Quick 2-3 exchange conversation |
| Content Screener | 300-500 | Quick validation |
| Context Enricher | 500-1,000 | Metadata only, no images |
| Image Generator | 1,290-2,000 | Fixed 1,290 for gen + prompt |
| Photo Manager | 200-500 | Minimal LLM use |
| Orchestrator | 300-500 | Coordination logic |
| **Total** | **3,390-5,700** | Per successful memory (20% reduction) |

### Key Optimizations
- **Faster collection**: 2-3 exchanges instead of 4-6 saves ~500-800 tokens
- Images handled as URLs/paths only (never base64 in LLM context)
- Content screening before expensive operations
- Conversation state keeps only last 3 exchanges
- Per-agent and per-session token budgets
- Graceful degradation at 80% threshold

## Security Features

### Guardrails
- **PromptInjectionGuardrail**: Detects injection attempts
- **PIIDetectionGuardrail**: Warns on sensitive data
- **ContentPolicyGuardrail**: Pre-validates content before image generation
- **TokenBudgetGuardrail**: Enforces token limits
- **ImageDataGuardrail**: Ensures no image bytes in LLM context
- **RateLimitGuardrail**: Prevents abuse (10 memories/day default)

### OAuth & Data Protection
- Google OAuth 2.0 with automatic token refresh
- Credentials stored in database (encrypt in production)
- HTTPS required in production
- CORS properly configured

## Development

### Project Structure Follows Agno Best Practices

- **Modularity**: Agents, Tools, and Storage in separate modules
- **Clear Agent Roles**: Each agent has specific persona and responsibilities
- **Token Efficiency**: URL-based image handling throughout
- **Production Ready**: Logging, monitoring, error handling

### Adding New Agents

1. Create agent file in `backend/app/agents/`
2. Define clear persona, tools, and token budget
3. Use `create_{agent_name}_agent()` factory pattern
4. Add to team orchestration in `team.py`
5. Update documentation

### Testing

```bash
cd backend
uv run pytest
```

## Production Deployment

### Option 1: Google Cloud Run (Recommended)
- Natural fit with Google Photos API
- Auto-scaling and managed infrastructure
- Cloud SQL for PostgreSQL

### Option 2: Docker Compose
```bash
docker-compose up -d
```

### Environment Variables for Production
- Use strong `SECRET_KEY`
- Enable HTTPS
- Use PostgreSQL instead of SQLite
- Set appropriate CORS origins
- Enable encryption for OAuth tokens
- Configure proper logging/monitoring

## Token Usage Monitoring

Monitor token usage through structured logs:

```json
{
  "event": "token_usage",
  "user_id": "...",
  "agent": "memory_collector",
  "tokens": 1500,
  "session_total": 3200,
  "daily_total": 8400
}
```

## Troubleshooting

### OAuth Issues
- Ensure redirect URI matches in Google Cloud Console: `http://localhost:8000/api/auth/callback`
- Check that Photos Library API and **Google Photos Picker API** are enabled
- If reference photo selection returns 401: have the user **sign out and sign in again** so the new Picker scope is granted
- Verify client ID and secret in `.env.local`

### Database Issues
- For SQLite: Ensure write permissions in project directory
- For PostgreSQL: Check connection string and database exists

### Token Budget Exceeded
- Increase limits in `.env.local` if needed
- Review agent efficiency in logs
- Check for unnecessary retries

## License

Proprietary - All rights reserved

## Support

For issues and questions, please refer to the project documentation or contact the development team.

# MemAgent: Deploying Frontend (Vercel) and Backend Separately

You can deploy from this **single repo (monorepo)** without splitting it: Vercel deploys the frontend from the `frontend/` directory, and the backend is deployed elsewhere (Cloud Run, Railway, Render, Fly.io, etc.) using the same repo.

---

## 1. Deploy frontend to Vercel

### From the monorepo

1. In [Vercel](https://vercel.com), **Import** your Git repository (this repo).
2. In **Project Settings → General**:
   - **Root Directory:** set to `frontend` (so Vercel only builds the Next.js app).
   - Leave **Framework Preset** as Next.js.
3. **Environment variables** (Settings → Environment Variables):
   - `NEXT_PUBLIC_API_URL` = your backend API URL (e.g. `https://your-backend.fly.dev` or `https://api.yourdomain.com`).
     - Use the **production** backend URL; Vercel will use it at build time for any `NEXT_PUBLIC_*` usage.
4. Deploy. The frontend will call the backend using `NEXT_PUBLIC_API_URL`.

### Notes

- The frontend is a client-side app that talks to your backend over HTTPS. No server-side secrets are required in Vercel beyond `NEXT_PUBLIC_API_URL`.
- After the first deploy, note your Vercel URL (e.g. `https://memagent.vercel.app`) — you’ll use it for backend CORS and OAuth.

---

## 2. Deploy backend separately

The backend is a FastAPI app. You can run it with Docker (recommended) or with a Python host (e.g. Cloud Run, Railway, Render, Fly.io).

### Build and run with Docker (from repo root)

```bash
# From the repository root (MemAgent/)
docker build -f backend/Dockerfile -t memagent-backend .
docker run -p 8000:8000 \
  -e BACKEND_URL=https://your-backend.example.com \
  -e FRONTEND_URL=https://memagent.vercel.app \
  -e CORS_ORIGINS=https://memagent.vercel.app \
  -e GOOGLE_API_KEY=... \
  -e GOOGLE_AUTH_CLIENT_ID=... \
  -e GOOGLE_AUTH_CLIENT_SECRET=... \
  -e SECRET_KEY=... \
  -e DATABASE_URL=postgresql+asyncpg://... \
  memagent-backend
```

Build context must be the **repo root** so that `COPY backend/` in the Dockerfile works.

### Backend environment variables (production)

Set these on your backend host (Cloud Run, Railway, Render, etc.):

| Variable | Required | Description |
|----------|----------|-------------|
| `BACKEND_URL` | Yes | Public URL of this API, no trailing slash (e.g. `https://api.yourdomain.com`). Used for OAuth callback and image URLs. |
| `FRONTEND_URL` | Yes | Frontend URL (e.g. `https://memagent.vercel.app`). Used for OAuth redirect after login. |
| `CORS_ORIGINS` | Yes | Comma-separated list of allowed origins (include your Vercel URL). Example: `https://memagent.vercel.app,https://www.yourdomain.com` |
| `GOOGLE_API_KEY` | Yes | Gemini API key |
| `GOOGLE_AUTH_CLIENT_ID` | Yes | Google OAuth client ID |
| `GOOGLE_AUTH_CLIENT_SECRET` | Yes | Google OAuth client secret |
| `SECRET_KEY` | Yes | Strong random secret for session/signing |
| `DATABASE_URL` | Yes | PostgreSQL recommended: `postgresql+asyncpg://user:pass@host/db` (or SQLite for minimal setups) |
| `LOG_LEVEL` | No | e.g. `INFO` |
| `TEMP_IMAGE_DIR` | No | Default `./tmp/images`; ensure writable in container |

### Google Cloud Console (OAuth)

1. **APIs & Services → Credentials → your OAuth 2.0 Client**
2. **Authorized redirect URIs:** add your production callback:
   - `https://<your-backend-url>/api/auth/callback`
   - Example: `https://api.yourdomain.com/api/auth/callback`
3. **Authorized JavaScript origins:** add your frontend URL (e.g. `https://memagent.vercel.app`).

Without this, production OAuth will fail with redirect_uri_mismatch.

---

## 3. Order of operations

1. Deploy the **backend** first and note its public URL.
2. In Google Cloud Console, add the **production** redirect URI and frontend origin.
3. Deploy the **frontend** on Vercel with `NEXT_PUBLIC_API_URL` set to the backend URL.
4. Set backend `FRONTEND_URL` and `CORS_ORIGINS` to your Vercel (or custom) frontend URL.

---

## 4. Example: Backend on Cloud Run

```bash
# From repo root
gcloud run deploy memagent-backend \
  --source . \
  --region us-central1
```

If using the Dockerfile instead of source build:

```bash
docker build -f backend/Dockerfile -t gcr.io/YOUR_PROJECT/memagent-backend .
docker push gcr.io/YOUR_PROJECT/memagent-backend
gcloud run deploy memagent-backend --image gcr.io/YOUR_PROJECT/memagent-backend ...
```

Set the environment variables above in Cloud Run (Console or `gcloud run services update ... --set-env-vars`).

---

## 5. Do you need to split the repo?

No. Keeping frontend and backend in one repo is fine:

- **Vercel:** Root Directory = `frontend` so only the Next.js app is built and deployed.
- **Backend:** Either build from repo root with `docker build -f backend/Dockerfile .` or point your PaaS at the `backend/` directory if it supports a subdirectory (e.g. Railway, Render).

If you later split into two repos (e.g. `memagent-frontend` and `memagent-backend`), you would:

- Point Vercel at the frontend repo (no Root Directory change needed).
- Point your backend host at the backend repo and adjust the Dockerfile so `COPY . .` is from the repo root of that repo.

The same environment variables and Google OAuth setup apply in both setups.

# Security Best Practices - MemAgent

## Current Security Status

### ✅ Implemented
- **CORS Configuration**: Uses explicit origins from environment variables, not wildcards
- **OAuth 2.0**: Google OAuth for authentication
- **Environment Variables**: Sensitive data stored in `.env.local` (not committed to git)
- **HTTPS Ready**: FastAPI supports HTTPS in production
- **Input Validation**: Pydantic models validate all API inputs
- **Token Tracking**: Monitor and limit AI token usage per user
- **Rate Limiting**: Configurable limits on memories per day

### ⚠️ Development Mode (Current)
The following are configured for local development:
- HTTP (not HTTPS) - acceptable for localhost
- CORS allows `http://localhost:3002` and `http://localhost:8000`
- OAuth tokens stored unencrypted in SQLite database

## Production Security Checklist

Before deploying to production, implement these security measures:

### 1. HTTPS/TLS
```bash
# Use a reverse proxy like nginx or deploy to a platform that handles TLS
# Update CORS_ORIGINS in .env.local to use https://
CORS_ORIGINS=["https://yourdomain.com","https://api.yourdomain.com"]
```

### 2. Environment Variables
```bash
# Generate a strong secret key
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Use production database
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/memagent

# Update origins
FRONTEND_URL=https://yourdomain.com
CORS_ORIGINS=["https://yourdomain.com"]
```

### 3. Database Security
- [ ] Use PostgreSQL instead of SQLite
- [ ] Enable SSL/TLS for database connections
- [ ] Encrypt OAuth tokens at rest (add encryption layer)
- [ ] Regular backups with encryption
- [ ] Rotate database credentials periodically

### 4. API Security

#### Rate Limiting
Already configured but can be adjusted:
```python
# .env.local
MAX_MEMORIES_PER_DAY=10  # Adjust based on your needs
```

#### Additional Headers (Add to main.py)
```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Only allow requests from your domain
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["yourdomain.com", "www.yourdomain.com"]
)
```

#### Security Headers
Add to nginx or use Starlette middleware:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
```

### 5. OAuth Security
- [ ] Use HTTPS for OAuth redirect URIs
- [ ] Implement token encryption at rest
- [ ] Rotate refresh tokens periodically
- [ ] Add token revocation on logout
- [ ] Monitor for suspicious OAuth activity

### 6. Input Validation
Already implemented with Pydantic, but verify:
- [ ] Max length limits on all text inputs
- [ ] Sanitize file uploads
- [ ] Validate image files before processing
- [ ] Check for SQL injection attempts (SQLAlchemy handles this)

### 7. Logging and Monitoring
- [ ] Use structured logging (already implemented with structlog)
- [ ] Set up log aggregation (ELK, Datadog, etc.)
- [ ] Monitor for suspicious activity patterns
- [ ] Alert on unusual token usage
- [ ] Track failed authentication attempts

### 8. Dependency Security
```bash
# Regularly update dependencies
uv pip list --outdated

# Audit for known vulnerabilities
pip install safety
safety check

# Use dependabot or similar for automated updates
```

### 9. API Documentation Access
In production, restrict API docs access:
```python
# main.py
app = FastAPI(
    title="MemAgent API",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,  # Disable in production
    redoc_url="/redoc" if settings.debug else None,
)
```

### 10. Frontend Security

#### Content Security Policy
Add to frontend response headers:
```html
<meta http-equiv="Content-Security-Policy" 
      content="default-src 'self'; 
               script-src 'self' 'unsafe-inline' 'unsafe-eval'; 
               style-src 'self' 'unsafe-inline'; 
               img-src 'self' data: https:; 
               connect-src 'self' https://yourdomain.com;">
```

#### Environment Variables
```bash
# frontend/.env.production
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

## Google Cloud Platform Security

If deploying to GCP (recommended for Google Photos integration):

### Cloud Run
- Enable HTTPS by default ✓
- Use Cloud SQL for PostgreSQL
- Use Secret Manager for sensitive data
- Enable Cloud Armor for DDoS protection
- Set up IAM roles correctly

### OAuth Configuration
1. Add production redirect URIs in Google Cloud Console
2. Restrict API keys to specific domains
3. Enable Google Photos Library API
4. Set up OAuth consent screen for production

## Security Incident Response

### If OAuth Tokens Compromised
1. Revoke all user tokens immediately
2. Force re-authentication for all users
3. Investigate access logs
4. Notify affected users
5. Rotate OAuth client secrets

### If Database Compromised
1. Take database offline immediately
2. Rotate all credentials
3. Restore from clean backup
4. Audit for data exfiltration
5. Implement additional security measures

## Compliance

### GDPR (if serving EU users)
- [ ] Add privacy policy
- [ ] Implement data deletion on request
- [ ] Add consent management
- [ ] Data processing agreement with Google
- [ ] Regular security audits

### Data Retention
- [ ] Define retention policies
- [ ] Implement automatic data cleanup
- [ ] Secure data deletion procedures

## Security Testing

Before production deployment:
```bash
# Run security scan
bandit -r backend/

# Test for common vulnerabilities
pytest tests/security/

# Load testing
locust -f tests/load/locustfile.py

# Penetration testing (hire professional)
# OWASP ZAP or similar tools
```

## Current CORS Configuration

The CORS configuration is **already secure** for development:

```python
# Uses environment variable from .env.local
CORS_ORIGINS=["http://localhost:3002","http://localhost:8000"]

# In main.py:
allow_origins=settings.cors_origins  # NOT ["*"]
allow_credentials=True  # Required for OAuth
allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]  # Explicit list
```

### Why This Is Secure
1. ✅ **Explicit Origins**: Only listed domains can make requests
2. ✅ **No Wildcards**: Never uses `["*"]` with credentials
3. ✅ **Configurable**: Change origins via environment variable
4. ✅ **Credentials Enabled**: Required for OAuth cookies/sessions
5. ✅ **Explicit Methods**: Only allows specific HTTP methods
6. ✅ **Preflight Caching**: Reduces OPTIONS requests

### For Production
Simply update `.env.local`:
```bash
CORS_ORIGINS=["https://yourdomain.com"]
FRONTEND_URL=https://yourdomain.com
```

## Questions?

For security concerns or questions, consult:
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Next.js Security](https://nextjs.org/docs/pages/building-your-application/configuring/environment-variables)

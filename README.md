# Xylon Growth Agent (MVP)

AI-assisted B2B lead research → website audit → opportunity analysis → human-approved outreach → CRM.

## Project structure
```
backend/
  app/main.py            FastAPI app, CORS, rate limiting, error handling
  app/config.py          Env-based settings (no hard-coded keys)
  app/models.py          users, companies, contacts, leads, research_reports, website_audits,
                         opportunities, outreach_messages, followups, activities
  app/security.py        bcrypt + JWT auth
  app/routers/           auth.py · leads.py (finder, CRM, research/audit/opportunity/outreach actions)
                         outreach.py (approval gate + send) · misc.py (dashboard, follow-ups)
  app/services/          one module per pipeline stage:
    lead_finder.py  (Lead Researcher)   researcher.py (Company Researcher)
    auditor.py      (Website Auditor)   opportunity.py (Opportunity Analyzer)
    outreach.py     (Outreach Generator)  CRM Manager = routers/leads.py + models
    fetcher.py (SSRF-safe scraping) · sanitize.py (prompt-injection defences) · ai_client.py · catalog.py · jobs.py
  tests/test_core.py
frontend/  Vite + React: Dashboard, Leads, Find Leads, Lead detail (tabs), Research, Website Audits,
           Outreach, Follow-ups, Settings
```

## Setup
**Prereqs:** Python 3.11+, Node 18+, PostgreSQL (local or Supabase), an OpenAI API key.

### Environment variables (backend/.env, copy from .env.example)
`DATABASE_URL`, `JWT_SECRET`, `OPENAI_API_KEY` (required); `OPENAI_MODEL`, `CORS_ORIGINS`, `ALLOW_REGISTRATION`,
`CACHE_DAYS`, `SENDER_NAME`, `SMTP_HOST/PORT/USER/PASSWORD/FROM` (optional).

### Database
Create an empty Postgres database (or a Supabase project and paste its connection string into `DATABASE_URL`).
Tables are created automatically on first backend start. Add Alembic before changing the schema in production.

### Run backend
```
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit
uvicorn app.main:app --reload --port 8000
```
### Run frontend
```
cd frontend && npm install && npm run dev      # http://localhost:5173 (proxies /api to :8000)
```
### Test
`cd backend && pytest` (auditor, contact extraction, prompt-injection sanitiser, SSRF block, auth/isolation).
Manual: register → Find Leads ("Dental clinics", "United Kingdom", 5) → open a lead → Research → Audit →
Find opportunities → Generate Outreach → Edit → Approve → Send/Mark as sent.

## API endpoints
```
POST /api/auth/register · POST /api/auth/login · GET /api/auth/me
POST /api/leads/find (202, job_id) · GET /api/jobs/{id}
GET  /api/leads?q=&status=&country=&sort=&order= · GET/PATCH /api/leads/{id}
POST /api/leads/{id}/research · /audit · /opportunities · /outreach
GET  /api/outreach · PATCH /api/outreach/{id} · POST /api/outreach/{id}/approve · /send
GET  /api/dashboard · GET/POST /api/followups · POST /api/followups/{id}/done · GET /api/health
```

## How the "no fabrication" rules are enforced in code
- Emails/phones/LinkedIn come from regex over fetched pages only; the model is never asked for them.
- Research facts need a `source_url` that was fetched or returned by the search tool; unsourced claims are demoted to "AI inference".
- Website score uses deterministic checks; unmeasurable checks are excluded and listed as "not assessed".
- Opportunities must cite real check/fact ids and a catalogue service; evidence text is attached by our code, not the model.
- Outreach is DRAFT → APPROVED (edits reset approval) → SENT. No bulk send exists. Email adds an opt-out line.
- Scraped text is sanitised, delimited as untrusted data, and all model output is validated before storage.

## Known limits / next steps
1. Add Alembic migrations; move the in-memory job store to Redis or n8n (webhook endpoints are easy to add around `services/`).
2. Move JWT from localStorage to httpOnly cookies; add refresh tokens, email verification, password reset.
3. Respect robots.txt in the fetcher; add per-domain throttling; handle JS-rendered sites (headless browser).
4. Optional PageSpeed Insights integration for real Core Web Vitals.
5. Wire LinkedIn/WhatsApp via official APIs; add reply tracking; then Recruitment Agent / Proposal Generator as new `services/` modules.
6. The OpenAI web_search tool and model name should be confirmed against your account; the live AI paths were not run here (no key), only the deterministic parts are tested.

# Earthquake Alerts - Project Context

## Overview
A serverless earthquake monitoring application that fetches earthquake data from USGS and sends configurable alerts to Slack and Twitter/X. Designed for deployment on Google Cloud Platform (Cloud Functions + Firestore).

**Live Twitter**: [@quake_alerts](https://x.com/quake_alerts) - Automated earthquake alerts for the Bay Area

---

## ⚠️ ULTRA-SENSITIVE CODE - NOTIFICATION SYSTEM

**THE FOLLOWING FILES SEND REAL NOTIFICATIONS TO PRODUCTION CHANNELS. MISTAKES HERE WILL SPAM USERS AND DAMAGE THE SERVICE'S REPUTATION.**

### Critical Files (Require Extra Caution)
| File | Risk | Description |
|------|------|-------------|
| `src/core/formatter.py` | 🔴 HIGH | Formats ALL alert messages (Slack, Twitter, WhatsApp) |
| `src/shell/slack_client.py` | 🔴 HIGH | Sends to real Slack channels |
| `src/shell/twitter_client.py` | 🔴 HIGH | Posts to @quake_alerts (public!) |
| `src/shell/whatsapp_client.py` | 🔴 HIGH | Sends to real phone numbers |
| `src/orchestrator.py` | 🔴 HIGH | Orchestrates all alert sending |
| `scripts/send_test_alert.py` | 🟡 MEDIUM | Test alerts - can spam if misconfigured |
| `.github/workflows/test-alert.yml` | 🟡 MEDIUM | Triggers test alerts |

### Mandatory Requirements Before Modifying Alert Code

1. **RUN ALL TESTS FIRST**: `pytest tests/ -v` - ALL tests must pass
2. **VERIFY BACKWARDS COMPATIBILITY**: Any new parameters MUST have safe defaults
3. **CHECK FOR UNINTENDED SENDS**: Trace the full code path to ensure alerts only go where intended
4. **TEST WITH DRY-RUN FIRST**: Use `--dry-run` flag when available
5. **NEVER REMOVE SAFEGUARDS**: Deduplication, rate limiting, and channel filtering exist for a reason

### Test Requirements for Alert Code Changes

Any PR modifying alert-related code MUST include:
- [ ] Unit tests for ALL new/modified formatting functions
- [ ] Tests verifying default behavior is unchanged (backwards compatibility)
- [ ] Tests for edge cases (empty data, missing fields, malformed input)
- [ ] Integration test showing the full alert path (if adding new channels)

### Common Mistakes to Avoid
- ❌ Adding parameters without defaults (breaks existing callers)
- ❌ Changing message format without testing all channels
- ❌ Modifying channel iteration logic without testing dedup
- ❌ Updating test alert scripts that send to production channels
- ❌ Forgetting to pass `is_test=True` in test alert code

---

## Architecture Pattern: Functional Core, Imperative Shell

This project strictly follows the **Functional Core, Imperative Shell** pattern from the [Google Testing Blog](https://testing.googleblog.com/2025/10/simplify-your-code-functional-core.html).

### Key Principles
1. **Functional Core** (`src/core/`): Pure functions with no side effects
   - All business logic lives here
   - No I/O, no network calls, no database access
   - Easy to test without mocks
   - Deterministic: same input always produces same output

2. **Imperative Shell** (`src/shell/`): Handles all I/O and side effects
   - USGS API client (HTTP)
   - Slack webhook client (HTTP)
   - Twitter/X API client (OAuth 1.0a)
   - WhatsApp client via Twilio
   - Firestore client (database)
   - Secret Manager client (credentials)
   - Configuration loading (environment/files)
   - Keep this layer thin and simple

3. **Orchestrator** (`src/orchestrator.py`): Wires core and shell together
   - Fetches data via shell
   - Processes via core
   - Sends results via shell

### Why This Matters
- Core logic can be unit tested with simple assertions (fast, no mocks)
- Shell components need fewer integration tests
- Business logic is portable and reusable
- Side effects are contained and predictable

## Project Structure
```
earthquake-alerts/
├── CLAUDE.md                 # This file
├── README.md                 # User documentation
├── main.py                   # Root entry point for Cloud Function
├── env-vars.yaml             # Environment variables for deployment
├── config/
│   ├── config.example.yaml   # Example configuration
│   └── config.yaml           # Local config (gitignored)
├── api/                      # FastAPI service (Cloud Run)
│   ├── main.py               # FastAPI application with API endpoints
│   ├── requirements.txt      # Minimal deps (fastapi, uvicorn, requests)
│   └── Dockerfile            # Container config
├── src/
│   ├── core/                 # FUNCTIONAL CORE (pure functions)
│   │   ├── earthquake.py     # Earthquake data models & parsing
│   │   ├── geo.py            # Distance/vicinity calculations
│   │   ├── rules.py          # Alert rule evaluation
│   │   ├── formatter.py      # Message formatting
│   │   └── dedup.py          # Deduplication logic
│   ├── shell/                # IMPERATIVE SHELL (I/O & effects)
│   │   ├── usgs_client.py    # USGS API client
│   │   ├── slack_client.py   # Slack webhook client
│   │   ├── twitter_client.py # Twitter/X API client (OAuth 1.0a)
│   │   ├── whatsapp_client.py # WhatsApp via Twilio
│   │   ├── firestore_client.py # Firestore for deduplication
│   │   ├── secret_manager_client.py # Secret Manager for secrets
│   │   └── config_loader.py  # Config loading
│   ├── orchestrator.py       # Wires core + shell
│   └── main.py               # Cloud Function entry point
├── web/                      # Next.js frontend (Cloud Run)
│   ├── app/                  # App Router pages
│   ├── lib/api.ts            # API client
│   └── Dockerfile            # Container config
├── tests/
│   ├── core/                 # Unit tests (fast, no mocks)
│   └── shell/                # Integration tests
├── .github/workflows/
│   ├── ci.yml                # PR checks (tests + API sanity)
│   └── deploy.yml            # Deploy to GCP
├── requirements.txt
└── pyproject.toml
```

## Data Flow
```
Cloud Scheduler (cron)
        │
        ▼
┌─────────────────┐
│ Cloud Function  │
│   main.py       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│  Orchestrator   │────▶│ USGS Client  │──▶ USGS API
└────────┬────────┘     └──────────────┘
         │
         ▼
┌─────────────────┐
│ Functional Core │
│ - Parse quakes  │
│ - Apply rules   │
│ - Check dedup   │
│ - Format msgs   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│  Orchestrator   │────▶│Firestore     │──▶ Dedup State
└────────┬────────┘     └──────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│  Orchestrator   │────▶│ Slack Client │──▶ Slack Webhooks
│                 │     └──────────────┘
│                 │     ┌──────────────┐
│                 │────▶│Twitter Client│──▶ Twitter/X API
│                 │     └──────────────┘
│                 │     ┌──────────────┐
│                 │────▶│WhatsApp Client│──▶ Twilio API
└─────────────────┘     └──────────────┘
```

## Configuration
- **Secret Manager (Recommended)**: Store sensitive webhook URLs in GCP Secret Manager
  - Use `${secret:SECRET_NAME}` syntax in YAML config files
  - Keeps secrets out of version control
  - Handled by `SecretManagerClient` in the shell layer
- **Environment variables**: Non-sensitive configuration
  - Set in `env-vars.yaml` for deployment (safe to commit)
  - Supports simple mode with bounds and thresholds
- **YAML config**: Regions, channels, rules
  - `config/config-production.yaml` for deployment (uses Secret Manager)
  - `config/config.yaml` for local development (gitignored)

## Key Design Decisions
1. **Firestore for deduplication**: Serverless, scales to zero, cheap for low-volume key-value lookups
   - Uses named database (`earthquake-alerts`) to avoid conflicts with default Datastore Mode database
   - Supports both default and named databases via configuration
2. **Cloud Functions**: Event-driven, pay-per-use, triggered by Cloud Scheduler
3. **Webhook-based Slack**: Simple, no OAuth flow, just POST to URL
4. **Twitter/X via OAuth 1.0a**: Uses Twitter API v2 with user context authentication
   - Credentials stored in Secret Manager
   - Tweets formatted to 280 char limit with prioritized content
5. **WhatsApp via Twilio**: Uses Twilio's WhatsApp Business API
   - Supports sending to multiple recipients (groups)
   - Rich message formatting with emojis
6. **USGS FDSN API**: Supports custom bounding boxes and time ranges

## Testing Strategy
- **Core tests**: Fast unit tests, no mocks needed, test pure logic
- **Shell tests**: Integration tests with real or mocked external services
- **Run tests**: `pytest tests/`

## Deployment
See README.md for full deployment instructions.

## Development Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Local testing
python -c "from src.main import earthquake_monitor; earthquake_monitor(None, None)"

# GCP Setup (first time)
gcloud services enable cloudfunctions.googleapis.com firestore.googleapis.com cloudscheduler.googleapis.com cloudbuild.googleapis.com
gcloud firestore databases create --location=us-central1 --type=firestore-native --database=earthquake-alerts

# Deploy to GCP
gcloud functions deploy earthquake-monitor \
  --gen2 \
  --runtime python311 \
  --region us-central1 \
  --trigger-http \
  --entry-point earthquake_monitor \
  --env-vars-file env-vars.yaml

# Create Cloud Scheduler job
gcloud scheduler jobs create http earthquake-monitor-scheduler \
  --location us-central1 \
  --schedule "*/5 * * * *" \
  --uri "https://REGION-PROJECT.cloudfunctions.net/earthquake-monitor" \
  --http-method POST
```

## Adding New Features

### Adding a New Notification Channel
1. Create new client in `src/shell/` (e.g., `discord_client.py`)
2. Add channel type to config schema
3. Update orchestrator to route to new client
4. Core logic remains unchanged

**Supported channel types:**
- `slack` - Slack incoming webhooks
- `twitter` - Twitter/X API (OAuth 1.0a)
- `whatsapp` - WhatsApp via Twilio

**Twitter channel config example:**
```yaml
- name: "quake-alerts-twitter"
  type: twitter
  credentials:
    api_key: "${secret:twitter-api-key}"
    api_secret: "${secret:twitter-api-secret}"
    access_token: "${secret:twitter-access-token}"
    access_token_secret: "${secret:twitter-access-token-secret}"
  rules:
    min_magnitude: 3.0
```

**WhatsApp channel config example:**
```yaml
- name: "earthquake-whatsapp"
  type: whatsapp
  credentials:
    account_sid: "${secret:twilio-account-sid}"
    auth_token: "${secret:twilio-auth-token}"
    from_number: "+14155238886"
    to_numbers:
      - "+1234567890"
      - "+0987654321"
  rules:
    min_magnitude: 4.0
```

### Adding New Alert Rules
1. Add rule evaluation logic to `src/core/rules.py` (pure function)
2. Add corresponding config options
3. Write unit tests for new rules
4. No changes to shell needed

## Web Frontend (earthquake.city)

The `web/` directory contains a Next.js 15 application for earthquake.city - a mobile-first landing page with Stripe-like aesthetics.

**Live Site**: [earthquake.city](https://earthquake.city)

### Web Architecture
```
earthquake.city/[locale]  (e.g., /sanramon, /bayarea, /la)
         │
         ▼
┌─────────────────────────┐
│   Next.js on Cloud Run  │
│   (earthquake-city)     │
│   - Static generation   │
│   - Client-side fetch   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  FastAPI on Cloud Run   │
│  (earthquake-api)       │
│  - /api-latest-earthquake│
│  - /api-recent-earthquakes│
│  - /api-locales         │
│  - /health              │
└─────────────────────────┘
```

### Web Stack
- **Framework**: Next.js 15 (App Router)
- **Styling**: Tailwind CSS
- **Globe**: Globe.gl (WebGL 3D visualization)
- **Hosting**: GCP Cloud Run

### API Service (api/)

The API is a separate FastAPI service deployed to Cloud Run. This architecture was chosen over Cloud Functions for:
- **Faster cold starts**: ~100ms vs 300-450ms
- **Single deployment**: 1 service vs 3 functions
- **Minimal dependencies**: 3 packages vs 10

### API Endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /api-latest-earthquake?locale=X` | Latest earthquake for a locale |
| `GET /api-recent-earthquakes?locale=X&limit=N` | Recent earthquakes (max 50) |
| `GET /api-locales` | List all available locales |
| `GET /health` | Health check |

### Supported Locales
- `sanramon` - San Ramon, CA
- `bayarea` - San Francisco Bay Area
- `la` - Los Angeles, CA

### Web Development Commands
```bash
cd web

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Deploy to Cloud Run
gcloud run deploy earthquake-city \
  --source . \
  --region us-central1 \
  --set-env-vars "NEXT_PUBLIC_API_URL=https://earthquake-api-793997436187.us-central1.run.app"
```

### API Development Commands
```bash
cd api

# Run locally
pip install -r requirements.txt
uvicorn main:app --reload

# Deploy to Cloud Run
gcloud run deploy earthquake-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

## CI/CD

### GitHub Actions Workflows

**ci.yml** - Runs on pull requests:
- `test` job: Unit tests with pytest
- `api-sanity` job: Tests production API endpoints

**deploy.yml** - Runs on push to main:
- Deploys `earthquake-monitor` Cloud Function
- Deploys `earthquake-api` Cloud Run service
- Deploys `earthquake-city` Cloud Run service (web)

### Branch Protection
PRs require both checks to pass before merge:
- `test` - Unit tests must pass
- `api-sanity` - Production API must be healthy

## Deployed Services

| Service | Type | URL | Purpose |
|---------|------|-----|---------|
| `earthquake-monitor` | Cloud Function | (scheduled) | Alert monitoring |
| `earthquake-api` | Cloud Run | https://earthquake-api-793997436187.us-central1.run.app | Web API |
| `earthquake-city` | Cloud Run | https://earthquake.city | Web frontend |

## Personal Preferences Applied
- Always use Functional Core, Imperative Shell pattern
- Keep shell layer thin
- Pure functions for all business logic
- Comprehensive type hints
- Dataclasses for models

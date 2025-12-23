# Earthquake Alerts - Project Context

## Overview
A serverless earthquake monitoring application that fetches earthquake data from USGS and sends configurable alerts to Slack channels. Designed for deployment on Google Cloud Platform (Cloud Functions + Firestore).

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
   - Firestore client (database)
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
├── main.py                   # Root entry point (imports from src)
├── env-vars.yaml             # Environment variables for deployment
├── config/
│   ├── config.example.yaml   # Example configuration
│   └── config.yaml           # Local config (gitignored)
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
│   │   ├── firestore_client.py # Firestore for deduplication
│   │   ├── secret_manager_client.py # Secret Manager for secrets
│   │   └── config_loader.py  # Config loading
│   ├── orchestrator.py       # Wires core + shell
│   └── main.py               # Cloud Function entry point
├── tests/
│   ├── core/                 # Unit tests (fast, no mocks)
│   └── shell/                # Integration tests
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
4. **USGS FDSN API**: Supports custom bounding boxes and time ranges

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

### Adding New Alert Rules
1. Add rule evaluation logic to `src/core/rules.py` (pure function)
2. Add corresponding config options
3. Write unit tests for new rules
4. No changes to shell needed

## Web Frontend (earthquake.city)

The `web/` directory contains a Next.js 15 application for earthquake.city - a mobile-first landing page with Stripe-like aesthetics.

### Web Architecture
```
earthquake.city/[locale]  (e.g., /sanramon, /bayarea, /la)
         │
         ▼
┌─────────────────────────┐
│   Next.js on Cloud Run  │
│   - Static generation   │
│   - ISR for fresh data  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Cloud Function API     │
│  /api-latest-earthquake │
│  - Returns latest quake │
│  - Per region/locale    │
└─────────────────────────┘
```

### Web Stack
- **Framework**: Next.js 15 (App Router)
- **Styling**: Tailwind CSS
- **Globe**: Globe.gl (WebGL 3D visualization)
- **Hosting**: GCP Cloud Run

### Web Development Commands
```bash
cd web

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Build and deploy to Cloud Run
docker build -t earthquake-city --build-arg NEXT_PUBLIC_API_URL=https://... .
docker push gcr.io/PROJECT/earthquake-city
gcloud run deploy earthquake-city --image gcr.io/PROJECT/earthquake-city
```

### API Endpoints (Cloud Function)
- `api_latest_earthquake?locale=sanramon` - Get latest earthquake for a locale
- `api_locales` - List all available locales

## Personal Preferences Applied
- Always use Functional Core, Imperative Shell pattern
- Keep shell layer thin
- Pure functions for all business logic
- Comprehensive type hints
- Dataclasses for models

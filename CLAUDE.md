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
├── config/
│   └── config.example.yaml   # Example configuration
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
- **Environment variables**: Secrets (webhook URLs, GCP project)
- **YAML config**: Regions, channels, rules (can be in GCS or bundled)

## Key Design Decisions
1. **Firestore for deduplication**: Serverless, scales to zero, cheap for low-volume key-value lookups
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

# Deploy to GCP
gcloud functions deploy earthquake-monitor \
  --runtime python311 \
  --trigger-http \
  --entry-point earthquake_monitor \
  --set-env-vars "CONFIG_PATH=config/config.yaml"
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

## Personal Preferences Applied
- Always use Functional Core, Imperative Shell pattern
- Keep shell layer thin
- Pure functions for all business logic
- Comprehensive type hints
- Dataclasses for models

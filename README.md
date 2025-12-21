# Earthquake Alerts

A serverless earthquake monitoring application that fetches real-time earthquake data from USGS and sends configurable alerts to Slack channels.

## Features

- **Real-time Monitoring**: Polls USGS Earthquake API for new events
- **Configurable Alerts**: Set magnitude thresholds, geographic bounds, and points of interest
- **Multiple Channels**: Route different alert levels to different Slack channels
- **Proximity Alerts**: Get notified when earthquakes occur near specific locations
- **Deduplication**: Prevents duplicate alerts using Firestore persistence
- **Serverless**: Runs on Google Cloud Functions with Cloud Scheduler

## Architecture

This project follows the **Functional Core, Imperative Shell** pattern for clean separation of concerns and easy testing:

```
┌─────────────────────────────────────────────────────────────┐
│                    IMPERATIVE SHELL                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ USGS Client │  │Slack Client │  │ Firestore Client    │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼─────────────────────┼────────────┘
          │                │                     │
          ▼                ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    FUNCTIONAL CORE                          │
│  • Earthquake parsing    • Alert rule evaluation            │
│  • Geo calculations      • Message formatting               │
│  • Deduplication logic   (All pure functions - no I/O)      │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Google Cloud SDK (`gcloud`)
- A GCP project with Firestore enabled
- Slack incoming webhook URL(s)

### 1. Clone and Install

```bash
git clone https://github.com/your-org/earthquake-alerts.git
cd earthquake-alerts
pip install -r requirements.txt
```

### 2. Configure

**Simple mode** (environment variables only):

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
export MONITORING_BOUNDS="35.9,39.2,-123.0,-120.7"  # min_lat,max_lat,min_lon,max_lon
export MIN_MAGNITUDE="3.0"
```

**Full mode** (YAML configuration with Secret Manager - Recommended for production):

```bash
# Store webhook URL securely in Secret Manager
echo -n "https://hooks.slack.com/services/YOUR/WEBHOOK/URL" | \
  gcloud secrets create slack-webhook-url --data-file=- --replication-policy=automatic

# Copy and edit config file (use ${secret:slack-webhook-url} for webhook URLs)
cp config/config.example.yaml config/config-production.yaml
# Edit config-production.yaml with your settings
```

### 3. Deploy to GCP

```bash
# Set your GCP project
gcloud config set project YOUR_PROJECT_ID

# Enable billing for your project (required)
# Visit: https://console.cloud.google.com/billing/projects

# Enable required APIs
gcloud services enable \
    cloudfunctions.googleapis.com \
    firestore.googleapis.com \
    cloudscheduler.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com

# Create Firestore database (Native mode)
gcloud firestore databases create \
    --location=us-central1 \
    --type=firestore-native \
    --database=earthquake-alerts

# Store Slack webhook in Secret Manager (recommended - keeps secrets out of code)
echo -n "https://hooks.slack.com/services/YOUR/WEBHOOK/URL" | \
    gcloud secrets create slack-webhook-url --data-file=- --replication-policy=automatic

# Grant Cloud Function service account access to the secret
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding slack-webhook-url \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# env-vars.yaml is already configured (no sensitive data)

# Deploy Cloud Function
gcloud functions deploy earthquake-monitor \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=earthquake_monitor \
  --trigger-http \
  --allow-unauthenticated \
  --memory=256MB \
  --timeout=60s \
  --env-vars-file=env-vars.yaml

# Create Cloud Scheduler job (runs every 5 minutes)
gcloud scheduler jobs create http earthquake-monitor-scheduler \
  --location=us-central1 \
  --schedule="*/5 * * * *" \
  --uri="https://REGION-PROJECT.cloudfunctions.net/earthquake-monitor" \
  --http-method=POST \
  --time-zone="UTC"
```

### 4. Test

```bash
# Trigger manually
curl -X POST https://REGION-PROJECT.cloudfunctions.net/earthquake-monitor

# View logs
gcloud functions logs read earthquake-monitor --region=us-central1
```

## Configuration

### Secret Management

**Recommended for production**: Use Google Cloud Secret Manager to store sensitive webhook URLs securely:

```yaml
# In your config YAML file
alert_channels:
  - name: "earthquake-alerts"
    type: slack
    webhook_url: "${secret:slack-webhook-url}"  # Reads from Secret Manager
```

The application supports:
- `${secret:SECRET_NAME}` - Reads from Google Cloud Secret Manager (recommended)
- `${ENV_VAR_NAME}` - Reads from environment variable (for local development)

### YAML Configuration

See [config/config.example.yaml](config/config.example.yaml) for full options.

```yaml
# Monitor the Bay Area
monitoring_regions:
  - name: "Bay Area"
    bounds:
      min_latitude: 35.9
      max_latitude: 39.2
      min_longitude: -123.0
      max_longitude: -120.7

# Alert channels with different thresholds
alert_channels:
  - name: "critical"
    type: slack
    webhook_url: "${SLACK_WEBHOOK_CRITICAL}"
    rules:
      min_magnitude: 5.0

  - name: "all-earthquakes"
    type: slack
    webhook_url: "${SLACK_WEBHOOK_ALL}"
    rules:
      min_magnitude: 2.5

# Proximity alerts for specific locations
points_of_interest:
  - name: "Office"
    latitude: 37.7749
    longitude: -122.4194
    alert_radius_km: 50
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SLACK_WEBHOOK_URL` | Default Slack webhook (simple mode) | If no config file |
| `SLACK_WEBHOOK_*` | Named webhooks referenced in config | If using YAML |
| `CONFIG_PATH` | Path to YAML config file | No |
| `FIRESTORE_DATABASE` | Firestore database name (e.g., "earthquake-alerts") | Recommended |
| `GCP_PROJECT` | GCP project ID | No (uses default) |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, etc.) | No |
| `MONITORING_BOUNDS` | Geographic bounds (simple mode) | No |
| `MIN_MAGNITUDE` | Minimum magnitude (simple mode) | No |
| `LOOKBACK_HOURS` | Hours to look back for earthquakes | No (default: 1) |

## Development

### Run Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Local Testing

```bash
# Set environment variables
export SLACK_WEBHOOK_URL="https://hooks.slack.com/..."

# Run locally
python -m src.main
```

### Project Structure

```
earthquake-alerts/
├── src/
│   ├── core/           # Functional Core (pure functions)
│   │   ├── earthquake.py   # Data models & parsing
│   │   ├── geo.py          # Distance calculations
│   │   ├── rules.py        # Alert rule evaluation
│   │   ├── formatter.py    # Message formatting
│   │   └── dedup.py        # Deduplication logic
│   ├── shell/          # Imperative Shell (I/O)
│   │   ├── usgs_client.py      # USGS API
│   │   ├── slack_client.py     # Slack webhooks
│   │   ├── firestore_client.py # Dedup storage
│   │   └── config_loader.py    # Configuration
│   ├── orchestrator.py  # Wires core + shell
│   └── main.py          # Cloud Function entry
└── tests/
    ├── core/            # Unit tests (fast, no mocks)
    └── shell/           # Integration tests
```

## Alert Message Format

Alerts include:
- Magnitude and severity level
- Location description
- Depth and coordinates
- Time (UTC)
- Tsunami warning (if applicable)
- PAGER alert level
- Number of "felt" reports
- Distance to nearby points of interest
- Link to USGS event page

## Cost Estimate

Running on GCP (estimated monthly):
- Cloud Functions: ~$0-5 (depends on frequency)
- Firestore: ~$0 (free tier covers typical usage)
- Cloud Scheduler: ~$0.10

**Note**: The application uses a named Firestore database (`earthquake-alerts`) in Native mode. If your GCP project already has a Datastore Mode database, the named database allows both to coexist without conflicts.

## Extending

### Adding a New Notification Channel

1. Create a new client in `src/shell/` (e.g., `discord_client.py`)
2. Add channel type handling in orchestrator
3. Update config schema

### Adding New Alert Rules

1. Add rule logic to `src/core/rules.py` (pure function)
2. Add config options
3. Write unit tests

## License

MIT

## Acknowledgments

- USGS Earthquake Hazards Program for the excellent API
- Inspired by the [Functional Core, Imperative Shell](https://testing.googleblog.com/2025/10/simplify-your-code-functional-core.html) pattern

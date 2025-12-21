#!/bin/bash
# Deploy earthquake-alerts to Google Cloud Functions
#
# Prerequisites:
# 1. gcloud CLI installed and authenticated
# 2. GCP project set: gcloud config set project YOUR_PROJECT
# 3. Required APIs enabled:
#    - Cloud Functions
#    - Cloud Firestore
#    - Cloud Scheduler
#    - Cloud Build

set -e

# Configuration
FUNCTION_NAME="${FUNCTION_NAME:-earthquake-monitor}"
REGION="${REGION:-us-central1}"
RUNTIME="python311"
MEMORY="${MEMORY:-256MB}"
TIMEOUT="${TIMEOUT:-60s}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Deploying Earthquake Monitor to GCP...${NC}"

# Check for required environment variables
if [ -z "$SLACK_WEBHOOK_CRITICAL" ] && [ -z "$SLACK_WEBHOOK_ALL" ]; then
    echo -e "${RED}Error: At least one SLACK_WEBHOOK_* environment variable must be set${NC}"
    exit 1
fi

# Build environment variables string
ENV_VARS="LOG_LEVEL=INFO"

if [ -n "$SLACK_WEBHOOK_CRITICAL" ]; then
    ENV_VARS="$ENV_VARS,SLACK_WEBHOOK_CRITICAL=$SLACK_WEBHOOK_CRITICAL"
fi

if [ -n "$SLACK_WEBHOOK_ALL" ]; then
    ENV_VARS="$ENV_VARS,SLACK_WEBHOOK_ALL=$SLACK_WEBHOOK_ALL"
fi

if [ -n "$SLACK_WEBHOOK_NEARBY" ]; then
    ENV_VARS="$ENV_VARS,SLACK_WEBHOOK_NEARBY=$SLACK_WEBHOOK_NEARBY"
fi

if [ -n "$CONFIG_PATH" ]; then
    ENV_VARS="$ENV_VARS,CONFIG_PATH=$CONFIG_PATH"
fi

echo -e "${YELLOW}Deploying Cloud Function...${NC}"

gcloud functions deploy "$FUNCTION_NAME" \
    --gen2 \
    --runtime="$RUNTIME" \
    --region="$REGION" \
    --source=. \
    --entry-point=earthquake_monitor \
    --trigger-http \
    --allow-unauthenticated \
    --memory="$MEMORY" \
    --timeout="$TIMEOUT" \
    --set-env-vars="$ENV_VARS"

FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --format='value(serviceConfig.uri)')

echo -e "${GREEN}Function deployed!${NC}"
echo -e "URL: ${YELLOW}$FUNCTION_URL${NC}"

# Create Cloud Scheduler job
SCHEDULER_NAME="${FUNCTION_NAME}-scheduler"

echo -e "\n${YELLOW}Creating Cloud Scheduler job...${NC}"

# Delete existing scheduler if it exists
gcloud scheduler jobs delete "$SCHEDULER_NAME" --location="$REGION" --quiet 2>/dev/null || true

gcloud scheduler jobs create http "$SCHEDULER_NAME" \
    --location="$REGION" \
    --schedule="*/5 * * * *" \
    --uri="$FUNCTION_URL" \
    --http-method=POST \
    --time-zone="UTC" \
    --description="Trigger earthquake monitor every 5 minutes"

echo -e "${GREEN}Cloud Scheduler job created!${NC}"
echo -e "Schedule: Every 5 minutes"

echo -e "\n${GREEN}Deployment complete!${NC}"
echo -e "\nTo test manually:"
echo -e "  curl -X POST $FUNCTION_URL"
echo -e "\nTo view logs:"
echo -e "  gcloud functions logs read $FUNCTION_NAME --region=$REGION"

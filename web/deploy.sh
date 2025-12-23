#!/bin/bash
# Deploy earthquake.city to Cloud Run
# Usage: ./deploy.sh

set -e

PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
SERVICE_NAME="earthquake-city"
REPO_NAME="earthquake-city"

echo "🚀 Deploying earthquake.city to Cloud Run"
echo "   Project: $PROJECT_ID"
echo "   Region: $REGION"
echo ""

# Step 1: Create Artifact Registry repository (if not exists)
echo "📦 Creating Artifact Registry repository..."
gcloud artifacts repositories create $REPO_NAME \
  --repository-format=docker \
  --location=$REGION \
  --description="earthquake.city web app" \
  2>/dev/null || echo "   Repository already exists"

# Step 2: Build and push Docker image
echo ""
echo "🔨 Building Docker image..."
IMAGE_URL="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/web:latest"
API_URL="https://$REGION-$PROJECT_ID.cloudfunctions.net"

docker build \
  -t $IMAGE_URL \
  --build-arg NEXT_PUBLIC_API_URL=$API_URL \
  .

echo ""
echo "📤 Pushing to Artifact Registry..."
docker push $IMAGE_URL

# Step 3: Deploy to Cloud Run
echo ""
echo "☁️  Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_URL \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10

# Step 4: Get the service URL
echo ""
echo "✅ Deployment complete!"
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
echo ""
echo "🌐 Cloud Run URL: $SERVICE_URL"
echo ""
echo "📋 Next steps for custom domain (earthquake.city):"
echo ""
echo "1. Map custom domain in Cloud Run:"
echo "   gcloud run domain-mappings create --service $SERVICE_NAME --domain earthquake.city --region $REGION"
echo ""
echo "2. Configure Cloudflare DNS (see CLOUDFLARE_SETUP.md)"
echo ""

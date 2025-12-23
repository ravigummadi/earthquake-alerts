# Cloudflare DNS Setup for earthquake.city

## Overview

This guide sets up Cloudflare DNS to point earthquake.city to your Cloud Run service.

## Prerequisites

1. earthquake.city domain registered and added to Cloudflare
2. Cloud Run service deployed (run `./deploy.sh` first)
3. Custom domain mapped in Cloud Run

## Step 1: Map Custom Domain in Cloud Run

First, create a domain mapping in Cloud Run:

```bash
# Map the root domain
gcloud run domain-mappings create \
  --service earthquake-city \
  --domain earthquake.city \
  --region us-central1

# Also map www subdomain (optional)
gcloud run domain-mappings create \
  --service earthquake-city \
  --domain www.earthquake.city \
  --region us-central1
```

After running this, GCP will provide DNS records you need to add.

Get the required DNS records:
```bash
gcloud run domain-mappings describe \
  --domain earthquake.city \
  --region us-central1 \
  --format='yaml(status.resourceRecords)'
```

## Step 2: Configure Cloudflare DNS

### Option A: Using Cloudflare Proxy (Recommended)

Go to Cloudflare Dashboard → earthquake.city → DNS → Records

Add these records:

| Type  | Name | Content                        | Proxy Status |
|-------|------|--------------------------------|--------------|
| CNAME | @    | ghs.googlehosted.com           | Proxied (orange cloud) |
| CNAME | www  | ghs.googlehosted.com           | Proxied (orange cloud) |

### Option B: DNS Only (No Cloudflare Proxy)

If you prefer to bypass Cloudflare proxy:

| Type  | Name | Content                        | Proxy Status |
|-------|------|--------------------------------|--------------|
| CNAME | @    | ghs.googlehosted.com           | DNS only (gray cloud) |
| CNAME | www  | ghs.googlehosted.com           | DNS only (gray cloud) |

**Note:** For root domain (@), Cloudflare uses CNAME flattening, so CNAME records work fine.

## Step 3: SSL/TLS Configuration

### In Cloudflare:

1. Go to SSL/TLS → Overview
2. Set encryption mode to **Full (strict)**
   - This ensures end-to-end encryption
   - Cloud Run provides SSL automatically

### In Cloudflare SSL/TLS → Edge Certificates:

1. Enable **Always Use HTTPS**
2. Enable **Automatic HTTPS Rewrites**

## Step 4: Verify Domain in Cloud Run

After adding DNS records, verify the domain mapping:

```bash
gcloud run domain-mappings describe \
  --domain earthquake.city \
  --region us-central1
```

Look for `status.conditions` - it should show:
- `CertificateProvisioned: True`
- `DomainRoutable: True`

This can take 15-30 minutes for SSL certificate provisioning.

## Step 5: Optional Cloudflare Settings

### Page Rules (optional)

Create a page rule to redirect www to root:
- URL: `www.earthquake.city/*`
- Setting: Forwarding URL (301 - Permanent Redirect)
- Destination: `https://earthquake.city/$1`

### Caching

The Next.js app handles caching via headers. Cloudflare will respect these.

For static assets, you can create a page rule:
- URL: `earthquake.city/_next/static/*`
- Setting: Cache Level → Cache Everything
- Setting: Edge Cache TTL → 1 month

## Troubleshooting

### Domain not resolving

1. Check DNS propagation: https://dnschecker.org/#CNAME/earthquake.city
2. Wait 5-10 minutes for propagation
3. Verify Cloudflare proxy is enabled (orange cloud)

### SSL Certificate errors

1. Ensure Cloudflare SSL mode is "Full (strict)"
2. Wait for Cloud Run to provision certificate (up to 30 min)
3. Check domain mapping status:
   ```bash
   gcloud run domain-mappings describe --domain earthquake.city --region us-central1
   ```

### 404 errors

1. Verify Cloud Run service is running:
   ```bash
   gcloud run services describe earthquake-city --region us-central1
   ```
2. Check the direct Cloud Run URL works first

## DNS Records Summary

```
earthquake.city.     CNAME   ghs.googlehosted.com.
www.earthquake.city. CNAME   ghs.googlehosted.com.
```

## Verification

After setup, verify everything works:

```bash
# Check DNS
dig earthquake.city CNAME

# Check HTTPS
curl -I https://earthquake.city

# Check redirect
curl -I https://www.earthquake.city
```

# Test Coverage Analysis

**Date**: 2026-02-15
**Current state**: 238 tests passing across 12 test files (7 core, 5 shell)

## Summary

The core functional layer (`src/core/`) has strong test coverage. The major gaps are in the orchestration layer, several untested pure-function modules, the API service, and all Firestore/Secret Manager clients.

## Coverage Gaps by Priority

### P0 — Critical Gaps

#### 1. Orchestrator (`src/orchestrator.py`) — 0 tests

The central wiring between core logic and notification clients. All alert routing flows through here.

**Untested logic:**
- `process()` — Main monitoring cycle: fetch → dedup → rules → send → store. Multiple error-handling branches and early returns.
- `_send_alert()` — Channel type routing (slack/twitter/whatsapp/default fallback).
- `_send_twitter_alert()` — Credential extraction from tuples, `KeyError` handling, map generation → media upload → tweet pipeline with fallback to tweet-without-image.
- `_send_whatsapp_alert()` — Credential parsing, `to_numbers` string-to-tuple coercion, empty-recipients guard, "any success" aggregation.
- `_send_slack_alert()` — Message formatting and sending.
- `ProcessingResult.success` and `.summary` properties.

**Recommended approach:** Unit tests with mocked shell clients (USGSClient, SlackClient, TwitterClient, WhatsAppClient, FirestoreClient, StaticMapClient). No real I/O needed.

#### 2. Locale module (`src/core/locale.py`) — 0 tests

Pure core module — trivially testable with no mocks needed.

**Untested functions:**
- `validate_locale()` — 10+ validation rules (slug format, name length, bounds validity, center-within-bounds, magnitude range)
- `locale_to_dict()` — API response serialization
- `locale_to_firestore_dict()` — Firestore serialization (includes `is_active`, `sort_order`, timestamps)
- `locale_from_dict()` — Firestore deserialization with default-value handling
- Round-trip: `locale_to_firestore_dict()` → `locale_from_dict()` should produce equivalent object

### P1 — Important Gaps

#### 3. Config loader (`src/shell/config_loader.py`) — 0 tests

Config parsing errors can cause silent misconfiguration or runtime crashes.

**Untested logic:**
- `_resolve_value()` — `${secret:...}` and `${ENV_VAR}` placeholder resolution
- `_parse_channel()` — Slack/Twitter/WhatsApp channel config parsing, credential resolution with nested lists
- `_parse_alert_rule()` — Rule parsing with POI name matching
- `load_config_from_dict()` — End-to-end config assembly from dict
- `load_config()` — File I/O with fallback to defaults
- `load_config_from_env()` — Environment variable parsing with Secret Manager fallback

#### 4. API service (`api/main.py`) — 0 tests

10 endpoints (4 public, 6 admin) serving earthquake.city.

**Untested:**
- Public: response structure, 404 for unknown locales, 502 for USGS failures
- Admin: auth verification, CRUD operations, 409 on duplicate create, soft vs. hard delete
- `_earthquake_to_dict()` — GeoJSON transform with timestamp conversion, tsunami boolean coercion, shakemap detection

**Recommended approach:** FastAPI `TestClient` with mocked Firestore and USGS responses.

### P2 — Moderate Gaps

#### 5. Firestore client (`src/shell/firestore_client.py`) — 0 tests

Dedup state errors cause duplicate alerts or missed alerts.

- `get_alerted_ids()`, `save_alerted_ids()`, `add_alerted_ids()`, `remove_alerted_ids()`
- Lazy client initialization

#### 6. Secret Manager client (`src/shell/secret_manager_client.py`) — 0 tests

- `get_secret()`, `get_secret_or_env()` — Secret retrieval with env-var fallback
- `resolve()` — Placeholder syntax parsing

#### 7. Entry points (`src/main.py`) — 0 tests

- `earthquake_monitor()` — HTTP handler error responses (400, 500, 207)
- `earthquake_monitor_pubsub()` — Pub/Sub handler exception re-raising
- `_get_config()` — Config loading priority logic

### P3 — Lower Priority

#### 8. Locale client (`src/shell/locale_client.py`) — 0 tests

- Cache TTL logic, cache invalidation
- CRUD operations (create, update, soft/hard delete, restore)

### Edge Cases Missing in Existing Tests

- **`rules.py`**: Special condition matching with location failure (e.g., tsunami outside bounds) not explicitly tested
- **`formatter.py`**: `format_twitter_message()` with nearby POIs populated; truncation behavior when POIs push tweet over 280 chars
- **`dedup.py`**: `compute_ids_to_expire()` boundary behavior when stored IDs overlap with current at `max_stored`
- **`earthquake.py`**: `parse_earthquake()` with non-numeric magnitude or coordinate values (malformed USGS data)

## Current Coverage Map

| Module | Tests | Status |
|--------|-------|--------|
| `src/core/earthquake.py` | 16 tests | Well covered |
| `src/core/geo.py` | 16 tests | Well covered |
| `src/core/rules.py` | 14 tests | Well covered |
| `src/core/formatter.py` | 33 tests | Well covered |
| `src/core/dedup.py` | 12 tests | Well covered |
| `src/core/config.py` | 18 tests | Well covered |
| `src/core/static_map.py` | 15 tests | Well covered |
| `src/core/locale.py` | 0 tests | **No coverage** |
| `src/shell/usgs_client.py` | 8 tests | Covered |
| `src/shell/slack_client.py` | 12 tests | Covered |
| `src/shell/twitter_client.py` | 20 tests | Well covered |
| `src/shell/whatsapp_client.py` | 11 tests | Covered |
| `src/shell/static_map_client.py` | 9 tests | Covered |
| `src/shell/firestore_client.py` | 0 tests | **No coverage** |
| `src/shell/secret_manager_client.py` | 0 tests | **No coverage** |
| `src/shell/config_loader.py` | 0 tests | **No coverage** |
| `src/shell/locale_client.py` | 0 tests | **No coverage** |
| `src/orchestrator.py` | 0 tests | **No coverage** |
| `src/main.py` | 0 tests | **No coverage** |
| `api/main.py` | 0 tests | **No coverage** |
| **Total** | **238** | |

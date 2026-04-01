# MongoDB Schema Reference

This project uses MongoDB. There are no SQL tables; persistent data lives in MongoDB collections.

## Overview

Primary collections currently used by the backend:

| Collection | Purpose |
| --- | --- |
| `users` | Authenticated accounts |
| `invites` | Invite-based onboarding |
| `tracked_lots` | Current user watchlist items |
| `lot_snapshots` | Historical state snapshots for tracked lots |
| `provider_connections` | Encrypted user-scoped Copart/IAAI connector bundles |
| `push_subscriptions` | Browser push subscriptions |
| `search_catalog` | Current make/model/year catalog |
| `saved_searches` | User-saved manual searches |
| `admin_runtime_settings` | Mongo-backed overrides for allowlisted admin-tunable runtime settings |

## Relationship Model

- `users._id` is the root identity for authenticated accounts.
- Several collections store user linkage as string fields, not Mongo `DBRef`:
  - `invites.created_by`
  - `tracked_lots.owner_user_id`
  - `lot_snapshots.owner_user_id`
  - `provider_connections.owner_user_id`
  - `push_subscriptions.owner_user_id`
  - `saved_searches.owner_user_id`
- `lot_snapshots.tracked_lot_id` stores `tracked_lots._id` as string.
- There is no foreign-key enforcement at Mongo level; integrity is maintained in service logic.

## Collections

### `users`

Purpose: application users created either as bootstrap admin or via accepted invite.

Typical document:

```json
{
  "_id": "ObjectId(...)",
  "email": "admin@example.com",
  "password_hash": "<salt>$<digest>",
  "role": "admin",
  "status": "active",
  "created_at": "2026-03-13T10:00:00Z",
  "updated_at": "2026-03-13T10:00:00Z",
  "last_login_at": "2026-03-13T11:00:00Z"
}
```

Key fields:

- `email`: normalized to lowercase
- `password_hash`: PBKDF2-HMAC-SHA256 with random salt
- `role`: `admin` or `user`
- `status`: `active`, `blocked`, `disabled`
- timestamps: `created_at`, `updated_at`, `last_login_at`

Indexes:

- unique: `email`

### `invites`

Purpose: pending/revoked/accepted invite records.

Typical document:

```json
{
  "_id": "ObjectId(...)",
  "email": "buyer@example.com",
  "token": "<invite-token>",
  "status": "pending",
  "expires_at": "2026-03-16T10:00:00Z",
  "accepted_at": null,
  "revoked_at": null,
  "created_at": "2026-03-13T10:00:00Z",
  "created_by": "user-id"
}
```

Key fields:

- `status`: `pending`, `accepted`, `revoked`
- `token`: invite acceptance token
- `created_by`: creator user id as string
- `expires_at`, `accepted_at`, `revoked_at`

Indexes:

- `email`
- unique: `token`

### `tracked_lots`

Purpose: current watchlist state for lots that user tracks.

Typical document:

```json
{
  "_id": "ObjectId(...)",
  "owner_user_id": "user-id",
  "provider": "copart",
  "auction_label": "Copart",
  "provider_lot_id": "12345678",
  "lot_key": "copart:12345678",
  "lot_number": "12345678",
  "url": "https://www.copart.com/lot/12345678",
  "title": "2025 FORD MUSTANG MACH-E PREMIUM",
  "thumbnail_url": "https://img.copart.com/12345678.jpg",
  "image_urls": ["https://img.copart.com/12345678.jpg"],
  "status": "live",
  "raw_status": "Live",
  "sale_date": "2026-03-20T17:00:00Z",
  "current_bid": 4200.0,
  "buy_now_price": null,
  "currency": "USD",
  "last_checked_at": "2026-03-13T10:00:00Z",
  "auction_reminder_sale_date": "2026-03-20T17:00:00Z",
  "auction_reminder_sent_minutes": [60, 15],
  "active": true,
  "created_at": "2026-03-13T10:00:00Z",
  "updated_at": "2026-03-13T10:00:00Z"
}
```

Key fields:

- `owner_user_id`: owning user id as string
- `provider`: `copart` or `iaai`
- `provider_lot_id`: provider-scoped immutable lot identity used for refresh routing
- `lot_key`: composite identity (`<provider>:<provider_lot_id>`) used for uniqueness and dedupe
- `lot_number`: display lot/stock number shown in UI
- `thumbnail_url`, `image_urls`: cached media
- `status` and `raw_status`: normalized and original sale state
- `active`: used by monitoring worker to select live tracked lots
- `last_checked_at`: worker scheduling input
- `auction_reminder_sale_date` and `auction_reminder_sent_minutes`: persisted once-only reminder state for 60-minute, 15-minute, and started pushes


Indexes:

- unique compound: `owner_user_id + lot_key`
- `owner_user_id`

### `lot_snapshots`

Purpose: historical point-in-time records for tracked lots.

Typical document:

```json
{
  "_id": "ObjectId(...)",
  "tracked_lot_id": "tracked-lot-id",
  "owner_user_id": "user-id",
  "provider": "copart",
  "provider_lot_id": "12345678",
  "lot_key": "copart:12345678",
  "lot_number": "12345678",
  "status": "live",
  "raw_status": "Live",
  "sale_date": "2026-03-20T17:00:00Z",
  "current_bid": 4200.0,
  "buy_now_price": null,
  "currency": "USD",
  "detected_at": "2026-03-13T10:00:00Z"
}
```

Key fields:

- `tracked_lot_id`: parent watchlist item id as string
- `provider`, `provider_lot_id`, `lot_key`: persisted provider identity mirrored from `tracked_lots`
- snapshot fields mirror the important mutable lot state
- `detected_at`: snapshot timestamp

Indexes:

- compound: `tracked_lot_id + detected_at(desc)`

Lifecycle note:

- deleting a tracked lot also deletes its snapshots.
- admin `purge_snapshots` removes historical documents while keeping the parent tracked lot.

### `push_subscriptions`

Purpose: browser push endpoints per user/device.

Typical document:

```json
{
  "_id": "ObjectId(...)",
  "owner_user_id": "user-id",
  "endpoint": "https://push.example/subscription-id",
  "expiration_time": null,
  "keys": {
    "p256dh": "<key>",
    "auth": "<key>"
  },
  "user_agent": "Mozilla/5.0 ...",
  "created_at": "2026-03-13T10:00:00Z",
  "updated_at": "2026-03-13T10:05:00Z"
}
```

Key fields:

- `endpoint`: unique per user
- `keys`: raw Web Push crypto material
- `user_agent`: optional device hint
- `expiration_time`: passthrough from browser subscription payload

Indexes:

- unique compound: `owner_user_id + endpoint`
- `owner_user_id`

Lifecycle note:

- admin `delete_user` and `delete_all_push_subscriptions` remove these records deterministically by `owner_user_id`.

### `admin_runtime_settings`

Purpose: store admin-managed overrides for safe operational settings that remain layered on top of `.env` defaults.

Typical document:

```json
{
  "_id": "ObjectId(...)",
  "key": "saved_search_poll_interval_minutes",
  "value": 10,
  "value_type": "integer",
  "updated_by": "user-id",
  "updated_at": "2026-04-01T16:40:00Z"
}
```

Key fields:

- `key`: allowlisted runtime setting identifier
- `value`: override payload (`integer` or `integer_list`)
- `value_type`: stored shape for the override payload
- `updated_by`: admin user id that last changed the override
- `updated_at`: timestamp of the last update

Indexes:

- unique: `key`
- `updated_at`

Lifecycle notes:

- absence of a document means the effective value falls back to `.env` / `Settings`
- current phase-1 allowlist covers polling intervals, stale window, auction reminder offsets, worker retry backoff, and invite TTL
- both web requests and worker cycles resolve effective values from this collection at runtime, so changing an override does not require a deploy

### `provider_connections`

Purpose: encrypted per-user connector bundles for Copart and IAAI.

Typical document:

```json
{
  "_id": "ObjectId(...)",
  "owner_user_id": "user-id",
  "provider": "iaai",
  "status": "connected",
  "account_label": "buyer@example.com",
  "bundle_version": 1,
  "bundle": {
    "encrypted_bundle": "<ciphertext>",
    "key_version": "v1",
    "captured_at": "2026-03-25T14:10:00Z",
    "expires_at": "2026-03-25T15:10:00Z"
  },
  "last_error": null,
  "connected_at": "2026-03-25T14:10:00Z",
  "disconnected_at": null,
  "last_verified_at": "2026-03-25T14:10:05Z",
  "last_used_at": "2026-03-25T14:20:00Z",
  "created_at": "2026-03-25T14:10:00Z",
  "updated_at": "2026-03-25T14:20:00Z"
}
```

Key fields:

- `provider`: `copart` or `iaai`
- `status`: `connected`, `expiring`, `reconnect_required`, `disconnected`, `error`
- `bundle.encrypted_bundle`: encrypted provider session bundle; Copart stores connector session metadata, IAAI stores refresh-capable auth bundle
- `last_error`: most recent provider-specific failure metadata

Indexes:

- unique compound: `owner_user_id + provider`
- `owner_user_id`

Lifecycle note:

- admin provider actions can mark one or all connections as `disconnected` without deleting the document.

### `search_catalog`

Purpose: cached/searchable catalog of makes, models, and years used by manual search UI.

Storage shape:

- singleton document
- `_id` is fixed: `copart_make_model_catalog`

Typical top-level fields:

```json
{
  "_id": "copart_make_model_catalog",
  "generated_at": "2026-03-13T10:00:00Z",
  "updated_at": "2026-03-13T10:05:00Z",
  "summary": {
    "make_count": 300,
    "model_count": 5000,
    "assigned_model_count": 4500,
    "exact_match_count": 3000,
    "fuzzy_match_count": 1500,
    "unassigned_model_count": 500,
    "year_count": 108
  },
  "years": [2027, 2026, 2025],
  "makes": [
    {
      "slug": "ford",
      "name": "FORD",
      "aliases": ["FORD"],
      "filter_queries": ["lot_make_desc:\"FORD\" OR manufacturer_make_desc:\"FORD\""],
      "models": [
        {
          "slug": "mustangmache",
          "name": "MUSTANG MACH-E",
          "filter_query": "lot_model_desc:\"MUSTANG MACH-E\" OR manufacturer_model_desc:\"MUSTANG MACH-E\""
        }
      ]
    }
  ],
  "manual_override_count": 1
}
```

Indexes:

- `generated_at`

Lifecycle note:

- collection stores exactly one active catalog document identified by fixed `_id`.

### `saved_searches`

Purpose: user-scoped saved manual search presets.

Typical document:

```json
{
  "_id": "ObjectId(...)",
  "owner_user_id": "user-id",
  "label": "FORD MUSTANG MACH-E 2025-2027",
  "criteria": {
    "providers": ["copart", "iaai"],
    "make": "FORD",
    "model": "MUSTANG MACH-E",
    "make_filter": "lot_make_desc:\"FORD\" OR manufacturer_make_desc:\"FORD\"",
    "model_filter": "lot_model_desc:\"MUSTANG MACH-E\" OR manufacturer_model_desc:\"MUSTANG MACH-E\"",
    "year_from": 2025,
    "year_to": 2027
  },
  "result_count": 42,
  "external_links": [
    { "provider": "copart", "label": "Copart", "url": "https://www.copart.com/lotSearchResults?..." },
    { "provider": "iaai", "label": "IAAI", "url": "https://www.iaai.com/Search?..." }
  ],
  "last_provider_diagnostics": [
    {
      "provider": "copart",
      "status": "ready",
      "message": "Copart live actions are available."
    }
  ],
  "criteria_key": "{\"make\":\"FORD\",...}",
  "created_at": "2026-03-13T10:00:00Z",
  "updated_at": "2026-03-13T10:00:00Z"
}
```

Key fields:

- `criteria`: normalized search payload
- `criteria.providers`: selected providers for fan-out search
- `criteria_key`: canonical JSON string used for duplicate detection
- `result_count`: last saved known number of matches
- `external_links`: provider-aware deep links shown by the frontend
- `last_provider_diagnostics`: last known provider-level live-action status snapshot

Indexes:

- unique compound: `owner_user_id + criteria_key`
- compound: `owner_user_id + created_at(desc)`

## What Is Not Persisted

- Plaintext provider passwords are never stored in MongoDB.
- Provider auth bundles are stored only in encrypted form inside `provider_connections.bundle`.
- Monitoring change events are calculated in worker/service flow and returned in memory; there is no dedicated `change_events` collection in the current codebase.
- Copart raw responses are not stored as a separate persistence layer.

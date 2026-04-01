# Backend API Reference

This document describes the current HTTP API exposed by the FastAPI backend.

## Overview

- Base URL: `/api`
- Auth scheme: `Authorization: Bearer <access_token>`
- Content type: `application/json`
- Public endpoints:
  - `GET /health`
  - `GET /system/status`
  - `POST /auth/login`
  - `POST /auth/refresh`
  - `POST /auth/invites/accept`
- Authenticated user endpoints:
  - `provider-connections/*`
  - `search/*`
  - `watchlist/*`
  - `notifications/*`
- Admin-only endpoints:
  - `admin/*`

## Authentication and Roles

- `access_token` and `refresh_token` are stateless JWTs signed with different secrets.
- `access_token` is required for all protected endpoints.
- `refresh_token` is used only by `POST /auth/refresh`.
- Roles:
  - `admin`: can create/revoke invites, refresh the search catalog, read platform-wide admin aggregates, and execute root-mode user/resource actions.
  - `user`: can use search, watchlist, and notification endpoints.
- User statuses:
  - `active`: normal access
  - `blocked`: login and token-backed requests are rejected
  - `disabled`: login and token-backed requests are rejected

## Common Error Semantics

| Status | Meaning |
| --- | --- |
| `400` | Invalid input or malformed request in downstream logic |
| `401` | Missing/invalid token or invalid credentials |
| `403` | Authenticated but admin role is required |
| `404` | Requested entity was not found |
| `409` | Conflict, duplicate resource, or invalid state transition |
| `410` | Expired invite |
| `429` | Rate limit exceeded |
| `422` | FastAPI/Pydantic validation error |
| `502` | Upstream Copart/IAAI failure, connector bootstrap failure, or failed catalog refresh |
| `503` | Search catalog is unavailable |

## Reliability Contract

- `/api/system/status.live_sync` is the global backend-plus-gateway availability surface. It stays separate from per-resource freshness.
- Saved searches and watchlist items now include `freshness` and `refresh_state` alongside legacy timestamps.
- Saved searches and watchlist items may also include additive `connection_diagnostic` / `connection_diagnostics` with `ready`, `connection_missing`, or `reconnect_required` when one or more user-scoped provider connectors block live actions.
- Ordinary dashboard reads stay cache-backed even if a live refresh fails. Use explicit `refresh-live` endpoints when the client needs an immediate upstream refresh attempt.
- `freshness.status` values:
  - `live`: snapshot is inside its freshness window and live sync is healthy
  - `cached`: snapshot is still usable, but global live sync is degraded
  - `degraded`: no usable recent snapshot is available and live sync is degraded
  - `outdated`: snapshot exists, but its freshness window is expired
  - `unknown`: no sync metadata is available yet
- `refresh_state.status` values:
  - `idle`: no active repair/failure state
  - `repair_pending`: background repair or manual refresh should run next
  - `retryable_failure`: last refresh failed and the worker will retry later
  - `failed`: last refresh failed in a non-retryable way

## Endpoint Summary

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | public | Healthcheck |
| `GET` | `/system/status` | public | Global live-sync status and freshness policies |
| `POST` | `/auth/login` | public | Login by email/password |
| `POST` | `/auth/refresh` | public | Refresh access token |
| `POST` | `/auth/invites/accept` | public | Accept invite and create user |
| `GET` | `/admin/overview` | admin | Read platform-wide admin metrics |
| `GET` | `/admin/system-health` | admin | Read operator-facing health signals |
| `GET` | `/admin/invites` | admin | List invite records |
| `POST` | `/admin/invites` | admin | Create invite |
| `DELETE` | `/admin/invites/{invite_id}` | admin | Revoke pending invite |
| `GET` | `/admin/users` | admin | Search/filter/paginate admin user directory |
| `GET` | `/admin/users/{user_id}` | admin | Read aggregate admin user detail payload |
| `POST` | `/admin/users/{user_id}/actions/{action}` | admin | Execute root-mode account/provider/resource action |
| `POST` | `/admin/search-catalog/refresh` | admin | Refresh Mongo-backed search catalog |
| `GET` | `/provider-connections` | user/admin | List current user's provider connections |
| `POST` | `/provider-connections/copart/connect` | user/admin | Create or replace current user's Copart connection |
| `POST` | `/provider-connections/copart/reconnect` | user/admin | Re-bootstrap an existing Copart connection |
| `DELETE` | `/provider-connections/copart` | user/admin | Disconnect current user's Copart connection |
| `POST` | `/provider-connections/iaai/connect` | user/admin | Create or replace current user's IAAI connection |
| `POST` | `/provider-connections/iaai/reconnect` | user/admin | Re-bootstrap an existing IAAI connection |
| `DELETE` | `/provider-connections/iaai` | user/admin | Disconnect current user's IAAI connection |
| `POST` | `/search` | user/admin | Manual multi-provider auction search |
| `GET` | `/search/saved` | user/admin | List saved searches |
| `POST` | `/search/saved` | user/admin | Save current search |
| `POST` | `/search/saved/{saved_search_id}/view` | user/admin | View cached saved-search results |
| `POST` | `/search/saved/{saved_search_id}/refresh-live` | user/admin | Force live refresh for a saved search |
| `DELETE` | `/search/saved/{saved_search_id}` | user/admin | Delete saved search |
| `GET` | `/search/catalog` | user/admin | Read make/model/year catalog |
| `POST` | `/search/watchlist` | user/admin | Add provider-aware search result to watchlist |
| `GET` | `/watchlist` | user/admin | List tracked lots |
| `POST` | `/watchlist` | user/admin | Add tracked lot by provider-aware identifier |
| `POST` | `/watchlist/{tracked_lot_id}/refresh-live` | user/admin | Force live refresh for one tracked lot |
| `DELETE` | `/watchlist/{tracked_lot_id}` | user/admin | Remove tracked lot |
| `GET` | `/notifications/subscription-config` | user/admin | Read browser push/VAPID config |
| `GET` | `/notifications/subscriptions` | user/admin | List push subscriptions |
| `POST` | `/notifications/subscriptions` | user/admin | Create/update push subscription |
| `POST` | `/notifications/test` | user/admin | Send test push to current user's subscriptions |
| `DELETE` | `/notifications/subscriptions?endpoint=...` | user/admin | Remove push subscription |

## Detailed Endpoints

### System

#### `GET /api/health`

Returns backend health metadata.

Response:

```json
{
  "status": "ok",
  "service": "CarTrap API",
  "environment": "development"
}
```

#### `GET /api/system/status`

Returns global live-sync status plus stale-window policies that the frontend can use for reliability UX.

Response:

```json
{
  "status": "ok",
  "service": "CarTrap API",
  "environment": "development",
  "live_sync": {
    "status": "available",
    "last_success_at": "2026-03-21T16:30:00Z",
    "last_success_source": "watchlist_poll",
    "last_failure_at": null,
    "last_failure_source": null,
    "last_error_message": null,
    "stale": false
  },
  "freshness_policies": {
    "saved_searches": {
      "stale_after_seconds": 900
    },
    "watchlist": {
      "stale_after_seconds": 900
    }
  }
}
```

### Auth

#### `POST /api/auth/login`

Request:

```json
{
  "email": "admin@example.com",
  "password": "AdminPass123"
}
```

Response:

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer"
}
```

#### `POST /api/auth/refresh`

Request:

```json
{
  "refresh_token": "<jwt>"
}
```

Response is the same `TokenPairResponse` as login.

#### `POST /api/auth/invites/accept`

Creates a regular user account from an invite token.

Request:

```json
{
  "token": "<invite-token>",
  "password": "UserPass123"
}
```

Response:

```json
{
  "user": {
    "id": "mongo-object-id",
    "email": "buyer@example.com",
    "role": "user",
    "status": "active"
  }
}
```

### Admin

#### `POST /api/admin/invites`

Creates a new pending invite.

Request:

```json
{
  "email": "buyer@example.com"
}
```

Response:

```json
{
  "id": "mongo-object-id",
  "email": "buyer@example.com",
  "status": "pending",
  "token": "<invite-token>",
  "expires_at": "2026-03-16T10:00:00Z"
}
```

#### `GET /api/admin/invites`

Returns invite records ordered by newest first.

Response:

```json
{
  "items": [
    {
      "id": "mongo-object-id",
      "email": "buyer@example.com",
      "status": "pending",
      "token": "<invite-token>",
      "expires_at": "2026-03-16T10:00:00Z",
      "accepted_at": null,
      "revoked_at": null,
      "created_at": "2026-03-13T10:00:00Z",
      "created_by": "admin-user-id"
    }
  ]
}
```

#### `GET /api/admin/overview`

Returns platform-wide metrics used by the admin command center.

Top-level response domains:

- `users`
- `invites`
- `providers`
- `searches`
- `watchlist`
- `push`
- `system`

#### `GET /api/admin/system-health`

Returns operator-facing health counters kept separate from overview cards.

Key fields:

- `live_sync`
- `blocked_users`
- `expired_pending_invites`
- `provider_reconnect_required`
- `saved_search_attention`
- `watchlist_attention`

#### `GET /api/admin/users`

Returns the admin user directory.

Query params:

- `q`
- `role`
- `status`
- `provider_state`
- `push_state`
- `saved_search_state`
- `watchlist_state`
- `last_login`
- `sort`
- `page`
- `page_size`

Directory row shape:

- `id`, `email`, `role`, `status`
- `created_at`, `updated_at`, `last_login_at`
- `provider_state`
- `counts.provider_connections`
- `counts.saved_searches`
- `counts.tracked_lots`
- `counts.push_subscriptions`
- `flags.has_pending_invite`
- `flags.has_reconnect_required_provider`
- `flags.has_unseen_watchlist_updates`

#### `GET /api/admin/users/{user_id}`

Returns one aggregate payload for the selected user.

Sections:

- `account`
- `counts`
- `invites`
- `provider_connections`
- `saved_searches`
- `tracked_lots`
- `push_subscriptions`
- `recent_activity`
- `danger_zone`

#### `POST /api/admin/users/{user_id}/actions/{action}`

Executes a root-mode action.

Supported actions:

- account: `block`, `unblock`, `promote`, `demote`, `reset_password`
- provider: `disconnect_provider`, `disconnect_all_providers`
- resource: `delete_saved_search`, `delete_all_saved_searches`, `delete_tracked_lot`, `delete_all_tracked_lots`, `delete_push_subscription`, `delete_all_push_subscriptions`, `purge_snapshots`
- danger: `delete_user`

Action request body:

```json
{
  "provider": "iaai",
  "resource_id": "mongo-object-id"
}
```

Both fields are optional and only used by actions that need them.

Important semantics:

- `demote`, `block`, and `delete_user` reject attempts to remove the last active admin account.
- `delete_user` also deletes owned provider connections, saved searches, saved-search caches, tracked lots, lot snapshots, push subscriptions, and invite records for the user email.
- `reset_password` returns a temporary generated password in the action response.

#### `DELETE /api/admin/invites/{invite_id}`

Revokes a pending invite. Returns the invite payload after the state change.

#### `POST /api/admin/search-catalog/refresh`

Rebuilds the Copart make/model/year catalog and stores it in MongoDB.

Response shape:

- `generated_at`
- `updated_at`
- `summary`
- `years`
- `makes[]`
- `manual_override_count`

### Provider Connections

#### `GET /api/provider-connections`

Lists provider connections for the authenticated user.

Response:

```json
{
  "items": [
    {
      "id": "mongo-object-id",
      "provider": "copart",
      "provider_label": "Copart",
      "status": "connected",
      "account_label": "buyer@example.com",
      "connected_at": "2026-03-24T09:30:00Z",
      "disconnected_at": null,
      "last_verified_at": "2026-03-24T09:35:00Z",
      "last_used_at": "2026-03-24T10:00:00Z",
      "expires_at": "2026-03-24T12:30:00Z",
      "reconnect_required": false,
      "usable": true,
      "bundle_version": 3,
      "bundle": {
        "key_version": "v1",
        "captured_at": "2026-03-24T09:30:00Z",
        "expires_at": "2026-03-24T12:30:00Z"
      },
      "last_error": null,
      "created_at": "2026-03-24T09:30:00Z",
      "updated_at": "2026-03-24T10:00:00Z"
    }
  ]
}
```

Connection status values:

- `connected`: live provider actions are available
- `expiring`: live actions still work, but bundle expiry is near
- `reconnect_required`: stored session became invalid and the user must re-enter credentials
- `disconnected`: connection exists historically, but live bundle is cleared
- `error`: connector metadata exists, but the connection is not currently usable

#### `POST /api/provider-connections/copart/connect`

Creates or replaces the authenticated user's Copart connection. Passwords are used only for bootstrap and are not persisted after a successful session capture.

Request:

```json
{
  "username": "buyer@example.com",
  "password": "secret123"
}
```

Response:

```json
{
  "connection": {
    "id": "mongo-object-id",
    "provider": "copart",
    "status": "connected"
  }
}
```

Error semantics:

- `401`: Copart credentials were rejected
- `429`: connector bootstrap rate limit reached
- `503`: NAS gateway/bootstrap path is unavailable

#### `POST /api/provider-connections/copart/reconnect`

Re-bootstrap an existing Copart connection after `reconnect_required`.

Request body matches `POST /api/provider-connections/copart/connect`.

Additional error semantics:

- `404`: current user does not have an existing Copart connection to reconnect

#### `DELETE /api/provider-connections/copart`

Disconnects the authenticated user's Copart connection and clears the stored encrypted session bundle.

Response:

```json
{
  "connection": {
    "id": "mongo-object-id",
    "provider": "copart",
    "status": "disconnected"
  }
}
```

#### `POST /api/provider-connections/iaai/connect`

Creates or replaces the authenticated user's IAAI connection. Request/response shapes match Copart, but the stored bundle is refresh-token capable and provider-specific.

Additional error semantics:

- `401`: IAAI credentials were rejected
- `502`: IAAI rejected connector bootstrap request or WAF/auth bootstrap failed

#### `POST /api/provider-connections/iaai/reconnect`

Re-bootstrap an existing IAAI connection after `reconnect_required`.

Additional error semantics:

- `404`: current user does not have an existing IAAI connection to reconnect

#### `DELETE /api/provider-connections/iaai`

Disconnects the authenticated user's IAAI connection and clears the stored encrypted session bundle.

### Search

#### `POST /api/search`

Runs manual auction search across one or more selected providers and merges normalized results by `lot_key`.

Accepted request fields:

| Field | Type | Notes |
| --- | --- | --- |
| `providers` | `string[]` | Optional; defaults to `["copart"]`; allowed values: `copart`, `iaai` |
| `make` | `string` | Optional if `make_filter` is used |
| `model` | `string` | Optional if `model_filter` is used |
| `make_filter` | `string` | Catalog-derived Copart filter query |
| `model_filter` | `string` | Catalog-derived Copart filter query |
| `year_from` | `integer` | `1900..2100` |
| `year_to` | `integer` | `1900..2100`, must be `>= year_from` |
| `lot_number` | `string` | Digits are normalized before search |

At least one of `make`, `model`, `make_filter`, `model_filter`, `lot_number` must be present.

Response:

```json
{
  "results": [
    {
      "provider": "copart",
      "auction_label": "Copart",
      "provider_lot_id": "12345678",
      "lot_key": "copart:12345678",
      "lot_number": "12345678",
      "title": "2025 FORD MUSTANG MACH-E PREMIUM",
      "url": "https://www.copart.com/lot/12345678",
      "thumbnail_url": "https://img.copart.com/12345678.jpg",
      "location": "CA - SACRAMENTO",
      "sale_date": "2026-03-20T17:00:00Z",
      "current_bid": 4200.0,
      "currency": "USD",
      "status": "live"
    }
  ],
  "total_results": 42,
  "provider_diagnostics": [
    {
      "provider": "copart",
      "status": "ready",
      "message": "Copart live actions are available.",
      "connection_id": "mongo-object-id",
      "reconnect_required": false
    }
  ],
  "source_request": {
    "MISC": ["..."],
    "sort": ["..."],
    "filter": [],
    "localFilters": [],
    "latlngFacets": false,
    "pageNumber": 1,
    "userStartUtcDatetime": "2026-03-13T00:00:00Z"
  }
}
```

#### `GET /api/search/saved`

Lists saved searches for the current user.

Response:

```json
{
  "items": [
    {
      "id": "mongo-object-id",
      "label": "FORD MUSTANG MACH-E 2025-2027",
      "criteria": {
        "providers": ["copart", "iaai"],
        "make": "FORD",
        "model": "MUSTANG MACH-E",
        "make_filter": null,
        "model_filter": null,
        "year_from": 2025,
        "year_to": 2027,
        "lot_number": null
      },
      "result_count": 42,
      "cached_result_count": 42,
      "new_count": 3,
      "external_url": "https://www.copart.com/lotSearchResults?...",
      "external_links": [
        { "provider": "copart", "label": "Copart", "url": "https://www.copart.com/lotSearchResults?..." },
        { "provider": "iaai", "label": "IAAI", "url": "https://www.iaai.com/Search?..." }
      ],
      "last_synced_at": "2026-03-21T16:20:00Z",
      "freshness": {
        "status": "cached",
        "last_synced_at": "2026-03-21T16:20:00Z",
        "stale_after": "2026-03-21T16:35:00Z",
        "degraded_reason": "Copart gateway is unavailable.",
        "retryable": true
      },
      "refresh_state": {
        "status": "retryable_failure",
        "last_attempted_at": "2026-03-21T16:31:00Z",
        "last_succeeded_at": "2026-03-21T16:20:00Z",
        "next_retry_at": "2026-03-21T16:36:00Z",
        "error_message": "Copart gateway is unavailable.",
        "retryable": true,
        "priority_class": "normal",
        "last_outcome": "refresh_failed",
        "metrics": {
          "cached_new_count": 3
        }
      },
      "connection_diagnostics": [
        {
          "provider": "copart",
          "status": "ready",
          "message": "Copart live actions are available.",
          "connection_id": "mongo-object-id",
          "reconnect_required": false
        }
      ],
      "created_at": "2026-03-13T10:00:00Z"
    }
  ]
}
```

`items[].connection_diagnostic` remains for backward compatibility. New multi-provider payloads should prefer `items[].connection_diagnostics[]` and `items[].external_links[]`.

#### `POST /api/search/saved`

Stores a user-scoped saved search.

Accepted request fields:

- all fields from `POST /api/search`
- `label` optional custom title
- `result_count` optional snapshot of the last known number of matches

Response:

```json
{
  "saved_search": {
    "id": "mongo-object-id",
    "label": "FORD MUSTANG MACH-E 2025-2027",
    "criteria": {
      "make": "FORD",
      "model": "MUSTANG MACH-E"
    },
    "result_count": 42,
    "cached_result_count": 42,
    "new_count": 0,
    "last_synced_at": "2026-03-21T16:20:00Z",
    "freshness": {
      "status": "live",
      "last_synced_at": "2026-03-21T16:20:00Z",
      "stale_after": "2026-03-21T16:35:00Z",
      "degraded_reason": null,
      "retryable": false
    },
    "refresh_state": {
      "status": "idle",
      "last_attempted_at": "2026-03-21T16:20:00Z",
      "last_succeeded_at": "2026-03-21T16:20:00Z",
      "next_retry_at": null,
      "error_message": null,
      "retryable": false,
      "priority_class": "normal",
      "last_outcome": "refreshed",
      "metrics": {}
    },
    "created_at": "2026-03-13T10:00:00Z"
  }
}
```

#### `POST /api/search/saved/{saved_search_id}/view`

Returns the latest cached saved-search snapshot without forcing an upstream fetch.

#### `POST /api/search/saved/{saved_search_id}/refresh-live`

Forces an immediate live refresh attempt for one saved search and returns the updated saved-search view payload.

Error semantics:

- `409`: current user has no usable connection for any selected provider
- `502`: upstream provider execution failed after a valid connector lookup

#### `DELETE /api/search/saved/{saved_search_id}`

Deletes a saved search belonging to the current user.

- Success response: `204 No Content`

#### `GET /api/search/catalog`

Returns current Mongo-backed search catalog.

Response fields:

- `generated_at`
- `updated_at`
- `summary.make_count`
- `summary.model_count`
- `summary.assigned_model_count`
- `summary.exact_match_count`
- `summary.fuzzy_match_count`
- `summary.unassigned_model_count`
- `summary.year_count`
- `years[]`
- `makes[].slug`
- `makes[].name`
- `makes[].aliases[]`
- `makes[].search_filter`
- `makes[].models[].slug`
- `makes[].models[].name`
- `makes[].models[].search_filter`
- `manual_override_count`

#### `POST /api/search/watchlist`

Adds a lot from search results to the watchlist.

Request:

```json
{
  "provider": "copart",
  "provider_lot_id": "12345678",
  "lot_url": "https://www.copart.com/lot/12345678"
}
```

Response shape is identical to `POST /api/watchlist`.

### Watchlist

#### `GET /api/watchlist`

Lists current user tracked lots.

Items with unseen polling updates are returned first. After the list response is served, those unseen markers are cleared for the current user, so the highlight behaves like a view-once notification.

Response:

```json
{
  "items": [
    {
      "id": "mongo-object-id",
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
      "current_bid": 4200.0,
      "buy_now_price": null,
      "currency": "USD",
      "sale_date": "2026-03-20T17:00:00Z",
      "last_checked_at": "2026-03-13T10:00:00Z",
      "freshness": {
        "status": "outdated",
        "last_synced_at": "2026-03-13T10:00:00Z",
        "stale_after": "2026-03-13T10:15:00Z",
        "degraded_reason": null,
        "retryable": false
      },
      "refresh_state": {
        "status": "repair_pending",
        "last_attempted_at": "2026-03-21T16:28:00Z",
        "last_succeeded_at": "2026-03-13T10:00:00Z",
        "next_retry_at": null,
        "error_message": null,
        "retryable": false,
        "priority_class": "auction_imminent",
        "last_outcome": "repair_requested",
        "metrics": {
          "change_count": 2
        }
      },
      "created_at": "2026-03-13T10:00:00Z",
      "has_unseen_update": true,
      "latest_change_at": "2026-03-17T15:40:00Z",
      "latest_changes": {
        "raw_status": { "before": "On Approval", "after": "Live" },
        "current_bid": { "before": 4200.0, "after": 5100.0 }
      }
    }
  ]
}
```

`items[].connection_diagnostic` is optional and appears when the tracked lot remains readable from cache but the owning user's live provider connector is missing or requires re-login.

#### `POST /api/watchlist`

Adds a lot by provider-aware identifier. Legacy Copart `lot_url` / `lot_number` requests remain supported.

Request variants:

```json
{
  "provider": "copart",
  "lot_url": "https://www.copart.com/lot/12345678"
}
```

```json
{
  "provider": "iaai",
  "provider_lot_id": "99112233",
  "lot_number": "STK-44"
}
```

Response:

```json
{
    "tracked_lot": {
      "id": "mongo-object-id",
      "provider": "copart",
      "auction_label": "Copart",
      "provider_lot_id": "12345678",
      "lot_key": "copart:12345678",
      "lot_number": "12345678",
    "url": "https://www.copart.com/lot/12345678",
    "title": "2025 FORD MUSTANG MACH-E PREMIUM",
    "thumbnail_url": "https://img.copart.com/12345678.jpg",
    "image_urls": ["https://img.copart.com/12345678.jpg"],
    "status": "upcoming",
    "raw_status": "Upcoming",
    "current_bid": 0.0,
    "buy_now_price": null,
    "currency": "USD",
    "sale_date": null,
    "last_checked_at": "2026-03-13T10:00:00Z",
    "freshness": {
      "status": "live",
      "last_synced_at": "2026-03-13T10:00:00Z",
      "stale_after": "2026-03-13T10:15:00Z",
      "degraded_reason": null,
      "retryable": false
    },
    "refresh_state": {
      "status": "idle",
      "last_attempted_at": "2026-03-13T10:00:00Z",
      "last_succeeded_at": "2026-03-13T10:00:00Z",
      "next_retry_at": null,
      "error_message": null,
      "retryable": false,
      "priority_class": "normal",
      "last_outcome": "refreshed",
      "metrics": {}
    },
    "created_at": "2026-03-13T10:00:00Z",
    "has_unseen_update": false,
    "latest_change_at": null,
    "latest_changes": {}
  },
    "initial_snapshot": {
      "id": "mongo-object-id",
      "tracked_lot_id": "mongo-object-id",
      "provider": "copart",
      "provider_lot_id": "12345678",
      "lot_key": "copart:12345678",
      "lot_number": "12345678",
    "status": "upcoming",
    "raw_status": "Upcoming",
    "current_bid": 0.0,
    "buy_now_price": null,
    "currency": "USD",
    "sale_date": null,
    "detected_at": "2026-03-13T10:00:00Z"
  }
}
```

#### `POST /api/watchlist/{tracked_lot_id}/refresh-live`

Forces an immediate live refresh attempt for one tracked lot and returns the updated tracked-lot payload.

Error semantics:

- `409`: current user has no usable connection for the tracked lot's provider
- `502`: upstream provider execution failed after a valid connector lookup

#### `DELETE /api/watchlist/{tracked_lot_id}`

Deletes tracked lot and all related snapshots.

- Success response: `204 No Content`

### Notifications

#### `GET /api/notifications/subscription-config`

Returns whether browser push subscription can be initialized and, when configured, exposes the VAPID public key required by `PushManager.subscribe()`.

Response when configured:

```json
{
  "enabled": true,
  "public_key": "<vapid-public-key>",
  "reason": null
}
```

Response when not configured:

```json
{
  "enabled": false,
  "public_key": null,
  "reason": "Push notifications are not configured on the server. Missing: VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT."
}
```

#### `GET /api/notifications/subscriptions`

Lists push subscriptions for current user.

Response:

```json
{
  "items": [
    {
      "id": "mongo-object-id",
      "endpoint": "https://push.example/subscription-id",
      "user_agent": "Mozilla/5.0 ...",
      "created_at": "2026-03-13T10:00:00Z",
      "updated_at": "2026-03-13T10:05:00Z"
    }
  ]
}
```

#### `POST /api/notifications/subscriptions`

Creates or updates push subscription by endpoint.

Request:

```json
{
  "subscription": {
    "endpoint": "https://push.example/subscription-id",
    "expirationTime": null,
    "keys": {
      "p256dh": "<key>",
      "auth": "<key>"
    }
  },
  "user_agent": "Mozilla/5.0 ..."
}
```

Response:

```json
{
  "id": "mongo-object-id",
  "endpoint": "https://push.example/subscription-id",
  "user_agent": "Mozilla/5.0 ...",
  "created_at": "2026-03-13T10:00:00Z",
  "updated_at": "2026-03-13T10:05:00Z"
}
```

#### `POST /api/notifications/test`

Sends a test push notification to the current user's registered browser subscriptions.

Request:

```json
{
  "title": "CarTrap test notification",
  "body": "Push delivery is working on this device."
}
```

Response:

```json
{
  "delivered": 1,
  "failed": 0,
  "removed": 0,
  "endpoints": ["https://push.example/subscription-id"]
}
```

#### `DELETE /api/notifications/subscriptions?endpoint=...`

Deletes subscription by exact endpoint string.

- Success response: `204 No Content`

## Notes on Internal Behavior

- Operator logs are emitted as structured JSON lines. Main event families include `live_sync.*`, `search.execute.*`, `saved_search.refresh.*`, `saved_search.poll.*`, `watchlist.refresh.*`, `worker.poll_cycle.*`, `copart_gateway.proxy.*`, and `copart_client.request.*`.
- Structured log records carry `event` and `correlation_id`, and refresh/gateway records add fields such as `duration_ms`, `priority_class`, `failure_class`, `status_code`, and resource identifiers when available.
- Search calls Copart JSON API and transparently loads all pages using `pageNumber`.
- `saved_searches.result_count` is a snapshot of the last known count passed from the client, not a live computed counter.
- Watchlist `GET` may backfill missing media for legacy documents.
- Notification delivery exists as backend service logic, but there is no public endpoint for sending arbitrary pushes.

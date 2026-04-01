import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/App";

function buildToken(payload: Record<string, unknown>) {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.signature`;
}

function buildTrackedLot(overrides: Record<string, unknown> = {}) {
  return {
    id: "tracked-1",
    provider: "copart",
    auction_label: "Copart",
    provider_lot_id: "12345678",
    lot_key: "copart:12345678",
    lot_number: "12345678",
    url: "https://www.copart.com/lot/12345678",
    title: "2020 TOYOTA CAMRY SE",
    thumbnail_url: "https://img.copart.com/12345678-detail.jpg",
    image_urls: [
      "https://img.copart.com/12345678-detail.jpg",
      "https://img.copart.com/12345678-detail-2.jpg",
    ],
    odometer: "12,345 ACTUAL",
    primary_damage: "FRONT END",
    estimated_retail_value: 36500,
    has_key: true,
    drivetrain: "AWD",
    highlights: ["Run and Drive", "Enhanced Vehicles"],
    vin: "1FA6P8TH0J5100001",
    status: "live",
    raw_status: "Live",
    current_bid: 4200,
    buy_now_price: null,
    currency: "USD",
    sale_date: null,
    last_checked_at: "2026-03-11T12:00:00Z",
    freshness: buildFreshness({ last_synced_at: "2026-03-11T12:00:00Z", stale_after: "2026-03-11T12:15:00Z" }),
    refresh_state: buildRefreshState({
      priority_class: "normal",
      metrics: { change_count: 0, reminder_count: 0 },
    }),
    created_at: "2026-03-11T12:00:00Z",
    has_unseen_update: false,
    latest_change_at: null,
    latest_changes: {},
    ...overrides,
  };
}

function buildTrackedLotHistoryEntry(overrides: Record<string, unknown> = {}) {
  return {
    snapshot: {
      id: "snapshot-2",
      tracked_lot_id: "tracked-1",
      provider: "copart",
      provider_lot_id: "12345678",
      lot_key: "copart:12345678",
      lot_number: "12345678",
      status: "live",
      raw_status: "Live",
      current_bid: 5100,
      buy_now_price: null,
      currency: "USD",
      sale_date: null,
      detected_at: "2026-03-17T15:40:00Z",
    },
    changes: {
      raw_status: { before: "On Approval", after: "Live" },
      current_bid: { before: 4200, after: 5100 },
    },
    ...overrides,
  };
}

function buildFreshness(overrides: Record<string, unknown> = {}) {
  return {
    status: "live",
    last_synced_at: "2026-03-16T11:00:00Z",
    stale_after: "2026-03-16T11:15:00Z",
    degraded_reason: null,
    retryable: false,
    ...overrides,
  };
}

function buildRefreshState(overrides: Record<string, unknown> = {}) {
  return {
    status: "idle",
    last_attempted_at: "2026-03-16T11:00:00Z",
    last_succeeded_at: "2026-03-16T11:00:00Z",
    next_retry_at: null,
    error_message: null,
    retryable: false,
    priority_class: "normal",
    last_outcome: "refreshed",
    metrics: {},
    ...overrides,
  };
}

function buildSavedSearch(overrides: Record<string, unknown> = {}) {
  return {
    id: "saved-1",
    label: "FORD MUSTANG MACH-E 2025-2027",
    criteria: {
      providers: ["copart"],
      make: "FORD",
      model: "MUSTANG MACH-E",
      year_from: 2025,
      year_to: 2027,
    },
    external_url:
      "https://www.copart.com/lotSearchResults?free=true&displayStr=FORD%20MUSTANG%20MACH-E%202025-2027&from=%2FvehicleFinder&fromSource=widget&qId=test-qid-1&searchCriteria=%7B%22query%22%3A%5B%22FORD%20MUSTANG%20MACH-E%202025-2027%22%5D%2C%22filter%22%3A%7B%22YEAR%22%3A%5B%22lot_year%3A%5B2025%20TO%202027%5D%22%5D%2C%22MAKE%22%3A%5B%22lot_make_desc%3A%5C%22FORD%5C%22%22%5D%2C%22MODL%22%3A%5B%22lot_model_desc%3A%5C%22MUSTANG%20MACH-E%5C%22%22%5D%2C%22DRIV%22%3A%5B%22drive%3A%5C%22ALL%20WHEEL%20DRIVE%5C%22%22%5D%7D%2C%22searchName%22%3A%22%22%2C%22watchListOnly%22%3Afalse%2C%22freeFormSearch%22%3Atrue%7D",
    external_links: [
      {
        provider: "copart",
        label: "Copart",
        url:
          "https://www.copart.com/lotSearchResults?free=true&displayStr=FORD%20MUSTANG%20MACH-E%202025-2027&from=%2FvehicleFinder&fromSource=widget&qId=test-qid-1&searchCriteria=%7B%22query%22%3A%5B%22FORD%20MUSTANG%20MACH-E%202025-2027%22%5D%2C%22filter%22%3A%7B%22YEAR%22%3A%5B%22lot_year%3A%5B2025%20TO%202027%5D%22%5D%2C%22MAKE%22%3A%5B%22lot_make_desc%3A%5C%22FORD%5C%22%22%5D%2C%22MODL%22%3A%5B%22lot_model_desc%3A%5C%22MUSTANG%20MACH-E%5C%22%22%5D%2C%22DRIV%22%3A%5B%22drive%3A%5C%22ALL%20WHEEL%20DRIVE%5C%22%22%5D%7D%2C%22searchName%22%3A%22%22%2C%22watchListOnly%22%3Afalse%2C%22freeFormSearch%22%3Atrue%7D",
      },
    ],
    result_count: 1,
    cached_result_count: 1,
    new_count: 0,
    last_synced_at: "2026-03-16T12:00:00Z",
    freshness: buildFreshness({
      last_synced_at: "2026-03-16T12:00:00Z",
      stale_after: "2026-03-16T12:15:00Z",
    }),
    refresh_state: buildRefreshState({
      priority_class: "normal",
      metrics: { new_matches: 0, cached_new_count: 0 },
    }),
    created_at: "2026-03-12T18:00:00Z",
    ...overrides,
  };
}

function buildSearchResult(overrides: Record<string, unknown> = {}) {
  return {
    provider: "copart",
    auction_label: "Copart",
    provider_lot_id: "12345678",
    lot_key: "copart:12345678",
    lot_number: "12345678",
    title: "2020 TOYOTA CAMRY SE",
    url: "https://www.copart.com/lot/12345678",
    thumbnail_url: "https://img.copart.com/12345678.jpg",
    location: "CA - SACRAMENTO",
    odometer: "12,345 ACTUAL",
    sale_date: null,
    current_bid: 4200,
    buy_now_price: 6500,
    currency: "USD",
    status: "live",
    raw_status: "Live",
    ...overrides,
  };
}

function formatExpectedLocalAuctionStart(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function addMinutes(value: string | null, minutes: number): string | null {
  if (!value) {
    return null;
  }
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return null;
  }
  return new Date(timestamp.getTime() + minutes * 60 * 1000).toISOString().replace(".000Z", "Z");
}

function buildLiveSyncStatus(overrides: Record<string, unknown> = {}) {
  return {
    status: "available",
    last_success_at: "2026-03-16T11:00:00Z",
    last_success_source: "manual_search",
    last_failure_at: null,
    last_failure_source: null,
    last_error_message: null,
    stale: false,
    ...overrides,
  };
}

function buildProviderConnection(overrides: Record<string, unknown> = {}) {
  return {
    id: "provider-connection-1",
    provider: "copart",
    status: "connected",
    account_label: "copart-user@example.com",
    connected_at: "2026-03-24T09:30:00Z",
    disconnected_at: null,
    last_verified_at: "2026-03-24T09:35:00Z",
    last_used_at: "2026-03-24T10:00:00Z",
    expires_at: "2026-03-24T12:30:00Z",
    reconnect_required: false,
    usable: true,
    bundle_version: 3,
    bundle: {
      key_version: "v1",
      captured_at: "2026-03-24T09:30:00Z",
      expires_at: "2026-03-24T12:30:00Z",
    },
    last_error: null,
    created_at: "2026-03-24T09:30:00Z",
    updated_at: "2026-03-24T10:00:00Z",
    ...overrides,
  };
}

function buildConnectionDiagnostic(overrides: Record<string, unknown> = {}) {
  return {
    provider: "copart",
    status: "reconnect_required",
    message: "Reconnect Copart from Account to restore live search and refresh actions.",
    connection_id: "provider-connection-1",
    reconnect_required: true,
    ...overrides,
  };
}

function buildAdminOverview(overrides: Record<string, unknown> = {}) {
  return {
    generated_at: "2026-04-01T12:00:00Z",
    users: {
      total: 3,
      admins: 1,
      regular_users: 2,
      active_last_24h: 1,
      active_last_7d: 2,
      blocked: 0,
      disabled: 0,
    },
    invites: {
      pending: 1,
      accepted: 2,
      revoked: 0,
      expired: 0,
    },
    providers: {
      total_connections: 2,
      connected: 1,
      expiring: 0,
      reconnect_required: 1,
      disconnected: 0,
      error: 0,
      connected_users: 1,
      reconnect_required_users: 1,
      disconnected_users: 0,
    },
    searches: {
      total_saved_searches: 2,
      users_with_saved_searches: 2,
      stale_or_problem: 1,
      searches_with_new_matches: 1,
    },
    watchlist: {
      total_tracked_lots: 1,
      users_with_tracked_lots: 1,
      unseen_updates: 1,
      stale_or_problem: 1,
    },
    push: {
      total_subscriptions: 1,
      users_with_push: 1,
      users_without_push: 2,
    },
    system: {
      live_sync_status: "degraded",
      stale: false,
      last_success_at: "2026-04-01T11:45:00Z",
      last_failure_at: "2026-04-01T11:58:00Z",
      last_error_message: "Gateway timeout",
    },
    ...overrides,
  };
}

function buildAdminSystemHealth(overrides: Record<string, unknown> = {}) {
  return {
    generated_at: "2026-04-01T12:00:00Z",
    app_name: "CarTrap API",
    environment: "test",
    live_sync: buildLiveSyncStatus({
      status: "degraded",
      last_failure_at: "2026-04-01T11:58:00Z",
      last_error_message: "Gateway timeout",
    }),
    blocked_users: 0,
    expired_pending_invites: 0,
    provider_reconnect_required: 1,
    saved_search_attention: 1,
    watchlist_attention: 1,
    ...overrides,
  };
}

function buildAdminUserRow(overrides: Record<string, unknown> = {}) {
  return {
    id: "managed-user-1",
    email: "managed-user@example.com",
    role: "user",
    status: "active",
    created_at: "2026-03-28T09:00:00Z",
    updated_at: "2026-04-01T11:58:00Z",
    last_login_at: "2026-04-01T10:00:00Z",
    provider_state: "reconnect_required",
    counts: {
      provider_connections: 1,
      saved_searches: 1,
      tracked_lots: 1,
      push_subscriptions: 1,
    },
    flags: {
      has_pending_invite: false,
      has_reconnect_required_provider: true,
      has_unseen_watchlist_updates: true,
    },
    ...overrides,
  };
}

function buildAdminUserDetail(overrides: Record<string, unknown> = {}) {
  return {
    account: {
      id: "managed-user-1",
      email: "managed-user@example.com",
      role: "user",
      status: "active",
      created_at: "2026-03-28T09:00:00Z",
      updated_at: "2026-04-01T11:58:00Z",
      last_login_at: "2026-04-01T10:00:00Z",
    },
    counts: {
      provider_connections: 1,
      saved_searches: 1,
      tracked_lots: 1,
      push_subscriptions: 1,
    },
    invites: [
      {
        id: "invite-1",
        email: "managed-user@example.com",
        status: "accepted",
        token: "invite-token-1",
        expires_at: "2026-03-27T12:00:00Z",
        accepted_at: "2026-03-27T10:00:00Z",
        revoked_at: null,
        created_at: "2026-03-26T10:00:00Z",
        created_by: "user-1",
      },
    ],
    provider_connections: [
      buildProviderConnection({
        id: "provider-managed-1",
        provider: "iaai",
        provider_label: "IAAI",
        status: "reconnect_required",
        account_label: "managed-user@iaai.test",
        reconnect_required: true,
        usable: false,
      }),
    ],
    saved_searches: [
      {
        id: "admin-saved-1",
        label: "Managed Search",
        providers: ["iaai"],
        result_count: 4,
        cached_result_count: 4,
        new_count: 1,
        last_synced_at: "2026-04-01T11:20:00Z",
        freshness: buildFreshness({
          status: "cached",
          last_synced_at: "2026-04-01T11:20:00Z",
          stale_after: "2026-04-01T11:35:00Z",
        }),
        refresh_state: buildRefreshState({
          status: "retryable_failure",
          error_message: "gateway timeout",
          retryable: true,
        }),
        created_at: "2026-03-28T09:30:00Z",
      },
    ],
    tracked_lots: [
      {
        id: "admin-tracked-1",
        provider: "iaai",
        lot_key: "iaai:STK-44",
        lot_number: "STK-44",
        title: "2025 FORD MUSTANG MACH-E PREMIUM",
        status: "live",
        raw_status: "Live",
        current_bid: 9100,
        buy_now_price: null,
        currency: "USD",
        sale_date: null,
        last_checked_at: "2026-04-01T11:10:00Z",
        freshness: buildFreshness({
          last_synced_at: "2026-04-01T11:10:00Z",
          stale_after: "2026-04-01T11:25:00Z",
        }),
        refresh_state: buildRefreshState(),
        has_unseen_update: true,
        latest_change_at: "2026-04-01T11:15:00Z",
        created_at: "2026-03-28T09:40:00Z",
      },
    ],
    push_subscriptions: [
      {
        id: "admin-push-1",
        endpoint: "https://push.example.test/managed",
        user_agent: "Managed Browser",
        created_at: "2026-03-30T10:00:00Z",
        updated_at: "2026-04-01T09:00:00Z",
      },
    ],
    recent_activity: {
      last_login_at: "2026-04-01T10:00:00Z",
      last_saved_search_at: "2026-03-28T09:30:00Z",
      last_tracked_lot_at: "2026-03-28T09:40:00Z",
      last_push_subscription_at: "2026-04-01T09:00:00Z",
      last_provider_activity_at: "2026-04-01T11:00:00Z",
      has_unseen_watchlist_updates: true,
    },
    danger_zone: {
      provider_connections: 1,
      saved_searches: 1,
      tracked_lots: 1,
      push_subscriptions: 1,
      lot_snapshots: 3,
      invites: 1,
    },
    ...overrides,
  };
}

function buildAdminRuntimeSettingsResponse() {
  return {
    groups: [
      {
        key: "polling",
        label: "Polling",
        items: [
          {
            key: "saved_search_poll_interval_minutes",
            category: "polling",
            label: "Saved search poll interval",
            description: "Minutes between worker refresh checks for saved searches.",
            value_type: "integer",
            restart_required: false,
            default_value: 15,
            override_value: null,
            effective_value: 15,
            updated_by: null,
            updated_at: null,
            min_value: 1,
            max_value: 240,
            min_items: null,
            max_items: null,
            step: 1,
            unit: "minutes",
            is_overridden: false,
          },
          {
            key: "watchlist_default_poll_interval_minutes",
            category: "polling",
            label: "Watchlist default poll interval",
            description: "Minutes between refresh checks for tracked lots outside the near-auction window.",
            value_type: "integer",
            restart_required: false,
            default_value: 15,
            override_value: null,
            effective_value: 15,
            updated_by: null,
            updated_at: null,
            min_value: 1,
            max_value: 240,
            min_items: null,
            max_items: null,
            step: 1,
            unit: "minutes",
            is_overridden: false,
          },
        ],
      },
      {
        key: "freshness",
        label: "Freshness",
        items: [
          {
            key: "watchlist_auction_reminder_offsets_minutes",
            category: "freshness",
            label: "Auction reminder offsets",
            description: "Minutes before sale time when watchlist auction reminder notifications are sent.",
            value_type: "integer_list",
            restart_required: false,
            default_value: [60, 15, 0],
            override_value: null,
            effective_value: [60, 15, 0],
            updated_by: null,
            updated_at: null,
            min_value: 0,
            max_value: 1440,
            min_items: 1,
            max_items: 8,
            step: 1,
            unit: "minutes",
            is_overridden: false,
          },
        ],
      },
      {
        key: "retries",
        label: "Retries",
        items: [
          {
            key: "job_retry_backoff_seconds",
            category: "retries",
            label: "Job retry backoff",
            description: "Seconds to wait before retrying a failed worker-managed refresh job.",
            value_type: "integer",
            restart_required: false,
            default_value: 60,
            override_value: null,
            effective_value: 60,
            updated_by: null,
            updated_at: null,
            min_value: 1,
            max_value: 3600,
            min_items: null,
            max_items: null,
            step: 1,
            unit: "seconds",
            is_overridden: false,
          },
        ],
      },
      {
        key: "invites",
        label: "Invites",
        items: [
          {
            key: "invite_ttl_hours",
            category: "invites",
            label: "Invite lifetime",
            description: "Hours before a newly created invite expires.",
            value_type: "integer",
            restart_required: false,
            default_value: 72,
            override_value: null,
            effective_value: 72,
            updated_by: null,
            updated_at: null,
            min_value: 1,
            max_value: 720,
            min_items: null,
            max_items: null,
            step: 1,
            unit: "hours",
            is_overridden: false,
          },
        ],
      },
    ],
  };
}

function submitLoginForm() {
  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "admin@example.com" } });
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "secret123" } });
  fireEvent.submit(screen.getByRole("button", { name: /sign in/i }).closest("form")!);
}

function openAccountMenu() {
  fireEvent.click(screen.getByRole("button", { name: /open account menu/i }));
}

function openSettingsFromAccountMenu() {
  openAccountMenu();
  fireEvent.click(screen.getByRole("button", { name: /^settings$/i }));
}

function mockMobileViewport(width = 390) {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: width,
  });
  Object.defineProperty(window, "scrollY", {
    configurable: true,
    value: 0,
  });
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn((query: string) => ({
      matches: query === "(pointer: coarse)",
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

function mockNarrowViewportWithoutCoarsePointer(width = 390) {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: width,
  });
  Object.defineProperty(window, "scrollY", {
    configurable: true,
    value: 0,
  });
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

async function openManualSearch() {
  fireEvent.click(screen.getAllByRole("button", { name: /^new search$/i })[0]!);
  await screen.findByRole("dialog", { name: /new search/i });
}

async function openTrackLotModal() {
  fireEvent.click(screen.getByRole("button", { name: /^track lot$/i }));
  await screen.findByRole("dialog", { name: /track lot/i });
}

async function runDefaultManualSearch() {
  await openManualSearch();
  fireEvent.click(screen.getByRole("button", { name: /search lots/i }));
  await screen.findByRole("dialog", { name: /search results/i });
}

describe("CarTrap app", () => {
  let lastSearchPayload: Record<string, unknown> | null;
  let loginRole: "admin" | "user";
  let liveSyncStatus: Record<string, unknown>;
  let searchShouldFail: boolean;
  let savedSearchesShouldFail: boolean;
  let savedSearchRefreshShouldFail: boolean;
  let pushTestShouldFail: boolean;
  let watchlistAddShouldFail: boolean;
  let watchlistRefreshShouldFail: boolean;
  let liveSearchCallCount: number;
  let watchlistListCallCount: number;
  let savedSearchesListCallCount: number;
  let systemStatusCallCount: number;
  let savedSearchViewCallCount: number;
  let savedSearchRefreshCallCount: number;
  let nextSavedSearchSeedNewLotNumbers: string[];
  let watchlistItems: Array<ReturnType<typeof buildTrackedLot>>;
  let watchlistHistoryById: Record<string, Array<ReturnType<typeof buildTrackedLotHistoryEntry>>>;
  let savedSearches: Array<ReturnType<typeof buildSavedSearch>>;
  let providerConnections: Array<ReturnType<typeof buildProviderConnection>>;
  let serviceWorkerMessageListener: ((event: MessageEvent) => void) | null;
  let adminOverviewCallCount: number;
  let adminUsersCallCount: number;
  let adminUserDetailCallCount: number;
  let adminRuntimeSettingsCallCount: number;
  let adminOverviewData: ReturnType<typeof buildAdminOverview>;
  let adminSystemHealthData: ReturnType<typeof buildAdminSystemHealth>;
  let adminUsersData: ReturnType<typeof buildAdminUserRow>[];
  let adminUserDetailsById: Record<string, ReturnType<typeof buildAdminUserDetail>>;
  let adminRuntimeSettingsData: ReturnType<typeof buildAdminRuntimeSettingsResponse>;

  beforeEach(() => {
    const storage = new Map<string, string>();
    const pushSubscriptions: Array<{
      id: string;
      endpoint: string;
      user_agent: string | null;
      created_at: string;
      updated_at: string;
    }> = [];
    lastSearchPayload = null;
    loginRole = "admin";
    liveSearchCallCount = 0;
    watchlistListCallCount = 0;
    savedSearchesListCallCount = 0;
    systemStatusCallCount = 0;
    savedSearchViewCallCount = 0;
    savedSearchRefreshCallCount = 0;
    nextSavedSearchSeedNewLotNumbers = [];
    watchlistItems = [];
    watchlistHistoryById = {};
    providerConnections = [buildProviderConnection()];
    serviceWorkerMessageListener = null;
    adminOverviewCallCount = 0;
    adminUsersCallCount = 0;
    adminUserDetailCallCount = 0;
    adminRuntimeSettingsCallCount = 0;
    adminOverviewData = buildAdminOverview();
    adminSystemHealthData = buildAdminSystemHealth();
    adminUsersData = [buildAdminUserRow()];
    adminUserDetailsById = {
      "managed-user-1": buildAdminUserDetail(),
    };
    adminRuntimeSettingsData = buildAdminRuntimeSettingsResponse();
    const findRuntimeSetting = (key: string) =>
      adminRuntimeSettingsData.groups.flatMap((group) => group.items).find((item) => item.key === key) ?? null;
    const applyRuntimeSettingUpdate = (key: string, value: number | number[]) => {
      const item = findRuntimeSetting(key);
      if (!item) {
        return false;
      }
      item.override_value = value;
      item.effective_value = value;
      item.updated_by = "user-1";
      item.updated_at = "2026-04-01T12:05:00Z";
      item.is_overridden = true;
      if (key === "saved_search_poll_interval_minutes" && typeof value === "number") {
        savedSearches = savedSearches.map((item) => ({
          ...item,
          freshness: {
            ...item.freshness,
            stale_after: addMinutes(item.last_synced_at, value),
          },
        }));
      }
      if (key === "watchlist_default_poll_interval_minutes" && typeof value === "number") {
        watchlistItems = watchlistItems.map((item) => ({
          ...item,
          freshness: {
            ...item.freshness,
            stale_after: addMinutes(item.last_checked_at, value),
          },
        }));
      }
      return true;
    };
    const resetRuntimeSetting = (key: string) => {
      const item = findRuntimeSetting(key);
      if (!item) {
        return false;
      }
      item.override_value = null;
      item.effective_value = item.default_value;
      item.updated_by = null;
      item.updated_at = null;
      item.is_overridden = false;
      return true;
    };
    savedSearchesShouldFail = false;
    savedSearchRefreshShouldFail = false;
    pushTestShouldFail = false;
    savedSearches = [];
    const savedSearchCaches = new Map<
      string,
      {
        results: Array<Record<string, unknown>>;
        new_lot_numbers: string[];
        cached_result_count: number;
        last_synced_at: string | null;
        seen_at: string | null;
      }
    >();
    liveSyncStatus = buildLiveSyncStatus();
    searchShouldFail = false;
    watchlistAddShouldFail = false;
    watchlistRefreshShouldFail = false;
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => void storage.set(key, value),
      removeItem: (key: string) => void storage.delete(key),
      clear: () => storage.clear(),
    });
    localStorage.clear();
    window.location.hash = "#/login";
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 0,
    });
    Object.defineProperty(window, "scrollTo", {
      configurable: true,
      value: vi.fn(),
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const authHeader =
          init?.headers && !Array.isArray(init.headers) && !(init.headers instanceof Headers)
            ? init.headers.Authorization
            : undefined;
        if (url.includes("/auth/login")) {
          return new Response(
            JSON.stringify({
              access_token: buildToken({ sub: "user-1", role: loginRole }),
              refresh_token: "refresh-token",
              token_type: "bearer",
            }),
            { status: 200 },
          );
        }
        if (url.includes("/auth/refresh")) {
          return new Response(
            JSON.stringify({
              access_token: buildToken({ sub: "user-1", role: loginRole, refreshed: true }),
              refresh_token: "refresh-token-next",
              token_type: "bearer",
            }),
            { status: 200 },
          );
        }
        if (url.includes("/admin/overview")) {
          adminOverviewCallCount += 1;
          return new Response(JSON.stringify(adminOverviewData), { status: 200 });
        }
        if (url.includes("/admin/system-health")) {
          return new Response(JSON.stringify(adminSystemHealthData), { status: 200 });
        }
        if (url.includes("/admin/runtime-settings/reset")) {
          const body = init?.body ? JSON.parse(String(init.body)) : {};
          for (const key of body.keys ?? []) {
            resetRuntimeSetting(String(key));
          }
          return new Response(JSON.stringify(adminRuntimeSettingsData), { status: 200 });
        }
        if (url.includes("/admin/runtime-settings")) {
          adminRuntimeSettingsCallCount += 1;
          if ((init?.method ?? "GET") === "POST") {
            const body = init?.body ? JSON.parse(String(init.body)) : {};
            const updates = Array.isArray(body.updates) ? body.updates : [];
            const invalidUpdate = updates.find((update) => {
              if (update.key === "saved_search_poll_interval_minutes") {
                return typeof update.value !== "number" || update.value < 1;
              }
              if (update.key === "watchlist_default_poll_interval_minutes") {
                return typeof update.value !== "number" || update.value < 1;
              }
              if (update.key === "job_retry_backoff_seconds") {
                return typeof update.value !== "number" || update.value < 1;
              }
              if (update.key === "invite_ttl_hours") {
                return typeof update.value !== "number" || update.value < 1;
              }
              if (update.key === "watchlist_auction_reminder_offsets_minutes") {
                return !Array.isArray(update.value) || update.value.length === 0;
              }
              return true;
            });
            if (invalidUpdate) {
              return new Response(JSON.stringify({ detail: "Runtime setting validation failed." }), { status: 422 });
            }
            for (const update of updates) {
              applyRuntimeSettingUpdate(update.key, update.value);
            }
          }
          return new Response(JSON.stringify(adminRuntimeSettingsData), { status: 200 });
        }
        if (url.includes("/admin/users/") && url.includes("/actions/")) {
          const action = url.split("/actions/")[1] ?? "";
          const userId = url.split("/admin/users/")[1]?.split("/actions/")[0] ?? "";
          const detail = adminUserDetailsById[userId];
          if (!detail) {
            return new Response(JSON.stringify({ detail: "User not found." }), { status: 404 });
          }
          if (action === "block") {
            detail.account.status = "blocked";
            const row = adminUsersData.find((item) => item.id === userId);
            if (row) {
              row.status = "blocked";
            }
            adminOverviewData = buildAdminOverview({
              users: { ...adminOverviewData.users, blocked: 1 },
            });
            adminSystemHealthData = buildAdminSystemHealth({ blocked_users: 1 });
            return new Response(
              JSON.stringify({
                action: "block",
                message: `Blocked ${detail.account.email}.`,
                scope: "account",
                user: detail.account,
                generated_password: null,
                counts: {},
              }),
              { status: 200 },
            );
          }
          return new Response(
            JSON.stringify({
              action,
              message: `Ran ${action}.`,
              scope: "resource",
              user: detail.account,
              generated_password: null,
              counts: {},
            }),
            { status: 200 },
          );
        }
        if (url.includes("/admin/users/") && !url.includes("/actions/")) {
          adminUserDetailCallCount += 1;
          const userId = url.split("/admin/users/")[1] ?? "";
          const detail = adminUserDetailsById[userId];
          if (!detail) {
            return new Response(JSON.stringify({ detail: "User not found." }), { status: 404 });
          }
          return new Response(JSON.stringify(detail), { status: 200 });
        }
        if (url.includes("/admin/users")) {
          adminUsersCallCount += 1;
          return new Response(
            JSON.stringify({
              items: adminUsersData,
              total: adminUsersData.length,
              page: 1,
              page_size: 25,
            }),
            { status: 200 },
          );
        }
        if (url.includes("/provider-connections")) {
          const method = init?.method ?? "GET";
          if (method === "GET") {
            return new Response(JSON.stringify({ items: providerConnections }), { status: 200 });
          }
          if (method === "POST" && url.endsWith("/copart/connect")) {
            const body = init?.body ? JSON.parse(String(init.body)) : {};
            const connection = buildProviderConnection({
              account_label: body.username ?? "copart-user@example.com",
              status: "connected",
              reconnect_required: false,
              usable: true,
              disconnected_at: null,
              last_error: null,
              updated_at: "2026-03-24T10:15:00Z",
            });
            providerConnections = [connection];
            return new Response(JSON.stringify({ connection }), { status: 200 });
          }
          if (method === "POST" && url.endsWith("/copart/reconnect")) {
            const body = init?.body ? JSON.parse(String(init.body)) : {};
            const current = providerConnections.find((item) => item.provider === "copart");
            const connection = buildProviderConnection({
              id: current?.id ?? "provider-connection-1",
              account_label: body.username ?? current?.account_label ?? "copart-user@example.com",
              status: "connected",
              reconnect_required: false,
              usable: true,
              disconnected_at: null,
              last_error: null,
              updated_at: "2026-03-24T10:20:00Z",
            });
            providerConnections = [connection];
            return new Response(JSON.stringify({ connection }), { status: 200 });
          }
          if (method === "DELETE" && url.endsWith("/provider-connections/copart")) {
            const current = providerConnections.find((item) => item.provider === "copart");
            const connection = buildProviderConnection({
              id: current?.id ?? "provider-connection-1",
              account_label: current?.account_label ?? "copart-user@example.com",
              status: "disconnected",
              reconnect_required: false,
              usable: false,
              disconnected_at: "2026-03-24T10:25:00Z",
              bundle: null,
              last_error: null,
              updated_at: "2026-03-24T10:25:00Z",
            });
            providerConnections = [connection];
            return new Response(JSON.stringify({ connection }), { status: 200 });
          }
        }
        if (url.includes("/watchlist") && !url.includes("/search/watchlist")) {
          if ((init?.method ?? "GET") === "GET" && authHeader === "Bearer expired-token") {
            return new Response(JSON.stringify({ detail: "Invalid access token." }), { status: 401 });
          }
          if ((init?.method ?? "GET") === "GET" && url.endsWith("/history")) {
            const id = url.split("/watchlist/")[1]?.replace("/history", "") ?? "";
            return new Response(
              JSON.stringify({
                tracked_lot_id: id,
                entries: watchlistHistoryById[id] ?? [],
              }),
              { status: 200 },
            );
          }
          if ((init?.method ?? "GET") === "GET") {
            watchlistListCallCount += 1;
          }
          if ((init?.method ?? "GET") === "POST" && url.endsWith("/acknowledge-update")) {
            const id = url.split("/watchlist/")[1]?.replace("/acknowledge-update", "") ?? "";
            const trackedLot = watchlistItems.find((item) => item.id === id);
            if (!trackedLot) {
              return new Response(JSON.stringify({ detail: "Tracked lot not found." }), { status: 404 });
            }
            const acknowledgedTrackedLot = {
              ...trackedLot,
              has_unseen_update: false,
            };
            watchlistItems = watchlistItems.map((item) => (item.id === id ? acknowledgedTrackedLot : item));
            return new Response(JSON.stringify({ tracked_lot: acknowledgedTrackedLot }), { status: 200 });
          }
          if ((init?.method ?? "GET") === "POST" && url.endsWith("/refresh-live")) {
            const id = url.split("/watchlist/")[1]?.replace("/refresh-live", "") ?? "";
            const trackedLot = watchlistItems.find((item) => item.id === id);
            if (!trackedLot) {
              return new Response(JSON.stringify({ detail: "Tracked lot not found." }), { status: 404 });
            }
            if (watchlistRefreshShouldFail) {
              const failedTrackedLot = {
                ...trackedLot,
                freshness: buildFreshness({
                  status: "outdated",
                  last_synced_at: trackedLot.last_checked_at ?? "2026-03-11T12:00:00Z",
                  stale_after: trackedLot.last_checked_at ?? "2026-03-11T12:15:00Z",
                  degraded_reason: "gateway timeout",
                  retryable: true,
                }),
                refresh_state: buildRefreshState({
                  status: "retryable_failure",
                  error_message: "gateway timeout",
                  retryable: true,
                  next_retry_at: "2026-03-16T12:25:00Z",
                  priority_class: "auction_imminent",
                  last_outcome: "refresh_failed",
                  metrics: { change_count: 0, reminder_count: 0 },
                }),
              };
              watchlistItems = watchlistItems.map((item) => (item.id === id ? failedTrackedLot : item));
              return new Response(JSON.stringify({ detail: "gateway timeout" }), { status: 502 });
            }
            const refreshedTrackedLot = {
              ...trackedLot,
              last_checked_at: "2026-03-16T12:18:00Z",
              freshness: buildFreshness({
                last_synced_at: "2026-03-16T12:18:00Z",
                stale_after: "2026-03-16T12:33:00Z",
              }),
              refresh_state: buildRefreshState({
                status: "idle",
                last_attempted_at: "2026-03-16T12:18:00Z",
                last_succeeded_at: "2026-03-16T12:18:00Z",
                priority_class: "manual",
                last_outcome: "refreshed",
                metrics: { change_count: 0, reminder_count: 0 },
              }),
            };
            watchlistItems = watchlistItems.map((item) => (item.id === id ? refreshedTrackedLot : item));
            return new Response(JSON.stringify({ tracked_lot: refreshedTrackedLot }), { status: 200 });
          }
          if ((init?.method ?? "GET") === "POST") {
            if (watchlistAddShouldFail) {
              return new Response(JSON.stringify({ detail: "Failed to fetch lot details from Copart: gateway unavailable" }), {
                status: 502,
              });
            }
            const body = init?.body ? JSON.parse(String(init.body)) : {};
            const trackedLot =
              body.lot_number === "99251295"
                ? buildTrackedLot({
                    id: "tracked-2",
                    lot_number: "99251295",
                    url: "https://www.copart.com/lot/99251295",
                    title: "2025 FORD MUSTANG MACH-E PREMIUM",
                    thumbnail_url: "https://img.copart.com/99251295-detail.jpg",
                    image_urls: [
                      "https://img.copart.com/99251295-detail.jpg",
                      "https://img.copart.com/99251295-detail-2.jpg",
                    ],
                    sale_date: "2026-03-13T18:30:00Z",
                    vin: "3FMTK3SU5SMA00001",
                  })
                : body.lot_number === "87654321"
                  ? buildTrackedLot({
                      id: "tracked-3",
                      lot_number: "87654321",
                      url: "https://www.copart.com/lot/87654321",
                      title: "2018 HONDA CIVIC EX",
                      thumbnail_url: "https://img.copart.com/87654321-detail.jpg",
                      image_urls: ["https://img.copart.com/87654321-detail.jpg"],
                      odometer: null,
                      primary_damage: null,
                      estimated_retail_value: null,
                      has_key: null,
                      drivetrain: null,
                      highlights: [],
                      vin: null,
                    })
                  : buildTrackedLot();
            watchlistItems = [trackedLot, ...watchlistItems.filter((item) => item.id !== trackedLot.id)];
            return new Response(JSON.stringify({ tracked_lot: trackedLot }), { status: 201 });
          }
          return new Response(JSON.stringify({ items: watchlistItems }), { status: 200 });
        }
        if (url.includes("/notifications/subscription-config")) {
          return new Response(
            JSON.stringify({
              enabled: true,
              public_key: "BKagOANM9SWjR8el7V_FakePublicKey1234567890abcdEFGHijklmnop",
              reason: null,
            }),
            { status: 200 },
          );
        }
        if (url.includes("/notifications/subscriptions")) {
          const method = init?.method ?? "GET";
          if (method === "POST") {
            const body = init?.body ? JSON.parse(String(init.body)) : {};
            const created = {
              id: `push-${pushSubscriptions.length + 1}`,
              endpoint: body.subscription?.endpoint ?? "https://push.example.test/subscriptions/default",
              user_agent: body.user_agent ?? null,
              created_at: "2026-03-13T16:24:00Z",
              updated_at: "2026-03-13T16:24:00Z",
            };
            const existingIndex = pushSubscriptions.findIndex((item) => item.endpoint === created.endpoint);
            if (existingIndex >= 0) {
              pushSubscriptions.splice(existingIndex, 1, created);
            } else {
              pushSubscriptions.unshift(created);
            }
            return new Response(JSON.stringify(created), { status: 201 });
          }
          if (method === "DELETE") {
            const endpoint = new URL(url).searchParams.get("endpoint");
            const nextItems = pushSubscriptions.filter((item) => item.endpoint !== endpoint);
            pushSubscriptions.splice(0, pushSubscriptions.length, ...nextItems);
            return new Response(null, { status: 204 });
          }
          return new Response(JSON.stringify({ items: pushSubscriptions }), { status: 200 });
        }
        if (url.includes("/search/catalog")) {
          return new Response(
            JSON.stringify({
              generated_at: "2026-03-12T16:40:00Z",
              updated_at: "2026-03-12T16:41:00Z",
              summary: {
                make_count: 2,
                model_count: 3,
                assigned_model_count: 3,
                exact_match_count: 2,
                fuzzy_match_count: 1,
                unassigned_model_count: 0,
                year_count: 108,
              },
              years: [2025, 2026, 2027],
              manual_override_count: 1,
              makes: [
                {
                  slug: "ford",
                  name: "FORD",
                  aliases: [],
                  search_filter: 'lot_make_desc:"FORD" OR manufacturer_make_desc:"FORD"',
                  models: [
                    {
                      slug: "broncosport",
                      name: "BRONCO SPORT",
                      search_filter:
                        'lot_model_desc:"BRONCO SPORT" OR manufacturer_model_desc:"BRONCO SPORT"',
                    },
                    {
                      slug: "mustangmache",
                      name: "MUSTANG MACH-E",
                      search_filter:
                        'lot_model_desc:"MUSTANG MACH-E" OR manufacturer_model_desc:"MUSTANG MACH-E"',
                    },
                  ],
                },
                {
                  slug: "fiat",
                  name: "FIAT",
                  aliases: [],
                  search_filter: 'lot_make_desc:"FIAT" OR manufacturer_make_desc:"FIAT"',
                  models: [
                    {
                      slug: "500x",
                      name: "500X",
                      search_filter: 'lot_model_desc:"500X" OR manufacturer_model_desc:"500X"',
                    },
                  ],
                },
                {
                  slug: "toyota",
                  name: "TOYOTA",
                  aliases: [],
                  search_filter: 'lot_make_desc:"TOYOTA" OR manufacturer_make_desc:"TOYOTA"',
                  models: [
                    {
                      slug: "camry",
                      name: "CAMRY",
                      search_filter: 'lot_model_desc:"CAMRY" OR manufacturer_model_desc:"CAMRY"',
                    },
                  ],
                },
              ],
            }),
            { status: 200 },
          );
        }
        if (url.includes("/search/saved/") && url.endsWith("/view")) {
          savedSearchViewCallCount += 1;
          const id = url.split("/search/saved/")[1]?.replace("/view", "") ?? "";
          const savedSearch = savedSearches.find((item) => item.id === id);
          if (!savedSearch) {
            return new Response(JSON.stringify({ detail: "Saved search not found." }), { status: 404 });
          }
          const cache = savedSearchCaches.get(id) ?? {
            results: [],
            new_lot_numbers: [],
            cached_result_count: 0,
            last_synced_at: null,
            seen_at: null,
          };
          const response = {
            saved_search: { ...savedSearch, new_count: 0 },
            results: cache.results.map((result) => ({
              ...result,
              is_new: cache.new_lot_numbers.includes(String(result.lot_number)),
            })),
            cached_result_count: cache.cached_result_count,
            new_count: cache.new_lot_numbers.length,
            last_synced_at: cache.last_synced_at,
            seen_at: cache.seen_at,
          };
          savedSearch.new_count = 0;
          savedSearchCaches.set(id, {
            ...cache,
            new_lot_numbers: [],
            seen_at: "2026-03-16T12:10:00Z",
          });
          return new Response(JSON.stringify(response), { status: 200 });
        }
        if (url.includes("/search/saved/") && url.endsWith("/refresh-live")) {
          savedSearchRefreshCallCount += 1;
          const id = url.split("/search/saved/")[1]?.replace("/refresh-live", "") ?? "";
          const savedSearch = savedSearches.find((item) => item.id === id);
          if (!savedSearch) {
            return new Response(JSON.stringify({ detail: "Saved search not found." }), { status: 404 });
          }
          if (savedSearchRefreshShouldFail) {
            const failedSavedSearch = {
              ...savedSearch,
              freshness: buildFreshness({
                status: "outdated",
                last_synced_at: savedSearch.last_synced_at ?? "2026-03-16T12:00:00Z",
                stale_after: savedSearch.last_synced_at ?? "2026-03-16T12:15:00Z",
                degraded_reason: "gateway timeout",
                retryable: true,
              }),
              refresh_state: buildRefreshState({
                status: "retryable_failure",
                error_message: "gateway timeout",
                retryable: true,
                next_retry_at: "2026-03-16T12:20:00Z",
                priority_class: "recently_changed",
                last_outcome: "refresh_failed",
                metrics: { new_matches: 0, cached_new_count: 0 },
              }),
            };
            const index = savedSearches.findIndex((item) => item.id === id);
            savedSearches.splice(index, 1, failedSavedSearch);
            return new Response(JSON.stringify({ detail: "gateway timeout" }), { status: 502 });
          }
          const refreshedResults = [
            buildSearchResult(),
            buildSearchResult({
              provider_lot_id: "87654321",
              lot_key: "copart:87654321",
              lot_number: "87654321",
              title: "2018 HONDA CIVIC EX",
              url: "https://www.copart.com/lot/87654321",
              thumbnail_url: null,
              location: "TX - DALLAS",
              current_bid: 1800,
              status: "upcoming",
            }),
          ];
          const refreshedSavedSearch = {
            ...savedSearch,
            result_count: refreshedResults.length,
            cached_result_count: refreshedResults.length,
            new_count: 0,
            last_synced_at: "2026-03-16T12:15:00Z",
            freshness: buildFreshness({
              last_synced_at: "2026-03-16T12:15:00Z",
              stale_after: "2026-03-16T12:30:00Z",
            }),
            refresh_state: buildRefreshState({
              status: "idle",
              last_attempted_at: "2026-03-16T12:15:00Z",
              last_succeeded_at: "2026-03-16T12:15:00Z",
              priority_class: "manual",
              last_outcome: "refreshed",
              metrics: { new_matches: 0, cached_new_count: 0 },
            }),
          };
          const index = savedSearches.findIndex((item) => item.id === id);
          savedSearches.splice(index, 1, refreshedSavedSearch);
          savedSearchCaches.set(id, {
            results: refreshedResults,
            new_lot_numbers: [],
            cached_result_count: refreshedResults.length,
            last_synced_at: "2026-03-16T12:15:00Z",
            seen_at: "2026-03-16T12:15:00Z",
          });
          return new Response(
            JSON.stringify({
              saved_search: refreshedSavedSearch,
              results: refreshedResults.map((result) => ({ ...result, is_new: false })),
              cached_result_count: refreshedResults.length,
              new_count: 0,
              last_synced_at: "2026-03-16T12:15:00Z",
              seen_at: "2026-03-16T12:15:00Z",
            }),
            { status: 200 },
          );
        }
        if (url.includes("/search/saved")) {
          if ((init?.method ?? "GET") === "DELETE") {
            const id = url.split("/").pop() ?? "";
            const index = savedSearches.findIndex((item) => item.id === id);
            if (index >= 0) {
              savedSearches.splice(index, 1);
            }
            savedSearchCaches.delete(id);
            return new Response(null, { status: 204 });
          }
          if ((init?.method ?? "GET") === "POST") {
            const body = init?.body ? JSON.parse(String(init.body)) : {};
            const duplicate = savedSearches.find(
              (item) =>
                JSON.stringify(item.criteria) ===
                JSON.stringify({
                  providers: body.providers,
                  make: body.make,
                  model: body.model,
                  make_filter: body.make_filter,
                  model_filter: body.model_filter,
                  drive_type: body.drive_type,
                  primary_damage: body.primary_damage,
                  title_type: body.title_type,
                  fuel_type: body.fuel_type,
                  lot_condition: body.lot_condition,
                  odometer_range: body.odometer_range,
                  year_from: body.year_from,
                  year_to: body.year_to,
                }),
            );
            if (duplicate) {
              return new Response("Search is already saved.", { status: 409 });
            }
            const seedResults = Array.isArray(body.seed_results) ? body.seed_results : [];
            const savedSearch = buildSavedSearch({
              id: `saved-${savedSearches.length + 1}`,
              label: body.label ?? `${body.make ?? ""} ${body.model ?? ""} ${body.year_from ?? ""}-${body.year_to ?? ""}`.trim(),
              criteria: {
                providers: body.providers ?? ["copart"],
                make: body.make,
                model: body.model,
                make_filter: body.make_filter,
                model_filter: body.model_filter,
                drive_type: body.drive_type,
                primary_damage: body.primary_damage,
                title_type: body.title_type,
                fuel_type: body.fuel_type,
                lot_condition: body.lot_condition,
                odometer_range: body.odometer_range,
                year_from: body.year_from,
                year_to: body.year_to,
              },
              result_count: body.result_count ?? seedResults.length ?? null,
              cached_result_count: seedResults.length,
              new_count: nextSavedSearchSeedNewLotNumbers.length,
              last_synced_at: seedResults.length > 0 ? "2026-03-16T12:00:00Z" : null,
              freshness: buildFreshness({
                status: seedResults.length > 0 ? "live" : "unknown",
                last_synced_at: seedResults.length > 0 ? "2026-03-16T12:00:00Z" : null,
                stale_after: seedResults.length > 0 ? "2026-03-16T12:15:00Z" : null,
              }),
              refresh_state: buildRefreshState({
                last_attempted_at: seedResults.length > 0 ? "2026-03-16T12:00:00Z" : null,
                last_succeeded_at: seedResults.length > 0 ? "2026-03-16T12:00:00Z" : null,
                last_outcome: seedResults.length > 0 ? "refreshed" : null,
                metrics: { new_matches: 0, cached_new_count: 0 },
              }),
            });
            savedSearches.unshift(savedSearch);
            savedSearchCaches.set(savedSearch.id, {
              results: seedResults,
              new_lot_numbers: nextSavedSearchSeedNewLotNumbers,
              cached_result_count: seedResults.length,
              last_synced_at: savedSearch.last_synced_at,
              seen_at: seedResults.length > 0 ? "2026-03-16T12:00:00Z" : null,
            });
            nextSavedSearchSeedNewLotNumbers = [];
            return new Response(JSON.stringify({ saved_search: savedSearch }), { status: 201 });
          }
          if (savedSearchesShouldFail) {
            return new Response(JSON.stringify({ detail: "Saved-search cache is unavailable." }), { status: 503 });
          }
          savedSearchesListCallCount += 1;
          return new Response(JSON.stringify({ items: savedSearches }), { status: 200 });
        }
        if (url.includes("/notifications/test")) {
          if (pushTestShouldFail) {
            return new Response(JSON.stringify({ detail: "Push sender is unavailable." }), { status: 503 });
          }
          return new Response(
            JSON.stringify({
              delivered: 1,
              failed: 0,
              removed: 0,
              endpoints: ["https://push.example.test/subscriptions/device-1"],
            }),
            { status: 200 },
          );
        }
        if (url.includes("/admin/search-catalog/refresh")) {
          return new Response(
            JSON.stringify({
              generated_at: "2026-03-12T17:00:00Z",
              updated_at: "2026-03-12T17:00:05Z",
              summary: {
                make_count: 2,
                model_count: 3,
                assigned_model_count: 3,
                exact_match_count: 2,
                fuzzy_match_count: 1,
                unassigned_model_count: 0,
                year_count: 108,
              },
              years: [2025, 2026, 2027],
              manual_override_count: 1,
              makes: [],
            }),
            { status: 200 },
          );
        }
        if (url.includes("/system/status")) {
          systemStatusCallCount += 1;
          const savedSearchPollInterval =
            (findRuntimeSetting("saved_search_poll_interval_minutes")?.effective_value as number | undefined) ?? 15;
          const watchlistPollInterval =
            (findRuntimeSetting("watchlist_default_poll_interval_minutes")?.effective_value as number | undefined) ?? 15;
          return new Response(
            JSON.stringify({
              status: "ok",
              service: "CarTrap API",
              environment: "test",
              live_sync: liveSyncStatus,
              freshness_policies: {
                saved_searches: { stale_after_seconds: savedSearchPollInterval * 60 },
                watchlist: { stale_after_seconds: watchlistPollInterval * 60 },
              },
            }),
            { status: 200 },
          );
        }
        if (url.endsWith("/search")) {
          liveSearchCallCount += 1;
          const body = init?.body ? JSON.parse(String(init.body)) : {};
          lastSearchPayload = body;
          if (searchShouldFail) {
            return new Response(JSON.stringify({ detail: "Failed to fetch search results from Copart." }), { status: 502 });
          }
          const requestedProviders = Array.isArray(body.providers) && body.providers.length > 0 ? body.providers : ["copart"];
          const buildIaaiSearchResult = () =>
            buildSearchResult({
              provider: "iaai",
              auction_label: "IAAI",
              provider_lot_id: "99112233",
              lot_key: "iaai:99112233",
              lot_number: "STK-44",
              title: "2025 FORD MUSTANG MACH-E PREMIUM",
              url: "https://www.iaai.com/VehicleDetail/99112233~US",
              thumbnail_url: "https://img.iaai.com/99112233.jpg",
              location: "Phoenix, AZ",
              odometer: "44,210",
              current_bid: 9100,
              buy_now_price: null,
              status: "live",
              raw_status: "Live",
            });
          if (body.make !== "FORD" || body.model !== "MUSTANG MACH-E") {
            return new Response(JSON.stringify({ total_results: 0, results: [] }), { status: 200 });
          }
          if (requestedProviders.length === 1 && requestedProviders[0] === "iaai") {
            return new Response(
              JSON.stringify({
                total_results: 1,
                results: [buildIaaiSearchResult()],
              }),
              { status: 200 },
            );
          }
          return new Response(
            JSON.stringify({
              total_results: requestedProviders.includes("iaai") ? 2 : 1,
              results: requestedProviders.includes("iaai") ? [buildSearchResult(), buildIaaiSearchResult()] : [buildSearchResult()],
            }),
            { status: 200 },
          );
        }
        if (url.includes("/search/watchlist")) {
          const body = init?.body ? JSON.parse(String(init.body)) : {};
          const trackedLot =
            body.provider === "iaai"
              ? buildTrackedLot({
                  id: "tracked-iaai-1",
                  provider: "iaai",
                  auction_label: "IAAI",
                  provider_lot_id: body.provider_lot_id ?? "99112233",
                  lot_key: `iaai:${body.provider_lot_id ?? "99112233"}`,
                  lot_number: body.lot_number ?? "STK-44",
                  url: "https://www.iaai.com/VehicleDetail/99112233~US",
                  title: "2025 FORD MUSTANG MACH-E PREMIUM",
                  thumbnail_url: "https://img.iaai.com/99112233.jpg",
                  image_urls: ["https://img.iaai.com/99112233.jpg"],
                  odometer: "44,210",
                  current_bid: 9100,
                })
              : buildTrackedLot();
          watchlistItems = [trackedLot, ...watchlistItems.filter((item) => item.id !== trackedLot.id)];
          return new Response(JSON.stringify({ tracked_lot: trackedLot }), { status: 201 });
        }
        if (url.includes("/admin/invites")) {
          if ((init?.method ?? "GET") === "POST") {
            return new Response(
              JSON.stringify({
                id: "invite-1",
                email: "buyer@example.com",
                status: "pending",
                token: "invite-token",
                expires_at: "2026-03-14T12:00:00Z",
              }),
              { status: 200 },
            );
          }
          return new Response(
            JSON.stringify({
              items: [
                {
                  id: "invite-1",
                  email: "buyer@example.com",
                  status: "pending",
                  token: "invite-token",
                  expires_at: "2026-03-14T12:00:00Z",
                },
              ],
            }),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify({}), { status: 200 });
      }),
    );
    vi.stubGlobal("Notification", {
      permission: "denied",
      requestPermission: vi.fn(async () => "denied"),
    });
    Object.defineProperty(window.navigator, "serviceWorker", {
      configurable: true,
      value: {
        addEventListener: vi.fn((type: string, listener: (event: MessageEvent) => void) => {
          if (type === "message") {
            serviceWorkerMessageListener = listener;
          }
        }),
        removeEventListener: vi.fn((type: string, listener: (event: MessageEvent) => void) => {
          if (type === "message" && serviceWorkerMessageListener === listener) {
            serviceWorkerMessageListener = null;
          }
        }),
        getRegistration: vi.fn(async () => undefined),
        register: vi.fn(async () => undefined),
        ready: Promise.resolve(undefined),
      },
    });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("renders login and opens dashboard after auth", async () => {
    render(<App />);

    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    expect(screen.queryByLabelText(/user summary/i)).toBeNull();
    expect(screen.getByRole("button", { name: /open account menu/i })).toBeTruthy();
    expect(screen.getByAltText(/cartrap for copart and iaai/i)).toBeTruthy();
    const searchHeading = screen.getByRole("heading", { name: /saved searches/i });
    const watchlistHeading = screen.getByRole("heading", { name: /tracked lots/i });
    const invitesHeading = screen.getByRole("heading", { name: /generate invites/i });
    expect(screen.getByText(/generate invites/i)).toBeTruthy();
    expect(searchHeading.compareDocumentPosition(invitesHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(watchlistHeading.compareDocumentPosition(invitesHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText(/you don't have any saved searches yet/i)).toBeTruthy();
  });

  it("loads admin command center for admin sessions", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/command center/i);
    await screen.findByRole("heading", { name: /^runtime settings$/i });
    expect(screen.getByText(/user directory/i)).toBeTruthy();
    expect(screen.getByRole("heading", { name: /^runtime settings$/i })).toBeTruthy();
    expect(screen.getByText(/managed-user@example\.com/i)).toBeTruthy();
    expect(screen.getByText(/live sync degraded/i)).toBeTruthy();
    expect(adminOverviewCallCount).toBeGreaterThan(0);
    expect(adminUsersCallCount).toBeGreaterThan(0);
    expect(adminRuntimeSettingsCallCount).toBeGreaterThan(0);
  });

  it("opens admin user detail and runs a confirmed root action", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/managed-user@example\.com/i);
    fireEvent.click(screen.getByRole("button", { name: /managed-user@example\.com/i }));

    await screen.findByRole("complementary", { name: /admin user detail/i }).catch(() => null);
    expect(await screen.findByText(/invite history/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /^block user$/i }));
    const confirmDialog = await screen.findByRole("dialog", { name: /block user/i });
    fireEvent.click(within(confirmDialog).getByRole("button", { name: /^block user$/i }));

    expect(await screen.findByText(/blocked managed-user@example\.com\./i)).toBeTruthy();
    await waitFor(() => {
      expect(screen.getAllByText(/^blocked$/i).length).toBeGreaterThan(0);
    });
    expect(adminUserDetailCallCount).toBeGreaterThan(0);
  });

  it("keeps admin workspace out of non-admin bootstrap", async () => {
    loginRole = "user";

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    expect(screen.queryByText(/command center/i)).toBeNull();
    expect(screen.queryByText(/user directory/i)).toBeNull();
    expect(adminOverviewCallCount).toBe(0);
    expect(adminUsersCallCount).toBe(0);
    expect(adminUserDetailCallCount).toBe(0);
    expect(adminRuntimeSettingsCallCount).toBe(0);
  });

  it("edits, saves, and resets runtime settings from admin workspace", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByRole("heading", { name: /^runtime settings$/i });
    const savedSearchInput = screen.getByRole("textbox", { name: /saved search poll interval/i });
    fireEvent.change(savedSearchInput, { target: { value: "6" } });
    fireEvent.click(screen.getByRole("button", { name: /save runtime settings/i }));

    expect(await screen.findByText(/runtime settings saved\./i)).toBeTruthy();
    expect((screen.getByRole("textbox", { name: /saved search poll interval/i }) as HTMLInputElement).value).toBe("6");

    fireEvent.click(screen.getByRole("button", { name: /reset saved search poll interval/i }));

    expect(await screen.findByText(/runtime setting reset to default\./i)).toBeTruthy();
    await waitFor(() => {
      expect((screen.getByRole("textbox", { name: /saved search poll interval/i }) as HTMLInputElement).value).toBe("15");
    });
  });

  it("shows validation errors for invalid runtime setting drafts", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByRole("heading", { name: /^runtime settings$/i });
    fireEvent.change(screen.getByRole("textbox", { name: /saved search poll interval/i }), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: /save runtime settings/i }));

    expect(await screen.findByText(/saved search poll interval must be at least 1\./i)).toBeTruthy();
  });

  it("renders invite acceptance screen from hash route", () => {
    window.location.hash = "#/invite?token=abc123";

    render(<App />);

    expect(screen.getByText(/create your cartrap password/i)).toBeTruthy();
    expect(screen.getByText("abc123")).toBeTruthy();
  });

  it("renders manual search as a portal outside the pullable app shell after dashboard scroll", async () => {
    mockMobileViewport();

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 420,
    });

    await openManualSearch();

    const manualSearchDialog = screen.getByRole("dialog", { name: /new search/i });
    const appShell = document.querySelector(".app-shell");
    expect(appShell?.contains(manualSearchDialog)).toBe(false);
    expect(document.body.style.position).toBe("fixed");
    expect(document.documentElement.style.overflow).toBe("hidden");
  });

  it("collapses saved searches and tracked lots on mobile", async () => {
    mockMobileViewport();

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    expect(screen.getByText(/you don't have any saved searches yet/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /^track lot$/i })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /collapse saved searches/i }));
    fireEvent.click(screen.getByRole("button", { name: /collapse tracked lots/i }));

    expect(screen.queryByText(/you don't have any saved searches yet/i)).toBeNull();
    expect(screen.queryByLabelText(/lot number/i)).toBeNull();
    expect(screen.queryByText(/you haven't added any lots yet/i)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /expand saved searches/i }));
    fireEvent.click(screen.getByRole("button", { name: /expand tracked lots/i }));

    expect(screen.getByText(/you don't have any saved searches yet/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /^track lot$/i })).toBeTruthy();
    expect(screen.getByText(/you haven't added any lots yet/i)).toBeTruthy();
  });

  it("updates track-lot modal copy when switching auction site", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await openTrackLotModal();
    const trackLotDialog = screen.getByRole("dialog", { name: /track lot/i });

    expect(within(trackLotDialog).getByLabelText(/lot number/i)).toBeTruthy();
    expect(within(trackLotDialog).getByText(/enter the copart lot number from the listing\./i)).toBeTruthy();

    fireEvent.click(within(trackLotDialog).getByRole("button", { name: /^iaai$/i }));

    expect(within(trackLotDialog).getByLabelText(/stock or item id/i)).toBeTruthy();
    expect(within(trackLotDialog).getByPlaceholderText("STK-44 or 42153827")).toBeTruthy();
    expect(within(trackLotDialog).getByText(/enter the iaai stock number or item id from the listing\./i)).toBeTruthy();
  });

  it("renders track-lot modal as a fullscreen mobile overlay outside the app shell", async () => {
    mockMobileViewport();

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 360,
    });

    await openTrackLotModal();

    const trackLotDialog = screen.getByRole("dialog", { name: /track lot/i });
    const appShell = document.querySelector(".app-shell");
    expect(appShell?.contains(trackLotDialog)).toBe(false);
    expect(trackLotDialog.className).toContain("modal-card--mobile-screen");
  });

  it("keeps mobile saved-search filter labels and counts visible", async () => {
    mockMobileViewport();
    savedSearches = [
      buildSavedSearch({
        id: "saved-1",
        new_count: 1,
        freshness: buildFreshness({
          status: "outdated",
          last_synced_at: "2026-03-16T10:00:00Z",
          stale_after: "2026-03-16T10:15:00Z",
        }),
        refresh_state: buildRefreshState({
          status: "retryable_failure",
          error_message: "gateway unavailable",
          retryable: true,
          priority_class: "recently_changed",
        }),
      }),
    ];

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    expect(screen.getByRole("button", { name: /all saved searches, 1/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /new saved searches, 1/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /attention needed, 1/i })).toBeTruthy();
    expect(screen.getByText(/^1 new$/i)).toBeTruthy();
  });

  it("renders provider branding in saved searches and tracked lots", async () => {
    savedSearches = [
      buildSavedSearch({
        criteria: {
          providers: ["copart", "iaai"],
          make: "FORD",
          model: "MUSTANG MACH-E",
          year_from: 2025,
          year_to: 2027,
        },
      }),
    ];
    watchlistItems = [
      buildTrackedLot({
        provider: "iaai",
        auction_label: "IAAI",
        provider_lot_id: "STK-44",
        lot_key: "iaai:STK-44",
        lot_number: "STK-44",
        url: "https://www.iaai.com/VehicleDetail/STK-44",
        title: "2025 FORD MUSTANG MACH-E PREMIUM",
      }),
    ];

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    const savedSearchCard = screen.getAllByText(/FORD MUSTANG MACH-E 2025-2027/i)[0]!.closest(".saved-search-card")!;
    expect(savedSearchCard.querySelector('.auction-provider-badge[aria-label="Copart"]')).toBeTruthy();
    expect(savedSearchCard.querySelector('.auction-provider-badge[aria-label="IAAI"]')).toBeTruthy();

    const watchlistCard = screen.getByText(/2025 FORD MUSTANG MACH-E PREMIUM/i).closest(".watchlist-card")!;
    expect(within(watchlistCard).getByText(/^IAAI$/i).closest(".auction-provider-badge")).toBeTruthy();
  });

  it("runs manual search and adds result to tracked lots", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await runDefaultManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /add to tracked lots/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/2020 TOYOTA CAMRY SE/i).length).toBeGreaterThan(1);
    });
    const resultsDialog = screen.getByRole("dialog", { name: /search results/i });
    const lotLink = within(resultsDialog).getByRole("link", { name: /open copart lot 12345678/i });
    const trackedButton = within(resultsDialog).getByRole("button", {
      name: /already in tracked lots: 2020 toyota camry se/i,
    });
    expect(within(resultsDialog).getByText(/^Copart$/i).closest(".auction-provider-badge")).toBeTruthy();
    expect(lotLink.getAttribute("href")).toBe("https://www.copart.com/lot/12345678");
    expect(lotLink.getAttribute("target")).toBe("_blank");
    expect(trackedButton.getAttribute("disabled")).not.toBeNull();
    expect(within(resultsDialog).getByText(/added 2020 toyota camry se to your tracked lots\./i)).toBeTruthy();
    expect(screen.getByText(/Lot#: 12345678/i)).toBeTruthy();
    expect(screen.getByText(/Odometer: 12,345 ACTUAL/i)).toBeTruthy();
    expect(screen.getAllByAltText(/2020 TOYOTA CAMRY SE/i).length).toBeGreaterThan(1);
  });

  it("supports IAAI-only manual search and adds IAAI result to tracked lots", async () => {
    providerConnections = [
      buildProviderConnection(),
      buildProviderConnection({
        id: "provider-connection-iaai-1",
        provider: "iaai",
        provider_label: "IAAI",
        account_label: "iaai-user@example.com",
      }),
    ];

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await openManualSearch();
    const manualSearchDialog = screen.getByRole("dialog", { name: /new search/i });

    fireEvent.click(within(manualSearchDialog).getByRole("button", { name: /^iaai$/i }));
    fireEvent.click(within(manualSearchDialog).getByRole("button", { name: /^copart$/i }));
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /providers unavailable/i })).toBeNull();
    });

    fireEvent.click(within(manualSearchDialog).getByRole("button", { name: /search lots/i }));

    const resultsDialog = await screen.findByRole("dialog", { name: /search results/i });
    expect(lastSearchPayload?.providers).toEqual(["iaai"]);
    expect(within(resultsDialog).getAllByText(/IAAI/i).length).toBeGreaterThan(0);
    expect(within(resultsDialog).getByText(/^IAAI$/i).closest(".auction-provider-badge")).toBeTruthy();
    expect(within(resultsDialog).getByRole("link", { name: /open iaai lot stk-44/i })).toBeTruthy();

    fireEvent.click(within(resultsDialog).getByRole("button", { name: /add to tracked lots: 2025 ford mustang mach-e premium/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/2025 FORD MUSTANG MACH-E PREMIUM/i).length).toBeGreaterThan(1);
    });
    expect(screen.getByText(/Lot STK-44/i)).toBeTruthy();
  });

  it("filters make and model lists while typing", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await openManualSearch();

    fireEvent.focus(screen.getByLabelText("Make"));
    fireEvent.change(screen.getByLabelText("Make"), { target: { value: "F" } });

    expect(screen.getByRole("button", { name: "FORD" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "FIAT" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "TOYOTA" })).toBeNull();

    fireEvent.focus(screen.getByLabelText("Model"));
    fireEvent.change(screen.getByLabelText("Model"), { target: { value: "MAC" } });

    expect(screen.getByRole("button", { name: "MUSTANG MACH-E" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "BRONCO SPORT" })).toBeNull();
  });

  it("applies modal filters before running search", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await openManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /filters/i }));
    await screen.findByRole("dialog", { name: /search filters/i });

    fireEvent.change(screen.getByLabelText(/drive train/i), { target: { value: "all_wheel_drive" } });
    fireEvent.change(screen.getByLabelText(/primary damage/i), { target: { value: "hail" } });
    fireEvent.change(screen.getByLabelText(/title type/i), { target: { value: "salvage_title" } });
    fireEvent.change(screen.getByLabelText(/fuel type/i), { target: { value: "electric" } });
    fireEvent.change(screen.getByLabelText(/sale highlight/i), { target: { value: "run_and_drive" } });
    fireEvent.change(screen.getByLabelText(/odometer/i), { target: { value: "under_25000" } });
    fireEvent.click(screen.getByRole("button", { name: /apply filters/i }));

    await screen.findByText(/Filters:/i);
    expect(screen.getByRole("button", { name: /filters \(6 active\)/i })).toBeTruthy();
    expect(screen.getByText(/All Wheel Drive · Hail · Salvage Title · Electric · Run and Drive · Under 25,000 mi/i)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /search lots/i }));
    await screen.findByRole("dialog", { name: /search results/i });

    expect(lastSearchPayload?.drive_type).toBe("all_wheel_drive");
    expect(lastSearchPayload?.primary_damage).toBe("hail");
    expect(lastSearchPayload?.title_type).toBe("salvage_title");
    expect(lastSearchPayload?.fuel_type).toBe("electric");
    expect(lastSearchPayload?.lot_condition).toBe("run_and_drive");
    expect(lastSearchPayload?.odometer_range).toBe("under_25000");
  });

  it("renders search filters as a mobile fullscreen overlay outside the app shell", async () => {
    mockMobileViewport();

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 360,
    });
    await openManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /filters/i }));

    const filtersDialog = await screen.findByRole("dialog", { name: /search filters/i });
    const appShell = document.querySelector(".app-shell");
    expect(appShell?.contains(filtersDialog)).toBe(false);
    expect(filtersDialog.className).toContain("modal-card--mobile-screen");
  });

  it("saves a search, seeds cached results, and reruns it from the saved searches list without live search", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await runDefaultManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /save search/i }));

    await screen.findByText(/just saved/i);
    expect(await screen.findByRole("button", { name: /^ford mustang mach-e 2025-2027/i })).toBeTruthy();
    expect(await screen.findByText(/1 lot found/i)).toBeTruthy();
    expect(liveSearchCallCount).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: /^ford mustang mach-e 2025-2027/i }));

    await screen.findByRole("dialog", { name: /search results/i });
    expect(savedSearchViewCallCount).toBe(1);
    expect(liveSearchCallCount).toBe(1);
    expect(screen.getAllByText(/up to date/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/last synced/i)).toBeNull();
  });

  it("shows NEW badges for cached saved-search results and clears list-level new count after opening", async () => {
    nextSavedSearchSeedNewLotNumbers = ["12345678"];
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await runDefaultManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /save search/i }));

    expect(await screen.findByText(/^1 new$/i)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /^ford mustang mach-e 2025-2027/i }));

    const resultsDialog = await screen.findByRole("dialog", { name: /search results/i });
    expect(within(resultsDialog).getByText(/^NEW$/i)).toBeTruthy();
    await waitFor(() => {
      expect(screen.queryByText(/^1 new$/i)).toBeNull();
    });
  });

  it("surfaces per-resource reliability states and admin diagnostics", async () => {
    savedSearches = [
      buildSavedSearch({
        freshness: buildFreshness({
          status: "cached",
          last_synced_at: "2026-03-16T11:40:00Z",
          stale_after: "2026-03-16T11:55:00Z",
          degraded_reason: "gateway unavailable",
          retryable: true,
        }),
        refresh_state: buildRefreshState({
          status: "retryable_failure",
          error_message: "gateway unavailable",
          retryable: true,
          next_retry_at: "2026-03-16T12:20:00Z",
          priority_class: "recently_changed",
          last_outcome: "refresh_failed",
          metrics: { new_matches: 0, cached_new_count: 0 },
        }),
      }),
    ];
    watchlistItems = [
      buildTrackedLot({
        freshness: buildFreshness({
          status: "outdated",
          last_synced_at: "2026-03-11T12:00:00Z",
          stale_after: "2026-03-11T12:15:00Z",
        }),
        refresh_state: buildRefreshState({
          status: "repair_pending",
          priority_class: "auction_imminent",
          metrics: { change_count: 1, reminder_count: 0 },
        }),
      }),
    ];

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    expect(screen.getByText(/^Update delayed$/i)).toBeTruthy();
    expect(screen.getByText(/gateway unavailable/i)).toBeTruthy();
    expect(screen.getByText(/we're fixing an issue with this vehicle entry/i)).toBeTruthy();
    expect(screen.queryByText(/^Last synced$/i)).toBeNull();
    expect(screen.queryByText(/^Last checked$/i)).toBeNull();

    openAccountMenu();
    await screen.findByRole("dialog", { name: /account menu/i });
    expect(screen.getByText(/items to review/i)).toBeTruthy();
    expect(screen.getByText(/2 items may need attention/i)).toBeTruthy();
    expect(screen.getByText(/1 may need attention, 1 using saved data, 0 out of date/i)).toBeTruthy();
    expect(screen.getByText(/1 may need attention, 0 using saved data, 1 out of date/i)).toBeTruthy();
  });

  it("refreshes a saved search from inside the cached modal", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await runDefaultManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /save search/i }));
    await screen.findByRole("button", { name: /^ford mustang mach-e 2025-2027/i });
    fireEvent.click(screen.getByRole("button", { name: /^ford mustang mach-e 2025-2027/i }));

    await screen.findByRole("dialog", { name: /search results/i });
    fireEvent.click(screen.getByRole("button", { name: /check for updates/i }));

    await screen.findByText(/2018 HONDA CIVIC EX/i);
    expect(savedSearchRefreshCallCount).toBe(1);
    expect(screen.getAllByText(/2 lots found/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Last synced/i)).toBeNull();
  });

  it("keeps cached saved-search results open and surfaces retryable refresh failure metadata", async () => {
    savedSearchRefreshShouldFail = true;

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await runDefaultManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /save search/i }));
    await screen.findByRole("button", { name: /^ford mustang mach-e 2025-2027/i });
    fireEvent.click(screen.getByRole("button", { name: /^ford mustang mach-e 2025-2027/i }));

    await screen.findByRole("dialog", { name: /search results/i });
    fireEvent.click(screen.getByRole("button", { name: /check for updates/i }));

    expect(await screen.findAllByText(/gateway timeout/i)).toHaveLength(3);
    await waitFor(() => {
      expect(screen.queryAllByText(/^update delayed$/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  it("renders saved-search results as a fullscreen mobile surface and locks background scroll", async () => {
    mockMobileViewport();

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await runDefaultManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /save search/i }));
    await screen.findByRole("button", { name: /^ford mustang mach-e 2025-2027/i });
    fireEvent.click(screen.getByRole("button", { name: /^ford mustang mach-e 2025-2027/i }));

    const resultsDialog = await screen.findByRole("dialog", { name: /search results/i });
    expect(resultsDialog.className).toContain("modal-card--mobile-screen");
    expect(document.body.style.position).toBe("fixed");
    expect(document.documentElement.style.overflow).toBe("hidden");

    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: /search results/i })).toBeNull();
    });
    expect(document.body.style.position).toBe("");
    expect(document.documentElement.style.overflow).toBe("");
  });

  it("renders saved-search results as fullscreen on narrow viewports even without coarse pointer detection", async () => {
    mockNarrowViewportWithoutCoarsePointer();

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await runDefaultManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /save search/i }));
    await screen.findByRole("button", { name: /^ford mustang mach-e 2025-2027/i });
    fireEvent.click(screen.getByRole("button", { name: /^ford mustang mach-e 2025-2027/i }));

    const resultsDialog = await screen.findByRole("dialog", { name: /search results/i });
    expect(resultsDialog.className).toContain("modal-card--mobile-screen");
  });

  it("renders fullscreen saved-search results outside the pullable app shell and collapses intro chrome on scroll", async () => {
    mockMobileViewport();

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await runDefaultManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /save search/i }));
    await screen.findByRole("button", { name: /^ford mustang mach-e 2025-2027/i });

    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 480,
    });
    fireEvent.click(screen.getByRole("button", { name: /^ford mustang mach-e 2025-2027/i }));

    const resultsDialog = await screen.findByRole("dialog", { name: /search results/i });
    const appShell = document.querySelector(".app-shell");
    expect(appShell?.contains(resultsDialog)).toBe(false);
    expect(screen.getByRole("button", { name: /close/i })).toBeTruthy();

    const resultsBody = resultsDialog.querySelector(".search-results-modal__body");
    const collapsibleChrome = resultsDialog.querySelector(".search-results-modal__collapsible") as HTMLElement | null;
    expect(resultsBody).toBeTruthy();
    expect(collapsibleChrome).toBeTruthy();
    await waitFor(() => {
      expect(Number.parseFloat(collapsibleChrome?.style.height ?? "0")).toBeGreaterThan(0);
    });
    const expandedHeight = Number.parseFloat(collapsibleChrome?.style.height ?? "0");
    fireEvent.scroll(resultsBody!, {
      target: { scrollTop: 72 },
    });
    let collapsedHeight = Number.parseFloat(collapsibleChrome?.style.height ?? "0");
    await waitFor(() => {
      collapsedHeight = Number.parseFloat(collapsibleChrome?.style.height ?? "0");
      expect(collapsedHeight).toBeLessThan(expandedHeight);
    });
    expect(collapsedHeight).toBeLessThan(expandedHeight);

    fireEvent.scroll(resultsBody!, {
      target: { scrollTop: 0 },
    });
    let restoredHeight = Number.parseFloat(collapsibleChrome?.style.height ?? "0");
    await waitFor(() => {
      restoredHeight = Number.parseFloat(collapsibleChrome?.style.height ?? "0");
      expect(restoredHeight).toBe(expandedHeight);
    });
    expect(restoredHeight).toBe(expandedHeight);
  });

  it("renders external url link for saved search", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await runDefaultManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /save search/i }));

    fireEvent.click(await screen.findByRole("button", { name: /more actions for ford mustang mach-e 2025-2027/i }));
    const link = await screen.findByRole("menuitem", { name: /open copart/i });
    expect(link.getAttribute("href")).toContain("https://www.copart.com/lotSearchResults?free=true&displayStr=FORD%20MUSTANG%20MACH-E%202025-2027");
    expect(link.getAttribute("href")).toContain("qId=test-qid-1");
    expect(link.getAttribute("href")).toContain("DRIV");
  });

  it("deletes a saved search from the list", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await runDefaultManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /save search/i }));
    await screen.findByRole("button", { name: /^ford mustang mach-e 2025-2027/i });

    fireEvent.click(screen.getByRole("button", { name: /more actions for ford mustang mach-e 2025-2027/i }));
    fireEvent.click(screen.getByRole("menuitem", { name: /delete/i }));

    await waitFor(() => {
      expect(screen.queryByText(/FORD MUSTANG MACH-E 2025-2027/i)).toBeNull();
    });
  });

  it("prioritizes inbox filters and keeps NEW searches ahead of older rows", async () => {
    nextSavedSearchSeedNewLotNumbers = ["12345678"];

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await runDefaultManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /save search/i }));
    await screen.findByRole("button", { name: /^ford mustang mach-e 2025-2027/i });

    await openManualSearch();
    fireEvent.focus(screen.getByLabelText("Make"));
    fireEvent.change(screen.getByLabelText("Make"), { target: { value: "FI" } });
    fireEvent.click(screen.getByRole("button", { name: "FIAT" }));
    fireEvent.click(screen.getByRole("button", { name: /search lots/i }));
    await screen.findByRole("dialog", { name: /search results/i });
    fireEvent.click(screen.getByRole("button", { name: /save search/i }));
    await screen.findByRole("button", { name: /^fiat/i });

    const cardTitles = Array.from(document.querySelectorAll(".saved-search-card strong")).map((node) => node.textContent);
    expect(cardTitles[0]).toContain("FORD MUSTANG MACH-E 2025-2027");
    expect(cardTitles[1]).toContain("FIAT");

    fireEvent.click(screen.getByRole("button", { name: /new saved searches, 1/i }));
    expect(screen.getByRole("button", { name: /^ford mustang mach-e 2025-2027/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^fiat/i })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /attention needed, 1/i }));
    expect(screen.getByRole("button", { name: /^fiat/i })).toBeTruthy();
  });

  it("adds lot to tracked lots by lot number", async () => {
    const localAuctionStart = formatExpectedLocalAuctionStart("2026-03-13T18:30:00Z");
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await openTrackLotModal();
    const trackLotDialog = screen.getByRole("dialog", { name: /track lot/i });
    fireEvent.change(within(trackLotDialog).getByPlaceholderText("99251295"), { target: { value: "99251295" } });
    fireEvent.click(within(trackLotDialog).getByRole("button", { name: /^track lot$/i }));

    await screen.findByText(/2025 FORD MUSTANG MACH-E PREMIUM/i);
    expect(screen.getByText(/Current bid/i)).toBeTruthy();
    expect(screen.getByText(/Odometer/i)).toBeTruthy();
    expect(screen.getByText(/12,345 ACTUAL/i)).toBeTruthy();
    expect(screen.getAllByText((_, element) => element?.textContent?.includes(localAuctionStart) ?? false).length).toBeGreaterThan(0);
    const detailsToggle = screen.getByRole("button", { name: /show details/i });
    expect(detailsToggle.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(detailsToggle);
    expect(detailsToggle.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText(/Primary damage:/i)).toBeTruthy();
    expect(screen.getByText(/FRONT END/i)).toBeTruthy();
    expect(screen.getByText(/Retail:/i)).toBeTruthy();
    expect(screen.getByText(/36,500 USD/i)).toBeTruthy();
    expect(screen.getByText(/Has Key:/i)).toBeTruthy();
    expect(screen.getByText(/^Yes$/i)).toBeTruthy();
    expect(screen.getByText(/Drivetrain:/i)).toBeTruthy();
    expect(screen.getByText(/^AWD$/i)).toBeTruthy();
    expect(screen.getByText(/Highlights:/i)).toBeTruthy();
    expect(screen.getByText(/Run and Drive · Enhanced Vehicles/i)).toBeTruthy();
    expect(screen.getByText(/Vin:/i)).toBeTruthy();
    expect(screen.getByText(/3FMTK3SU5SMA00001/i)).toBeTruthy();
    const lotLink = screen.getByRole("link", { name: /open copart lot 99251295/i });
    expect(lotLink.getAttribute("href")).toBe("https://www.copart.com/lot/99251295");
    expect(lotLink.getAttribute("target")).toBe("_blank");
  });

  it("refreshes a tracked lot from the tracked lots list", async () => {
    watchlistItems = [buildTrackedLot()];

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    fireEvent.click(screen.getByRole("button", { name: /check now/i }));

    expect(await screen.findByText(/updated 2020 toyota camry se\./i)).toBeTruthy();
    expect(screen.getByText(/up to date/i)).toBeTruthy();
    expect(screen.queryByText(/^Last checked$/i)).toBeNull();
  });

  it("keeps watchlist visible and shows retryable failure details when tracked-lot refresh fails", async () => {
    watchlistItems = [buildTrackedLot()];
    watchlistRefreshShouldFail = true;

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    fireEvent.click(screen.getByRole("button", { name: /check now/i }));

    expect(await screen.findAllByText(/gateway timeout/i)).toHaveLength(2);
    expect(screen.getByText(/^Update delayed$/i)).toBeTruthy();
  });

  it("highlights updated tracked lots without breaking auction-date ordering", async () => {
    watchlistItems = [
      buildTrackedLot({
        id: "tracked-updated",
        lot_number: "12345678",
        title: "2020 TOYOTA CAMRY SE",
        sale_date: "2026-03-21T18:30:00Z",
        has_unseen_update: true,
        latest_change_at: "2026-03-17T15:40:00Z",
        latest_changes: {
          raw_status: { before: "On Approval", after: "Live" },
          current_bid: { before: 4200, after: 5100 },
        },
      }),
      buildTrackedLot({
        id: "tracked-newer",
        lot_number: "99251295",
        title: "2025 FORD MUSTANG MACH-E PREMIUM",
        url: "https://www.copart.com/lot/99251295",
        sale_date: "2026-03-20T17:00:00Z",
        created_at: "2026-03-17T15:45:00Z",
        last_checked_at: "2026-03-17T15:45:00Z",
      }),
    ];

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    const watchlistCards = document.querySelectorAll(".watchlist-card");
    expect(watchlistCards[0]?.textContent).toContain("2025 FORD MUSTANG MACH-E PREMIUM");
    expect(watchlistCards[1]?.textContent).toContain("2020 TOYOTA CAMRY SE");
    expect(screen.getByText(/^Changed$/i)).toBeTruthy();
    expect(screen.getByText(/Status: On Approval -> Live/i)).toBeTruthy();
    expect(screen.getByText(/Bid: 4,200 USD -> 5,100 USD/i)).toBeTruthy();
  });

  it("keeps the latest change summary visible after marking a tracked-lot update as seen", async () => {
    watchlistItems = [
      buildTrackedLot({
        has_unseen_update: true,
        latest_change_at: "2026-03-17T15:40:00Z",
        latest_changes: {
          raw_status: { before: "On Approval", after: "Live" },
          current_bid: { before: 4200, after: 5100 },
        },
      }),
    ];

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    expect(screen.getByText(/^Changed$/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /mark seen/i }));

    await waitFor(() => {
      expect(screen.queryByText(/^Changed$/i)).toBeNull();
    });
    expect(screen.getByText(/^Last change$/i)).toBeTruthy();
    expect(screen.getByText(/Status: On Approval -> Live/i)).toBeTruthy();
    expect(screen.getByText(/Bid: 4,200 USD -> 5,100 USD/i)).toBeTruthy();
  });

  it("opens tracked-lot change history from the action row right after show details", async () => {
    watchlistItems = [buildTrackedLot()];
    watchlistHistoryById["tracked-1"] = [
      buildTrackedLotHistoryEntry(),
      buildTrackedLotHistoryEntry({
        snapshot: {
          id: "snapshot-3",
          tracked_lot_id: "tracked-1",
          provider: "copart",
          provider_lot_id: "12345678",
          lot_key: "copart:12345678",
          lot_number: "12345678",
          status: "on_approval",
          raw_status: "On Approval",
          current_bid: 4200,
          buy_now_price: null,
          currency: "USD",
          sale_date: "2026-03-20T17:00:00Z",
          detected_at: "2026-03-16T14:10:00Z",
        },
        changes: {
          sale_date: { before: "2026-03-21T17:00:00Z", after: "2026-03-20T17:00:00Z" },
        },
      }),
    ];

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    const card = document.querySelector(".watchlist-card");
    const actionButtons = within(card as HTMLElement).getAllByRole("button");
    const showDetailsIndex = actionButtons.findIndex((button) => button.textContent?.match(/show details/i));
    const changeHistoryIndex = actionButtons.findIndex((button) => button.textContent?.match(/change history/i));

    expect(showDetailsIndex).toBeGreaterThanOrEqual(0);
    expect(changeHistoryIndex).toBe(showDetailsIndex + 1);

    fireEvent.click(actionButtons[changeHistoryIndex]!);

    expect(await screen.findByRole("dialog", { name: /change history/i })).toBeTruthy();
    expect(screen.getByText(/Status: On Approval -> Live/i)).toBeTruthy();
    expect(screen.getByText(/Bid: 4,200 USD -> 5,100 USD/i)).toBeTruthy();
    expect(screen.getByText(/Sale:/i)).toBeTruthy();
  });

  it("marks near-auction tracked lots as sale soon", async () => {
    watchlistItems = [
      buildTrackedLot({
        id: "tracked-soon",
        lot_number: "99251295",
        title: "2025 FORD MUSTANG MACH-E PREMIUM",
        url: "https://www.copart.com/lot/99251295",
        sale_date: new Date(Date.now() + 90 * 60 * 1000).toISOString(),
      }),
    ];

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    expect(screen.getByText(/sale soon/i)).toBeTruthy();
  });

  it("marks already-started tracked lots as auction live", async () => {
    watchlistItems = [
      buildTrackedLot({
        id: "tracked-live",
        lot_number: "55551234",
        title: "2024 FORD F-150 XLT",
        url: "https://www.copart.com/lot/55551234",
        sale_date: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
      }),
    ];

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    expect(screen.getByText(/auction live/i)).toBeTruthy();
  });

  it("enables browser push subscription on this device", async () => {
    const subscribe = vi.fn(async () => ({
      endpoint: "https://push.example.test/subscriptions/device-1",
      expirationTime: null,
      getKey: (name: PushEncryptionKeyName) =>
        name === "p256dh" ? Uint8Array.from([1, 2, 3, 4]).buffer : Uint8Array.from([5, 6, 7, 8]).buffer,
      unsubscribe: vi.fn(async () => true),
    }));
    const registration = {
      pushManager: {
        getSubscription: vi.fn(async () => null),
        subscribe,
      },
    } as unknown as ServiceWorkerRegistration;

    vi.stubGlobal("Notification", {
      permission: "default",
      requestPermission: vi.fn(async () => "granted"),
    });
    Object.defineProperty(window.navigator, "serviceWorker", {
      configurable: true,
      value: {
        getRegistration: vi.fn(async () => registration),
        register: vi.fn(async () => registration),
        ready: Promise.resolve(registration),
      },
    });
    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: true,
    });
    vi.stubGlobal("PushManager", class PushManager {});

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    openSettingsFromAccountMenu();
    await screen.findByRole("dialog", { name: /settings/i });
    fireEvent.click(screen.getByRole("button", { name: /turn on notifications/i }));

    expect(await screen.findByText(/push\.example\.test\/subscriptions\/device-1/i)).toBeTruthy();
    expect(subscribe).toHaveBeenCalledTimes(1);
  });

  it("opens push settings as a mobile full-screen modal and keeps long device labels wrapped", async () => {
    mockMobileViewport();
    Object.defineProperty(window.navigator, "userAgent", {
      configurable: true,
      value:
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.3 Mobile/15E148 Safari/604.1",
    });
    const subscribe = vi.fn(async () => ({
      endpoint: "https://push.example.test/subscriptions/device-iphone-15-pro-max",
      expirationTime: null,
      getKey: (name: PushEncryptionKeyName) =>
        name === "p256dh" ? Uint8Array.from([1, 2, 3, 4]).buffer : Uint8Array.from([5, 6, 7, 8]).buffer,
      unsubscribe: vi.fn(async () => true),
    }));
    const registration = {
      pushManager: {
        getSubscription: vi.fn(async () => null),
        subscribe,
      },
    } as unknown as ServiceWorkerRegistration;

    vi.stubGlobal("Notification", {
      permission: "default",
      requestPermission: vi.fn(async () => "granted"),
    });
    Object.defineProperty(window.navigator, "serviceWorker", {
      configurable: true,
      value: {
        getRegistration: vi.fn(async () => registration),
        register: vi.fn(async () => registration),
        ready: Promise.resolve(registration),
      },
    });
    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: true,
    });
    vi.stubGlobal("PushManager", class PushManager {});

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    openSettingsFromAccountMenu();
    const dialog = await screen.findByRole("dialog", { name: /settings/i });

    expect(dialog.className).toContain("modal-card--mobile-screen");
    expect(document.body.style.position).toBe("fixed");
    expect(document.documentElement.style.overflow).toBe("hidden");

    fireEvent.click(screen.getByRole("button", { name: /turn on notifications/i }));

    expect(await screen.findByText(/^this browser$/i)).toBeTruthy();
    expect(await screen.findByText(/iphone-15-pro-max/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /^close$/i }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: /settings/i })).toBeNull();
    });
    expect(document.body.style.position).toBe("");
    expect(document.documentElement.style.overflow).toBe("");
  });

  it("renders account menu as a portal sheet outside the app shell after dashboard scroll", async () => {
    mockMobileViewport();

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 520,
    });
    openAccountMenu();

    const accountDialog = await screen.findByRole("dialog", { name: /account menu/i });
    const appShell = document.querySelector(".app-shell");
    expect(appShell?.contains(accountDialog)).toBe(false);
    expect(document.body.style.position).toBe("fixed");
    expect(document.documentElement.style.overflow).toBe("hidden");
  });

  it("renders push settings outside the app shell after dashboard scroll on mobile", async () => {
    mockMobileViewport();

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 520,
    });
    openSettingsFromAccountMenu();

    const settingsDialog = await screen.findByRole("dialog", { name: /settings/i });
    const appShell = document.querySelector(".app-shell");
    expect(appShell?.contains(settingsDialog)).toBe(false);
    expect(settingsDialog.className).toContain("modal-card--mobile-screen");
    expect(document.body.style.position).toBe("fixed");
  });

  it("moves connector controls into settings and expands the form only after disconnect", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);

    openAccountMenu();
    await screen.findByRole("dialog", { name: /account menu/i });
    expect(screen.queryByText(/copart account/i)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /^settings$/i }));
    await screen.findByRole("dialog", { name: /settings/i });

    const getCopartSection = () => screen.getAllByText(/^copart account$/i)[0]!.closest("section")!;

    expect(within(getCopartSection()).getByText(/copart-user@example\.com/i)).toBeTruthy();
    expect(within(getCopartSection()).queryByLabelText(/copart email/i)).toBeNull();
    expect(within(getCopartSection()).queryByRole("button", { name: /connect copart/i })).toBeNull();

    fireEvent.click(within(getCopartSection()).getByRole("button", { name: /^disconnect$/i }));

    await waitFor(() => {
      expect(within(getCopartSection()).getByLabelText(/copart email/i)).toBeTruthy();
    });
    expect(within(getCopartSection()).getByRole("button", { name: /connect copart/i })).toBeTruthy();
  });

  it("keeps IAAI expiring sessions collapsed like connected connectors", async () => {
    providerConnections = [
      buildProviderConnection(),
      buildProviderConnection({
        id: "provider-connection-iaai-1",
        provider: "iaai",
        status: "expiring",
        account_label: "iaai-user@example.com",
      }),
    ];

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    openSettingsFromAccountMenu();
    await screen.findByRole("dialog", { name: /settings/i });

    const iaaiSection = screen.getByText(/iaai account/i).closest("section")!;
    expect(within(iaaiSection).getByText(/^Expires soon$/i)).toBeTruthy();
    expect(within(iaaiSection).queryByLabelText(/iaai email/i)).toBeNull();
    expect(within(iaaiSection).queryByLabelText(/iaai password/i)).toBeNull();
    expect(within(iaaiSection).queryByRole("button", { name: /connect iaai/i })).toBeNull();
    expect(within(iaaiSection).getByRole("button", { name: /^disconnect$/i })).toBeTruthy();
  });

  it("retries a partial bootstrap failure for saved searches without reloading the whole dashboard", async () => {
    savedSearchesShouldFail = true;

    render(<App />);
    submitLoginForm();

    await screen.findByText(/couldn't load saved searches/i);
    savedSearchesShouldFail = false;
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => {
      expect(screen.queryByText(/couldn't load saved searches/i)).toBeNull();
    });
    expect(screen.getByText(/you don't have any saved searches yet/i)).toBeTruthy();
  });

  it("sends a push test from settings diagnostics", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    openSettingsFromAccountMenu();
    await screen.findByRole("dialog", { name: /settings/i });
    fireEvent.click(screen.getByRole("button", { name: /send test notification/i }));

    expect(await screen.findByText(/test notification finished: 1 delivered, 0 failed, 0 removed\./i)).toBeTruthy();
  });

  it("refreshes watchlist data after a push update message without reloading the page", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    expect(screen.queryByText(/2020 TOYOTA CAMRY SE/i)).toBeNull();

    watchlistItems = [
      buildTrackedLot({
        has_unseen_update: true,
        latest_change_at: "2026-03-18T10:00:00Z",
        latest_changes: {
          current_bid: { before: 4200, after: 5100 },
        },
      }),
    ];

    serviceWorkerMessageListener?.({
      data: {
        type: "cartrap:push-received",
        payload: { refresh_targets: ["watchlist"] },
      },
    } as MessageEvent);

    await waitFor(() => {
      expect(screen.getByText(/2020 TOYOTA CAMRY SE/i)).toBeTruthy();
    });
    expect(screen.getByText(/Bid: 4,200 USD -> 5,100 USD/i)).toBeTruthy();
  });

  it("accepts object-shaped push refresh targets from the service worker bridge", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    const initialWatchlistLoads = watchlistListCallCount;

    watchlistItems = [
      buildTrackedLot({
        has_unseen_update: true,
        latest_change_at: "2026-03-18T10:00:00Z",
        latest_changes: {
          current_bid: { before: 4200, after: 5100 },
        },
      }),
    ];

    serviceWorkerMessageListener?.({
      data: {
        type: "cartrap:push-received",
        payload: { refresh_targets: { targets: ["watchlist"] } },
      },
    } as MessageEvent);

    await waitFor(() => {
      expect(watchlistListCallCount).toBeGreaterThan(initialWatchlistLoads);
    });
    expect(screen.getByText(/Bid: 4,200 USD -> 5,100 USD/i)).toBeTruthy();
  });

  it("refreshes operational resources when the window regains focus", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    const initialWatchlistLoads = watchlistListCallCount;
    const initialSavedSearchLoads = savedSearchesListCallCount;
    const initialSystemStatusLoads = systemStatusCallCount;

    watchlistItems = [
      buildTrackedLot({
        has_unseen_update: true,
        latest_change_at: "2026-03-18T10:00:00Z",
        latest_changes: {
          current_bid: { before: 4200, after: 5100 },
        },
      }),
    ];

    fireEvent(window, new Event("focus"));

    await waitFor(() => {
      expect(watchlistListCallCount).toBeGreaterThan(initialWatchlistLoads);
      expect(savedSearchesListCallCount).toBeGreaterThan(initialSavedSearchLoads);
      expect(systemStatusCallCount).toBeGreaterThan(initialSystemStatusLoads);
    });
    expect(screen.getByText(/Bid: 4,200 USD -> 5,100 USD/i)).toBeTruthy();
  });

  it("polls for hidden-tab updates and blinks the document title until the tab becomes visible", async () => {
    vi.useFakeTimers();
    let visibilityState: DocumentVisibilityState = "hidden";
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => visibilityState,
    });

    render(<App />);
    submitLoginForm();

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByText(/cartrap dispatch board/i)).toBeTruthy();
    expect(document.title).toBe("CarTrap");

    watchlistItems = [
      buildTrackedLot({
        has_unseen_update: true,
        latest_change_at: "2026-03-18T10:00:00Z",
        latest_changes: {
          current_bid: { before: 4200, after: 5100 },
        },
      }),
    ];

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });

    expect(screen.getByText(/Bid: 4,200 USD -> 5,100 USD/i)).toBeTruthy();
    expect(document.title).toBe("1 tracked lot update | CarTrap");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });
    expect(document.title).toBe("CarTrap");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });
    expect(document.title).toBe("1 tracked lot update | CarTrap");

    await act(async () => {
      visibilityState = "visible";
      document.dispatchEvent(new Event("visibilitychange"));
      await Promise.resolve();
    });

    expect(document.title).toBe("CarTrap");
  });

  it("reloads dashboard resources after mobile pull to refresh", async () => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 390,
    });
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 0,
    });
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn((query: string) => ({
        matches: query === "(pointer: coarse)",
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    render(<App />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "admin@example.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "secret123" } });
    fireEvent.submit(screen.getByRole("button", { name: /sign in/i }).closest("form")!);

    await screen.findByText(/cartrap dispatch board/i);
    const initialWatchlistLoads = watchlistListCallCount;
    const initialSavedSearchLoads = savedSearchesListCallCount;
    const initialSystemStatusLoads = systemStatusCallCount;

    fireEvent.touchStart(window, {
      touches: [{ clientY: 8 }],
    });
    fireEvent.touchMove(window, {
      touches: [{ clientY: 180 }],
    });

    expect(screen.getByText(/release to update/i)).toBeTruthy();

    fireEvent.touchEnd(window);

    await waitFor(() => {
      expect(watchlistListCallCount).toBeGreaterThan(initialWatchlistLoads);
      expect(savedSearchesListCallCount).toBeGreaterThan(initialSavedSearchLoads);
      expect(systemStatusCallCount).toBeGreaterThan(initialSystemStatusLoads);
    });
    await waitFor(() => {
      expect(screen.queryByText(/reloading saved searches, tracked lots, and connection status\./i)).toBeNull();
    });
  });

  it("suppresses mobile pull to refresh while the new-search screen is open", async () => {
    mockMobileViewport();

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    const initialWatchlistLoads = watchlistListCallCount;
    const initialSavedSearchLoads = savedSearchesListCallCount;
    const initialSystemStatusLoads = systemStatusCallCount;

    await openManualSearch();
    expect(document.body.style.position).toBe("fixed");
    expect(document.documentElement.style.overflow).toBe("hidden");
    fireEvent.touchStart(window, {
      touches: [{ clientY: 8 }],
    });
    fireEvent.touchMove(window, {
      touches: [{ clientY: 180 }],
    });
    fireEvent.touchEnd(window);

    expect(screen.queryByText(/release to refresh/i)).toBeNull();
    expect(watchlistListCallCount).toBe(initialWatchlistLoads);
    expect(savedSearchesListCallCount).toBe(initialSavedSearchLoads);
    expect(systemStatusCallCount).toBe(initialSystemStatusLoads);

    fireEvent.click(screen.getByRole("button", { name: /back to inbox/i }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: /new search/i })).toBeNull();
    });
    expect(document.body.style.position).toBe("");
    expect(document.documentElement.style.overflow).toBe("");
  });

  it("hides admin-only push diagnostics for non-admin accounts", async () => {
    loginRole = "user";

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    openAccountMenu();
    await screen.findByRole("dialog", { name: /account menu/i });
    expect(screen.queryByText(/^live updates$/i)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    openSettingsFromAccountMenu();
    await screen.findByRole("dialog", { name: /settings/i });

    expect(screen.queryByRole("button", { name: /send test notification/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /refresh info/i })).toBeNull();
    expect(screen.queryByText(/server setup:/i)).toBeNull();
    expect(screen.queryByText(/this browser:/i)).toBeNull();
    expect(screen.getByText(/permission:/i)).toBeTruthy();
    expect(screen.getByText(/connected devices:/i)).toBeTruthy();
  });

  it("renders fallbacks for missing tracked lot detail fields", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await openTrackLotModal();
    const trackLotDialog = screen.getByRole("dialog", { name: /track lot/i });
    fireEvent.change(within(trackLotDialog).getByPlaceholderText("99251295"), { target: { value: "87654321" } });
    fireEvent.click(within(trackLotDialog).getByRole("button", { name: /^track lot$/i }));

    await screen.findByText(/2018 HONDA CIVIC EX/i);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("opens gallery modal for tracked lot thumbnails", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await openTrackLotModal();
    const trackLotDialog = screen.getByRole("dialog", { name: /track lot/i });
    fireEvent.change(within(trackLotDialog).getByPlaceholderText("99251295"), { target: { value: "99251295" } });
    fireEvent.click(within(trackLotDialog).getByRole("button", { name: /^track lot$/i }));

    await screen.findByText(/2025 FORD MUSTANG MACH-E PREMIUM/i);
    fireEvent.click(screen.getByRole("button", { name: /open gallery for 2025 ford mustang mach-e premium/i }));

    await screen.findByRole("dialog", { name: /2025 ford mustang mach-e premium photo gallery/i });
    expect(screen.getByAltText(/2025 ford mustang mach-e premium photo 1/i)).toBeTruthy();
    expect(screen.getByAltText(/2025 ford mustang mach-e premium thumbnail 2/i)).toBeTruthy();
  });

  it("renders gallery modal as a fullscreen mobile overlay outside the app shell after scroll", async () => {
    mockMobileViewport();

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await openTrackLotModal();
    const trackLotDialog = screen.getByRole("dialog", { name: /track lot/i });
    fireEvent.change(within(trackLotDialog).getByPlaceholderText("99251295"), { target: { value: "99251295" } });
    fireEvent.click(within(trackLotDialog).getByRole("button", { name: /^track lot$/i }));

    await screen.findByText(/2025 FORD MUSTANG MACH-E PREMIUM/i);
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 560,
    });
    fireEvent.click(screen.getByRole("button", { name: /open gallery for 2025 ford mustang mach-e premium/i }));

    const galleryDialog = await screen.findByRole("dialog", { name: /2025 ford mustang mach-e premium photo gallery/i });
    const appShell = document.querySelector(".app-shell");
    expect(appShell?.contains(galleryDialog)).toBe(false);
    expect(galleryDialog.className).toContain("modal-card--mobile-screen");
    expect(document.body.style.position).toBe("fixed");
  });

  it("connects Copart from a disconnected state and re-enables live actions", async () => {
    providerConnections = [
      buildProviderConnection({
        status: "disconnected",
        usable: false,
        disconnected_at: "2026-03-24T10:25:00Z",
        bundle: null,
      }),
    ];

    render(<App />);
    submitLoginForm();

    expect((await screen.findAllByText(/connect copart in settings to turn on live updates\./i)).length).toBe(2);
    const newSearchButtons = screen.getAllByRole("button", { name: /new search|reconnect account/i });
    expect((newSearchButtons[0] as HTMLButtonElement).disabled).toBe(true);

    openSettingsFromAccountMenu();
    await screen.findByRole("dialog", { name: /settings/i });
    const connectionCard = screen.getByText(/copart account/i).closest("section")!;
    expect(within(connectionCard).getByText(/^Disconnected$/i)).toBeTruthy();
    fireEvent.change(within(connectionCard).getByLabelText(/copart email/i), {
      target: { value: "buyer@example.com" },
    });
    fireEvent.change(within(connectionCard).getByLabelText(/copart password/i), {
      target: { value: "secret123" },
    });
    fireEvent.click(within(connectionCard).getByRole("button", { name: /connect copart/i }));

    expect(await within(connectionCard).findByText(/copart account connected\./i)).toBeTruthy();
    await waitFor(() => {
      expect(within(connectionCard).getByText(/^Connected$/i)).toBeTruthy();
    });
    expect(screen.queryByText(/connect copart in settings to turn on live updates\./i)).toBeNull();
    expect((screen.getAllByRole("button", { name: /^new search$/i })[0] as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows reconnect-required notice and restores the connector after reconnect", async () => {
    providerConnections = [
      buildProviderConnection({
        status: "reconnect_required",
        reconnect_required: true,
        usable: false,
        last_error: {
          code: "auth_invalid",
          message: "Copart session expired.",
          retryable: false,
          occurred_at: "2026-03-24T10:10:00Z",
        },
      }),
    ];

    render(<App />);
    submitLoginForm();

    expect(await screen.findByText(/account sign-in needed/i)).toBeTruthy();

    openSettingsFromAccountMenu();
    await screen.findByRole("dialog", { name: /settings/i });
    const connectionCard = screen.getByText(/copart account/i).closest("section")!;
    expect(within(connectionCard).getByText(/^Sign in again$/i)).toBeTruthy();
    fireEvent.change(within(connectionCard).getByLabelText(/copart password/i), {
      target: { value: "secret123" },
    });
    fireEvent.click(within(connectionCard).getByRole("button", { name: /reconnect copart/i }));

    expect(await within(connectionCard).findByText(/copart account is connected again\./i)).toBeTruthy();
    await waitFor(() => {
      expect(screen.queryByText(/account sign-in needed/i)).toBeNull();
    });
    expect(within(connectionCard).getByText(/^Connected$/i)).toBeTruthy();
  });

  it("disconnects Copart from settings and surfaces the missing-connection guardrail", async () => {
    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    openSettingsFromAccountMenu();
    await screen.findByRole("dialog", { name: /settings/i });
    const connectionCard = screen.getByText(/copart account/i).closest("section")!;
    fireEvent.click(within(connectionCard).getByRole("button", { name: /^disconnect$/i }));

    expect(await within(connectionCard).findByText(/copart account disconnected\./i)).toBeTruthy();
    await waitFor(() => {
      expect(within(connectionCard).getByText(/^Disconnected$/i)).toBeTruthy();
    });
    expect(screen.getAllByText(/connect copart in settings to turn on live updates\./i).length).toBe(2);
    expect((screen.getAllByRole("button", { name: /new search|reconnect account/i })[0] as HTMLButtonElement).disabled).toBe(
      true,
    );
  });

  it("surfaces resource-level connection diagnostics and blocks affected live actions", async () => {
    savedSearches = [
      buildSavedSearch({
        connection_diagnostic: buildConnectionDiagnostic({
          message: "Reconnect Copart to refresh this saved search.",
        }),
      }),
    ];
    watchlistItems = [
      buildTrackedLot({
        connection_diagnostic: buildConnectionDiagnostic({
          message: "Reconnect Copart to refresh this tracked lot.",
        }),
      }),
    ];

    render(<App />);
    submitLoginForm();

    await screen.findByText(/reconnect copart to refresh this saved search\./i);
    expect(screen.getByText(/reconnect copart to refresh this tracked lot\./i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /more actions for ford mustang mach-e 2025-2027/i }));
    const refreshSavedSearchButton = await screen.findByRole("menuitem", { name: /reconnect copart/i });
    expect((refreshSavedSearchButton as HTMLButtonElement).disabled).toBe(true);

    const refreshWatchlistButton = screen.getAllByRole("button", { name: /reconnect copart/i }).find((button) =>
      button.className.includes("ghost-button--quiet"),
    );
    expect(refreshWatchlistButton).toBeTruthy();
    expect((refreshWatchlistButton as HTMLButtonElement).disabled).toBe(true);
  });

  it("refreshes expired access token and keeps the session active", async () => {
    localStorage.setItem(
      "cartrap.user",
      JSON.stringify({ id: "user-1", email: "admin@example.com", role: "admin", status: "active" }),
    );
    localStorage.setItem(
      "cartrap.tokens",
      JSON.stringify({ access_token: "expired-token", refresh_token: "refresh-token", token_type: "bearer" }),
    );
    window.location.hash = "#/dashboard";

    render(<App />);

    await screen.findByText(/cartrap dispatch board/i);
    await waitFor(() => {
      expect(localStorage.getItem("cartrap.tokens")).toContain("refresh-token-next");
    });
  });

  it("shows offline banner when live sync is degraded and clears it after recovery", async () => {
    liveSyncStatus = buildLiveSyncStatus({
      status: "degraded",
      last_failure_at: "2026-03-16T11:05:00Z",
      last_failure_source: "watchlist_poll",
      last_error_message: "gateway unavailable",
    });

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    expect(screen.queryByText(/live updates are temporarily unavailable/i)).toBeNull();
    openAccountMenu();
    const accountDialog = await screen.findByRole("dialog", { name: /account menu/i });
    expect(within(accountDialog).getByText(/^Live updates$/i)).toBeTruthy();
    expect(within(accountDialog).getByText(/^Needs attention$/i)).toBeTruthy();
    expect(within(accountDialog).getByText(/gateway unavailable/i)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    liveSyncStatus = buildLiveSyncStatus();
    await openManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /search lots/i }));

    await screen.findByRole("dialog", { name: /search results/i });
    expect(screen.queryByText(/live updates are temporarily unavailable/i)).toBeNull();
  });

  it("shows degraded-mode message when manual search fails while live sync is offline", async () => {
    liveSyncStatus = buildLiveSyncStatus({
      status: "degraded",
      last_failure_at: "2026-03-16T11:05:00Z",
      last_failure_source: "manual_search",
      last_error_message: "gateway unavailable",
    });
    searchShouldFail = true;

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await openManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /search lots/i }));

    expect(
      await screen.findByText(
        /search isn't available right now because live updates are having trouble\. you can still view saved data\./i,
      ),
    ).toBeTruthy();
    expect(screen.queryByRole("dialog", { name: /search results/i })).toBeNull();
  });

  it("shows degraded-mode message when adding a lot fails while live sync is offline", async () => {
    liveSyncStatus = buildLiveSyncStatus({
      status: "degraded",
      last_failure_at: "2026-03-16T11:05:00Z",
      last_failure_source: "watchlist_poll",
      last_error_message: "gateway unavailable",
    });
    watchlistAddShouldFail = true;

    render(<App />);
    submitLoginForm();

    await screen.findByText(/cartrap dispatch board/i);
    await openTrackLotModal();
    const trackLotDialog = screen.getByRole("dialog", { name: /track lot/i });
    fireEvent.change(within(trackLotDialog).getByPlaceholderText("99251295"), { target: { value: "12345678" } });
    fireEvent.click(within(trackLotDialog).getByRole("button", { name: /^track lot$/i }));

    expect(
      await screen.findByText(
        /adding a lot to tracked lots isn't available right now because live updates are having trouble\. you can still view saved data\./i,
      ),
    ).toBeTruthy();
  });

  it("shows browser-offline messaging separately from backend degraded mode", async () => {
    Object.defineProperty(window.navigator, "onLine", {
      configurable: true,
      value: false,
    });
    searchShouldFail = true;

    render(<App />);
    submitLoginForm();

    await screen.findByRole("heading", { name: /this device is offline/i });
    await openManualSearch();
    fireEvent.click(screen.getByRole("button", { name: /search lots/i }));

    expect(
      await screen.findByText(/search isn't available because this device is offline\. reconnect and try again\./i),
    ).toBeTruthy();
  });
});

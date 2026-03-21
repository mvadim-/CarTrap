import type { FreshnessEnvelope, RefreshState } from "../../types";

export type ReliabilityTone = "live" | "cached" | "warning" | "danger" | "refreshing";

export type ReliabilityDescriptor = {
  label: string;
  tone: ReliabilityTone;
  detail: string;
  needsAttention: boolean;
};

type ReliabilityOptions = {
  freshness: FreshnessEnvelope | null;
  refreshState: RefreshState | null;
  isRefreshing?: boolean;
  repairPendingDetail: string;
  unknownDetail: string;
};

function formatTimestamp(value: string | null | undefined, fallback = "the latest successful sync"): string {
  if (!value) {
    return fallback;
  }
  return new Date(value).toLocaleString();
}

function buildLastGoodSyncPrefix(syncedAt: string | null | undefined): string {
  return syncedAt ? `Last good sync ${formatTimestamp(syncedAt)}.` : "No trusted sync yet.";
}

export function buildResourceReliability({
  freshness,
  refreshState,
  isRefreshing = false,
  repairPendingDetail,
  unknownDetail,
}: ReliabilityOptions): ReliabilityDescriptor {
  const syncedAt = freshness?.last_synced_at ?? refreshState?.last_succeeded_at ?? null;

  if (isRefreshing) {
    return {
      label: "Refreshing",
      tone: "refreshing",
      detail: "Syncing live data now. Cached data stays visible while the update completes.",
      needsAttention: false,
    };
  }

  if (refreshState?.status === "repair_pending") {
    return {
      label: "Repair pending",
      tone: "refreshing",
      detail: syncedAt ? `${repairPendingDetail} ${buildLastGoodSyncPrefix(syncedAt)}` : repairPendingDetail,
      needsAttention: true,
    };
  }

  if (refreshState?.status === "retryable_failure") {
    const retrySuffix = ` Retry after ${formatTimestamp(refreshState.next_retry_at, "the next worker run")}.`;
    return {
      label: "Degraded",
      tone: "warning",
      detail: refreshState.error_message
        ? `${refreshState.error_message} ${buildLastGoodSyncPrefix(syncedAt)}${retrySuffix}`.trim()
        : `${buildLastGoodSyncPrefix(syncedAt)}${retrySuffix}`,
      needsAttention: true,
    };
  }

  if (refreshState?.status === "failed") {
    return {
      label: "Outdated",
      tone: "danger",
      detail: refreshState.error_message
        ? `${refreshState.error_message} ${buildLastGoodSyncPrefix(syncedAt)} Manual attention is required.`.trim()
        : `${buildLastGoodSyncPrefix(syncedAt)} Manual attention is required.`,
      needsAttention: true,
    };
  }

  switch (freshness?.status) {
    case "live":
      return {
        label: "Live",
        tone: "live",
        detail: `Synced ${formatTimestamp(syncedAt)}.`,
        needsAttention: false,
      };
    case "cached":
      return {
        label: "Cached",
        tone: "cached",
        detail: freshness.degraded_reason
          ? `Using synced data from ${formatTimestamp(syncedAt)}. Live sync degraded: ${freshness.degraded_reason}`
          : `Using synced data from ${formatTimestamp(syncedAt)}.`,
        needsAttention: false,
      };
    case "degraded":
      return {
        label: "Degraded",
        tone: "warning",
        detail: freshness.degraded_reason
          ? syncedAt
            ? `Live sync degraded: ${freshness.degraded_reason} Last good sync ${formatTimestamp(syncedAt)}.`
            : `Live sync degraded: ${freshness.degraded_reason}`
          : "Live sync is degraded. Cached data remains available.",
        needsAttention: true,
      };
    case "outdated":
      return {
        label: "Outdated",
        tone: "danger",
        detail: `${buildLastGoodSyncPrefix(syncedAt)} Refresh Live to update now.`,
        needsAttention: true,
      };
    default:
      return {
        label: "Awaiting sync",
        tone: "warning",
        detail: unknownDetail,
        needsAttention: true,
      };
  }
}

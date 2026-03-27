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
  return syncedAt ? `Last updated ${formatTimestamp(syncedAt)}.` : "We haven't saved a trusted update yet.";
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
      label: "Updating",
      tone: "refreshing",
      detail: "Checking for the latest changes now. You can keep viewing the last saved info while this finishes.",
      needsAttention: false,
    };
  }

  if (refreshState?.status === "repair_pending") {
    return {
      label: "Fixing",
      tone: "refreshing",
      detail: syncedAt ? `${repairPendingDetail} ${buildLastGoodSyncPrefix(syncedAt)}` : repairPendingDetail,
      needsAttention: true,
    };
  }

  if (refreshState?.status === "retryable_failure") {
    const retrySuffix = ` We'll try again ${formatTimestamp(refreshState.next_retry_at, "soon")}.`;
    return {
      label: "Update delayed",
      tone: "warning",
      detail: refreshState.error_message
        ? `We couldn't update this just now: ${refreshState.error_message}. ${buildLastGoodSyncPrefix(syncedAt)}${retrySuffix}`.trim()
        : `${buildLastGoodSyncPrefix(syncedAt)}${retrySuffix}`,
      needsAttention: true,
    };
  }

  if (refreshState?.status === "failed") {
    return {
      label: "Needs attention",
      tone: "danger",
      detail: refreshState.error_message
        ? `We couldn't update this: ${refreshState.error_message}. ${buildLastGoodSyncPrefix(syncedAt)} Please try again or reconnect the account.`.trim()
        : `${buildLastGoodSyncPrefix(syncedAt)} Please try again or reconnect the account.`,
      needsAttention: true,
    };
  }

  switch (freshness?.status) {
    case "live":
      return {
        label: "Up to date",
        tone: "live",
        detail: `Updated ${formatTimestamp(syncedAt)}.`,
        needsAttention: false,
      };
    case "cached":
      return {
        label: "Saved data",
        tone: "cached",
        detail: freshness.degraded_reason
          ? `Showing the last saved update from ${formatTimestamp(syncedAt)}. Live updates are having trouble: ${freshness.degraded_reason}`
          : `Showing the last saved update from ${formatTimestamp(syncedAt)}.`,
        needsAttention: false,
      };
    case "degraded":
      return {
        label: "May be out of date",
        tone: "warning",
        detail: freshness.degraded_reason
          ? syncedAt
            ? `Live updates are having trouble: ${freshness.degraded_reason}. Last updated ${formatTimestamp(syncedAt)}.`
            : `Live updates are having trouble: ${freshness.degraded_reason}.`
          : "Live updates are having trouble right now. You can still view the last saved data.",
        needsAttention: true,
      };
    case "outdated":
      return {
        label: "Needs refresh",
        tone: "danger",
        detail: `${buildLastGoodSyncPrefix(syncedAt)} Use "Check for updates" to refresh it now.`,
        needsAttention: true,
      };
    default:
      return {
        label: "Not checked yet",
        tone: "warning",
        detail: unknownDetail,
        needsAttention: true,
      };
  }
}

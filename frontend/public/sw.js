const DEFAULT_TITLE = "CarTrap";
const DEFAULT_BODY = "Lot updated";
const PUSH_MESSAGE_TYPE = "cartrap:push-received";
const APP_PATH = "/#/dashboard";

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

function parsePushPayload(event) {
  if (!event.data) {
    return { title: DEFAULT_TITLE, body: DEFAULT_BODY };
  }
  try {
    return event.data.json();
  } catch {
    return { title: DEFAULT_TITLE, body: event.data.text() || DEFAULT_BODY };
  }
}

function deriveRefreshTargets(payload) {
  const explicitTargetsValue = Array.isArray(payload.refresh_targets)
    ? payload.refresh_targets
    : payload.refresh_targets && typeof payload.refresh_targets === "object"
      ? payload.refresh_targets.targets ?? payload.refresh_targets.items ?? payload.refresh_targets.resources ?? []
      : payload.refresh && typeof payload.refresh === "object"
        ? payload.refresh.targets ?? payload.refresh.items ?? payload.refresh.resources ?? []
        : [];
  const explicitTargets = Array.isArray(explicitTargetsValue)
    ? explicitTargetsValue.filter((target) => typeof target === "string")
    : [];
  if (explicitTargets.length > 0) {
    return Array.from(new Set(explicitTargets));
  }

  const derivedTargets = [];
  if (payload.tracked_lot_id) {
    derivedTargets.push("watchlist", "liveSync");
  }
  if (payload.saved_search_id) {
    derivedTargets.push("savedSearches", "liveSync");
  }
  return Array.from(new Set(derivedTargets));
}

async function broadcastPushUpdate(payload) {
  const clientList = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  const message = {
    type: PUSH_MESSAGE_TYPE,
    payload: {
      ...payload,
      refresh_targets: deriveRefreshTargets(payload),
    },
  };

  await Promise.all(
    clientList.map(async (client) => {
      client.postMessage(message);
    }),
  );
}

async function focusOrOpenClient() {
  const clientList = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  for (const client of clientList) {
    if ("focus" in client) {
      await client.focus();
      return client;
    }
  }
  if (self.clients.openWindow) {
    return self.clients.openWindow(APP_PATH);
  }
  return null;
}

self.addEventListener("push", (event) => {
  const payload = parsePushPayload(event);
  const notificationPayload = {
    ...payload,
    refresh_targets: deriveRefreshTargets(payload),
  };

  event.waitUntil(
    Promise.all([
      self.registration.showNotification(notificationPayload.title ?? DEFAULT_TITLE, {
        body: notificationPayload.body ?? DEFAULT_BODY,
        data: notificationPayload,
      }),
      broadcastPushUpdate(notificationPayload),
    ]),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(focusOrOpenClient());
});

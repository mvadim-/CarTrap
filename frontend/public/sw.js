const DEFAULT_TITLE = "CarTrap";
const DEFAULT_BODY = "Lot updated";
const PUSH_MESSAGE_TYPE = "cartrap:push-received";
const PUSH_BADGE_CLEAR_MESSAGE_TYPE = "cartrap:badge-clear";
const APP_PATH = "/#/dashboard";
const BADGE_DB_NAME = "cartrap-push-state";
const BADGE_STORE_NAME = "meta";
const BADGE_COUNT_KEY = "push-badge-count";

let badgeDbPromise = null;
let inMemoryBadgeCount = 0;

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

function openBadgeDb() {
  if (!("indexedDB" in self)) {
    return Promise.resolve(null);
  }
  if (badgeDbPromise) {
    return badgeDbPromise;
  }

  badgeDbPromise = new Promise((resolve) => {
    try {
      const request = indexedDB.open(BADGE_DB_NAME, 1);
      request.onupgradeneeded = () => {
        const database = request.result;
        if (!database.objectStoreNames.contains(BADGE_STORE_NAME)) {
          database.createObjectStore(BADGE_STORE_NAME);
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });

  return badgeDbPromise;
}

async function readStoredBadgeCount() {
  const database = await openBadgeDb();
  if (!database) {
    return inMemoryBadgeCount;
  }

  return new Promise((resolve) => {
    try {
      const transaction = database.transaction(BADGE_STORE_NAME, "readonly");
      const request = transaction.objectStore(BADGE_STORE_NAME).get(BADGE_COUNT_KEY);
      request.onsuccess = () => {
        const value = Number(request.result);
        resolve(Number.isFinite(value) && value > 0 ? Math.trunc(value) : 0);
      };
      request.onerror = () => resolve(inMemoryBadgeCount);
    } catch {
      resolve(inMemoryBadgeCount);
    }
  });
}

async function writeStoredBadgeCount(value) {
  const nextValue = Number.isFinite(value) && value > 0 ? Math.trunc(value) : 0;
  inMemoryBadgeCount = nextValue;

  const database = await openBadgeDb();
  if (!database) {
    return nextValue;
  }

  return new Promise((resolve) => {
    try {
      const transaction = database.transaction(BADGE_STORE_NAME, "readwrite");
      transaction.objectStore(BADGE_STORE_NAME).put(nextValue, BADGE_COUNT_KEY);
      transaction.oncomplete = () => resolve(nextValue);
      transaction.onerror = () => resolve(nextValue);
    } catch {
      resolve(nextValue);
    }
  });
}

async function incrementBadgeCount() {
  const currentValue = await readStoredBadgeCount();
  return writeStoredBadgeCount(currentValue + 1);
}

async function clearBadgeCount() {
  await writeStoredBadgeCount(0);
}

async function setApplicationBadge(count) {
  if (self.navigator && typeof self.navigator.setAppBadge === "function") {
    try {
      await self.navigator.setAppBadge(count);
    } catch {
      // Ignore unsupported or transient badging failures.
    }
  }
}

async function clearApplicationBadge() {
  if (self.navigator && typeof self.navigator.clearAppBadge === "function") {
    try {
      await self.navigator.clearAppBadge();
      return;
    } catch {
      // Ignore unsupported or transient badging failures.
    }
  }

  if (self.navigator && typeof self.navigator.setAppBadge === "function") {
    try {
      await self.navigator.setAppBadge(0);
    } catch {
      // Ignore unsupported or transient badging failures.
    }
  }
}

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
  event.waitUntil(
    (async () => {
      const badgeCount = await incrementBadgeCount();
      const notificationPayload = {
        ...payload,
        refresh_targets: deriveRefreshTargets(payload),
        badge_count: badgeCount,
      };

      await Promise.all([
        self.registration.showNotification(notificationPayload.title ?? DEFAULT_TITLE, {
          body: notificationPayload.body ?? DEFAULT_BODY,
          data: notificationPayload,
        }),
        broadcastPushUpdate(notificationPayload),
        setApplicationBadge(badgeCount),
      ]);
    })(),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(focusOrOpenClient());
});

self.addEventListener("message", (event) => {
  const data = event.data;
  if (data?.type !== PUSH_BADGE_CLEAR_MESSAGE_TYPE) {
    return;
  }

  event.waitUntil(
    (async () => {
      await clearBadgeCount();
      await clearApplicationBadge();
    })(),
  );
});

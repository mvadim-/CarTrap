const PUSH_BADGE_CLEAR_MESSAGE_TYPE = "cartrap:badge-clear";

type BadgingNavigator = Navigator & {
  setAppBadge?: (count?: number) => Promise<void>;
  clearAppBadge?: () => Promise<void>;
};

function getBadgingNavigator(): BadgingNavigator | null {
  if (typeof navigator === "undefined") {
    return null;
  }
  return navigator as BadgingNavigator;
}

async function postMessageToServiceWorker(message: { type: string }): Promise<void> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) {
    return;
  }

  const registration = await navigator.serviceWorker.getRegistration();
  const target =
    registration?.active ?? registration?.waiting ?? registration?.installing ?? navigator.serviceWorker.controller;
  target?.postMessage?.(message);
}

export async function clearApplicationBadge(): Promise<void> {
  const badgingNavigator = getBadgingNavigator();
  if (!badgingNavigator) {
    return;
  }

  try {
    if (typeof badgingNavigator.clearAppBadge === "function") {
      await badgingNavigator.clearAppBadge();
      return;
    }
    if (typeof badgingNavigator.setAppBadge === "function") {
      await badgingNavigator.setAppBadge(0);
    }
  } catch {
    // Ignore unsupported or transient badging failures.
  }
}

export async function clearPushBadgeState(): Promise<void> {
  await Promise.allSettled([
    clearApplicationBadge(),
    postMessageToServiceWorker({ type: PUSH_BADGE_CLEAR_MESSAGE_TYPE }),
  ]);
}

export { PUSH_BADGE_CLEAR_MESSAGE_TYPE };

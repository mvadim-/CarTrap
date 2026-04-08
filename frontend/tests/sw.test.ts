import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it, vi } from "vitest";

const SERVICE_WORKER_SOURCE = readFileSync(resolve(process.cwd(), "public/sw.js"), "utf8");

type ServiceWorkerListener = (event: {
  data?: unknown;
  notification?: { close: () => void };
  waitUntil?: (promise: Promise<unknown>) => void;
}) => void;

type WindowClientStub = {
  focused?: boolean;
  visibilityState?: "hidden" | "visible";
  postMessage: ReturnType<typeof vi.fn>;
};

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function setupServiceWorkerHarness(clients: WindowClientStub[] = []) {
  const listeners = new Map<string, ServiceWorkerListener>();
  const self = {
    addEventListener: vi.fn((type: string, listener: ServiceWorkerListener) => {
      listeners.set(type, listener);
    }),
    skipWaiting: vi.fn(async () => undefined),
    clients: {
      matchAll: vi.fn(async () => clients),
      openWindow: vi.fn(async () => null),
    },
    registration: {
      showNotification: vi.fn(async () => undefined),
    },
    navigator: {
      setAppBadge: vi.fn(async () => undefined),
      clearAppBadge: vi.fn(async () => undefined),
    },
  };

  const bootstrap = new Function("self", "indexedDB", SERVICE_WORKER_SOURCE);
  bootstrap(self, undefined);

  function dispatch(type: string, eventInit: Record<string, unknown> = {}) {
    const pending: Promise<unknown>[] = [];
    listeners.get(type)?.({
      ...eventInit,
      waitUntil: (promise: Promise<unknown>) => pending.push(Promise.resolve(promise)),
    });
    return Promise.all(pending);
  }

  return { self, dispatch };
}

describe("service worker push badge flow", () => {
  it("does not keep a badge count when a visible client is already open", async () => {
    const client = {
      visibilityState: "visible" as const,
      postMessage: vi.fn(),
    };
    const { self, dispatch } = setupServiceWorkerHarness([client]);

    await dispatch("push", {
      data: {
        json: () => ({ title: "Lot updated", body: "Foreground event" }),
      },
    });

    expect(self.navigator.setAppBadge).not.toHaveBeenCalled();
    expect(self.navigator.clearAppBadge).toHaveBeenCalledTimes(1);
    expect(self.registration.showNotification).toHaveBeenCalledTimes(1);
    expect(client.postMessage).toHaveBeenCalledTimes(1);
  });

  it("serializes clear requests after an in-flight badge write", async () => {
    const { self, dispatch } = setupServiceWorkerHarness();
    const badgeWrite = createDeferred<void>();
    const callOrder: string[] = [];

    self.navigator.setAppBadge.mockImplementation(async (count?: number) => {
      callOrder.push(`set:${count ?? 0}`);
      return badgeWrite.promise;
    });
    self.navigator.clearAppBadge.mockImplementation(async () => {
      callOrder.push("clear");
    });

    const pushPromise = dispatch("push", {
      data: {
        json: () => ({ title: "Lot updated", body: "Background event" }),
      },
    });
    const clearPromise = dispatch("message", {
      data: { type: "cartrap:badge-clear" },
    });

    badgeWrite.resolve();
    await Promise.all([pushPromise, clearPromise]);

    expect(callOrder).toEqual(["set:1", "clear"]);
    expect(self.navigator.clearAppBadge).toHaveBeenCalledTimes(1);
  });
});

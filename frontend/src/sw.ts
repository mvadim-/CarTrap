self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  const payload = event.data ? event.data.json() : { title: "CarTrap", body: "Lot updated" };
  event.waitUntil(
    self.registration.showNotification(payload.title ?? "CarTrap", {
      body: payload.body ?? "Lot updated",
      data: payload,
    }),
  );
});

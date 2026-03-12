import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/App";

function buildToken(payload: Record<string, unknown>) {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.signature`;
}

describe("CarTrap app", () => {
  beforeEach(() => {
    const storage = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => void storage.set(key, value),
      removeItem: (key: string) => void storage.delete(key),
      clear: () => storage.clear(),
    });
    localStorage.clear();
    window.location.hash = "#/login";
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
              access_token: buildToken({ sub: "user-1", role: "admin" }),
              refresh_token: "refresh-token",
              token_type: "bearer",
            }),
            { status: 200 },
          );
        }
        if (url.includes("/auth/refresh")) {
          return new Response(
            JSON.stringify({
              access_token: buildToken({ sub: "user-1", role: "admin", refreshed: true }),
              refresh_token: "refresh-token-next",
              token_type: "bearer",
            }),
            { status: 200 },
          );
        }
        if (url.includes("/watchlist") && !url.includes("/search/watchlist")) {
          if ((init?.method ?? "GET") === "GET" && authHeader === "Bearer expired-token") {
            return new Response(JSON.stringify({ detail: "Invalid access token." }), { status: 401 });
          }
          if ((init?.method ?? "GET") === "POST") {
            const body = init?.body ? JSON.parse(String(init.body)) : {};
            return new Response(
              JSON.stringify({
                tracked_lot: {
                  id: body.lot_number === "99251295" ? "tracked-2" : "tracked-1",
                  lot_number: body.lot_number ?? "12345678",
                  url: `https://www.copart.com/lot/${body.lot_number ?? "12345678"}`,
                  title: body.lot_number === "99251295" ? "2025 FORD MUSTANG MACH-E PREMIUM" : "2020 TOYOTA CAMRY SE",
                  status: "live",
                  raw_status: "Live",
                  current_bid: 4200,
                  buy_now_price: null,
                  currency: "USD",
                  sale_date: null,
                  last_checked_at: "2026-03-11T12:00:00Z",
                  created_at: "2026-03-11T12:00:00Z",
                },
              }),
              { status: 201 },
            );
          }
          return new Response(JSON.stringify({ items: [] }), { status: 200 });
        }
        if (url.includes("/notifications/subscriptions")) {
          return new Response(JSON.stringify({ items: [] }), { status: 200 });
        }
        if (url.endsWith("/search")) {
          const body = init?.body ? JSON.parse(String(init.body)) : {};
          if (body.make !== "ford" || body.model !== "mustang mach-e") {
            return new Response(JSON.stringify({ results: [] }), { status: 200 });
          }
          return new Response(
            JSON.stringify({
              results: [
                {
                  lot_number: "12345678",
                  title: "2020 TOYOTA CAMRY SE",
                  url: "https://www.copart.com/lot/12345678",
                  location: "CA - SACRAMENTO",
                  sale_date: null,
                  current_bid: 4200,
                  currency: "USD",
                  status: "live",
                },
              ],
            }),
            { status: 200 },
          );
        }
        if (url.includes("/search/watchlist")) {
          return new Response(
            JSON.stringify({
              tracked_lot: {
                id: "tracked-1",
                lot_number: "12345678",
                url: "https://www.copart.com/lot/12345678",
                title: "2020 TOYOTA CAMRY SE",
                status: "live",
                raw_status: "Live",
                current_bid: 4200,
                buy_now_price: null,
                currency: "USD",
                sale_date: null,
                last_checked_at: "2026-03-11T12:00:00Z",
                created_at: "2026-03-11T12:00:00Z",
              },
            }),
            { status: 201 },
          );
        }
        if (url.includes("/admin/invites")) {
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
        return new Response(JSON.stringify({}), { status: 200 });
      }),
    );
    vi.stubGlobal("Notification", {
      permission: "denied",
      requestPermission: vi.fn(async () => "denied"),
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders login and opens dashboard after auth", async () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await screen.findByText(/cartrap dispatch board/i);
    expect(screen.getByText(/generate invites/i)).toBeTruthy();
  });

  it("renders invite acceptance screen from hash route", () => {
    window.location.hash = "#/invite?token=abc123";

    render(<App />);

    expect(screen.getByText(/create your cartrap password/i)).toBeTruthy();
    expect(screen.getByText("abc123")).toBeTruthy();
  });

  it("runs manual search and adds result to watchlist", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await screen.findByText(/cartrap dispatch board/i);
    fireEvent.click(screen.getByRole("button", { name: /search lots/i }));

    await screen.findByText(/2020 TOYOTA CAMRY SE/i);
    fireEvent.click(screen.getByRole("button", { name: /add to watchlist/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/2020 TOYOTA CAMRY SE/i).length).toBeGreaterThan(1);
    });
  });

  it("adds lot to watchlist by lot number", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await screen.findByText(/cartrap dispatch board/i);
    fireEvent.change(screen.getByPlaceholderText("99251295"), { target: { value: "99251295" } });
    fireEvent.click(screen.getByRole("button", { name: /add lot/i }));

    await screen.findByText(/2025 FORD MUSTANG MACH-E PREMIUM/i);
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
});

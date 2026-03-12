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
    const savedSearches: Array<{
      id: string;
      label: string;
      criteria: {
        make?: string;
        model?: string;
        make_filter?: string;
        model_filter?: string;
        year_from?: number;
        year_to?: number;
      };
      created_at: string;
    }> = [];
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
                  thumbnail_url:
                    body.lot_number === "99251295"
                      ? "https://img.copart.com/99251295-detail.jpg"
                      : "https://img.copart.com/12345678-detail.jpg",
                  image_urls:
                    body.lot_number === "99251295"
                      ? [
                          "https://img.copart.com/99251295-detail.jpg",
                          "https://img.copart.com/99251295-detail-2.jpg",
                        ]
                      : [
                          "https://img.copart.com/12345678-detail.jpg",
                          "https://img.copart.com/12345678-detail-2.jpg",
                        ],
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
                      slug: "mustangmache",
                      name: "MUSTANG MACH-E",
                      search_filter:
                        'lot_model_desc:"MUSTANG MACH-E" OR manufacturer_model_desc:"MUSTANG MACH-E"',
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
        if (url.includes("/search/saved")) {
          if ((init?.method ?? "GET") === "POST") {
            const body = init?.body ? JSON.parse(String(init.body)) : {};
            const duplicate = savedSearches.find(
              (item) =>
                JSON.stringify(item.criteria) ===
                JSON.stringify({
                  make: body.make,
                  model: body.model,
                  make_filter: body.make_filter,
                  model_filter: body.model_filter,
                  year_from: body.year_from,
                  year_to: body.year_to,
                }),
            );
            if (duplicate) {
              return new Response("Search is already saved.", { status: 409 });
            }
            const savedSearch = {
              id: `saved-${savedSearches.length + 1}`,
              label: body.label ?? `${body.make ?? ""} ${body.model ?? ""} ${body.year_from ?? ""}-${body.year_to ?? ""}`.trim(),
              criteria: {
                make: body.make,
                model: body.model,
                make_filter: body.make_filter,
                model_filter: body.model_filter,
                year_from: body.year_from,
                year_to: body.year_to,
              },
              created_at: "2026-03-12T18:00:00Z",
            };
            savedSearches.unshift(savedSearch);
            return new Response(JSON.stringify({ saved_search: savedSearch }), { status: 201 });
          }
          return new Response(JSON.stringify({ items: savedSearches }), { status: 200 });
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
        if (url.endsWith("/search")) {
          const body = init?.body ? JSON.parse(String(init.body)) : {};
          if (body.make !== "FORD" || body.model !== "MUSTANG MACH-E") {
            return new Response(JSON.stringify({ results: [] }), { status: 200 });
          }
          return new Response(
            JSON.stringify({
              results: [
                {
                  lot_number: "12345678",
                  title: "2020 TOYOTA CAMRY SE",
                  url: "https://www.copart.com/lot/12345678",
                  thumbnail_url: "https://img.copart.com/12345678.jpg",
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
                thumbnail_url: "https://img.copart.com/12345678-detail.jpg",
                image_urls: [
                  "https://img.copart.com/12345678-detail.jpg",
                  "https://img.copart.com/12345678-detail-2.jpg",
                ],
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

    await screen.findByRole("dialog", { name: /search results/i });
    fireEvent.click(screen.getByRole("button", { name: /add to watchlist/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/2020 TOYOTA CAMRY SE/i).length).toBeGreaterThan(1);
    });
    expect(screen.getAllByAltText(/2020 TOYOTA CAMRY SE/i).length).toBeGreaterThan(1);
  });

  it("saves a search and reruns it from the saved searches list", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await screen.findByText(/cartrap dispatch board/i);
    fireEvent.click(screen.getByRole("button", { name: /search lots/i }));

    await screen.findByRole("dialog", { name: /search results/i });
    fireEvent.click(screen.getByRole("button", { name: /save search/i }));

    await screen.findByText(/FORD MUSTANG MACH-E 2025-2027/i);
    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    fireEvent.click(screen.getByRole("button", { name: /run search/i }));

    await screen.findByRole("dialog", { name: /search results/i });
  });

  it("adds lot to watchlist by lot number", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await screen.findByText(/cartrap dispatch board/i);
    fireEvent.change(screen.getByPlaceholderText("99251295"), { target: { value: "99251295" } });
    fireEvent.click(screen.getByRole("button", { name: /add lot/i }));

    await screen.findByText(/2025 FORD MUSTANG MACH-E PREMIUM/i);
  });

  it("opens gallery modal for tracked lot thumbnails", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await screen.findByText(/cartrap dispatch board/i);
    fireEvent.change(screen.getByPlaceholderText("99251295"), { target: { value: "99251295" } });
    fireEvent.click(screen.getByRole("button", { name: /add lot/i }));

    await screen.findByText(/2025 FORD MUSTANG MACH-E PREMIUM/i);
    fireEvent.click(screen.getByRole("button", { name: /open gallery for 2025 ford mustang mach-e premium/i }));

    await screen.findByRole("dialog", { name: /2025 ford mustang mach-e premium photo gallery/i });
    expect(screen.getByAltText(/2025 ford mustang mach-e premium photo 1/i)).toBeTruthy();
    expect(screen.getByAltText(/2025 ford mustang mach-e premium thumbnail 2/i)).toBeTruthy();
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

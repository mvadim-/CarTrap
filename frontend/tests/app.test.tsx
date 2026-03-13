import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    created_at: "2026-03-11T12:00:00Z",
    ...overrides,
  };
}

describe("CarTrap app", () => {
  let lastSearchPayload: Record<string, unknown> | null;

  beforeEach(() => {
    const storage = new Map<string, string>();
    lastSearchPayload = null;
    const savedSearches: Array<{
      id: string;
      label: string;
      criteria: {
        make?: string;
        model?: string;
        make_filter?: string;
        model_filter?: string;
        drive_type?: string;
        primary_damage?: string;
        title_type?: string;
        fuel_type?: string;
        lot_condition?: string;
        odometer_range?: string;
        year_from?: number;
        year_to?: number;
      };
      external_url: string;
      result_count: number | null;
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
                tracked_lot:
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
                      : buildTrackedLot(),
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
        if (url.includes("/search/saved")) {
          if ((init?.method ?? "GET") === "DELETE") {
            const id = url.split("/").pop() ?? "";
            const index = savedSearches.findIndex((item) => item.id === id);
            if (index >= 0) {
              savedSearches.splice(index, 1);
            }
            return new Response(null, { status: 204 });
          }
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
            const savedSearch = {
              id: `saved-${savedSearches.length + 1}`,
              label: body.label ?? `${body.make ?? ""} ${body.model ?? ""} ${body.year_from ?? ""}-${body.year_to ?? ""}`.trim(),
              criteria: {
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
              external_url:
                "https://www.copart.com/lotSearchResults?free=true&displayStr=FORD%20MUSTANG%20MACH-E%202025-2027&from=%2FvehicleFinder&fromSource=widget&qId=test-qid-1&searchCriteria=%7B%22query%22%3A%5B%22FORD%20MUSTANG%20MACH-E%202025-2027%22%5D%2C%22filter%22%3A%7B%22YEAR%22%3A%5B%22lot_year%3A%5B2025%20TO%202027%5D%22%5D%2C%22MAKE%22%3A%5B%22lot_make_desc%3A%5C%22FORD%5C%22%22%5D%2C%22MODL%22%3A%5B%22lot_model_desc%3A%5C%22MUSTANG%20MACH-E%5C%22%22%5D%2C%22DRIV%22%3A%5B%22drive%3A%5C%22ALL%20WHEEL%20DRIVE%5C%22%22%5D%7D%2C%22searchName%22%3A%22%22%2C%22watchListOnly%22%3Afalse%2C%22freeFormSearch%22%3Atrue%7D",
              result_count: body.result_count ?? null,
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
          lastSearchPayload = body;
          if (body.make !== "FORD" || body.model !== "MUSTANG MACH-E") {
            return new Response(JSON.stringify({ total_results: 0, results: [] }), { status: 200 });
          }
          return new Response(
            JSON.stringify({
              total_results: 1,
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
              tracked_lot: buildTrackedLot(),
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

  it("filters make and model lists while typing", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await screen.findByText(/cartrap dispatch board/i);

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
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await screen.findByText(/cartrap dispatch board/i);
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

  it("saves a search and reruns it from the saved searches list", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await screen.findByText(/cartrap dispatch board/i);
    fireEvent.click(screen.getByRole("button", { name: /search lots/i }));

    await screen.findByRole("dialog", { name: /search results/i });
    fireEvent.click(screen.getByRole("button", { name: /save search/i }));

    await screen.findByText(/FORD MUSTANG MACH-E 2025-2027/i);
    expect(await screen.findAllByText(/1 lot found/i)).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    fireEvent.click(screen.getByRole("button", { name: /run search/i }));

    await screen.findByRole("dialog", { name: /search results/i });
  });

  it("renders external url link for saved search", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await screen.findByText(/cartrap dispatch board/i);
    fireEvent.click(screen.getByRole("button", { name: /search lots/i }));
    await screen.findByRole("dialog", { name: /search results/i });
    fireEvent.click(screen.getByRole("button", { name: /save search/i }));

    const link = await screen.findByRole("link", { name: /open url/i });
    expect(link.getAttribute("href")).toContain("https://www.copart.com/lotSearchResults?free=true&displayStr=FORD%20MUSTANG%20MACH-E%202025-2027");
    expect(link.getAttribute("href")).toContain("qId=test-qid-1");
    expect(link.getAttribute("href")).toContain("DRIV");
  });

  it("deletes a saved search from the list", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await screen.findByText(/cartrap dispatch board/i);
    fireEvent.click(screen.getByRole("button", { name: /search lots/i }));

    await screen.findByRole("dialog", { name: /search results/i });
    fireEvent.click(screen.getByRole("button", { name: /save search/i }));
    await screen.findByText(/FORD MUSTANG MACH-E 2025-2027/i);

    fireEvent.click(screen.getByRole("button", { name: /delete/i }));

    await waitFor(() => {
      expect(screen.queryByText(/FORD MUSTANG MACH-E 2025-2027/i)).toBeNull();
    });
  });

  it("adds lot to watchlist by lot number", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await screen.findByText(/cartrap dispatch board/i);
    fireEvent.change(screen.getByPlaceholderText("99251295"), { target: { value: "99251295" } });
    fireEvent.click(screen.getByRole("button", { name: /add lot/i }));

    await screen.findByText(/2025 FORD MUSTANG MACH-E PREMIUM/i);
    expect(screen.getByText(/Odometer:/i)).toBeTruthy();
    expect(screen.getByText(/12,345 ACTUAL/i)).toBeTruthy();
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

  it("renders fallbacks for missing tracked lot detail fields", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await screen.findByText(/cartrap dispatch board/i);
    fireEvent.change(screen.getByPlaceholderText("99251295"), { target: { value: "87654321" } });
    fireEvent.click(screen.getByRole("button", { name: /add lot/i }));

    await screen.findByText(/2018 HONDA CIVIC EX/i);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
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

import { describe, expect, it } from "vitest";

import config from "../vite.config";

describe("vite config", () => {
  it("binds dev server to all interfaces", () => {
    expect(config.server?.host).toBe("0.0.0.0");
    expect(config.server?.port).toBe(5173);
  });
});

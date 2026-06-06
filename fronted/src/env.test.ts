import { describe, expect, it } from "vitest";

import { isProductionRuntime, shouldShowDevAuth } from "./env";

describe("runtime environment helpers", () => {
  it("treats production-like modes as production", () => {
    expect(isProductionRuntime("production", "")).toBe(true);
    expect(isProductionRuntime("development", "prod")).toBe(true);
    expect(isProductionRuntime("development", "")).toBe(false);
  });

  it("hides development auth by default in production", () => {
    expect(shouldShowDevAuth("production", "", undefined)).toBe(false);
    expect(shouldShowDevAuth("development", "", undefined)).toBe(true);
    expect(shouldShowDevAuth("production", "", "true")).toBe(true);
    expect(shouldShowDevAuth("development", "", "false")).toBe(false);
  });
});

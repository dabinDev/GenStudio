import { describe, expect, it } from "vitest";

import { ApiRequestError, shouldFallbackToLocalReference } from "./api";

describe("upload helpers", () => {
  it("falls back to local references when upstream presign support is unavailable", () => {
    expect(shouldFallbackToLocalReference(new ApiRequestError("Invalid URL (POST /api/upload/presign)", 500))).toBe(true);
    expect(shouldFallbackToLocalReference(new ApiRequestError("not found", 404))).toBe(true);
    expect(shouldFallbackToLocalReference(new ApiRequestError("Invalid API key", 401))).toBe(false);
    expect(shouldFallbackToLocalReference(new Error("network failed"))).toBe(false);
  });
});

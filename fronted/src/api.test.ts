import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError, fetchCsrfToken, loginWithPassword, postApi, setCsrfToken, shouldFallbackToLocalReference } from "./api";

describe("upload helpers", () => {
  it("falls back to local references when upstream presign support is unavailable", () => {
    expect(shouldFallbackToLocalReference(new ApiRequestError("Invalid URL (POST /api/upload/presign)", 500))).toBe(true);
    expect(shouldFallbackToLocalReference(new ApiRequestError("not found", 404))).toBe(true);
    expect(shouldFallbackToLocalReference(new ApiRequestError("Invalid API key", 401))).toBe(false);
    expect(shouldFallbackToLocalReference(new Error("network failed"))).toBe(false);
  });
});

describe("auth api helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    setCsrfToken("");
  });

  it("attaches csrf token to state-changing json requests", async () => {
    setCsrfToken("csrf-123");
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await postApi("/api/models", { name: "Model" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/models",
      expect.objectContaining({
        credentials: "include",
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-123" }),
      }),
    );
  });

  it("does not attach csrf token to login and register endpoints", async () => {
    setCsrfToken("csrf-123");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ user: { id: "u1", externalUserId: "local", email: "a@example.com", phone: "", nickname: "A", avatarUrl: "" } }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrfToken: "csrf-456" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await loginWithPassword({ identifier: "a@example.com", password: "StrongPass123!" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/login",
      expect.objectContaining({
        headers: expect.not.objectContaining({ "X-CSRF-Token": "csrf-123" }),
      }),
    );
  });

  it("fetches csrf token for the current session", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ csrfToken: "csrf-456" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchCsrfToken()).resolves.toBe("csrf-456");
  });

  it("refreshes csrf token and retries once when a session write request is rejected", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: { message: "缺少 CSRF 令牌。" } }), { status: 403 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrfToken: "csrf-new" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(postApi<{ ok: boolean }>("/api/auth/logout", {})).resolves.toEqual({ ok: true });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/auth/logout",
      expect.objectContaining({
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-new" }),
      }),
    );
  });
});

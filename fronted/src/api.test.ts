import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiRequestError,
  dismissCreditGrantNotice,
  fetchCsrfToken,
  fetchMyCredits,
  loginWithPassword,
  postApi,
  registerAccount,
  setCsrfToken,
  shouldFallbackToLocalReference,
  uploadAsset,
} from "./api";

describe("upload helpers", () => {
  it("falls back to local references when upstream presign support is unavailable", () => {
    expect(shouldFallbackToLocalReference(new ApiRequestError("Invalid URL (POST /api/upload/presign)", 500))).toBe(true);
    expect(shouldFallbackToLocalReference(new ApiRequestError("not found", 404))).toBe(true);
    expect(shouldFallbackToLocalReference(new ApiRequestError("Invalid API key", 401))).toBe(false);
    expect(shouldFallbackToLocalReference(new Error("network failed"))).toBe(false);
  });

  it("does not fall back to local references in production", () => {
    const error = new ApiRequestError("Invalid URL (POST /api/upload/presign)", 500);

    expect(shouldFallbackToLocalReference(error, { mode: "production" })).toBe(false);
    expect(shouldFallbackToLocalReference(error, { env: "production" })).toBe(false);
    expect(shouldFallbackToLocalReference(error, { mode: "development" })).toBe(true);
  });

  it("falls back for structurally equivalent upload presign errors", () => {
    const error = {
      name: "ApiRequestError",
      message: "获取上传地址失败。",
      status: 404,
      detail: {
        message: "获取上传地址失败。",
        raw: "404 page not found",
      },
    };

    expect(shouldFallbackToLocalReference(error, { mode: "development" })).toBe(true);
    expect(shouldFallbackToLocalReference(error, { mode: "production" })).toBe(false);
  });

  it("uploads to the local fallback endpoint instead of returning a data url", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: { message: "404 page not found" } }), { status: 404 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "local-upload-1",
            fileName: "reference.png",
            publicUrl: "/api/assets/uploads/reference.png",
            contentType: "image/png",
            localPreviewUrl: "/api/assets/uploads/reference.png",
          }),
          { status: 200 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: () => "asset-id" });

    const result = await uploadAsset(new File(["fake"], "reference.png", { type: "image/png" }), {
      baseUrl: "https://token.example.com",
      apiKey: "sk-test",
    });

    expect(result.publicUrl).toBe("/api/assets/uploads/reference.png");
    expect(result.publicUrl.startsWith("data:")).toBe(false);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/upload/local",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: expect.any(FormData),
      }),
    );
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

  it("shows FastAPI validation messages when registration is rejected", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          detail: [
            {
              type: "value_error",
              loc: ["body", "password"],
              msg: "Value error, 密码至少需要 8 位。",
            },
          ],
        }),
        { status: 422 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      registerAccount({
        email: "new@example.com",
        password: "123",
      }),
    ).rejects.toMatchObject({
      message: "密码至少需要 8 位。",
      status: 422,
    });
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

  it("loads current user credits through the user endpoint", async () => {
    const requests: string[] = [];
    const fetchMock = vi.fn(async (url: RequestInfo | URL) => {
      requests.push(String(url));
      return new Response(JSON.stringify({ account: { balance: 3 }, transactions: [] }), { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchMyCredits()).resolves.toMatchObject({ account: { balance: 3 } });

    expect(requests).toEqual(["/api/credits/me"]);
  });

  it("dismisses a credit grant notice with the session csrf token", async () => {
    setCsrfToken("csrf-credit-notice");
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ transaction: { id: "credit-1" } }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(dismissCreditGrantNotice("credit-1")).resolves.toMatchObject({ id: "credit-1" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/credits/notifications/credit-1/dismiss",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-credit-notice" }),
      }),
    );
  });
});

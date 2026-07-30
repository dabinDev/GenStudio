import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiRequestError,
  createReferenceThumbnail,
  dismissCreditGrantNotice,
  fetchCsrfToken,
  fetchMyCredits,
  loginWithPassword,
  postApi,
  registerAccount,
  setCsrfToken,
  shouldFallbackToLocalReference,
  uploadAsset,
  uploadReferenceBatch,
} from "./api";

describe("upload helpers", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

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

  it("uploads a bounded webp thumbnail and preserves both object keys", async () => {
    const canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn(() => ({ drawImage: vi.fn() })),
      toBlob: vi.fn((callback: BlobCallback, type?: string, quality?: number) => {
        expect(type).toBe("image/webp");
        expect(quality).toBe(0.78);
        callback(new Blob(["thumbnail"], { type: "image/webp" }));
      }),
    };
    const bitmap = { width: 1600, height: 800, close: vi.fn() };
    vi.stubGlobal("document", { createElement: vi.fn(() => canvas) });
    vi.stubGlobal("createImageBitmap", vi.fn(async () => bitmap));
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            uploadUrl: "https://uploads.example.com/reference.png",
            method: "PUT",
            publicUrl: "https://cdn.example.com/reference.png",
            objectKey: "references/reference.png",
            contentType: "image/png",
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            uploadUrl: "https://uploads.example.com/reference.webp",
            method: "PUT",
            publicUrl: "https://cdn.example.com/reference.webp",
            objectKey: "references/reference.webp",
            contentType: "image/webp",
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: () => "asset-id" });
    vi.stubGlobal("URL", { createObjectURL: () => "blob:reference-preview" });

    const result = await uploadAsset(new File(["fake"], "reference.png", { type: "image/png" }), {
      subModelId: "sub-model-1",
    });

    expect(result).toMatchObject({
      objectKey: "references/reference.png",
      thumbnailUrl: "https://cdn.example.com/reference.webp",
      thumbnailObjectKey: "references/reference.webp",
    });
    expect(canvas.width).toBe(640);
    expect(canvas.height).toBe(320);
    expect(bitmap.close).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toMatchObject({
      fileName: "reference.webp",
      contentType: "image/webp",
    });
  });

  it("creates a reference thumbnail without upscaling", async () => {
    const canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn(() => ({ drawImage: vi.fn() })),
      toBlob: vi.fn((callback: BlobCallback) => callback(new Blob(["thumbnail"], { type: "image/webp" }))),
    };
    vi.stubGlobal("document", { createElement: vi.fn(() => canvas) });
    vi.stubGlobal("createImageBitmap", vi.fn(async () => ({ width: 320, height: 200, close: vi.fn() })));

    await createReferenceThumbnail(new File(["fake"], "small.png", { type: "image/png" }));

    expect(canvas.width).toBe(320);
    expect(canvas.height).toBe(200);
  });

  it("keeps successful uploads when another file in the batch fails", async () => {
    const files = [
      new File(["one"], "one.png", { type: "image/png" }),
      new File(["two"], "two.png", { type: "image/png" }),
      new File(["three"], "three.png", { type: "image/png" }),
    ];
    const uploader = vi.fn(async (file: File) => {
      if (file.name === "two.png") throw new Error("network interrupted");
      return {
        id: file.name,
        fileName: file.name,
        publicUrl: `https://cdn.example.com/${file.name}`,
        contentType: file.type,
        localPreviewUrl: `blob:${file.name}`,
        objectKey: `references/${file.name}`,
        thumbnailUrl: `https://cdn.example.com/${file.name}.webp`,
        thumbnailObjectKey: `references/${file.name}.webp`,
      };
    });

    const result = await uploadReferenceBatch(files, { subModelId: "sub-model-1" }, uploader);

    expect(result.uploaded.map((asset) => asset.fileName)).toEqual(["one.png", "three.png"]);
    expect(result.failed).toEqual([{ fileName: "two.png", message: "network interrupted" }]);
    expect(uploader).toHaveBeenCalledTimes(3);
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

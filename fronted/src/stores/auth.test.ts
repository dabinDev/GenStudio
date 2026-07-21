import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  changeMyPassword: vi.fn(),
  devLogin: vi.fn(),
  dismissCreditGrantNotice: vi.fn(),
  fetchCsrfToken: vi.fn(),
  fetchCurrentUser: vi.fn(),
  fetchMyCredits: vi.fn(),
  loginWithPassword: vi.fn(),
  logout: vi.fn(),
  registerAccount: vi.fn(),
  setCsrfToken: vi.fn(),
  updateMyProfile: vi.fn(),
}));

vi.mock("../api", () => api);

import { useAuthStore } from "./auth";

describe("auth credit notices", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const auth = useAuthStore();
    auth.state.user = {
      id: "artist-1",
      externalUserId: "artist-1",
      email: "artist@example.com",
      phone: "",
      nickname: "Artist",
      avatarUrl: "",
    };
    (auth.state as { creditTransactions?: unknown[] }).creditTransactions = [];
  });

  it("retains the latest credit transactions whenever credits refresh", async () => {
    api.fetchMyCredits.mockResolvedValue({
      account: { balance: 12 },
      transactions: [{ id: "grant-1", amount: 12 }],
    });
    const auth = useAuthStore();

    await auth.refreshCredits();

    expect(auth.state.user?.credits).toMatchObject({ balance: 12 });
    expect((auth.state as { creditTransactions?: unknown[] }).creditTransactions).toEqual([{ id: "grant-1", amount: 12 }]);
  });

  it("dismisses a grant then refreshes the transaction snapshot", async () => {
    api.dismissCreditGrantNotice.mockResolvedValue({ id: "grant-1" });
    api.fetchMyCredits.mockResolvedValue({ account: { balance: 12 }, transactions: [] });
    const auth = useAuthStore();

    await auth.dismissCreditGrantNotice("grant-1");

    expect(api.dismissCreditGrantNotice).toHaveBeenCalledWith("grant-1");
    expect(api.fetchMyCredits).toHaveBeenCalledTimes(1);
    expect((auth.state as { creditTransactions?: unknown[] }).creditTransactions).toEqual([]);
  });
});

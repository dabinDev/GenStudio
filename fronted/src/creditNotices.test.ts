import { describe, expect, it } from "vitest";

import { creditGrantNoticeMessage, nextCreditGrantNotice } from "./creditNotices";
import type { CreditTransaction } from "./types";

function transaction(overrides: Partial<CreditTransaction>): CreditTransaction {
  return {
    id: "credit-1",
    userId: "user-1",
    type: "admin_adjustment",
    amount: 1,
    balanceAfter: 1,
    reservedAfter: 0,
    capability: "",
    modelGroupId: "",
    subModelId: "",
    conversationId: "",
    messageId: "",
    taskId: "",
    relatedTransactionId: "",
    status: "succeeded",
    reason: "",
    operatorUserId: "admin-1",
    metadata: {},
    createdAt: "2026-07-22T00:00:00Z",
    ...overrides,
  };
}

describe("credit grant notices", () => {
  it("selects the newest undismissed administrator grant", () => {
    const dismissed = transaction({
      id: "dismissed",
      amount: 30,
      createdAt: "2026-07-22T03:00:00Z",
      metadata: { notification: { kind: "admin_credit_grant", delivery: "single", dismissedAt: "2026-07-22T03:01:00Z" } },
    });
    const pendingSingle = transaction({
      id: "pending-single",
      amount: 120,
      createdAt: "2026-07-22T01:00:00Z",
      reason: "活动奖励",
      metadata: { notification: { kind: "admin_credit_grant", delivery: "single", dismissedAt: null } },
    });
    const pendingBatch = transaction({
      id: "pending-batch",
      amount: 60,
      createdAt: "2026-07-22T02:00:00Z",
      reason: "补偿额度",
      metadata: { notification: { kind: "admin_credit_grant", delivery: "batch", dismissedAt: null } },
    });
    const ordinaryAdjustment = transaction({
      id: "ordinary-adjustment",
      amount: 80,
      createdAt: "2026-07-22T04:00:00Z",
    });

    expect(nextCreditGrantNotice([dismissed, pendingSingle, pendingBatch, ordinaryAdjustment])?.id).toBe("pending-batch");
  });

  it("formats individual and batch grants with their reason", () => {
    const pendingSingle = transaction({
      amount: 120,
      reason: "活动奖励",
      metadata: { notification: { kind: "admin_credit_grant", delivery: "single", dismissedAt: null } },
    });
    const pendingBatch = transaction({
      amount: 60,
      reason: "补偿额度",
      metadata: { notification: { kind: "admin_credit_grant", delivery: "batch", dismissedAt: null } },
    });

    expect(creditGrantNoticeMessage(pendingSingle)).toBe("管理员赠送了 120 积分：活动奖励");
    expect(creditGrantNoticeMessage(pendingBatch)).toBe("管理员批量赠送了 60 积分：补偿额度");
  });
});

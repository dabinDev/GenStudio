import type { CreditTransaction } from "./types";

type CreditGrantNotification = {
  kind?: unknown;
  delivery?: unknown;
  dismissedAt?: unknown;
};

function notificationFor(transaction: CreditTransaction): CreditGrantNotification | null {
  const candidate = transaction.metadata?.notification;
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) return null;
  return candidate as CreditGrantNotification;
}

function isPendingCreditGrant(transaction: CreditTransaction): boolean {
  const notification = notificationFor(transaction);
  return Boolean(
    transaction.type === "admin_adjustment" &&
      transaction.amount > 0 &&
      notification?.kind === "admin_credit_grant" &&
      !notification.dismissedAt,
  );
}

export function nextCreditGrantNotice(transactions: CreditTransaction[]): CreditTransaction | null {
  return (
    transactions
      .filter(isPendingCreditGrant)
      .sort((left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt))[0] || null
  );
}

export function creditGrantNoticeDelivery(transaction: CreditTransaction): "single" | "batch" {
  return notificationFor(transaction)?.delivery === "batch" ? "batch" : "single";
}

export function creditGrantNoticeMessage(transaction: CreditTransaction): string {
  const prefix = creditGrantNoticeDelivery(transaction) === "batch" ? "管理员批量赠送了" : "管理员赠送了";
  const reason = transaction.reason.trim();
  return reason ? `${prefix} ${transaction.amount} 积分：${reason}` : `${prefix} ${transaction.amount} 积分`;
}

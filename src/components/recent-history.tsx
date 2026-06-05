"use client";

import { useMemo } from "react";

import { useWorkbenchStore } from "@/components/workbench-provider";
import { formatTime } from "@/lib/utils";
import type { Capability } from "@/lib/types";

interface RecentHistoryProps {
  capability: Capability;
}

export function RecentHistory({ capability }: RecentHistoryProps) {
  const { history, models } = useWorkbenchStore();

  const entries = useMemo(
    () =>
      history
        .filter((item) => item.capability === capability)
        .map((item) => ({
          ...item,
          modelLabel:
            models.find((model) => model.id === item.modelId)?.name ||
            item.modelName,
        }))
        .slice(0, 6),
    [capability, history, models],
  );

  if (entries.length === 0) {
    return (
      <div className="panel">
        <h3>最近记录</h3>
        <p className="muted">这里会保留最近的调试结果，方便回看。</p>
      </div>
    );
  }

  return (
    <div className="panel">
      <h3>最近记录</h3>
      <div className="history-list">
        {entries.map((entry) => (
          <article key={entry.id} className="history-item">
            <div className="history-head">
              <strong>{entry.title}</strong>
              <span
                className={`badge ${
                  entry.status === "success"
                    ? "badge-success"
                    : entry.status === "processing"
                      ? "badge-warn"
                      : "badge-danger"
                }`}
              >
                {entry.status === "success"
                  ? "成功"
                  : entry.status === "processing"
                    ? "处理中"
                    : "失败"}
              </span>
            </div>
            <p className="muted">{entry.modelLabel}</p>
            <p>{entry.summary}</p>
            <p className="history-time">{formatTime(entry.createdAt)}</p>
          </article>
        ))}
      </div>
    </div>
  );
}

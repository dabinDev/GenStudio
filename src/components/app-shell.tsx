"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { PropsWithChildren } from "react";
import {
  Bot,
  Boxes,
  FileText,
  ImageIcon,
  MessageSquare,
  Sparkles,
  Video,
} from "lucide-react";
import { useMemo, useState } from "react";

import { CAPABILITY_LABELS } from "@/lib/catalog";
import { useWorkbenchStore } from "@/components/workbench-provider";
import type { Capability, ModelDefinition } from "@/lib/types";

const FILTERS: Array<{ label: string; value: Capability | "all" }> = [
  {
    label: "全部",
    value: "all",
  },
  {
    label: "聊天",
    value: "text",
  },
  {
    label: "图片",
    value: "image",
  },
  {
    label: "视频",
    value: "video",
  },
];

function getModelHref(model: ModelDefinition): string {
  if (model.capability === "image") {
    return "/images";
  }

  if (model.capability === "video") {
    return "/videos";
  }

  return "/text";
}

export function AppShell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  const { models } = useWorkbenchStore();
  const [filter, setFilter] = useState<Capability | "all">("all");

  const filteredModels = useMemo(
    () =>
      models.filter((model) =>
        filter === "all" ? true : model.capability === filter,
      ),
    [filter, models],
  );
  const activeModelId = useMemo(() => {
    const activeCapability =
      pathname === "/images"
        ? "image"
        : pathname === "/videos"
          ? "video"
          : pathname === "/text"
            ? "text"
            : null;

    return (
      models.find((model) => model.capability === activeCapability)?.id || ""
    );
  }, [models, pathname]);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-mark">
            <Sparkles aria-hidden="true" size={18} strokeWidth={2} />
          </div>
          <div>
            <strong>CreativePannel</strong>
            <span>多模型创作调试台</span>
          </div>
        </div>

        <div className="category-tabs">
          <div className="primary-selector">
            <button type="button" className="primary-item primary-item-active">
              <Boxes aria-hidden="true" size={18} strokeWidth={2} />
              <span>大模型</span>
            </button>
            <button type="button" className="primary-item" disabled>
              <Bot aria-hidden="true" size={18} strokeWidth={2} />
              <span>智能体</span>
            </button>
          </div>

          <div className="secondary-selector">
            {FILTERS.map((item) => (
              <button
                key={item.value}
                type="button"
                className={`secondary-item ${
                  filter === item.value ? "secondary-item-active" : ""
                }`}
                onClick={() => setFilter(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="model-list">
          <div className="model-list-special">
            <div className="model-avatar model-avatar-duo">
              <MessageSquare aria-hidden="true" size={18} strokeWidth={2} />
            </div>
            <div className="model-info">
              <strong>多模型协作</strong>
              <span>多个模型同时调试，对比响应结果</span>
            </div>
            <span className="model-tag tag-duo">多模型</span>
          </div>

          <div className="model-divider">
            <span>模型列表</span>
          </div>

          {filteredModels.map((model) => {
            const active = model.id === activeModelId;

            return (
              <Link
                key={model.id}
                href={getModelHref(model)}
                className={`sidebar-model-item ${
                  active ? "sidebar-model-active" : ""
                }`}
              >
                <div className={`model-avatar model-avatar-${model.capability}`}>
                  {model.capability === "text" ? (
                    <FileText aria-hidden="true" size={17} strokeWidth={2} />
                  ) : null}
                  {model.capability === "image" ? (
                    <ImageIcon aria-hidden="true" size={17} strokeWidth={2} />
                  ) : null}
                  {model.capability === "video" ? (
                    <Video aria-hidden="true" size={17} strokeWidth={2} />
                  ) : null}
                </div>
                <div className="model-info">
                  <strong title={model.name}>{model.name}</strong>
                  <span>{model.description}</span>
                </div>
                <span className={`model-tag tag-${model.capability}`}>
                  {CAPABILITY_LABELS[model.capability]}
                </span>
              </Link>
            );
          })}
        </div>

        <div className="sidebar-account">
          <div className="account-avatar">S</div>
          <div className="account-copy">
            <strong>本地调试台</strong>
            <span>在线</span>
          </div>
          <Link href="/settings" className="account-recharge">
            账户充值
          </Link>
        </div>
      </aside>

      <main className="main">{children}</main>
    </div>
  );
}

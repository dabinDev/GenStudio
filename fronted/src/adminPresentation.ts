import type { Capability } from "./types";

export type AdminTab =
  | "overview"
  | "models"
  | "prompts"
  | "users"
  | "text-records"
  | "image-records"
  | "video-records"
  | "audit";

export interface AdminTabDefinition {
  value: AdminTab;
  label: string;
  hint: string;
  icon: string;
  tone: "blue" | "green" | "amber" | "red" | "cyan" | "slate";
}

export const adminTabs: AdminTabDefinition[] = [
  { value: "overview", label: "运营概览", hint: "调用统计、成功率、模型分布", icon: "chart", tone: "blue" },
  { value: "models", label: "模型管理", hint: "发布、配置公用模型", icon: "model", tone: "green" },
  { value: "prompts", label: "提示词模板", hint: "AI文案优化模板", icon: "spark", tone: "cyan" },
  { value: "users", label: "用户管理", hint: "启用、禁用、角色管理", icon: "user", tone: "cyan" },
  { value: "text-records", label: "文案记录", hint: "提示词与响应追踪", icon: "text", tone: "slate" },
  { value: "image-records", label: "生图记录", hint: "图片结果与参数", icon: "image", tone: "amber" },
  { value: "video-records", label: "视频记录", hint: "任务状态与视频结果", icon: "video", tone: "blue" },
  { value: "audit", label: "操作日志", hint: "管理员变更审计", icon: "audit", tone: "slate" },
];

export const adminCapabilityTabs: Array<{ value: Capability | "all"; label: string }> = [
  { value: "all", label: "全部" },
  { value: "text", label: "文案" },
  { value: "image", label: "图片" },
  { value: "video", label: "视频" },
];

export const adminRecordCapabilityTabs: Array<{ value: Capability; label: string; hint: string }> = [
  { value: "text", label: "文案", hint: "提问 / 回答" },
  { value: "image", label: "图片", hint: "提示词 / 结果" },
  { value: "video", label: "视频", hint: "任务 / 视频" },
];

export const adminNavGroups: Array<{ title: string; tabs: AdminTab[] }> = [
  { title: "总览", tabs: ["overview"] },
  { title: "配置", tabs: ["models", "prompts"] },
  { title: "用户", tabs: ["users"] },
  { title: "记录", tabs: ["text-records", "image-records", "video-records"] },
  { title: "审计", tabs: ["audit"] },
];

export const ADMIN_RECORD_CAPABILITY_BY_TAB: Partial<Record<AdminTab, Capability>> = {
  "text-records": "text",
  "image-records": "image",
  "video-records": "video",
};

export const ADMIN_PAGE_SUGGESTIONS: Record<AdminTab, string[]> = {
  overview: [
    "趋势图支持日/周/月切换，快速定位增长和异常。",
    "失败模型可直接点击查看相关记录。",
    "成功率、调用数、模型分布一目了然。",
  ],
  models: [
    "支持批量设置公用状态。",
    "图标URL实时预览，避免失效。",
    "默认参数支持结构化表单编辑。",
  ],
  prompts: [
    "模板支持启用/禁用切换。",
    "测试预览支持多场景验证。",
    "按能力类型快速筛选模板。",
  ],
  users: [
    "支持按角色筛选用户。",
    "用户状态一键切换。",
    "操作日志完整记录变更。",
  ],
  "text-records": [
    "支持关键词搜索提示词。",
    "按模型和状态筛选记录。",
    "查看完整请求参数。",
  ],
  "image-records": [
    "图片结果缩略图预览。",
    "按尺寸和比例筛选。",
    "查看参考图和生成参数。",
  ],
  "video-records": [
    "任务状态实时更新。",
    "视频在线播放预览。",
    "按模型和状态筛选。",
  ],
  audit: [
    "高风险操作醒目标记。",
    "按目标对象快速筛选。",
    "支持审计日志导出。",
  ],
};

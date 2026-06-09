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
  { value: "overview", label: "运营面板", hint: "调用、失败率、公私模型分布", icon: "chart", tone: "blue" },
  { value: "models", label: "公用模型配置", hint: "发布、取消公用、图标、提示语", icon: "model", tone: "green" },
  { value: "prompts", label: "提示语模板", hint: "AI 文案优化模板", icon: "spark", tone: "cyan" },
  { value: "users", label: "用户管理", hint: "启用、禁用、删除、恢复", icon: "user", tone: "cyan" },
  { value: "text-records", label: "文案记录", hint: "提示词与响应追踪", icon: "text", tone: "slate" },
  { value: "image-records", label: "生图记录", hint: "图片结果与参数", icon: "image", tone: "amber" },
  { value: "video-records", label: "视频记录", hint: "任务、视频、失败原因", icon: "video", tone: "blue" },
  { value: "audit", label: "操作记录", hint: "管理员变更审计", icon: "audit", tone: "slate" },
];

export const adminCapabilityTabs: Array<{ value: Capability | "all"; label: string }> = [
  { value: "all", label: "全部" },
  { value: "text", label: "文案创作" },
  { value: "image", label: "图片创作" },
  { value: "video", label: "视频创作" },
];

export const adminRecordCapabilityTabs: Array<{ value: Capability; label: string; hint: string }> = [
  { value: "text", label: "文案", hint: "提问 / 回答" },
  { value: "image", label: "图片/图文", hint: "提示词 / 图片结果" },
  { value: "video", label: "视频", hint: "提示词 / 视频结果" },
];

export const adminNavGroups: Array<{ title: string; tabs: AdminTab[] }> = [
  { title: "总览", tabs: ["overview"] },
  { title: "模型资产", tabs: ["models", "prompts"] },
  { title: "用户与权限", tabs: ["users"] },
  { title: "创作记录", tabs: ["text-records", "image-records", "video-records"] },
  { title: "安全审计", tabs: ["audit"] },
];

export const ADMIN_RECORD_CAPABILITY_BY_TAB: Partial<Record<AdminTab, Capability>> = {
  "text-records": "text",
  "image-records": "image",
  "video-records": "video",
};

export const ADMIN_PAGE_SUGGESTIONS: Record<AdminTab, string[]> = {
  overview: [
    "补充按日、按周、按月的趋势曲线，方便判断增长和异常波动。",
    "把失败率最高的模型入口联动到视频/图片/文案记录页，减少排查路径。",
    "增加额度消耗、平均排队时间、任务超时率，形成更完整的运营健康分。",
  ],
  models: [
    "增加批量设为公用、批量取消公用和批量启用提示优化。",
    "给图标 URL 加预览和失败提示，避免上线后模型图标静默失效。",
    "把默认参数 JSON 改成结构化表单，同时保留高级 JSON 模式。",
  ],
  prompts: [
    "增加模板版本历史，方便回滚一次效果不佳的提示语修改。",
    "把测试预览扩展为多样例测试，覆盖文案、图片、视频三类短提示词。",
    "增加模型级启用状态总览，避免模板存在但某个模型未启用。",
  ],
  users: [
    "增加用户详情侧栏，集中展示模型数、调用数、失败率和最近记录。",
    "增加角色筛选和管理员变更确认，降低误操作风险。",
    "增加导出用户列表和最近登录 IP，便于上线后的运营和风控。",
  ],
  "text-records": [
    "增加关键词搜索，支持在提示词和回答中快速定位内容。",
    "支持按模型和状态保存常用筛选条件，方便反复排查同类问题。",
    "增加 Markdown 渲染开关，在后台直接查看文案最终展示效果。",
  ],
  "image-records": [
    "增加图片瀑布流密度模式，快速扫生成质量和失败样本。",
    "支持点击图片打开详情抽屉，展示原图、引用图和完整参数。",
    "增加按尺寸、比例、参考图数量筛选，便于定位参数异常。",
  ],
  "video-records": [
    "增加任务状态时间线，展示创建、轮询、成功或失败的关键节点。",
    "支持视频在线播放和复制任务 ID，减少跳转排查成本。",
    "增加按视频时长、分辨率、模式筛选，定位具体模型参数限制。",
  ],
  audit: [
    "增加高风险操作标记，例如删除用户、取消公用模型、修改模板。",
    "增加按目标对象筛选，快速查看某个模型或用户的变更历史。",
    "增加审计日志导出，满足上线后的追踪和备份需求。",
  ],
};

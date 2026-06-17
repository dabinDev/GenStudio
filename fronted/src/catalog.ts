import type { Adapter, Capability, ModelDefinition, PromptTemplate } from "./types";

export const BUILTIN_MODELS: ModelDefinition[] = [
  {
    id: "text-gpt-4o",
    name: "GPT-4o",
    vendor: "OpenAI",
    capability: "text",
    adapter: "text-chat",
    model: "gpt-4o",
    description: "适合文案起稿、提示词润色与多场景写作。",
    builtin: true,
  },
  {
    id: "text-claude-sonnet",
    name: "Claude Sonnet 4",
    vendor: "Anthropic",
    capability: "text",
    adapter: "text-chat",
    model: "claude-sonnet-4-20250514",
    description: "适合长文整理、风格化改写与结构化输出。",
    builtin: true,
  },
  {
    id: "text-gemini-pro",
    name: "Gemini 2.5 Pro",
    vendor: "Google",
    capability: "text",
    adapter: "text-chat",
    model: "gemini-2.5-pro",
    description: "适合复杂理解、跨模态描述与长上下文任务。",
    builtin: true,
  },
  {
    id: "text-deepseek-chat",
    name: "DeepSeek Chat",
    vendor: "DeepSeek",
    capability: "text",
    adapter: "text-chat",
    model: "deepseek-chat",
    description: "适合成本敏感型创作与中文长文扩写。",
    builtin: true,
  },
  {
    id: "image-gpt-image-1",
    name: "GPT Image 1",
    vendor: "OpenAI",
    capability: "image",
    adapter: "image-openai",
    model: "gpt-image-1",
    description: "统一图像入口，适合标准文生图与图生图。",
    builtin: true,
  },
  {
    id: "image-gpt-image-2-pro",
    name: "GPT Image 2 Pro",
    vendor: "OpenAI",
    capability: "image",
    adapter: "image-openai",
    model: "gpt-image-2-pro",
    description: "适合高分辨率图像生成与画质优先场景。",
    builtin: true,
  },
  {
    id: "image-jimeng-45",
    name: "即梦 4.5",
    vendor: "字节",
    capability: "image",
    adapter: "image-openai",
    model: "jimeng-4.5",
    description: "支持参考图、比例与分辨率控制。",
    builtin: true,
  },
  {
    id: "image-seedream-50",
    name: "豆包 Seedream 5.0",
    vendor: "字节",
    capability: "image",
    adapter: "image-openai",
    model: "doubao-seedream-5-0-260128",
    description: "适合高质量中文生图与电商视觉。",
    builtin: true,
  },
  {
    id: "video-jimeng-30",
    name: "即梦视频 3.0",
    vendor: "字节",
    capability: "video",
    adapter: "video-unified-jimeng",
    model: "jimeng-video-3.0",
    description: "统一视频接口，支持文生、图生和首尾帧。",
    builtin: true,
  },
  {
    id: "video-vidu-q3",
    name: "Vidu Q3 Pro",
    vendor: "Vidu",
    capability: "video",
    adapter: "video-unified-vidu",
    model: "viduq3-pro",
    description: "统一视频接口，支持音频开关、首帧与首尾帧。",
    builtin: true,
  },
  {
    id: "video-veo-fast",
    name: "Veo 3.1 Fast",
    vendor: "Google",
    capability: "video",
    adapter: "video-unified-veo",
    model: "veo3.1-fast-components",
    description: "统一视频接口，适合文生视频与参考图驱动。",
    builtin: true,
  },
  {
    id: "video-seedance-20",
    name: "Seedance 2.0",
    vendor: "字节",
    capability: "video",
    adapter: "video-seedance",
    model: "doubao-seedance-2-0-260128",
    description: "支持首帧、尾帧、参考图与多模态内容组织。",
    builtin: true,
  },
];

export const CAPABILITY_LABELS: Record<Capability, string> = {
  text: "文案创作",
  image: "图片创作",
  video: "视频创作",
};

export const ADAPTER_LABELS: Record<Adapter, string> = {
  "text-chat": "Chat Completions",
  "image-openai": "/v1/images/generations",
  "video-unified-jimeng": "统一视频 /v1/video/create（即梦）",
  "video-unified-vidu": "统一视频 /v1/video/create（Vidu）",
  "video-unified-veo": "统一视频 /v1/video/create（Veo）",
  "video-unified-generic": "统一视频 /v1/video/create（通用）",
  "video-seedance": "Seedance /v1/video/generations",
};

export const TEXT_TEMPLATES: PromptTemplate[] = [
  {
    id: "text-brand",
    label: "品牌短文案",
    category: "营销",
    summary: "把零散卖点压缩成多组可直接上架的短文案。",
    example: "新品果茶、夏季、轻负担",
    prompt: "请基于给定关键词，输出 5 组简洁有力的品牌短文案，每组控制在 18 个字以内，并附一句风格说明。",
  },
  {
    id: "text-storyboard",
    label: "视频脚本",
    category: "脚本",
    summary: "把想法整理成镜头、旁白、时长都清楚的分镜表。",
    example: "30 秒小米 SU7 变形广告",
    prompt: "请把需求整理成分镜脚本，按镜头编号、画面内容、旁白、镜头运动、时长输出，适合直接喂给视频模型。",
  },
  {
    id: "text-image-prompt",
    label: "图片提示词",
    category: "提示词",
    summary: "补齐构图、光影、材质、镜头语言，适合生图前润色。",
    example: "生成小米 SU7 变形金刚",
    prompt: "请把需求改写成适合图像模型的高质量提示词，输出中英双语版本，并补充构图、光影、材质与镜头语言。",
  },
  {
    id: "text-video-prompt",
    label: "视频提示词",
    category: "提示词",
    summary: "强化动作、节奏、镜头运动和结尾定格。",
    example: "汽车从首帧变形成机甲",
    prompt: "请把需求改写成适合视频模型的生成提示词，突出主体动作、镜头运动、节奏、景别、风格和时长建议。",
  },
];

export const IMAGE_TEMPLATES: PromptTemplate[] = [
  {
    id: "image-poster",
    label: "电商海报",
    category: "商业",
    summary: "适合产品主图、活动图，强调主体、留白和质感。",
    example: "高端耳机新品发布海报",
    prompt: "生成一张高级电商海报，突出主体产品，画面干净，主次分明，保留大面积可排版留白，强调质感光影。",
  },
  {
    id: "image-cinema",
    label: "电影感剧照",
    category: "视觉",
    summary: "把普通描述拉成有景别、情绪和光影的大片镜头。",
    example: "雨夜霓虹街道中的蓝色跑车",
    prompt: "生成一张电影感剧照，具有强烈情绪氛围、明确景别、胶片级光影与真实材质细节。",
  },
  {
    id: "image-character",
    label: "角色设定",
    category: "角色",
    summary: "适合人物、机甲、IP 设定，强调可持续统一。",
    example: "蓝色汽车人机甲角色设定",
    prompt: "生成人物角色设定图，完整交代服装、姿态、表情、材质与世界观氛围，风格统一且可持续扩展。",
  },
  {
    id: "image-realism",
    label: "写实增强",
    category: "编辑",
    summary: "用于图生图和修图，优先保留主体特征和构图。",
    example: "参考照片增强真实质感",
    prompt: "参考输入素材，输出更写实、更精致的画面，保留主体核心特征，提升光线、层次与质感。",
  },
];

export const VIDEO_TEMPLATES: PromptTemplate[] = [
  {
    id: "video-product",
    label: "产品广告",
    category: "商业",
    summary: "开场质感、中段功能展示、结尾品牌记忆点。",
    example: "智能手表 8 秒短广告",
    prompt: "第一人称产品广告镜头：开场特写建立质感，中段通过切换景别展示功能，结尾定格品牌记忆点。",
  },
  {
    id: "video-motion",
    label: "人物动作",
    category: "动态",
    summary: "适合人物、宠物、角色动作，让动作和镜头更自然。",
    example: "人物转身看向镜头",
    prompt: "人物自然向前移动并与镜头产生互动，动作流畅，表情自然，镜头带轻微推进，氛围真实高级。",
  },
  {
    id: "video-transition",
    label: "首尾帧过渡",
    category: "首尾帧",
    summary: "用于两张图之间生成稳定过渡，减少跳变。",
    example: "汽车首帧到机甲尾帧",
    prompt: "让首帧与尾帧之间形成自然、连贯、节奏稳定的视觉过渡，避免跳变，突出镜头连续性。",
  },
  {
    id: "video-travel",
    label: "氛围旅拍",
    category: "镜头",
    summary: "自动补足远中近景、节奏和统一风格。",
    example: "海边咖啡馆慢镜头",
    prompt: "生成旅拍质感短片，镜头有节奏地切换远景、中景和特写，画面通透，风格统一，动作自然。",
  },
];

export function getCapabilityDefaultAdapter(capability: Capability): Adapter {
  if (capability === "text") return "text-chat";
  if (capability === "image") return "image-openai";
  return "video-unified-generic";
}

export function getAdapterOptions(capability: Capability): Adapter[] {
  if (capability === "text") return ["text-chat"];
  if (capability === "image") return ["image-openai"];
  return [
    "video-unified-generic",
    "video-unified-jimeng",
    "video-unified-vidu",
    "video-unified-veo",
    "video-seedance",
  ];
}

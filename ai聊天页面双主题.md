# 创意工坊 - 聊天页面双主题设计（白天 + 夜间）

> 生成时间：2026-06-10
> 设计参考：ChatGPT / Claude / Linear
> 支持：白天模式 + 夜间模式切换

---

## 一、配色方案对比

### 1.1 颜色变量定义

```css
/* ============================================
   双主题配色系统
   ============================================ */

/* ===== 白天模式（默认）===== */
:root,
[data-theme="light"] {
  /* 背景层级 */
  --bg-base: #f8fafc;
  --bg-surface: #ffffff;
  --bg-elevated: #f1f5f9;
  --bg-hover: rgba(34, 211, 238, 0.08);
  --bg-active: rgba(34, 211, 238, 0.12);

  /* 文字层级 */
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #94a3b8;
  --text-inverse: #ffffff;

  /* 边框 */
  --border: #e2e8f0;
  --border-hover: #cbd5e1;
  --border-focus: #22d3ee;
  --divider: #f1f5f9;

  /* 主色 */
  --primary: #0891b2;
  --primary-hover: #0e7490;
  --primary-gradient: linear-gradient(135deg, #0891b2, #059669);
  --primary-subtle: rgba(8, 145, 178, 0.1);

  /* 状态色 */
  --success: #16a34a;
  --success-bg: rgba(22, 163, 74, 0.1);
  --success-border: rgba(22, 163, 74, 0.3);
  --warning: #d97706;
  --warning-bg: rgba(217, 119, 6, 0.1);
  --warning-border: rgba(217, 119, 6, 0.3);
  --danger: #dc2626;
  --danger-bg: rgba(220, 38, 38, 0.1);
  --danger-border: rgba(220, 38, 38, 0.3);

  /* 阴影 */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
  --shadow-lg: 0 12px 40px rgba(0, 0, 0, 0.12);

  /* 毛玻璃 */
  --glass-bg: rgba(255, 255, 255, 0.8);
  --glass-border: rgba(0, 0, 0, 0.08);
  --glass-blur: blur(20px);
}

/* ===== 夜间模式 ===== */
[data-theme="dark"] {
  /* 背景层级 */
  --bg-base: #09090b;
  --bg-surface: #18181b;
  --bg-elevated: #27272a;
  --bg-hover: rgba(34, 211, 238, 0.08);
  --bg-active: rgba(34, 211, 238, 0.12);

  /* 文字层级 */
  --text-primary: #fafafa;
  --text-secondary: #a1a1aa;
  --text-muted: #71717a;
  --text-inverse: #000000;

  /* 边框 */
  --border: #27272a;
  --border-hover: #3f3f46;
  --border-focus: #22d3ee;
  --divider: #18181b;

  /* 主色 */
  --primary: #22d3ee;
  --primary-hover: #06b6d4;
  --primary-gradient: linear-gradient(135deg, #22d3ee, #10b981);
  --primary-subtle: rgba(34, 211, 238, 0.1);

  /* 状态色 */
  --success: #22c55e;
  --success-bg: rgba(34, 197, 94, 0.1);
  --success-border: rgba(34, 197, 94, 0.3);
  --warning: #f59e0b;
  --warning-bg: rgba(245, 158, 11, 0.1);
  --warning-border: rgba(245, 158, 11, 0.3);
  --danger: #ef4444;
  --danger-bg: rgba(239, 68, 68, 0.1);
  --danger-border: rgba(239, 68, 68, 0.3);

  /* 阴影 */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 12px 40px rgba(0, 0, 0, 0.5);

  /* 毛玻璃 */
  --glass-bg: rgba(24, 24, 27, 0.8);
  --glass-border: rgba(255, 255, 255, 0.08);
  --glass-blur: blur(20px);
}
```

---

## 二、聊天页面完整样式

### 2.1 在 styles.css 中添加以下代码

```css
/* ============================================
   聊天页面双主题样式
   ============================================ */

/* ===== 聊天容器 ===== */
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-base);
  transition: background 0.3s ease;
}

/* ===== 顶部栏 ===== */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border-bottom: 1px solid var(--glass-border);
  transition: all 0.3s ease;
}

.chat-header-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-header-label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--primary);
  padding: 4px 10px;
  background: var(--primary-subtle);
  border-radius: 6px;
}

.chat-header-name {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.chat-header-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-header-stat {
  font-size: 13px;
  color: var(--text-muted);
  padding: 4px 12px;
  background: var(--bg-elevated);
  border-radius: 9999px;
}

/* ===== 对话区域 ===== */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}

/* 自定义滚动条 */
.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 9999px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: var(--border-hover);
}

/* ===== 消息项 ===== */
.chat-message {
  display: flex;
  flex-direction: column;
  gap: 8px;
  animation: chatFadeIn 0.3s ease;
}

@keyframes chatFadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 用户消息 - 靠右 */
.chat-message-user {
  align-self: flex-end;
  align-items: flex-end;
  max-width: 80%;
}

/* AI消息 - 靠左 */
.chat-message-ai {
  align-self: flex-start;
  align-items: flex-start;
  max-width: 80%;
}

/* ===== 消息头部 ===== */
.chat-message-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 用户头像 */
.chat-message-user .chat-message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 9999px;
  background: var(--primary-gradient);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-inverse);
  font-size: 14px;
  font-weight: 700;
}

/* AI头像 */
.chat-message-ai .chat-message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 9999px;
  background: var(--bg-elevated);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 14px;
}

.chat-message-sender {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.chat-message-time {
  font-size: 12px;
  color: var(--text-muted);
}

/* 状态标签 */
.chat-message-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 9999px;
  font-weight: 500;
}

.chat-message-status-success {
  background: var(--success-bg);
  color: var(--success);
}

.chat-message-status-processing {
  background: var(--warning-bg);
  color: var(--warning);
  animation: pulse 2s ease-in-out infinite;
}

.chat-message-status-error {
  background: var(--danger-bg);
  color: var(--danger);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* ===== 消息内容 ===== */
.chat-message-content {
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-primary);
}

/* 用户消息内容 - 右对齐 */
.chat-message-user .chat-message-content {
  text-align: right;
}

/* AI消息内容 - 左对齐 */
.chat-message-ai .chat-message-content {
  text-align: left;
}

/* ===== 图片消息 ===== */
.chat-message-image {
  max-width: 400px;
  border-radius: 12px;
  overflow: hidden;
  background: var(--bg-elevated);
  border: 1px solid var(--glass-border);
}

.chat-message-image img {
  width: 100%;
  height: auto;
  display: block;
}

/* 图片操作按钮 */
.chat-message-image-actions {
  display: flex;
  gap: 8px;
  padding: 12px;
  background: var(--bg-surface);
  border-top: 1px solid var(--glass-border);
}

/* ===== 加载状态 ===== */
.chat-loading {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: 12px;
}

.chat-loading-dots {
  display: flex;
  gap: 4px;
}

.chat-loading-dot {
  width: 8px;
  height: 8px;
  background: var(--primary);
  border-radius: 9999px;
  animation: bounce 1.4s infinite ease-in-out;
}

.chat-loading-dot:nth-child(1) { animation-delay: -0.32s; }
.chat-loading-dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.chat-loading-text {
  font-size: 13px;
  color: var(--text-muted);
}

/* ===== 输入区域 ===== */
.chat-input-container {
  padding: 16px 24px;
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border-top: 1px solid var(--glass-border);
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
  transition: all 0.3s ease;
}

/* 收起按钮 */
.chat-input-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 8px;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.chat-input-toggle:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

/* 玩法说明 */
.chat-input-tips {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--bg-elevated);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-muted);
}

.chat-input-tips-tag {
  padding: 2px 8px;
  background: var(--primary-subtle);
  color: var(--primary);
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

/* 快捷标签 */
.chat-input-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.chat-input-tag {
  padding: 6px 12px;
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 9999px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.chat-input-tag:hover {
  color: var(--text-primary);
  border-color: var(--border-hover);
  background: var(--bg-hover);
}

.chat-input-tag-active {
  color: var(--primary);
  border-color: var(--primary);
  background: var(--primary-subtle);
}

/* 输入框主体 */
.chat-input-main {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

/* 参考图区域 */
.chat-input-ref {
  flex-shrink: 0;
}

.chat-input-ref-btn {
  width: 80px;
  height: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--bg-elevated);
  border: 2px dashed var(--border);
  border-radius: 12px;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.chat-input-ref-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-subtle);
}

.chat-input-ref-icon {
  font-size: 24px;
}

/* 文本输入框 */
.chat-input-field {
  flex: 1;
  min-height: 80px;
  max-height: 200px;
  padding: 16px;
  font-size: 15px;
  color: var(--text-primary);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 12px;
  outline: none;
  resize: none;
  transition: all 0.15s ease;
}

.chat-input-field::placeholder {
  color: var(--text-muted);
}

.chat-input-field:hover {
  border-color: var(--border-hover);
}

.chat-input-field:focus {
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px var(--primary-subtle);
}

/* AI优化按钮 */
.chat-input-ai-btn {
  position: absolute;
  right: 12px;
  bottom: 12px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-subtle);
  border: 1px solid var(--primary);
  border-radius: 8px;
  color: var(--primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.chat-input-ai-btn:hover {
  background: var(--primary);
  color: var(--text-inverse);
}

/* 底部工具栏 */
.chat-input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
}

/* 左侧工具 */
.chat-input-tools {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-input-keyword {
  padding: 6px 12px;
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 8px;
  outline: none;
  transition: all 0.15s ease;
}

.chat-input-keyword::placeholder {
  color: var(--text-muted);
}

.chat-input-keyword:focus {
  border-color: var(--border-focus);
}

/* 右侧按钮 */
.chat-input-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-input-status {
  font-size: 13px;
  color: var(--text-muted);
}

.chat-input-status-ready {
  color: var(--success);
}

/* ===== 生成按钮 ===== */
.chat-btn-generate {
  padding: 10px 24px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-inverse);
  background: var(--primary-gradient);
  border: none;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
  box-shadow: 0 2px 8px rgba(34, 211, 238, 0.3);
}

.chat-btn-generate:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(34, 211, 238, 0.4);
}

.chat-btn-generate:active:not(:disabled) {
  transform: translateY(0) scale(0.98);
}

.chat-btn-generate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* 查询按钮 */
.chat-btn-query {
  padding: 10px 24px;
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.chat-btn-query:hover {
  background: var(--bg-hover);
  border-color: var(--border-hover);
}

/* ===== 按钮组件（复用） ===== */
.admin-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  transition: all 0.15s ease;
  text-decoration: none;
  white-space: nowrap;
}

.admin-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.admin-btn-primary {
  background: var(--primary-gradient);
  color: var(--text-inverse);
}

.admin-btn-primary:hover:not(:disabled) {
  box-shadow: 0 2px 8px rgba(34, 211, 238, 0.3);
}

.admin-btn-secondary {
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 1px solid var(--border);
}

.admin-btn-secondary:hover:not(:disabled) {
  background: var(--bg-hover);
  border-color: var(--border-hover);
}

.admin-btn-ghost {
  background: transparent;
  color: var(--text-secondary);
}

.admin-btn-ghost:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.admin-btn-sm {
  padding: 6px 12px;
  font-size: 13px;
  border-radius: 6px;
}

/* ===== 响应式 ===== */
@media (max-width: 1024px) {
  .chat-messages {
    padding: 16px;
  }

  .chat-input-container {
    padding: 12px 16px;
  }

  .chat-message {
    max-width: 85%;
  }
}

@media (max-width: 768px) {
  .chat-messages {
    padding: 12px;
  }

  .chat-input-container {
    padding: 12px;
  }

  .chat-message {
    max-width: 90%;
  }

  .chat-input-main {
    flex-direction: column;
  }

  .chat-input-ref {
    width: 100%;
  }

  .chat-input-ref-btn {
    width: 100%;
    height: 60px;
    flex-direction: row;
    justify-content: center;
  }

  .chat-input-tools {
    flex-wrap: wrap;
  }

  .chat-input-footer {
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
  }

  .chat-input-actions {
    justify-content: space-between;
  }
}
```

---

## 三、Vue 组件代码

### 3.1 ChatMessage.vue

```vue
<template>
  <div class="chat-message" :class="messageClass">
    <div class="chat-message-header">
      <div class="chat-message-avatar">{{ avatarText }}</div>
      <span class="chat-message-sender">{{ message.sender }}</span>
      <span class="chat-message-time">{{ message.time }}</span>
      <span v-if="message.status" class="chat-message-status" :class="statusClass">
        {{ statusLabel }}
      </span>
    </div>
    <div class="chat-message-content">
      <div v-if="message.type === 'text'" v-html="renderMarkdown(message.content)"></div>
      <div v-else-if="message.type === 'image'" class="chat-message-image">
        <img :src="message.imageUrl" :alt="message.prompt" />
        <div class="chat-message-image-actions">
          <button class="admin-btn admin-btn-secondary admin-btn-sm">查看</button>
          <button class="admin-btn admin-btn-ghost admin-btn-sm">引用编辑</button>
          <button class="admin-btn admin-btn-ghost admin-btn-sm">选取编辑</button>
          <button class="admin-btn admin-btn-ghost admin-btn-sm">保存</button>
        </div>
      </div>
      <div v-else-if="message.type === 'loading'" class="chat-loading">
        <div class="chat-loading-dots">
          <div class="chat-loading-dot"></div>
          <div class="chat-loading-dot"></div>
          <div class="chat-loading-dot"></div>
        </div>
        <span class="chat-loading-text">{{ message.loadingText || '生成中...' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

interface ChatMessage {
  id: string;
  sender: string;
  content: string;
  type: 'text' | 'image' | 'loading';
  imageUrl?: string;
  prompt?: string;
  time: string;
  status?: 'success' | 'processing' | 'error';
  loadingText?: string;
}

const props = defineProps<{
  message: ChatMessage;
}>();

const isUser = computed(() => props.message.sender === '你');
const messageClass = computed(() => ({
  'chat-message-user': isUser.value,
  'chat-message-ai': !isUser.value,
}));
const avatarText = computed(() => isUser.value ? '你' : 'AI');
const statusClass = computed(() => {
  switch (props.message.status) {
    case 'success': return 'chat-message-status-success';
    case 'processing': return 'chat-message-status-processing';
    case 'error': return 'chat-message-status-error';
    default: return '';
  }
});
const statusLabel = computed(() => {
  switch (props.message.status) {
    case 'success': return '完成';
    case 'processing': return '生成中';
    case 'error': return '失败';
    default: return '';
  }
});

function renderMarkdown(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}
</script>
```

### 3.2 ChatInput.vue

```vue
<template>
  <div class="chat-input-container">
    <button class="chat-input-toggle" @click="toggleExpanded">
      <span>{{ isExpanded ? '收起输入' : '展开输入' }}</span>
      <span>{{ isExpanded ? '▼' : '▲' }}</span>
    </button>
    <template v-if="isExpanded">
      <div class="chat-input-tips">
        <span class="chat-input-tips-tag">玩法说明</span>
        <span>{{ tipText }}</span>
      </div>
      <div class="chat-input-tags">
        <button v-for="tag in tags" :key="tag" class="chat-input-tag"
          :class="{ 'chat-input-tag-active': selectedTag === tag }" @click="selectTag(tag)">
          {{ tag }}
        </button>
      </div>
      <div class="chat-input-main">
        <div class="chat-input-ref">
          <label class="chat-input-ref-btn">
            <span class="chat-input-ref-icon">+</span>
            <span>参考图</span>
            <input type="file" accept="image/*" multiple hidden @change="handleRefUpload" />
          </label>
        </div>
        <div style="position: relative; flex: 1;">
          <textarea v-model="inputText" class="chat-input-field" :placeholder="placeholder"
            @keydown.enter.exact="handleGenerate"></textarea>
          <button class="chat-input-ai-btn" @click="optimizePrompt">AI</button>
        </div>
      </div>
      <div class="chat-input-footer">
        <div class="chat-input-tools">
          <input v-model="keyword" class="chat-input-keyword" placeholder="关键词 玻璃感、青柠色" type="text" />
          <button class="chat-input-tag">{{ sizeText }}</button>
          <button class="chat-input-tag">参考与高级 JSON</button>
        </div>
        <div class="chat-input-actions">
          <span class="chat-input-status" :class="{ 'chat-input-status-ready': modelReady }">
            {{ modelReady ? '模型已就绪' : '模型加载中...' }}
          </span>
          <button class="chat-btn-query" @click="handleQuery">查询</button>
          <button class="chat-btn-generate" :disabled="!canGenerate" @click="handleGenerate">生成</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';

const props = defineProps<{
  modelReady: boolean;
  tipText?: string;
  tags?: string[];
  placeholder?: string;
  sizeText?: string;
}>();

const emit = defineEmits<{
  generate: [text: string, keyword: string, refImages: File[]];
  query: [];
  optimize: [text: string];
}>();

const isExpanded = ref(true);
const inputText = ref('');
const keyword = ref('');
const selectedTag = ref('');
const refImages = ref<File[]>([]);

const canGenerate = computed(() => inputText.value.trim().length > 0 && props.modelReady);
function toggleExpanded() { isExpanded.value = !isExpanded.value; }
function selectTag(tag: string) { selectedTag.value = tag; inputText.value = tag; }
function handleRefUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  if (input.files) refImages.value = Array.from(input.files);
}
function handleGenerate() {
  if (canGenerate.value) { emit('generate', inputText.value, keyword.value, refImages.value); inputText.value = ''; }
}
function handleQuery() { emit('query'); }
function optimizePrompt() { if (inputText.value.trim()) emit('optimize', inputText.value); }
</script>
```

---

## 四、配色效果对比

### 4.1 白天模式效果

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 背景: #f8fafc (浅灰白)                                                     │
│ 卡片: #ffffff (纯白)                                                       │
│ 文字: #0f172a (深黑)                                                       │
│ 主色: #0891b2 (青色)                                                       │
│                                                                             │
│                     👤 你                                                   │
│                     生成一个科技感的海报                                     │
│                                                                             │
│  🤖 AI                                                                      │
│  [图片结果]                                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 夜间模式效果

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 背景: #09090b (纯黑)                                                       │
│ 卡片: #18181b (深灰)                                                       │
│ 文字: #fafafa (纯白)                                                       │
│ 主色: #22d3ee (亮青)                                                       │
│                                                                             │
│                     👤 你                                                   │
│                     生成一个科技感的海报                                     │
│                                                                             │
│  🤖 AI                                                                      │
│  [图片结果]                                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 五、实施步骤

### 步骤 1: 创建组件文件

```bash
cd E:\FlutterProject\GenStudio\fronted\src\components
```

创建：
- `ChatMessage.vue`
- `ChatInput.vue`

### 步骤 2: 添加 CSS 样式

将"二、聊天页面完整样式"中的代码添加到 `styles.css` 文件。

### 步骤 3: 确保主题切换功能正常

确保 `data-theme` 属性能正确切换：

```css
/* 在 body 或根元素上 */
body {
  transition: background 0.3s ease, color 0.3s ease;
}
```

### 步骤 4: 测试验证

访问 `http://127.0.0.1:5175/#/` 验证：

- [ ] 点击"夜间模式"切换到深色主题
- [ ] 再次点击切换回浅色主题
- [ ] 用户消息靠右显示
- [ ] AI回复靠左显示
- [ ] 两种主题下颜色正确
- [ ] 输入框对齐正常

---

*本文档包含完整的双主题配色方案，支持白天/夜间模式切换。*

# 创意工坊 - 聊天页面完整重设计方案

> 生成时间：2026-06-10
> 项目地址：E:\FlutterProject\GenStudio
> 设计风格：现代深色主题 + 左右对话布局

---

## 一、当前问题分析

### 1.1 核心问题

| 问题 | 当前表现 | 应该的样子 |
|------|----------|-----------|
| **对话方向** | 全部靠左显示 | 用户靠右，AI靠左 |
| **消息样式** | 灰色卡片背景 | 无背景，简洁现代 |
| **输入框对齐** | 与内容区不对齐 | 完全对齐 |
| **整体风格** | 浅色主题 | 深色主题 |

### 1.2 当前布局

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 侧边栏        │  主内容区                                                   │
│                │                                                             │
│                │  ┌─────────────────────────────────────────────────────┐   │
│                │  │  顶部栏                                              │   │
│                │  └─────────────────────────────────────────────────────┘   │
│                │                                                             │
│                │  ┌─────────────────────────────────────────────────────┐   │
│                │  │  📝 生成一个科技感的海报                            │   │
│                │  │                                                     │   │
│                │  │  ┌─────────────────────────────────────────────┐   │   │
│                │  │  │ 你 / 完成 / 14:32                           │   │   │
│                │  │  │ 生成一个科技感的海报                        │   │   │
│                │  │  └─────────────────────────────────────────────┘   │   │
│                │  │                                                     │   │
│                │  │  ┌─────────────────────────────────────────────┐   │   │
│                │  │  │ 模型 / 完成 / 14:33                         │   │   │
│                │  │  │ completed                                   │   │   │
│                │  │  │ [图片结果]                                  │   │   │
│                │  │  └─────────────────────────────────────────────┘   │   │
│                │  │                                                     │   │
│                │  └─────────────────────────────────────────────────────┘   │
│                │                                                             │
│                │  ┌─────────────────────────────────────────────────────┐   │
│                │  │  输入区域（不对齐）                                  │   │
│                │  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、新设计方案

### 2.1 新布局结构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 侧边栏        │  主内容区                                                   │
│                │                                                             │
│                │  ┌─────────────────────────────────────────────────────┐   │
│                │  │  顶部栏                                              │   │
│                │  └─────────────────────────────────────────────────────┘   │
│                │                                                             │
│                │  ┌─────────────────────────────────────────────────────┐   │
│                │  │                                                     │   │
│                │  │                          ┌──────────────────┐      │   │
│                │  │                          │ 你 / 完成 / 14:32│      │   │
│                │  │                          │ 生成一个科技感的 │      │   │
│                │  │                          │ 海报             │      │   │
│                │  │                          └──────────────────┘      │   │
│                │  │                                                     │   │
│                │  │  ┌──────────────────────────────────────────────┐  │   │
│                │  │  │ AI / 完成 / 14:33                            │  │   │
│                │  │  │                                              │  │   │
│                │  │  │  ┌────────────────────────────────────────┐  │  │   │
│                │  │  │  │           [图片结果]                   │  │  │   │
│                │  │  │  └────────────────────────────────────────┘  │  │   │
│                │  │  │                                              │  │   │
│                │  │  │  [查看] [引用编辑] [选取编辑] [保存]        │  │   │
│                │  │  └──────────────────────────────────────────────┘  │   │
│                │  │                                                     │   │
│                │  └─────────────────────────────────────────────────────┘   │
│                │                                                             │
│                │  ┌─────────────────────────────────────────────────────┐   │
│                │  │  输入区域（与内容对齐）                              │   │
│                │  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 设计特点

| 特点 | 说明 |
|------|------|
| **左右对话** | 用户靠右，AI靠左 |
| **无卡片背景** | 移除灰色卡片，使用简洁布局 |
| **输入框对齐** | 与内容区域完全对齐 |
| **深色主题** | 现代深色背景 |
| **毛玻璃效果** | 半透明背景 + 模糊效果 |

---

## 三、详细组件设计

### 3.1 消息布局 CSS

```css
/* ============================================
   聊天页面样式 - 现代深色主题
   ============================================ */

/* ===== 聊天容器 ===== */
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-bg-base);
}

/* ===== 顶部栏 ===== */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-6);
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border-bottom: 1px solid var(--glass-border);
}

.chat-header-title {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.chat-header-label {
  font-size: var(--text-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-primary);
  padding: 4px 10px;
  background: var(--color-primary-subtle);
  border-radius: var(--radius-sm);
}

.chat-header-name {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--color-text-primary);
}

.chat-header-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.chat-header-stat {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  padding: 4px 12px;
  background: var(--color-bg-elevated);
  border-radius: var(--radius-full);
}

/* ===== 对话区域 ===== */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6) var(--space-8);  /* 左右有内边距 */
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
  max-width: 1000px;
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
  background: var(--color-border);
  border-radius: var(--radius-full);
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: var(--color-border-hover);
}

/* ===== 消息项 ===== */
.chat-message {
  display: flex;
  flex-direction: column;
  max-width: 80%;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 用户消息 - 靠右 */
.chat-message-user {
  align-self: flex-end;
  align-items: flex-end;
}

/* AI消息 - 靠左 */
.chat-message-ai {
  align-self: flex-start;
  align-items: flex-start;
}

/* ===== 消息头部 ===== */
.chat-message-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.chat-message-avatar {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

/* 用户头像 */
.chat-message-user .chat-message-avatar {
  background: var(--color-primary-gradient);
  color: var(--color-text-inverse);
  order: 1;  /* 在右侧 */
}

/* AI头像 */
.chat-message-ai .chat-message-avatar {
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
  order: -1;  /* 在左侧 */
}

.chat-message-sender {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.chat-message-time {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.chat-message-status {
  font-size: var(--text-xs);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-weight: 500;
}

.chat-message-status-success {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.chat-message-status-processing {
  background: var(--color-warning-bg);
  color: var(--color-warning);
  animation: pulse 2s ease-in-out infinite;
}

.chat-message-status-error {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* ===== 消息内容 ===== */
.chat-message-content {
  font-size: var(--text-base);
  line-height: var(--leading-relaxed);
  color: var(--color-text-primary);
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
  border-radius: var(--radius-lg);
  overflow: hidden;
  margin-top: var(--space-3);
  background: var(--color-bg-elevated);
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
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--color-bg-surface);
  border-top: 1px solid var(--glass-border);
}

/* ===== 加载状态 ===== */
.chat-loading {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
}

.chat-loading-dots {
  display: flex;
  gap: 4px;
}

.chat-loading-dot {
  width: 8px;
  height: 8px;
  background: var(--color-primary);
  border-radius: var(--radius-full);
  animation: bounce 1.4s infinite ease-in-out;
}

.chat-loading-dot:nth-child(1) { animation-delay: -0.32s; }
.chat-loading-dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.chat-loading-text {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

/* ===== 输入区域 ===== */
.chat-input-container {
  padding: var(--space-4) var(--space-8);  /* 与消息区域对齐 */
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border-top: 1px solid var(--glass-border);
  max-width: 1000px;
  margin: 0 auto;
  width: 100%;
}

/* 收起按钮 */
.chat-input-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2);
  margin-bottom: var(--space-3);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.chat-input-toggle:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-hover);
}

/* 玩法说明 */
.chat-input-tips {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg-elevated);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.chat-input-tips-tag {
  padding: 2px 8px;
  background: var(--color-primary-subtle);
  color: var(--color-primary);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: 500;
}

/* 快捷标签 */
.chat-input-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.chat-input-tag {
  padding: 6px 12px;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.chat-input-tag:hover {
  color: var(--color-text-primary);
  border-color: var(--color-border-hover);
  background: var(--color-bg-hover);
}

.chat-input-tag-active {
  color: var(--color-primary);
  border-color: var(--color-primary);
  background: var(--color-primary-subtle);
}

/* 输入框主体 */
.chat-input-main {
  display: flex;
  gap: var(--space-3);
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
  gap: var(--space-2);
  background: var(--color-bg-elevated);
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-muted);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.chat-input-ref-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-subtle);
}

.chat-input-ref-icon {
  font-size: 24px;
}

/* 文本输入框 */
.chat-input-field {
  flex: 1;
  min-height: 80px;
  max-height: 200px;
  padding: var(--space-4);
  font-size: var(--text-base);
  color: var(--color-text-primary);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  outline: none;
  resize: none;
  transition: all var(--transition-fast);
}

.chat-input-field::placeholder {
  color: var(--color-text-muted);
}

.chat-input-field:hover {
  border-color: var(--color-border-hover);
}

.chat-input-field:focus {
  border-color: var(--color-border-focus);
  box-shadow: 0 0 0 3px var(--color-primary-subtle);
}

/* AI优化按钮 */
.chat-input-ai-btn {
  position: absolute;
  right: var(--space-3);
  bottom: var(--space-3);
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-primary-subtle);
  border: 1px solid rgba(34, 211, 238, 0.3);
  border-radius: var(--radius-sm);
  color: var(--color-primary);
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.chat-input-ai-btn:hover {
  background: var(--color-primary);
  color: var(--color-text-inverse);
}

/* 底部工具栏 */
.chat-input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--space-3);
}

/* 左侧工具 */
.chat-input-tools {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.chat-input-keyword {
  padding: 6px 12px;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  outline: none;
  transition: all var(--transition-fast);
}

.chat-input-keyword::placeholder {
  color: var(--color-text-muted);
}

.chat-input-keyword:focus {
  border-color: var(--color-border-focus);
}

/* 右侧按钮 */
.chat-input-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.chat-input-status {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.chat-input-status-ready {
  color: var(--color-success);
}

/* ===== 生成按钮 ===== */
.chat-btn-generate {
  padding: 10px 24px;
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-text-inverse);
  background: var(--color-primary-gradient);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
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
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--color-text-primary);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.chat-btn-query:hover {
  background: var(--color-bg-hover);
  border-color: var(--color-border-hover);
}

/* ===== 响应式 ===== */
@media (max-width: 1024px) {
  .chat-messages {
    padding: var(--space-4) var(--space-6);
  }

  .chat-input-container {
    padding: var(--space-4) var(--space-6);
  }

  .chat-message {
    max-width: 85%;
  }
}

@media (max-width: 768px) {
  .chat-messages {
    padding: var(--space-4);
  }

  .chat-input-container {
    padding: var(--space-3) var(--space-4);
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
    gap: var(--space-3);
    align-items: stretch;
  }

  .chat-input-actions {
    justify-content: space-between;
  }
}
```

### 3.2 消息组件 Vue

创建 `E:\FlutterProject\GenStudio\fronted\src\components\ChatMessage.vue`：

```vue
<template>
  <div class="chat-message" :class="messageClass">
    <!-- 消息头部 -->
    <div class="chat-message-header">
      <div class="chat-message-avatar" :class="avatarClass">
        {{ avatarText }}
      </div>
      <span class="chat-message-sender">{{ message.sender }}</span>
      <span class="chat-message-time">{{ message.time }}</span>
      <span v-if="message.status" class="chat-message-status" :class="statusClass">
        {{ statusLabel }}
      </span>
    </div>

    <!-- 消息内容 -->
    <div class="chat-message-content">
      <!-- 文本消息 -->
      <div v-if="message.type === 'text'" v-html="renderMarkdown(message.content)"></div>

      <!-- 图片消息 -->
      <div v-else-if="message.type === 'image'" class="chat-message-image">
        <img :src="message.imageUrl" :alt="message.prompt" />
        <div class="chat-message-image-actions">
          <button class="admin-btn admin-btn-secondary admin-btn-sm">查看</button>
          <button class="admin-btn admin-btn-ghost admin-btn-sm">引用编辑</button>
          <button class="admin-btn admin-btn-ghost admin-btn-sm">选取编辑</button>
          <button class="admin-btn admin-btn-ghost admin-btn-sm">保存</button>
        </div>
      </div>

      <!-- 加载状态 -->
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

const avatarClass = computed(() => ({
  'chat-message-avatar-user': isUser.value,
  'chat-message-avatar-ai': !isUser.value,
}));

const avatarText = computed(() => {
  return isUser.value ? '你' : 'AI';
});

const statusClass = computed(() => {
  switch (props.message.status) {
    case 'success':
      return 'chat-message-status-success';
    case 'processing':
      return 'chat-message-status-processing';
    case 'error':
      return 'chat-message-status-error';
    default:
      return '';
  }
});

const statusLabel = computed(() => {
  switch (props.message.status) {
    case 'success':
      return '完成';
    case 'processing':
      return '生成中';
    case 'error':
      return '失败';
    default:
      return '';
  }
});

function renderMarkdown(text: string): string {
  // 简单的 Markdown 渲染
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}
</script>
```

### 3.3 输入框组件 Vue

创建 `E:\FlutterProject\GenStudio\fronted\src\components\ChatInput.vue`：

```vue
<template>
  <div class="chat-input-container">
    <!-- 收起按钮 -->
    <button class="chat-input-toggle" @click="toggleExpanded">
      <span>{{ isExpanded ? '收起输入' : '展开输入' }}</span>
      <span>{{ isExpanded ? '▼' : '▲' }}</span>
    </button>

    <template v-if="isExpanded">
      <!-- 玩法说明 -->
      <div class="chat-input-tips">
        <span class="chat-input-tips-tag">玩法说明</span>
        <span>{{ tipText }}</span>
      </div>

      <!-- 快捷标签 -->
      <div class="chat-input-tags">
        <button
          v-for="tag in tags"
          :key="tag"
          class="chat-input-tag"
          :class="{ 'chat-input-tag-active': selectedTag === tag }"
          @click="selectTag(tag)"
        >
          {{ tag }}
        </button>
      </div>

      <!-- 输入框主体 -->
      <div class="chat-input-main">
        <!-- 参考图 -->
        <div class="chat-input-ref">
          <label class="chat-input-ref-btn">
            <span class="chat-input-ref-icon">+</span>
            <span>参考图</span>
            <input
              type="file"
              accept="image/*"
              multiple
              hidden
              @change="handleRefUpload"
            />
          </label>
        </div>

        <!-- 文本输入框 -->
        <div style="position: relative; flex: 1;">
          <textarea
            v-model="inputText"
            class="chat-input-field"
            :placeholder="placeholder"
            @keydown.enter.exact="handleGenerate"
          ></textarea>
          <button class="chat-input-ai-btn" @click="optimizePrompt">AI</button>
        </div>
      </div>

      <!-- 底部工具栏 -->
      <div class="chat-input-footer">
        <!-- 左侧工具 -->
        <div class="chat-input-tools">
          <input
            v-model="keyword"
            class="chat-input-keyword"
            placeholder="关键词 玻璃感、青柠色"
            type="text"
          />
          <button class="chat-input-tag">{{ sizeText }}</button>
          <button class="chat-input-tag">参考与高级 JSON</button>
        </div>

        <!-- 右侧按钮 -->
        <div class="chat-input-actions">
          <span class="chat-input-status" :class="{ 'chat-input-status-ready': modelReady }">
            {{ modelReady ? '模型已就绪' : '模型加载中...' }}
          </span>
          <button class="chat-btn-query" @click="handleQuery">查询</button>
          <button
            class="chat-btn-generate"
            :disabled="!canGenerate"
            @click="handleGenerate"
          >
            生成
          </button>
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

const canGenerate = computed(() => {
  return inputText.value.trim().length > 0 && props.modelReady;
});

function toggleExpanded() {
  isExpanded.value = !isExpanded.value;
}

function selectTag(tag: string) {
  selectedTag.value = tag;
  inputText.value = tag;
}

function handleRefUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  if (input.files) {
    refImages.value = Array.from(input.files);
  }
}

function handleGenerate() {
  if (canGenerate.value) {
    emit('generate', inputText.value, keyword.value, refImages.value);
    inputText.value = '';
  }
}

function handleQuery() {
  emit('query');
}

function optimizePrompt() {
  if (inputText.value.trim()) {
    emit('optimize', inputText.value);
  }
}
</script>
```

---

## 四、消息布局详细设计

### 4.1 用户消息（靠右）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                                                    ┌──────────────────┐   │
│                                                    │ 你 / 完成 / 14:32│   │
│                                                    │                  │   │
│                                                    │ 生成一个科技感的 │   │
│                                                    │ 海报             │   │
│                                                    └──────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**特点：**
- 靠右对齐（`align-self: flex-end`）
- 头像在右侧（`order: 1`）
- 无背景色，简洁现代

### 4.2 AI回复（靠左）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ AI / 完成 / 14:33                                                   │   │
│  │                                                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                                                             │   │   │
│  │  │                    [图片结果]                               │   │   │
│  │  │                                                             │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                     │   │
│  │  [查看] [引用编辑] [选取编辑] [保存]                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**特点：**
- 靠左对齐（`align-self: flex-start`）
- 头像在左侧（`order: -1`）
- 图片有边框和操作按钮

---

## 五、实施步骤

### 步骤 1: 创建组件文件

```bash
cd E:\FlutterProject\GenStudio\fronted\src\components
```

创建以下文件：
- `ChatMessage.vue` - 消息组件
- `ChatInput.vue` - 输入框组件

### 步骤 2: 添加 CSS 样式

将"三、详细组件设计"中的 CSS 代码添加到 `styles.css` 文件。

### 步骤 3: 集成到主应用

在 `App.vue` 中导入并使用新组件：

```vue
<script setup lang="ts">
import ChatMessage from './components/ChatMessage.vue';
import ChatInput from './components/ChatInput.vue';
</script>

<template>
  <div class="chat-container">
    <!-- 顶部栏 -->
    <div class="chat-header">
      <div class="chat-header-title">
        <span class="chat-header-label">{{ currentCapability }}</span>
        <span class="chat-header-name">{{ currentModel }}</span>
      </div>
      <div class="chat-header-meta">
        <span class="chat-header-stat">{{ messageCount }} 条消息</span>
        <span class="chat-header-stat">{{ conversationStatus }}</span>
      </div>
    </div>

    <!-- 对话区域 -->
    <div class="chat-messages">
      <ChatMessage
        v-for="message in messages"
        :key="message.id"
        :message="message"
      />
    </div>

    <!-- 输入区域 -->
    <ChatInput
      :model-ready="modelReady"
      :tip-text="currentTipText"
      :tags="currentTags"
      :placeholder="currentPlaceholder"
      :size-text="currentSizeText"
      @generate="handleGenerate"
      @query="handleQuery"
      @optimize="handleOptimize"
    />
  </div>
</template>
```

### 步骤 4: 启动开发服务器

```bash
cd E:\FlutterProject\GenStudio\fronted
npm run dev
```

### 步骤 5: 测试验证

访问 `http://127.0.0.1:5175/#/` 验证以下功能：

- [ ] 用户消息靠右显示
- [ ] AI回复靠左显示
- [ ] 输入框与内容区域对齐
- [ ] 毛玻璃效果正常
- [ ] 响应式布局在不同屏幕下正常

---

## 六、设计效果对比

| 维度 | 当前设计 ❌ | 新设计 ✅ |
|------|------------|----------|
| 对话方向 | 全部靠左 | 用户靠右，AI靠左 |
| 消息样式 | 灰色卡片背景 | 无背景，简洁现代 |
| 输入框对齐 | 不对齐 | 完全对齐 |
| 整体风格 | 浅色主题 | 深色主题 |
| 空间利用 | 浪费空间 | 紧凑高效 |

---

*本文档包含完整的聊天页面重设计，可直接实现现代化的左右对话布局。*

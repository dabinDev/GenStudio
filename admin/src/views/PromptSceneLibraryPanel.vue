<template>
  <section class="admin-prompt-scene-library">
    <header class="admin-prompt-scene-library__header">
      <div>
        <h3>图片场景提示词库</h3>
        <p>管理上传参考图后由 GPT 5.5 推荐的小标签模板，支持导入、编辑、批量启停和统计复盘。</p>
      </div>
      <div class="admin-prompt-scene-library__actions">
        <label class="el-button el-button--primary admin-prompt-scene-library__import">
          <span>导入 Yuque JS</span>
          <input hidden type="file" accept=".js,.json,application/json,text/javascript" @change="handleImportFile" />
        </label>
        <el-button :loading="isLoading" @click="loadTemplates">刷新</el-button>
      </div>
    </header>

    <el-alert
      title="图片创作页会在用户上传参考图后调用 GPT 5.5 识别图片，并从这里启用的模板中推荐标签。未配置 GPT 5.5 时前台不会降级到其他模型。"
      type="info"
      show-icon
      :closable="false"
    />
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-alert v-if="noticeMessage" :title="noticeMessage" type="success" show-icon @close="noticeMessage = ''" />

    <section class="admin-prompt-scene-library__stats">
      <article>
        <span>模板总数</span>
        <strong>{{ total }}</strong>
        <small>后台可运营模板</small>
      </article>
      <article>
        <span>本页启用</span>
        <strong>{{ enabledCount }}</strong>
        <small>会进入推荐候选池</small>
      </article>
      <article>
        <span>曝光</span>
        <strong>{{ impressionCount }}</strong>
        <small>GPT 5.5 推荐次数</small>
      </article>
      <article>
        <span>点击</span>
        <strong>{{ clickCount }}</strong>
        <small>用户点选标签次数</small>
      </article>
    </section>

    <section class="admin-prompt-scene-library__filters">
      <el-input v-model="filters.search" clearable placeholder="搜索标题、分类、标签或提示词" @keyup.enter="loadTemplates" />
      <el-select v-model="filters.enabled" aria-label="启用状态" @change="loadTemplates">
        <el-option label="全部状态" value="" />
        <el-option label="仅启用" value="true" />
        <el-option label="仅停用" value="false" />
      </el-select>
      <el-button @click="loadTemplates">查询</el-button>
    </section>

    <section class="admin-prompt-scene-library__bulk">
      <span>已选 {{ selectedIds.length }} 个模板</span>
      <el-button :disabled="!selectedIds.length || !canUpdateSettings" @click="batchSetEnabled(true)">批量启用</el-button>
      <el-button :disabled="!selectedIds.length || !canUpdateSettings" @click="batchSetEnabled(false)">批量停用</el-button>
    </section>

    <section class="admin-prompt-scene-library__table-wrap">
      <el-table
        v-loading="isLoading"
        :data="templates"
        row-key="id"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="46" />
        <el-table-column label="模板" min-width="280">
          <template #default="{ row }">
            <div class="admin-prompt-scene-library__template-cell">
              <strong>{{ row.title || '未命名模板' }}</strong>
              <small>{{ row.category || '未分类' }} / {{ row.subcategory || '未分组' }}</small>
              <p>{{ row.promptSummary || row.promptText }}</p>
              <div class="admin-prompt-scene-library__tags">
                <el-tag v-for="tag in row.tags.slice(0, 4)" :key="tag" effect="plain">{{ tag }}</el-tag>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="权重" width="96">
          <template #default="{ row }">{{ row.weight }}</template>
        </el-table-column>
        <el-table-column label="统计" width="180">
          <template #default="{ row }">
            <div class="admin-prompt-scene-library__metrics">
              <span>曝光 {{ row.impressionCount }}</span>
              <span>点击 {{ row.clickCount }}</span>
              <span>使用 {{ row.useCount }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" effect="plain">
              {{ row.enabled ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDrawer(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <footer class="admin-prompt-scene-library__pager">
      <span>第 {{ page }} 页，每页 {{ pageSize }} 条</span>
      <div>
        <el-button :disabled="page <= 1 || isLoading" @click="changePage(page - 1)">上一页</el-button>
        <el-button :disabled="offset + templates.length >= total || isLoading" @click="changePage(page + 1)">下一页</el-button>
      </div>
    </footer>

    <el-drawer v-model="drawerVisible" size="min(720px, 100vw)" title="编辑图片场景模板" destroy-on-close>
      <div v-if="activeTemplate" class="admin-prompt-scene-library__drawer">
        <el-form label-position="top">
          <el-form-item label="标题">
            <el-input v-model="form.title" :disabled="!canUpdateSettings" />
          </el-form-item>
          <el-form-item label="提示词">
            <el-input v-model="form.promptText" type="textarea" :rows="10" :disabled="!canUpdateSettings" />
          </el-form-item>
          <el-form-item label="标签">
            <el-input v-model="form.tagsText" :disabled="!canUpdateSettings" placeholder="人像，电影感，柔光" />
          </el-form-item>
          <div class="admin-prompt-scene-library__form-grid">
            <el-form-item label="分类 ID">
              <el-input v-model="form.categoryId" :disabled="!canUpdateSettings" />
            </el-form-item>
            <el-form-item label="一级分类">
              <el-input v-model="form.category" :disabled="!canUpdateSettings" />
            </el-form-item>
            <el-form-item label="子分类">
              <el-input v-model="form.subcategory" :disabled="!canUpdateSettings" />
            </el-form-item>
            <el-form-item label="推荐权重">
              <el-input-number v-model="form.weight" :min="0" :max="100000" :disabled="!canUpdateSettings" />
            </el-form-item>
          </div>
          <el-form-item label="启用状态">
            <el-switch v-model="form.enabled" active-text="启用" inactive-text="停用" :disabled="!canUpdateSettings" />
          </el-form-item>
        </el-form>
        <div class="admin-prompt-scene-library__drawer-actions">
          <el-button @click="drawerVisible = false">关闭</el-button>
          <el-button type="primary" :disabled="!canUpdateSettings" :loading="isSaving" @click="saveActiveTemplate">保存</el-button>
        </div>
      </div>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';

import {
  batchUpdatePromptSceneTemplates,
  fetchPromptSceneTemplates,
  importPromptSceneTemplates,
  updatePromptSceneTemplate,
} from '@/api/admin';
import { ADMIN_PERMISSIONS } from '@/adminPermissions';
import { AdminApiError } from '@/api/http';
import { useAdminAuthStore } from '@/stores/auth';
import type { PromptSceneTemplate } from '@/types';
import {
  buildPromptSceneTemplateUpdatePayload,
  createPromptSceneTemplateForm,
  parseYuquePromptLibrarySource,
} from './promptSceneLibraryState';

const auth = useAdminAuthStore();
const canUpdateSettings = computed(() => auth.can(ADMIN_PERMISSIONS.settingsUpdate));
const templates = ref<PromptSceneTemplate[]>([]);
const total = ref(0);
const pageSize = 50;
const page = ref(1);
const selectedIds = ref<string[]>([]);
const isLoading = ref(false);
const isSaving = ref(false);
const errorMessage = ref('');
const noticeMessage = ref('');
const drawerVisible = ref(false);
const activeTemplate = ref<PromptSceneTemplate | null>(null);
const form = reactive(createPromptSceneTemplateForm());
const filters = reactive({
  search: '',
  enabled: '',
});

const offset = computed(() => (page.value - 1) * pageSize);
const enabledCount = computed(() => templates.value.filter((item) => item.enabled).length);
const impressionCount = computed(() => templates.value.reduce((sum, item) => sum + item.impressionCount, 0));
const clickCount = computed(() => templates.value.reduce((sum, item) => sum + item.clickCount, 0));

function friendlyError(error: unknown, fallback: string) {
  return error instanceof AdminApiError && error.message.trim() ? error.message.trim() : fallback;
}

function syncForm(template: PromptSceneTemplate) {
  Object.assign(form, createPromptSceneTemplateForm(template));
}

async function loadTemplates() {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    const payload = await fetchPromptSceneTemplates({
      search: filters.search.trim(),
      enabled: filters.enabled as '' | 'true' | 'false',
      limit: pageSize,
      offset: offset.value,
    });
    templates.value = payload.templates;
    total.value = payload.total;
    selectedIds.value = [];
  } catch (error) {
    errorMessage.value = friendlyError(error, '图片场景提示词库加载失败，请稍后重试。');
  } finally {
    isLoading.value = false;
  }
}

function changePage(nextPage: number) {
  page.value = Math.max(1, nextPage);
  void loadTemplates();
}

function handleSelectionChange(rows: PromptSceneTemplate[]) {
  selectedIds.value = rows.map((item) => item.id);
}

function openDrawer(template: PromptSceneTemplate) {
  activeTemplate.value = template;
  syncForm(template);
  drawerVisible.value = true;
}

async function handleImportFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;
  if (!canUpdateSettings.value) {
    errorMessage.value = '当前账号没有导入提示词库的权限。';
    return;
  }
  isLoading.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    const source = await file.text();
    const index = parseYuquePromptLibrarySource(source);
    const summary = await importPromptSceneTemplates(index, true);
    noticeMessage.value = `导入完成：新增 ${summary.imported}，更新 ${summary.updated}，停用 ${summary.disabled}，总计 ${summary.total}。`;
    page.value = 1;
    await loadTemplates();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Yuque 提示词库导入失败。';
  } finally {
    isLoading.value = false;
  }
}

async function batchSetEnabled(enabled: boolean) {
  if (!selectedIds.value.length || !canUpdateSettings.value) return;
  isLoading.value = true;
  errorMessage.value = '';
  try {
    const updated = await batchUpdatePromptSceneTemplates(selectedIds.value, { enabled });
    noticeMessage.value = `已${enabled ? '启用' : '停用'} ${updated} 个图片场景模板。`;
    await loadTemplates();
  } catch (error) {
    errorMessage.value = friendlyError(error, '批量更新图片场景模板失败。');
  } finally {
    isLoading.value = false;
  }
}

async function saveActiveTemplate() {
  if (!activeTemplate.value || !canUpdateSettings.value) return;
  isSaving.value = true;
  errorMessage.value = '';
  try {
    const saved = await updatePromptSceneTemplate(
      activeTemplate.value.id,
      buildPromptSceneTemplateUpdatePayload(form),
    );
    const index = templates.value.findIndex((item) => item.id === saved.id);
    if (index >= 0) {
      templates.value.splice(index, 1, saved);
    }
    activeTemplate.value = saved;
    noticeMessage.value = '图片场景模板已保存。';
    drawerVisible.value = false;
  } catch (error) {
    errorMessage.value = friendlyError(error, '图片场景模板保存失败。');
  } finally {
    isSaving.value = false;
  }
}

onMounted(() => {
  void loadTemplates();
});
</script>

<style scoped>
.admin-prompt-scene-library {
  display: grid;
  gap: 14px;
  min-width: 0;
}

.admin-prompt-scene-library__header,
.admin-prompt-scene-library__actions,
.admin-prompt-scene-library__bulk,
.admin-prompt-scene-library__pager,
.admin-prompt-scene-library__drawer-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.admin-prompt-scene-library__header,
.admin-prompt-scene-library__pager {
  justify-content: space-between;
}

.admin-prompt-scene-library__header {
  align-items: flex-start;
}

.admin-prompt-scene-library__header h3,
.admin-prompt-scene-library__header p {
  margin: 0;
}

.admin-prompt-scene-library__header h3 {
  color: var(--el-text-color-primary);
  font-size: 18px;
}

.admin-prompt-scene-library__header p,
.admin-prompt-scene-library__pager,
.admin-prompt-scene-library__bulk {
  color: var(--el-text-color-secondary);
}

.admin-prompt-scene-library__actions,
.admin-prompt-scene-library__bulk,
.admin-prompt-scene-library__pager {
  flex-wrap: wrap;
}

.admin-prompt-scene-library__import {
  cursor: pointer;
}

.admin-prompt-scene-library__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.admin-prompt-scene-library__stats article {
  display: grid;
  gap: 4px;
  padding: 12px;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
}

.admin-prompt-scene-library__stats span,
.admin-prompt-scene-library__stats small {
  color: var(--el-text-color-secondary);
}

.admin-prompt-scene-library__stats strong {
  color: var(--el-text-color-primary);
  font-size: 22px;
  line-height: 1.1;
}

.admin-prompt-scene-library__filters {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 160px auto;
  gap: 10px;
  min-width: 0;
}

.admin-prompt-scene-library__table-wrap {
  width: 100%;
  overflow-x: auto;
}

.admin-prompt-scene-library__table-wrap :deep(.el-table) {
  min-width: 820px;
}

.admin-prompt-scene-library__template-cell {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.admin-prompt-scene-library__template-cell strong {
  color: var(--el-text-color-primary);
}

.admin-prompt-scene-library__template-cell small,
.admin-prompt-scene-library__template-cell p {
  margin: 0;
  color: var(--el-text-color-secondary);
}

.admin-prompt-scene-library__template-cell p {
  display: -webkit-box;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow-wrap: anywhere;
}

.admin-prompt-scene-library__tags,
.admin-prompt-scene-library__metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.admin-prompt-scene-library__metrics {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.admin-prompt-scene-library__drawer {
  display: grid;
  gap: 16px;
}

.admin-prompt-scene-library__form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.admin-prompt-scene-library__form-grid :deep(.el-input-number) {
  width: 100%;
}

.admin-prompt-scene-library__drawer-actions {
  justify-content: flex-end;
}

@media (max-width: 760px) {
  .admin-prompt-scene-library__header,
  .admin-prompt-scene-library__pager {
    display: grid;
    justify-items: start;
  }

  .admin-prompt-scene-library__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .admin-prompt-scene-library__filters,
  .admin-prompt-scene-library__form-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .admin-prompt-scene-library__actions,
  .admin-prompt-scene-library__actions > *,
  .admin-prompt-scene-library__bulk > *,
  .admin-prompt-scene-library__pager > div,
  .admin-prompt-scene-library__pager button {
    width: 100%;
  }
}
</style>

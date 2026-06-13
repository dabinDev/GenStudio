<template>
  <section class="admin-content-page">
    <header class="admin-content-page__header">
      <div>
        <h2>提示语中心</h2>
        <p>管理文案、图片、视频的提示语模板，验证模板渲染结果，并控制模板是否启用。</p>
      </div>
      <div class="admin-content-page__actions">
        <el-button :loading="isLoading" @click="loadTemplates">刷新</el-button>
      </div>
    </header>

    <section class="admin-content-page__filters">
      <el-select v-model="capability" aria-label="模板类型" @change="loadTemplates">
        <el-option label="全部类型" value="all" />
        <el-option label="文案" value="text" />
        <el-option label="图片" value="image" />
        <el-option label="视频" value="video" />
      </el-select>
      <el-input v-model="keyword" clearable placeholder="搜索模板名称或内容" />
    </section>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-alert v-if="noticeMessage" :title="noticeMessage" type="success" show-icon @close="noticeMessage = ''" />

    <section class="admin-content-page__table">
      <el-table v-loading="isLoading" :data="filteredTemplates" row-key="id">
        <el-table-column label="模板" min-width="240">
          <template #default="{ row }">
            <div class="admin-content-page__title-cell">
              <strong>{{ row.name || '未命名模板' }}</strong>
              <small>{{ capabilityLabel(row.capability) }} / {{ row.templateType || '默认模板' }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="内容摘要" min-width="320" show-overflow-tooltip>
          <template #default="{ row }">{{ row.content }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" effect="plain">
              {{ row.enabled ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="160">
          <template #default="{ row }">{{ formatDate(row.updatedAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDrawer(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-drawer v-model="drawerVisible" size="min(640px, 100vw)" :title="drawerTitle" destroy-on-close>
      <div v-if="activeTemplate" class="admin-content-page__drawer">
        <el-form label-position="top">
          <el-form-item label="模板名称">
            <el-input v-model="form.name" :disabled="!canUpdateSettings" />
          </el-form-item>
          <el-form-item label="创作类型">
            <el-select v-model="form.capability" disabled>
              <el-option label="文案" value="text" />
              <el-option label="图片" value="image" />
              <el-option label="视频" value="video" />
            </el-select>
          </el-form-item>
          <el-form-item label="模板类型">
            <el-input v-model="form.templateType" disabled placeholder="prompt_optimize" />
          </el-form-item>
          <el-form-item label="模板内容">
            <el-input v-model="form.content" type="textarea" :rows="10" :disabled="!canUpdateSettings" />
          </el-form-item>
          <el-form-item label="启用状态">
            <el-switch
              v-model="form.enabled"
              active-text="启用"
              inactive-text="停用"
              :disabled="!canUpdateSettings"
            />
          </el-form-item>
        </el-form>

        <section class="admin-content-page__test-panel">
          <strong>模型启用概览</strong>
          <div class="admin-content-page__meta-grid">
            <span>模型数 {{ modelStatus.length }}</span>
            <span>专属启用 {{ modelSpecificEnabledCount }}</span>
            <span>专属停用 {{ modelSpecificDisabledCount }}</span>
          </div>
          <div class="admin-content-page__model-status-list">
            <article v-for="item in visibleModelStatus" :key="item.modelGroupId">
              <div>
                <strong>{{ item.modelName }}</strong>
                <small>{{ capabilityLabel(item.capability) }}</small>
              </div>
              <div class="admin-content-page__status-tags">
                <el-tag :type="item.promptOptimizeEnabled ? 'success' : 'info'" effect="plain">
                  AI 文案{{ item.promptOptimizeEnabled ? '启用' : '停用' }}
                </el-tag>
                <el-tag :type="item.usesDefault ? 'success' : 'warning'" effect="plain">
                  {{ item.usesDefault ? '默认模板可用' : '默认模板未启用' }}
                </el-tag>
                <el-tag :type="item.hasModelTemplate ? (item.modelTemplateEnabled ? 'success' : 'info') : 'info'" effect="plain">
                  {{
                    item.hasModelTemplate
                      ? item.modelTemplateEnabled
                        ? '专属模板启用'
                        : '专属模板停用'
                      : '无专属模板'
                  }}
                </el-tag>
              </div>
            </article>
          </div>
          <strong>样例测试</strong>
          <el-input v-model="testPrompt" type="textarea" :rows="5" placeholder="每行一个测试样例" />
          <el-button :loading="isTesting" @click="runTemplateTest">测试渲染</el-button>
          <div v-if="testResults.length" class="admin-content-page__sample-list">
            <article v-for="item in testResults" :key="item.prompt">
              <small>{{ item.prompt }}</small>
              <pre>{{ item.rendered }}</pre>
            </article>
          </div>
          <pre v-else-if="testResult">{{ testResult }}</pre>
        </section>

        <section class="admin-content-page__test-panel">
          <strong>版本历史</strong>
          <el-empty v-if="!versions.length" description="暂无版本记录" />
          <div v-else class="admin-content-page__version-list">
            <article v-for="item in versions" :key="item.id">
              <header>
                <strong>v{{ item.version }} · {{ item.enabled ? '启用' : '停用' }}</strong>
                <small>{{ formatDate(item.createdAt) }}</small>
              </header>
              <p>{{ item.name }}</p>
              <pre>{{ item.content }}</pre>
            </article>
          </div>
        </section>

        <div class="admin-content-page__drawer-actions">
          <el-button @click="drawerVisible = false">关闭</el-button>
          <el-button
            v-if="canUpdateSettings"
            type="primary"
            :loading="isSaving"
            @click="saveTemplate"
          >
            保存模板
          </el-button>
        </div>
      </div>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import {
  fetchPromptTemplateModelStatus,
  fetchPromptTemplates,
  fetchPromptTemplateVersions,
  savePromptTemplate,
  testPromptTemplate,
} from '@/api/admin';
import { ADMIN_PERMISSIONS } from '@/adminPermissions';
import { AdminApiError } from '@/api/http';
import { useAdminAuthStore } from '@/stores/auth';
import type { PromptTemplate, PromptTemplateModelStatus, PromptTemplateTestResult, PromptTemplateVersion } from '@/types';
import {
  buildPromptTemplateSavePayload,
  buildPromptTemplateTestSamples,
  createPromptTemplateForm,
  syncPromptTemplateForm,
} from './promptCenterState';

const templates = ref<PromptTemplate[]>([]);
const modelStatus = ref<PromptTemplateModelStatus[]>([]);
const versions = ref<PromptTemplateVersion[]>([]);
const auth = useAdminAuthStore();
const capability = ref('all');
const keyword = ref('');
const isLoading = ref(false);
const isSaving = ref(false);
const isTesting = ref(false);
const errorMessage = ref('');
const noticeMessage = ref('');
const drawerVisible = ref(false);
const activeTemplate = ref<PromptTemplate | null>(null);
const testPrompt = ref('');
const testResult = ref('');
const testResults = ref<PromptTemplateTestResult[]>([]);
const form = createPromptTemplateForm({
  id: '',
  capability: 'text',
  modelGroupId: '',
  templateType: 'prompt_optimize',
  name: '',
  content: '',
  enabled: true,
});
const canUpdateSettings = computed(() => auth.can(ADMIN_PERMISSIONS.settingsUpdate));
const modelSpecificEnabledCount = computed(() =>
  modelStatus.value.filter((item) => item.hasModelTemplate && item.modelTemplateEnabled).length,
);
const modelSpecificDisabledCount = computed(() =>
  modelStatus.value.filter((item) => item.hasModelTemplate && !item.modelTemplateEnabled).length,
);
const visibleModelStatus = computed(() => modelStatus.value.slice(0, 12));

const filteredTemplates = computed(() => {
  const clean = keyword.value.trim().toLowerCase();
  if (!clean) {
    return templates.value;
  }
  return templates.value.filter((template) =>
    `${template.name} ${template.content} ${template.templateType}`.toLowerCase().includes(clean),
  );
});

const drawerTitle = computed(() => activeTemplate.value?.name || '提示语模板');

function formatDate(value?: string) {
  if (!value) return '暂无记录';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '暂无记录' : date.toLocaleString('zh-CN');
}

function capabilityLabel(value: string) {
  if (value === 'text') return '文案';
  if (value === 'image') return '图片';
  if (value === 'video') return '视频';
  return value || '通用';
}

function friendlyError(error: unknown, fallback: string) {
  return error instanceof AdminApiError && error.message.trim() ? error.message.trim() : fallback;
}

async function loadTemplates() {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    templates.value = await fetchPromptTemplates(capability.value);
    modelStatus.value = await fetchPromptTemplateModelStatus(capability.value);
  } catch (error) {
    errorMessage.value = friendlyError(error, '提示语模板加载失败，请稍后重试。');
  } finally {
    isLoading.value = false;
  }
}


async function loadVersions(template: PromptTemplate) {
  versions.value = [];
  try {
    versions.value = await fetchPromptTemplateVersions(template.id);
  } catch (error) {
    errorMessage.value = friendlyError(error, '版本历史加载失败，请稍后重试。');
  }
}
function openDrawer(template: PromptTemplate) {
  activeTemplate.value = template;
  syncPromptTemplateForm(form, template);
  testPrompt.value = '';
  testResult.value = '';
  testResults.value = [];
  versions.value = [];
  void loadVersions(template);
  drawerVisible.value = true;
}

function replaceTemplate(template: PromptTemplate) {
  const index = templates.value.findIndex((item) => item.id === template.id);
  if (index >= 0) {
    templates.value.splice(index, 1, template);
  }
  activeTemplate.value = template;
}

async function saveTemplate() {
  if (!activeTemplate.value) return;
  if (!canUpdateSettings.value) {
    errorMessage.value = '当前账号没有保存提示语模板的权限。';
    return;
  }
  isSaving.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    replaceTemplate(await savePromptTemplate(
      activeTemplate.value.id,
      buildPromptTemplateSavePayload(activeTemplate.value, form),
    ));
    if (activeTemplate.value) {
      await loadVersions(activeTemplate.value);
    }
    modelStatus.value = await fetchPromptTemplateModelStatus(capability.value);
    noticeMessage.value = '提示语模板已保存。';
  } catch (error) {
    errorMessage.value = friendlyError(error, '提示语模板保存失败，请稍后重试。');
  } finally {
    isSaving.value = false;
  }
}

async function runTemplateTest() {
  isTesting.value = true;
  errorMessage.value = '';
  try {
    const samples = buildPromptTemplateTestSamples(testPrompt.value);
    const result = await testPromptTemplate({
      capability: form.capability,
      content: form.content,
      prompt: samples[0] || testPrompt.value,
      prompts: samples,
    });
    if (Array.isArray(result)) {
      testResults.value = result;
      testResult.value = '';
    } else {
      testResult.value = result;
      testResults.value = [];
    }
  } catch (error) {
    errorMessage.value = friendlyError(error, '模板测试失败，请稍后重试。');
  } finally {
    isTesting.value = false;
  }
}

onMounted(() => {
  void loadTemplates();
});
</script>

<style scoped>
.admin-content-page__meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 10px 0 14px;
}

.admin-content-page__meta-grid span {
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  padding: 10px 12px;
  color: var(--el-text-color-regular);
  background: var(--el-fill-color-lighter);
}

.admin-content-page__model-status-list,
.admin-content-page__sample-list,
.admin-content-page__version-list {
  display: grid;
  gap: 10px;
  margin: 12px 0 18px;
}

.admin-content-page__model-status-list article,
.admin-content-page__sample-list article,
.admin-content-page__version-list article {
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 12px;
  background: var(--el-bg-color-overlay);
}

.admin-content-page__model-status-list article {
  display: grid;
  gap: 10px;
}

.admin-content-page__model-status-list strong,
.admin-content-page__version-list strong {
  display: block;
  color: var(--el-text-color-primary);
}

.admin-content-page__model-status-list small,
.admin-content-page__sample-list small,
.admin-content-page__version-list small {
  color: var(--el-text-color-secondary);
}

.admin-content-page__status-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.admin-content-page__test-panel {
  display: grid;
  gap: 10px;
}

.admin-content-page__test-panel pre,
.admin-content-page__sample-list pre,
.admin-content-page__version-list pre {
  max-height: 180px;
  overflow: auto;
  margin: 8px 0 0;
  border-radius: 10px;
  padding: 10px;
  color: var(--el-text-color-primary);
  background: var(--el-fill-color-light);
  white-space: pre-wrap;
  word-break: break-word;
}

.admin-content-page__version-list header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.admin-content-page__version-list p {
  margin: 8px 0 0;
  color: var(--el-text-color-regular);
}
</style>

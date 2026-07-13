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

    <el-tabs v-model="activeTab" class="admin-prompt-center__tabs">
      <el-tab-pane label="优化模板" name="optimize">
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

    <section class="admin-prompt-center__overview">
      <article>
        <span>真实模板总数</span>
        <strong>{{ templates.length }}</strong>
        <small>{{ capability === 'all' ? '全部创作类型' : capabilityLabel(capability) }}</small>
      </article>
      <article>
        <span>已启用</span>
        <strong>{{ enabledTemplateCount }}</strong>
        <small>影响前台 AI 完善提示词</small>
      </article>
      <article>
        <span>模型启用</span>
        <strong>{{ modelPromptOptimizeEnabledCount }}</strong>
        <small>当前筛选下可用模型</small>
      </article>
      <article>
        <span>专属模板</span>
        <strong>{{ modelSpecificEnabledCount }}</strong>
        <small>模型级覆盖默认模板</small>
      </article>
    </section>

    <section class="admin-prompt-center__starter">
      <div class="admin-prompt-center__starter-head">
        <div>
          <h3>模板样例</h3>
          <p>样例仅用于预览，不计入真实模板总数；进入真实模板后再调整启用状态、内容和模型覆盖。</p>
        </div>
        <div class="admin-prompt-center__starter-signal">
          <span>运营校验</span>
          <strong>3 步闭环</strong>
          <small>预览 · 测试 · 覆盖</small>
        </div>
      </div>
      <div class="admin-prompt-center__roadmap">
        <article class="admin-prompt-center__roadmap-step">
          <span>01</span>
          <strong>选择创作类型</strong>
          <small>文案、图片、视频使用不同补全策略，先确认模板所属场景。</small>
        </article>
        <article class="admin-prompt-center__roadmap-step">
          <span>02</span>
          <strong>多样例渲染</strong>
          <small>用短提示词、参考图提示词和分镜提示词各测一次。</small>
        </article>
        <article class="admin-prompt-center__roadmap-step">
          <span>03</span>
          <strong>模型级覆盖</strong>
          <small>检查默认模板和专属模板，避免某个模型仍使用旧提示语。</small>
        </article>
      </div>
      <div class="admin-prompt-center__starter-grid">
        <button
          v-for="item in promptStarterExamples"
          :key="item.id"
          type="button"
          @click="openStarterExample(item)"
        >
          <span>{{ capabilityLabel(item.capability) }}</span>
          <strong>{{ item.name }}</strong>
          <small>{{ item.description }}</small>
        </button>
      </div>
    </section>

    <section v-if="filteredTemplates.length || isLoading" class="admin-content-page__table">
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
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDrawer(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
    <section v-else class="admin-prompt-center__empty">
      <strong>还没有匹配的提示语模板</strong>
      <p>当前筛选下真实模板 0 个；可以先查看上方模板样例，确认结构后切换筛选条件查看其它类型。</p>
      <div class="admin-prompt-center__empty-steps">
        <article>
          <span>01</span>
          <strong>确认模板类型</strong>
          <small>先选择文案、图片或视频，保证前台 AI 完善按钮使用正确模板。</small>
        </article>
        <article>
          <span>02</span>
          <strong>测试多样例</strong>
          <small>用短提示词、参考图提示词和复杂分镜各测一次渲染效果。</small>
        </article>
        <article>
          <span>03</span>
          <strong>检查模型启用</strong>
          <small>确认目标模型已启用 AI 文案优化，并检查是否存在专属模板。</small>
        </article>
      </div>
      <div>
        <el-button @click="keyword = ''; capability = 'all'; loadTemplates()">查看全部</el-button>
        <el-button type="primary" @click="openStarterExample(promptStarterExamples[0])">查看模板样例</el-button>
      </div>
    </section>

    <el-drawer v-model="drawerVisible" size="min(640px, 100vw)" :title="drawerTitle" destroy-on-close>
      <div v-if="activeTemplate" class="admin-content-page__drawer">
        <el-alert
          v-if="starterExampleActive"
          title="这是模板样例，可用于理解结构和测试渲染；请在真实模板中保存配置。"
          type="info"
          show-icon
          :closable="false"
        />
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
            <div class="admin-content-page__template-hint">
              <span>可用变量：<code>{{ promptVarLabel }}</code>（用户原始输入）、<code>{{ capabilityVarLabel }}</code>（创作类型）。</span>
              <el-button v-if="canUpdateSettings" size="small" @click="insertPromptVariable">插入 {{ promptVarLabel }}</el-button>
            </div>
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
          <el-button
            v-if="modelStatus.length > 12"
            link
            type="primary"
            @click="showAllModels = !showAllModels"
          >
            {{ showAllModels ? '收起' : `展开全部（共 ${modelStatus.length} 个）` }}
          </el-button>
          <strong>样例测试</strong>
          <el-input v-model="testPrompt" type="textarea" :rows="5" placeholder="每行一个测试样例" />
          <el-button :loading="isTesting" @click="runTemplateTest">测试渲染</el-button>
          <div v-if="testResults.length" class="admin-content-page__sample-list">
            <article v-for="item in testResults" :key="item.prompt">
              <small>{{ item.prompt }}</small>
              <el-button size="small" @click="copyRendered(item.rendered)">复制结果</el-button>
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
                <div class="admin-content-page__version-actions">
                  <small>{{ formatDate(item.createdAt) }}</small>
                  <el-button
                    v-if="canUpdateSettings && !starterExampleActive && activeTemplate"
                    size="small"
                    :loading="restoringVersion === item.version"
                    @click="restoreVersion(item)"
                  >
                    恢复此版本
                  </el-button>
                </div>
              </header>
              <p>{{ item.name }}</p>
              <pre>{{ item.content }}</pre>
            </article>
          </div>
        </section>

        <div class="admin-content-page__drawer-actions">
          <el-button @click="drawerVisible = false">关闭</el-button>
          <el-button
            v-if="canUpdateSettings && !starterExampleActive"
            type="primary"
            :loading="isSaving"
            @click="saveTemplate"
          >
            保存模板
          </el-button>
        </div>
      </div>
    </el-drawer>
      </el-tab-pane>
      <el-tab-pane label="图片场景库" name="scene-library">
        <PromptSceneLibraryPanel />
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { ElMessageBox } from 'element-plus';

import {
  fetchPromptTemplateModelStatus,
  fetchPromptTemplates,
  fetchPromptTemplateVersions,
  restorePromptTemplateVersion,
  savePromptTemplate,
  testPromptTemplate,
} from '@/api/admin';
import { copyText } from '@/utils/clipboard';
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
import PromptSceneLibraryPanel from './PromptSceneLibraryPanel.vue';

const templates = ref<PromptTemplate[]>([]);
const modelStatus = ref<PromptTemplateModelStatus[]>([]);
const versions = ref<PromptTemplateVersion[]>([]);
const auth = useAdminAuthStore();
const activeTab = ref('optimize');
const capability = ref('all');
const keyword = ref('');
const isLoading = ref(false);
const isSaving = ref(false);
const isTesting = ref(false);
const errorMessage = ref('');
const noticeMessage = ref('');
const drawerVisible = ref(false);
const activeTemplate = ref<PromptTemplate | null>(null);
const starterExampleActive = ref(false);
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
const enabledTemplateCount = computed(() => templates.value.filter((template) => template.enabled).length);
const modelPromptOptimizeEnabledCount = computed(() =>
  modelStatus.value.filter((item) => item.promptOptimizeEnabled).length,
);
const showAllModels = ref(false);
const visibleModelStatus = computed(() =>
  showAllModels.value ? modelStatus.value : modelStatus.value.slice(0, 12),
);
const restoringVersion = ref<number | null>(null);
const promptVarLabel = '{{prompt}}';
const capabilityVarLabel = '{{capability}}';
const promptStarterExamples: Array<PromptTemplate & { description: string }> = [
  {
    id: 'starter-text-copy',
    capability: 'text',
    modelGroupId: '',
    templateType: 'prompt_optimize',
    name: '文案完善模板',
    description: '把一句简短需求整理成目标、受众、语气、输出格式。',
    content: '请将用户原始需求改写为更清晰的文案创作指令，补充目标受众、语气、结构、限制条件和交付格式。\n\n原始需求：{{prompt}}',
    enabled: true,
  },
  {
    id: 'starter-image-prompt',
    capability: 'image',
    modelGroupId: '',
    templateType: 'prompt_optimize',
    name: '图片提示词模板',
    description: '补齐主体、构图、光影、材质、参考图约束和负面描述。',
    content: '请把用户需求扩写为图片生成提示词，明确主体、场景、构图、光影、材质、风格、画幅和参考图一致性。\n\n原始需求：{{prompt}}',
    enabled: true,
  },
  {
    id: 'starter-video-shot',
    capability: 'video',
    modelGroupId: '',
    templateType: 'prompt_optimize',
    name: '视频分镜模板',
    description: '把视频想法拆成镜头运动、时间节奏、首尾帧和负面提示。',
    content: '请将用户需求改写为视频生成提示词，包含时间节奏、主体动作、镜头运动、画面风格、首尾帧约束和负面提示词。\n\n原始需求：{{prompt}}',
    enabled: true,
  },
];

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
  starterExampleActive.value = false;
  activeTemplate.value = template;
  syncPromptTemplateForm(form, template);
  testPrompt.value = '';
  testResult.value = '';
  testResults.value = [];
  versions.value = [];
  void loadVersions(template);
  drawerVisible.value = true;
}

function openStarterExample(template: PromptTemplate) {
  starterExampleActive.value = true;
  activeTemplate.value = template;
  syncPromptTemplateForm(form, template);
  testPrompt.value = '生成小米 SU7 变形金刚，科技感，真实质感';
  testResult.value = '';
  testResults.value = [];
  versions.value = [];
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
  if (form.templateType === 'prompt_optimize' && !form.content.includes('{{prompt}}')) {
    errorMessage.value = '模板内容需要包含 {{prompt}} 占位符，否则用户输入不会被引用。';
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

async function restoreVersion(version: PromptTemplateVersion) {
  if (!activeTemplate.value) return;
  try {
    await ElMessageBox.confirm(
      `确认将模板恢复到 v${version.version}？会生成一条新的版本记录。`,
      '恢复历史版本',
      { type: 'warning', confirmButtonText: '确认恢复', cancelButtonText: '取消' },
    );
  } catch {
    return;
  }
  restoringVersion.value = version.version;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    const restored = await restorePromptTemplateVersion(activeTemplate.value.id, version.version);
    replaceTemplate(restored);
    syncPromptTemplateForm(form, restored);
    await loadVersions(restored);
    modelStatus.value = await fetchPromptTemplateModelStatus(capability.value);
    noticeMessage.value = `已恢复到 v${version.version}。`;
  } catch (error) {
    errorMessage.value = friendlyError(error, '版本恢复失败，请稍后重试。');
  } finally {
    restoringVersion.value = null;
  }
}

function insertPromptVariable() {
  if (!form.content.includes('{{prompt}}')) {
    form.content = `${form.content}${form.content ? '\n' : ''}{{prompt}}`;
  }
}

async function copyRendered(text: string) {
  const ok = await copyText(text);
  if (ok) {
    noticeMessage.value = '已复制渲染结果。';
  } else {
    errorMessage.value = '复制失败，请手动复制。';
  }
}

onMounted(() => {
  void loadTemplates();
});
</script>

<style scoped>
.admin-prompt-center__overview {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.admin-prompt-center__overview article {
  display: grid;
  gap: 4px;
  padding: 14px;
  color: var(--el-text-color-regular);
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--el-color-primary) 8%, transparent), transparent 58%),
    var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-light);
  border-radius: 14px;
}

.admin-prompt-center__overview span,
.admin-prompt-center__overview small {
  color: var(--el-text-color-secondary);
}

.admin-prompt-center__overview strong {
  color: var(--el-text-color-primary);
  font-size: 24px;
  line-height: 1.1;
}

.admin-prompt-center__starter,
.admin-prompt-center__empty {
  margin-top: 14px;
  padding: 16px;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-light);
  border-radius: 16px;
}

.admin-prompt-center__starter-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.admin-prompt-center__starter-head h3,
.admin-prompt-center__starter-head p,
.admin-prompt-center__empty strong,
.admin-prompt-center__empty p {
  margin: 0;
}

.admin-prompt-center__starter-head h3,
.admin-prompt-center__empty strong {
  color: var(--el-text-color-primary);
}

.admin-prompt-center__starter-head p,
.admin-prompt-center__empty p {
  color: var(--el-text-color-secondary);
}

.admin-prompt-center__starter-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.admin-prompt-center__starter-grid button {
  display: grid;
  gap: 7px;
  min-height: 124px;
  padding: 14px;
  text-align: left;
  color: var(--el-text-color-regular);
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-light);
  border-radius: 14px;
  cursor: pointer;
  transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}

.admin-prompt-center__starter-grid button:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 12px 28px rgb(15 111 198 / 12%);
  transform: translateY(-1px);
}

.admin-prompt-center__starter-grid span {
  color: var(--el-color-primary);
  font-size: 12px;
  font-weight: 700;
}

.admin-prompt-center__starter-grid strong {
  color: var(--el-text-color-primary);
  font-size: 15px;
}

.admin-prompt-center__starter-grid small {
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

.admin-prompt-center__empty {
  display: grid;
  justify-items: start;
  gap: 12px;
}

.admin-prompt-center__empty div {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

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

@media (max-width: 980px) {
  .admin-prompt-center__overview,
  .admin-prompt-center__starter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .admin-prompt-center__overview,
  .admin-prompt-center__starter-grid {
    grid-template-columns: 1fr;
  }

  .admin-prompt-center__starter-head {
    display: grid;
  }
}
</style>

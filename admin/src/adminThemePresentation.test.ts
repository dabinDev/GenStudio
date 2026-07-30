import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const layoutVue = () => readFileSync(resolve(process.cwd(), 'src/layouts/AdminLayout.vue'), 'utf8');
const imageViewerVue = () => readFileSync(resolve(process.cwd(), 'src/components/AdminImageViewer.vue'), 'utf8');
const promptCenterVue = () => readFileSync(resolve(process.cwd(), 'src/views/PromptCenterView.vue'), 'utf8');
const promptSceneLibraryVue = () => readFileSync(resolve(process.cwd(), 'src/views/PromptSceneLibraryPanel.vue'), 'utf8');
const recordsVue = () => readFileSync(resolve(process.cwd(), 'src/views/RecordsView.vue'), 'utf8');
const modelCenterVue = () => readFileSync(resolve(process.cwd(), 'src/views/ModelCenterView.vue'), 'utf8');
const auditLogsVue = () => readFileSync(resolve(process.cwd(), 'src/views/AuditLogsView.vue'), 'utf8');
const viteConfig = () => readFileSync(resolve(process.cwd(), 'vite.config.ts'), 'utf8');
const mainTs = () => readFileSync(resolve(process.cwd(), 'src/main.ts'), 'utf8');
const stylesCss = () => readFileSync(resolve(process.cwd(), 'src/styles/global.css'), 'utf8').replace(/\r\n/g, '\n');
const packageJson = () => readFileSync(resolve(process.cwd(), 'package.json'), 'utf8');

const mojibakeFragments = [
  '绠＄悊',
  '妯″瀷',
  '鍒涗綔',
  '璁板綍',
  '鐢ㄦ埛',
  '鎿嶄綔',
  '鐘舵€',
  '锛',
  '銆',
  '??',
  '�',
];

function expectNoMojibake(source: string) {
  const visibleTemplate = source.split('</template>')[0] || source;
  for (const fragment of mojibakeFragments) {
    expect(visibleTemplate).not.toContain(fragment);
  }
}

function stubLocalStorage(initial: Record<string, string> = {}) {
  const store = new Map(Object.entries(initial));
  const storage = {
    getItem: vi.fn((key: string) => store.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store.set(key, value);
    }),
    removeItem: vi.fn((key: string) => {
      store.delete(key);
    }),
    clear: vi.fn(() => {
      store.clear();
    }),
  };
  vi.stubGlobal('localStorage', storage);
  return storage;
}

describe('admin shared theme store', () => {
  beforeEach(() => {
    vi.resetModules();
    setActivePinia(createPinia());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('initializes from the front-end shared theme preference', async () => {
    stubLocalStorage({ 'genstudio-theme': 'dark', 'genstudio-admin-theme': 'light' });
    const { useAdminThemeStore } = await import('./stores/theme');

    const theme = useAdminThemeStore();

    expect(theme.theme).toBe('dark');
  });

  it('prefers the admin theme URL parameter for cross-origin local entry', async () => {
    stubLocalStorage({ 'genstudio-theme': 'light', 'genstudio-admin-theme': 'light' });
    const { readAdminThemeQuery } = await import('./stores/theme');

    expect(readAdminThemeQuery('?theme=dark')).toBe('dark');
    expect(readAdminThemeQuery('?theme=system')).toBeNull();
  });

  it('persists admin theme changes to the shared and legacy keys', async () => {
    const storage = stubLocalStorage({ 'genstudio-theme': 'light' });
    const { useAdminThemeStore } = await import('./stores/theme');

    const theme = useAdminThemeStore();
    theme.toggle();

    expect(storage.setItem).toHaveBeenCalledWith('genstudio-theme', 'dark');
    expect(storage.setItem).toHaveBeenCalledWith('genstudio-admin-theme', 'dark');
  });
});

describe('admin theme presentation', () => {
  it('keeps high-traffic admin pages free of mojibake labels', () => {
    const pageSources = [
      layoutVue(),
      modelCenterVue(),
      recordsVue(),
      promptCenterVue(),
    ];

    for (const source of pageSources) {
      expectNoMojibake(source);
    }
  });

  it('keeps the admin console static and free of decorative ambient effects', () => {
    const layout = layoutVue();
    const styles = stylesCss();
    const manifest = packageJson();
    const markerIndex = styles.indexOf('Admin NewUI detail pass v1');

    expect(manifest).not.toContain('"gsap"');
    expect(layout).not.toContain("import { gsap } from 'gsap'");
    expect(layout).toContain('safeIdentityLabel');
    expect(layout).toContain("auth.user?.email || '管理员'");
    expect(layout).not.toContain("auth.user?.displayName || auth.user?.nickname || auth.user?.email || '管理员'");
    expect(layout).not.toContain('setupAdminAmbientAnimation');
    expect(layout).not.toContain('teardownAdminAmbientAnimation');
    expect(layout).not.toContain('admin-ambient');
    expect(layout).not.toContain('admin-ambient-drift');
    expect(layout).not.toContain('admin-ambient-line');

    expect(markerIndex).toBeGreaterThan(-1);
    const finalStyles = styles.slice(markerIndex);
    expect(finalStyles).toContain('.admin-layout {');
    expect(finalStyles).toContain('background: var(--admin-color-bg) !important');
    expect(finalStyles).not.toContain('.admin-ambient');
    expect(finalStyles).not.toContain('radial-gradient');
  });

  it('keeps Element Plus controls readable in both admin themes', () => {
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin Element Plus theme contrast v3');

    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf("[data-theme='light'] .el-button--primary:not(.is-link):not(.is-text)", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('--el-button-bg-color: #0891b2', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='light'] .el-button--primary.is-disabled", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='light'] .el-tag.el-tag--success", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='dark'] .admin-menu .el-menu-item", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='dark'] .el-button--primary:not(.is-link):not(.is-text)", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('--el-button-bg-color: #17a89f', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('--el-switch-on-color: #17a89f', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='dark'] .el-switch.is-checked .el-switch__core", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='dark'] .el-table", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='dark'] .el-card", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='dark'] .el-form-item__label", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='dark'] .el-tabs__item", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('--el-table-tr-bg-color: #172033', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('keeps audit filters inside a responsive contained toolbar', () => {
    const view = auditLogsVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin audit filter containment v1');

    expect(view).toContain('admin-content-page__filters--audit');
    expect(view).toContain('admin-content-page__audit-date-range');
    expect(view).toContain('admin-content-page__audit-submit');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-content-page__filters--audit', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('grid-template-columns: repeat(4, minmax(0, 1fr))', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-content-page__audit-date-range', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('grid-column: span 2', styles.indexOf('.admin-content-page__audit-date-range', markerIndex))).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('min-width: 0', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('@media (max-width: 1180px)', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('presents multi-image creation records as horizontal galleries', () => {
    const view = recordsVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin records multi-image gallery v4');

    expect(view).toContain('imageAssets(record)');
    expect(view).toContain('admin-content-page__image-strip');
    expect(view).toContain('admin-content-page__image-count');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-content-page__image-strip', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('overflow-x: auto', styles.indexOf('.admin-content-page__image-strip', markerIndex))).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-content-page__asset-strip', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('uses a responsive record gallery instead of a single masonry column for image records', () => {
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin records responsive image gallery v5');

    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-content-page__waterfall', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('display: grid', styles.indexOf('.admin-content-page__waterfall', markerIndex))).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('column-count: initial', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-content-page__image-card', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('display: grid', styles.indexOf('.admin-content-page__image-card', markerIndex))).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('aspect-ratio: 16 / 10', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('opens admin record images in a zoomable queue viewer', () => {
    const view = recordsVue();
    const viewer = imageViewerVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin image viewer overlay v1');

    expect(view).toContain('AdminImageViewer');
    expect(view).toContain('openImageViewer');
    expect(view).toContain('recordImageAssets(activeRecord)');
    expect(view).toContain('imageViewerState');
    expect(view).not.toContain('v-if="asset.type === \'image\'" :src="asset.thumbnailUrl || asset.url"');

    expect(viewer).toContain('@wheel.prevent="handleWheel"');
    expect(viewer).toContain('@pointerdown="handlePointerDown"');
    expect(viewer).toContain('showPreviousImage');
    expect(viewer).toContain('showNextImage');
    expect(viewer).toContain('downloadActiveImage');
    expect(viewer).toContain('transform: viewerTransform');

    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-image-viewer', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('position: fixed', styles.indexOf('.admin-image-viewer', markerIndex))).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-image-viewer__toolbar', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-image-viewer__nav', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('shows a thumbnail rail inside the admin image viewer for multi-image queues', () => {
    const viewer = imageViewerVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin image viewer thumbnail rail v2');

    expect(viewer).toContain('admin-image-viewer__thumbs');
    expect(viewer).toContain('admin-image-viewer__thumb');
    expect(viewer).toContain('setActiveIndex(index)');
    expect(viewer).toContain(':aria-current="index === activeIndex"');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-image-viewer__thumbs', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('position: fixed', styles.indexOf('.admin-image-viewer__thumbs', markerIndex))).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('overflow-x: auto', styles.indexOf('.admin-image-viewer__thumbs', markerIndex))).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-image-viewer__thumb[aria-current=\'true\']', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('presents the admin image viewer as a full-screen command surface', () => {
    const viewer = imageViewerVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin image viewer command surface v3');

    expect(viewer).toContain('admin-image-viewer__action-label');
    expect(viewer).toContain('admin-image-viewer__shortcut');
    expect(viewer).toContain('滚轮缩放');
    expect(viewer).toContain('拖动查看细节');
    expect(viewer).toContain('← / → 切换图片');

    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-image-viewer__shortcut', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-image-viewer__actions button', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('min-width: 76px', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('backdrop-filter: blur(24px)', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('adds a refined admin shell polish layer for light and dark mode', () => {
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin console product polish v4');

    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-sidebar', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-topbar', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-dashboard__header', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('[data-theme=\'dark\'] .admin-sidebar', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('linear-gradient(180deg', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('box-shadow: 0 24px 70px', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('presents prompt templates as an admin operating workspace with examples', () => {
    const view = promptCenterVue();

    expect(view).toContain('admin-prompt-center__overview');
    expect(view).toContain('admin-prompt-center__starter-grid');
    expect(view).toContain('promptStarterExamples');
    expect(view).toContain('filteredTemplates.length');
    expect(view).toContain('openStarterExample');
    expect(view).toContain('模板样例');
    expect(view).toContain('模型启用');
  });

  it('renders creation records with capability-specific preview cells', () => {
    const view = recordsVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin records typed preview cells v6');

    expect(view).toContain('admin-content-page__record-cell');
    expect(view).toContain('recordPreviewResponse(row)');
    expect(view).toContain('videoAssets(row)');
    expect(view).toContain('imageAssets(row).slice(0, 4)');
    expect(view).toContain('admin-content-page__record-media-strip');
    expect(view).toContain('admin-content-page__record-task');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-content-page__record-cell', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-content-page__record-media-strip', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-content-page__record-task', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('keeps record filters focused with a collapsible advanced section', () => {
    const view = recordsVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin records focused filters v7');

    expect(view).toContain('showAdvancedFilters');
    expect(view).toContain('admin-content-page__quick-filters');
    expect(view).toContain('admin-content-page__advanced-filters');
    expect(view).toContain('基础筛选');
    expect(view).toContain('高级筛选');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-content-page__quick-filters', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-content-page__advanced-filters', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('grid-template-columns: repeat(auto-fit', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('presents dashboard failures as actionable record links', () => {
    const view = readFileSync(resolve(process.cwd(), 'src/views/DashboardView.vue'), 'utf8');
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin dashboard actionable insight cards v5');

    expect(view).toContain('admin-dashboard__action-card');
    expect(view).toContain('查看失败记录');
    expect(view).toContain('查看慢调用');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-dashboard__action-card', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-dashboard__action-pill', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('shows model assets with source badges and compact identity rows', () => {
    const view = modelCenterVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin model asset list polish v6');

    expect(view).toContain('admin-model-center__identity');
    expect(view).toContain('admin-model-center__source-badges');
    expect(view).toContain('capabilityLabel(row.capability)');
    expect(view).toContain('row.adapter');
    expect(view).toContain('row.isPublic ?');
    expect(view).toContain("source === 'private_model'");
    expect(view).toContain("source === 'capability_default'");
    expect(view).toContain('私有模型');
    expect(view).toContain('能力默认');
    expect(view).toContain('模型定价');
    expect(view).not.toContain("return source || '默认'");
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-model-center__identity', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-model-center__source-badges', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('turns the prompt empty state into a guided admin setup surface', () => {
    const view = promptCenterVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin prompt empty setup surface v8');

    expect(view).toContain('admin-prompt-center__empty-steps');
    expect(view).toContain('确认模板类型');
    expect(view).toContain('测试多样例');
    expect(view).toContain('检查模型启用');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-prompt-center__empty-steps', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('localizes admin controls and removes generic select placeholders', () => {
    const main = readFileSync(resolve(process.cwd(), 'src/main.ts'), 'utf8');
    const records = recordsVue();
    const audit = readFileSync(resolve(process.cwd(), 'src/views/AuditLogsView.vue'), 'utf8');
    const users = readFileSync(resolve(process.cwd(), 'src/views/UserCreditsView.vue'), 'utf8');
    const system = readFileSync(resolve(process.cwd(), 'src/views/SystemSettingsView.vue'), 'utf8');
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin localized operations polish v9');

    expect(main).toContain("element-plus/es/locale/lang/zh-cn");
    expect(main).toContain('locale: zhCn');
    expect(records).toContain('选择常用筛选');
    expect(records).toContain('导出筛选结果');
    expect(audit).toContain('选择对象类型');
    expect(audit).toContain('选择执行状态');
    expect(audit).toContain('选择风险等级');
    expect(audit).toContain('导出审计日志');
    expect(audit).toContain('statusLabel(row.status)');
    expect(users).toContain('导出用户列表');
    expect(system).toContain('个人私有模型不扣积分');
    expect(`${records}\n${audit}\n${users}`).not.toContain('导出当前列表');
    expect(system).not.toContain('用户自定义模型不扣积分');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-content-page__filters .el-select', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-content-page__actions .el-button', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('adds an editorial polish layer for admin model and record lists', () => {
    const records = recordsVue();
    const modelCenter = modelCenterVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin list editorial polish v10');

    expect(modelCenter).toContain('admin-model-center__asset-card');
    expect(modelCenter).toContain('admin-model-center__price-pill');
    expect(records).toContain('admin-content-page__record-summary');
    expect(records).toContain('admin-content-page__record-meta');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-model-center__asset-card', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-model-center__price-pill', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-content-page__record-summary', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-content-page__record-meta', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('box-shadow: inset 4px 0 0', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('presents creation records as scan-friendly operation cards', () => {
    const records = recordsVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin records operation stream polish v11');

    expect(records).toContain('admin-content-page__record-flow');
    expect(records).toContain('admin-content-page__record-context');
    expect(records).toContain('admin-content-page__record-open');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-content-page__record-flow', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-content-page__record-context', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-content-page__record-open', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('grid-template-columns: minmax(280px, 1.05fr) minmax(320px, 1.2fr) minmax(180px, 0.58fr) 84px', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('min-height: 112px', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('contains overlong record content without distorting creation record layouts', () => {
    const records = recordsVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin records long content containment v13');

    expect(records).toContain('admin-content-page__record-prompt');
    expect(records).toContain('admin-content-page__image-card-prompt');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-content-page__record-prompt', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-content-page__image-card-prompt', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('-webkit-line-clamp: 5', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('overflow-wrap: anywhere', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('word-break: break-word', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('max-height: calc(1.45em * 5)', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('minmax(0, 1fr)', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-content-page__record-cell .admin-content-page__record-prompt', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('repeat(auto-fill, minmax(280px, min(360px, 100%)))', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('justify-content: start', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('turns model rows into operational asset cards with clear status chips', () => {
    const modelCenter = modelCenterVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin model operational asset cards v12');

    expect(modelCenter).toContain('admin-model-center__asset-shell');
    expect(modelCenter).toContain('admin-model-center__empty-asset');
    expect(modelCenter).toContain('admin-model-center__visibility-chip');
    expect(modelCenter).toContain('admin-model-center__asset-meta');
    expect(modelCenter).toContain('admin-model-center__action-stack');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-model-center__asset-shell', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-model-center__empty-asset', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('grid-template-columns: minmax(260px, 1.1fr) repeat(3, minmax(120px, 0.42fr)) minmax(116px, 0.38fr)', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-model-center__visibility-chip', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-model-center__action-stack', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('gives prompt templates a guided operations roadmap instead of a plain empty block', () => {
    const promptCenter = promptCenterVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin prompt operations roadmap v12');

    expect(promptCenter).toContain('admin-prompt-center__roadmap');
    expect(promptCenter).toContain('admin-prompt-center__roadmap-step');
    expect(promptCenter).toContain('admin-prompt-center__starter-signal');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-prompt-center__roadmap', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('grid-template-columns: repeat(3, minmax(0, 1fr))', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-prompt-center__starter-signal', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('contains the admin shell and Element Plus tables on narrow screens', () => {
    const layout = layoutVue();
    const users = readFileSync(resolve(process.cwd(), 'src/views/UserCreditsView.vue'), 'utf8');
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin responsive shell containment v16');

    expect(layout).toContain('admin-mobile-nav');
    expect(users).toContain('admin-user-credits__table-scroll');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-layout', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('overflow-x: hidden', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-mobile-nav', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('@media (max-width: 900px)', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('grid-template-columns: minmax(0, 1fr) !important', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-content-page__table', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-user-credits__table-scroll', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('overflow-x: auto !important', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-ambient', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('overflow: hidden !important', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('adds mobile scroll affordances to admin navigation and wide data tables', () => {
    const layout = layoutVue();
    const users = readFileSync(resolve(process.cwd(), 'src/views/UserCreditsView.vue'), 'utf8');
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin mobile scroll affordances v17');

    expect(layout).toContain('admin-mobile-nav__track');
    expect(layout).toContain(":aria-current=\"activePath === item.path ? 'page' : undefined\"");
    expect(layout).toContain('ref="mobileNavTrackRef"');
    expect(layout).toContain('scrollActiveMobileNavIntoView');
    expect(layout).toContain('track.scrollTo({');
    expect(layout).toContain('activeItem.offsetLeft + activeItem.offsetWidth / 2 - track.clientWidth / 2');
    expect(layout).toContain('track.scrollLeft = targetLeft');
    expect(layout).toContain('requestAnimationFrame(alignActiveMobileNav)');
    expect(layout).toContain('window.setTimeout(alignActiveMobileNav');
    expect(layout).toContain('watch(() => menuItems.value.length');
    expect(users).toContain('data-scroll-hint=');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-mobile-nav::before', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-mobile-nav::after', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('pointer-events: none', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-mobile-nav__item.is-active::after', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-user-credits__table-scroll::after', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('content: attr(data-scroll-hint)', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('keeps asset synchronization primary and orphan cleanup mobile friendly', () => {
    const system = readFileSync(resolve(process.cwd(), 'src/views/SystemSettingsView.vue'), 'utf8');
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin asset cleanup mobile polish v18');

    expect(system).toContain('<strong>图片存储与同步</strong>');
    expect(system).toContain('<strong>孤儿缓存清理</strong>');
    expect(system.indexOf('图片存储与同步')).toBeLessThan(system.indexOf('孤儿缓存清理'));
    expect(system).toContain('默认保留 ${assetCleanupForm.defaultRetentionDays || 7} 天');
    expect(system).toContain('不删除数据库创作记录');
    expect(system).toContain('admin-asset-cleanup-card__safe-actions');
    expect(system).toContain('admin-asset-cleanup-card__danger-actions');
    expect(system).toContain('admin-asset-cleanup-card__path-col');
    expect(system).not.toContain('缓存照片');
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-asset-cleanup-card__form .el-input-number', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-asset-cleanup-card__danger-actions', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-asset-cleanup-card__path-col', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('grid-template-columns: repeat(2, minmax(0, 1fr))', markerIndex)).toBeGreaterThan(markerIndex);
  });

  it('runs manual asset cleanup from the confirmed preview snapshot', () => {
    const system = readFileSync(resolve(process.cwd(), 'src/views/SystemSettingsView.vue'), 'utf8');

    expect(system).toContain('assetCleanupPreviewRetentionDays');
    expect(system).toContain('assetCleanupSummary.value = null');
    expect(system).toContain('runAssetCleanup({ retentionDays: assetCleanupPreviewRetentionDays.value })');
    expect(system).not.toContain('runAssetCleanup({ retentionDays: assetCleanupForm.retentionDays })');
  });

  it('keeps heavy admin runtime libraries split away from the entry chunk', () => {
    const dashboard = readFileSync(resolve(process.cwd(), 'src/views/DashboardView.vue'), 'utf8');
    const config = viteConfig();
    const main = mainTs();

    expect(dashboard).not.toContain("import * as echarts from 'echarts'");
    expect(dashboard).toContain("import('echarts/core')");
    expect(dashboard).toContain("import('echarts/lib/chart/bar')");
    expect(dashboard).toContain("import('echarts/lib/component/legend')");
    expect(dashboard).toContain("import('echarts/lib/component/dataZoom')");
    expect(dashboard).not.toContain("import('echarts/charts')");
    expect(config).toContain('manualChunks');
    expect(config).toContain("'admin-ui'");
    expect(config).toContain("'admin-charts'");
    expect(main).not.toContain("import ElementPlus from 'element-plus'");
    expect(main).toContain("element-plus/es/components/button/index.mjs");
    expect(main).toContain("element-plus/es/components/pagination/index.mjs");
    expect(main).toContain('app.use(ElPagination)');
  });

  it('shows prompt starter examples as examples instead of mixing them into template counts', () => {
    const promptCenter = promptCenterVue();

    expect(promptCenter).toContain('真实模板总数');
    expect(promptCenter).toContain('样例仅用于预览');
    expect(promptCenter).toContain('真实模板 0 个');
  });

  it('adds an operational image scene prompt library to the prompt center', () => {
    const promptCenter = promptCenterVue();
    const sceneLibrary = promptSceneLibraryVue();

    expect(promptCenter).toContain('PromptSceneLibraryPanel');
    expect(promptCenter).toContain('图片场景库');
    expect(sceneLibrary).toContain('图片场景提示词库');
    expect(sceneLibrary).toContain('导入 Yuque JS');
    expect(sceneLibrary).toContain('批量启用');
    expect(sceneLibrary).toContain('批量停用');
    expect(sceneLibrary).toContain('曝光');
    expect(sceneLibrary).toContain('点击');
    expect(sceneLibrary).toContain('GPT 5.5');
    expect(sceneLibrary).toContain('admin-prompt-scene-library__table-wrap');
    expect(sceneLibrary).toContain('grid-template-columns: repeat(2, minmax(0, 1fr))');
    expect(sceneLibrary).toContain('overflow-x: auto');
  });

  it('stabilizes admin headers, filters, tables, media, and overlays in the final cascade', () => {
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin NewUI detail pass v1');
    const finalStyles = styles.slice(markerIndex);

    expect(markerIndex).toBeGreaterThan(-1);
    expect(finalStyles).toContain('.admin-content {');
    expect(finalStyles).toContain('padding: clamp(16px, 2vw, 28px) !important');
    expect(finalStyles).toContain('.admin-content-page__header,');
    expect(finalStyles).toContain('min-height: 72px !important');
    expect(finalStyles).toContain('.admin-content-page__filters,');
    expect(finalStyles).toContain('min-height: 52px !important');
    expect(finalStyles).toContain('.admin-content-page__table > .el-table,');
    expect(finalStyles).toContain('min-width: 760px !important');
    expect(finalStyles).toContain('.el-table .el-table__row > td.el-table__cell');
    expect(finalStyles).toContain('height: 56px !important');
    expect(finalStyles).toContain('.admin-content-page__record-media-strip img,');
    expect(finalStyles).toContain('aspect-ratio: 1 !important');
    expect(finalStyles).toContain('.el-dialog__footer,');
    expect(finalStyles).toContain('justify-content: flex-end !important');
    expect(finalStyles).toContain('overflow-wrap: anywhere !important');
  });

  it('keeps admin focus, motion, safe areas, and narrow data views usable', () => {
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin NewUI detail pass v1');
    const finalStyles = styles.slice(markerIndex);

    expect(markerIndex).toBeGreaterThan(-1);
    expect(finalStyles).toContain(':where(button, a, input, textarea, select):focus-visible');
    expect(finalStyles).toContain('@media (prefers-reduced-motion: reduce)');
    expect(finalStyles).toContain('@media screen and (max-width: 900px)');
    expect(finalStyles).toContain('overflow-x: auto !important');
    expect(finalStyles).toContain('padding-bottom: max(16px, env(safe-area-inset-bottom, 0px)) !important');
    expect(finalStyles).not.toMatch(/letter-spacing:\s*-/);
  });
});

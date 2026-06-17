import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const layoutVue = () => readFileSync(resolve(process.cwd(), 'src/layouts/AdminLayout.vue'), 'utf8');
const imageViewerVue = () => readFileSync(resolve(process.cwd(), 'src/components/AdminImageViewer.vue'), 'utf8');
const recordsVue = () => readFileSync(resolve(process.cwd(), 'src/views/RecordsView.vue'), 'utf8');
const stylesCss = () => readFileSync(resolve(process.cwd(), 'src/styles/global.css'), 'utf8');
const packageJson = () => readFileSync(resolve(process.cwd(), 'package.json'), 'utf8');

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
  it('renders a theme-specific GSAP ambient layer behind the admin console', () => {
    const layout = layoutVue();
    const styles = stylesCss();
    const manifest = packageJson();
    const markerIndex = styles.indexOf('Admin console theme ambient background v2');

    expect(manifest).toContain('"gsap"');
    expect(layout).toContain("import { gsap } from 'gsap'");
    expect(layout).toContain('safeIdentityLabel');
    expect(layout).toContain("auth.user?.email || '管理员'");
    expect(layout).not.toContain("auth.user?.displayName || auth.user?.nickname || auth.user?.email || '管理员'");
    expect(layout).toContain('setupAdminAmbientAnimation');
    expect(layout).toContain('teardownAdminAmbientAnimation');
    expect(layout).toContain('onUnmounted(() =>');
    expect(layout).toContain('teardownAdminAmbientAnimation();');
    expect(layout).toContain('watch(() => theme.theme, () => setupAdminAmbientAnimation());');
    expect(layout).toContain('admin-ambient');
    expect(layout).toContain('admin-ambient-drift');
    expect(layout).toContain('admin-ambient-line');

    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf('.admin-layout::before', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('animation: none', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('pointer-events: none', styles.indexOf('.admin-ambient', markerIndex))).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('z-index: 0', styles.indexOf('.admin-ambient', markerIndex))).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('.admin-sidebar,\n.admin-main', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('z-index: 1', styles.indexOf('.admin-sidebar,\n.admin-main', markerIndex))).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('[data-theme=\'light\'] .admin-ambient', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('[data-theme=\'dark\'] .admin-ambient', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('#f7fafc', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('#0d1624', markerIndex)).toBeGreaterThan(markerIndex);

    const lightThemeIndex = styles.indexOf("[data-theme='light'] {", markerIndex);
    const darkThemeIndex = styles.indexOf("[data-theme='dark'] {", markerIndex);
    const lightAmbientBlock = styles.slice(lightThemeIndex, darkThemeIndex);
    expect(lightAmbientBlock).not.toContain('46px 46px');
    expect(lightAmbientBlock).not.toContain('#101827');
  });

  it('keeps Element Plus controls readable in both admin themes', () => {
    const styles = stylesCss();
    const markerIndex = styles.indexOf('Admin Element Plus theme contrast v3');

    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf("[data-theme='light'] .el-button--primary:not(.is-link):not(.is-text)", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('--el-button-bg-color: #0f6fc6', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='light'] .el-button--primary.is-disabled", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='light'] .el-tag.el-tag--success", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='dark'] .admin-menu .el-menu-item", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='dark'] .el-button--primary:not(.is-link):not(.is-text)", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('--el-button-bg-color: #1769bd', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('--el-switch-on-color: #1769bd', markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='dark'] .el-switch.is-checked .el-switch__core", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='dark'] .el-table", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='dark'] .el-card", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='dark'] .el-form-item__label", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("[data-theme='dark'] .el-tabs__item", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf('--el-table-tr-bg-color: #172033', markerIndex)).toBeGreaterThan(markerIndex);
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
});

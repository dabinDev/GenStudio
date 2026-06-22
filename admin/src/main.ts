import 'element-plus/dist/index.css';
import './styles/tokens.css';
import './styles/global.css';

import { ElButton } from 'element-plus/es/components/button/index.mjs';
import { ElIcon } from 'element-plus/es/components/icon/index.mjs';
import { ElLoading } from 'element-plus/es/components/loading/index.mjs';
import { ElMenu, ElMenuItem } from 'element-plus/es/components/menu/index.mjs';
import { provideGlobalConfig } from 'element-plus/es/components/config-provider/index.mjs';
import zhCn from 'element-plus/es/locale/lang/zh-cn';
import { createPinia } from 'pinia';
import { createApp, defineAsyncComponent, type Component } from 'vue';

import App from './App.vue';
import router from './router';

const layoutElementPlusComponents = [
  ElButton,
  ElIcon,
  ElLoading,
  ElMenu,
  ElMenuItem,
];

const app = createApp(App);

layoutElementPlusComponents.forEach((component) => {
  app.use(component);
});

const asyncElementPlusComponents: Record<string, () => Promise<Component>> = {
  ElAlert: () => import('element-plus/es/components/alert/index.mjs').then((module) => module.ElAlert),
  ElCard: () => import('element-plus/es/components/card/index.mjs').then((module) => module.ElCard),
  ElCollapse: () => import('element-plus/es/components/collapse/index.mjs').then((module) => module.ElCollapse),
  ElCollapseItem: () => import('element-plus/es/components/collapse/index.mjs').then((module) => module.ElCollapseItem),
  ElDatePicker: () => import('element-plus/es/components/date-picker/index.mjs').then((module) => module.ElDatePicker),
  ElDescriptions: () => import('element-plus/es/components/descriptions/index.mjs').then((module) => module.ElDescriptions),
  ElDescriptionsItem: () => import('element-plus/es/components/descriptions/index.mjs').then((module) => module.ElDescriptionsItem),
  ElDivider: () => import('element-plus/es/components/divider/index.mjs').then((module) => module.ElDivider),
  ElDrawer: () => import('element-plus/es/components/drawer/index.mjs').then((module) => module.ElDrawer),
  ElDropdown: () => import('element-plus/es/components/dropdown/index.mjs').then((module) => module.ElDropdown),
  ElDropdownItem: () => import('element-plus/es/components/dropdown/index.mjs').then((module) => module.ElDropdownItem),
  ElDropdownMenu: () => import('element-plus/es/components/dropdown/index.mjs').then((module) => module.ElDropdownMenu),
  ElEmpty: () => import('element-plus/es/components/empty/index.mjs').then((module) => module.ElEmpty),
  ElForm: () => import('element-plus/es/components/form/index.mjs').then((module) => module.ElForm),
  ElFormItem: () => import('element-plus/es/components/form/index.mjs').then((module) => module.ElFormItem),
  ElInput: () => import('element-plus/es/components/input/index.mjs').then((module) => module.ElInput),
  ElInputNumber: () => import('element-plus/es/components/input-number/index.mjs').then((module) => module.ElInputNumber),
  ElOption: () => import('element-plus/es/components/select/index.mjs').then((module) => module.ElOption),
  ElSelect: () => import('element-plus/es/components/select/index.mjs').then((module) => module.ElSelect),
  ElSwitch: () => import('element-plus/es/components/switch/index.mjs').then((module) => module.ElSwitch),
  ElTable: () => import('element-plus/es/components/table/index.mjs').then((module) => module.ElTable),
  ElTableColumn: () => import('element-plus/es/components/table/index.mjs').then((module) => module.ElTableColumn),
  ElTabPane: () => import('element-plus/es/components/tabs/index.mjs').then((module) => module.ElTabPane),
  ElTabs: () => import('element-plus/es/components/tabs/index.mjs').then((module) => module.ElTabs),
  ElTag: () => import('element-plus/es/components/tag/index.mjs').then((module) => module.ElTag),
  ElTimeline: () => import('element-plus/es/components/timeline/index.mjs').then((module) => module.ElTimeline),
  ElTimelineItem: () => import('element-plus/es/components/timeline/index.mjs').then((module) => module.ElTimelineItem),
};

Object.entries(asyncElementPlusComponents).forEach(([name, loader]) => {
  app.component(name, defineAsyncComponent(loader));
});
provideGlobalConfig({ locale: zhCn }, app, true);

app.use(createPinia()).use(router).mount('#app');

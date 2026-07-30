import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const readSource = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8").replace(/\r\n/g, "\n");
const appVue = () => readSource("src/App.vue");
const stylesCss = () => readSource("src/styles.css");
const redesignCss = () => readSource("src/workbenchRedesign.css");
const mainTs = () => readSource("src/main.ts");
const catalogTs = () => readSource("src/catalog.ts");

describe("workbench style application", () => {
  it("does not import chat prototype components that are not rendered by App", () => {
    const source = appVue();

    expect(source).not.toContain("./components/ChatMessage.vue");
    expect(source).not.toContain("./components/ChatInput.vue");
  });

  it("keeps the final workbench overrides on the classes rendered by App", () => {
    const source = stylesCss();
    const overrideIndex = source.indexOf("Creative Workshop effective workbench surfaces v12");

    expect(overrideIndex).toBeGreaterThan(-1);
    expect(source.indexOf(".shell .conversation-timeline", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf(".shell .message-card", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf(".shell .composer-card", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf(".shell .composer-surface", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("uses wide rails for chat history and composer content", () => {
    const source = stylesCss();
    const overrideIndex = source.indexOf("Creative Workshop wide conversation rails v13");

    expect(overrideIndex).toBeGreaterThan(-1);
    expect(source.indexOf(".shell .conversation-timeline", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("max-width: none !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf(".shell .message-user", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("margin-left: auto !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf(".shell .composer-card", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("1480px", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("keeps media composer actions right aligned without stretching desktop buttons", () => {
    const source = stylesCss();
    const overrideIndex = source.indexOf("Creative Workshop composer action alignment v15");

    expect(overrideIndex).toBeGreaterThan(-1);
    expect(source.indexOf(".shell .composer-footer-bar", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("grid-template-columns: minmax(0, 1fr) auto !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf(".shell .composer-action-group", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("justify-self: end !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("margin-left: auto !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("min-width: max-content !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf(".shell .composer-submit-button", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("height: 40px !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("border-radius: 10px !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("white-space: nowrap !important", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("shows the active conversation name in the top bar instead of a sticky chat header", () => {
    const source = appVue();
    const styles = stylesCss();

    expect(source).toContain("topbar-conversation-name");
    expect(source).toContain("currentConversationTitle");
    expect(source).not.toContain("class=\"conversation-header\"");
    expect(styles).toContain("Creative Workshop conversation title rail v16");
  });

  it("wires composer keyboard shortcuts to the active prompt controls", () => {
    const source = appVue();

    expect(source).toContain("window.addEventListener(\"keydown\", handleComposerShortcutKey)");
    expect(source).toContain("window.removeEventListener(\"keydown\", handleComposerShortcutKey)");
    expect(source).toContain("composerShortcutFromKeyboardEvent(event)");
    expect(source).toContain("handlePromptOptimize(capability)");
    expect(source).toContain("submitActiveComposer(capability)");
    expect(source).toContain("优化提示词（Ctrl+I）");
    expect(source).toContain("Ctrl+Enter");
  });

  it("renders chat avatars, GSAP thinking states, and a floating composer shell", () => {
    const source = appVue();
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop chat presence and floating composer v17");

    expect(source).toContain("import { gsap } from \"gsap\"");
    expect(source).toContain("setupAiThinkingAnimation");
    expect(source).toContain("teardownAiThinkingAnimation");
    expect(source).toContain("ai-thinking-panel");
    expect(source).toContain("ai-thinking-orb");
    expect(source).toContain("message-avatar");
    expect(source).toContain("message-bubble");
    expect(source).not.toContain("class=\"loader-dot\"");

    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .composer-card", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("background: transparent !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .message-avatar", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .ai-thinking-panel", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("keeps the composer edge veil transparent so scrolled chat remains partially visible", () => {
    const styles = stylesCss();
    const markerIndex = styles.indexOf("Creative Workshop transparent composer veil v33");

    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .composer-card::before", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("pointer-events: none !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("linear-gradient(90deg, transparent 0%, #000 18%, #000 82%, transparent 100%)", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("-webkit-mask-image", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("mask-image", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .composer-card::after", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("background: transparent !important", markerIndex)).toBeGreaterThan(markerIndex);
  });

  it("makes image and video composer side rails translucent without fading controls", () => {
    const styles = stylesCss();
    const markerIndex = styles.indexOf("Creative Workshop media composer translucent side rails v34");

    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .composer-surface:has(.media-composer-grid)", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .composer-surface:has(.media-composer-grid)::before", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("linear-gradient(90deg, transparent 0%,", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("pointer-events: none !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .composer-surface:has(.media-composer-grid) > *", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("z-index: 1 !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .composer-surface:has(.media-composer-grid)::before", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .composer-surface:has(.media-composer-grid)::before", markerIndex)).toBeGreaterThan(markerIndex);
  });

  it("keeps media composer template and top rows unmasked and visually lightweight", () => {
    const styles = stylesCss();
    const markerIndex = styles.indexOf("Creative Workshop media composer lightweight chrome v35");

    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .composer-card-expanded:has(.media-composer-grid)", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("mask-image: none !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("-webkit-mask-image: none !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .composer-card-expanded:has(.media-composer-grid) .composer-toolbar", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .composer-card-expanded:has(.media-composer-grid) .composer-template-card", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("backdrop-filter: none !important", markerIndex)).toBeGreaterThan(markerIndex);
  });

  it("presents prompt templates as scenario cards inside the composer", () => {
    const source = appVue();
    const catalog = catalogTs();
    const styles = stylesCss();
    const markerIndex = styles.indexOf("Creative Workshop prompt template cards v19");

    expect(source).toContain("composer-template-library");
    expect(source).toContain("composer-template-card");
    expect(source).toContain("template.summary");
    expect(source).toContain("模板已加入输入框");

    expect(catalog).toContain("category:");
    expect(catalog).toContain("summary:");
    expect(catalog).toContain("example:");

    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .composer-template-library", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .composer-template-card", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("grid-template-columns: repeat(auto-fit, minmax(178px, 1fr))", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .composer-template-card", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .composer-template-card", markerIndex)).toBeGreaterThan(markerIndex);
  });

  it("uses theme-specific GSAP ambient backgrounds without the old light-mode blue grid", () => {
    const source = appVue();
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop theme ambient background v18");

    expect(source).toContain("setupStudioAmbientAnimation");
    expect(source).toContain("teardownStudioAmbientAnimation");
    expect(source).toContain("studio-ambient");
    expect(source).toContain("studio-ambient-drift");
    expect(source).toContain("studio-ambient-line");
    expect(source).toContain("onUnmounted(() =>");
    expect(source).toContain("teardownStudioAmbientAnimation();");
    expect(source.indexOf("watch(\n  themeMode")).toBeGreaterThan(-1);
    expect(source.indexOf("setupStudioAmbientAnimation();", source.indexOf("watch(\n  themeMode"))).toBeGreaterThan(-1);
    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell::before", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("animation: none !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .studio-ambient", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .studio-ambient", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("pointer-events: none", styles.indexOf(".studio-ambient", overrideIndex))).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("z-index: 0", styles.indexOf(".studio-ambient", overrideIndex))).toBeGreaterThan(overrideIndex);
    const shellChromeLayerMatch = /\.sidebar,\r?\n\.main \{/.exec(styles.slice(overrideIndex));
    const shellChromeLayerIndex = shellChromeLayerMatch ? overrideIndex + shellChromeLayerMatch.index : -1;
    expect(shellChromeLayerIndex).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("z-index: 1", shellChromeLayerIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("#f8fbfc", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("#050b13", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .studio-canvas", overrideIndex)).toBeGreaterThan(overrideIndex);

    const lightThemeIndex = styles.indexOf(".shell[data-theme=\"light\"] {", overrideIndex);
    const darkThemeIndex = styles.indexOf(".shell[data-theme=\"dark\"] {", overrideIndex);
    const lightAmbientBlock = styles.slice(lightThemeIndex, darkThemeIndex);
    expect(lightAmbientBlock).not.toContain("46px 46px");
    expect(lightAmbientBlock).not.toContain("#07101d");
    expect(lightAmbientBlock).not.toContain("#050b13");

    const finalLightCanvasIndex = styles.indexOf(".shell[data-theme=\"light\"] .studio-canvas", overrideIndex);
    const finalDarkThemeIndex = styles.indexOf(".shell[data-theme=\"dark\"] {", finalLightCanvasIndex);
    const finalLightCanvasBlock = styles.slice(finalLightCanvasIndex, finalDarkThemeIndex);
    expect(finalLightCanvasBlock).not.toContain("36px 36px");
    expect(finalLightCanvasBlock).not.toContain("linear-gradient(90deg");
    expect(finalLightCanvasBlock).not.toContain("1px, transparent 1px");
  });

  it("removes legacy grid backgrounds from every chat canvas rule", () => {
    const styles = stylesCss();
    const canvasBlocks = Array.from(
      styles.matchAll(/[^{]*\.studio-canvas(?!::)[^{]*\{[^}]*\}/g),
      (match) => match[0],
    );

    expect(canvasBlocks.length).toBeGreaterThan(0);
    canvasBlocks.forEach((block) => {
      expect(block).not.toContain("36px 36px");
      expect(block).not.toContain("34px 34px");
      expect(block).not.toContain("38px 38px");
      expect(block).not.toContain("42px 42px");
      expect(block).not.toContain("1px, transparent 1px");
    });
  });

  it("keeps the settings page background theme-specific without the blue grid in light mode", () => {
    const styles = stylesCss();
    const themeOverrideIndex = styles.indexOf("Creative Workshop theme ambient background v18");

    expect(themeOverrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-page", themeOverrideIndex)).toBeGreaterThan(themeOverrideIndex);

    const rawSettingsBlocks = Array.from(
      styles.matchAll(/(?<!\[data-theme="light"\]\s)(?<!\[data-theme="dark"\]\s)(?<!\.shell\[data-theme="light"\]\s)(?<!\.shell\[data-theme="dark"\]\s)\.settings-page\s*\{[^}]*\}/g),
      (match) => match[0],
    );
    expect(rawSettingsBlocks.length).toBeGreaterThan(0);
    rawSettingsBlocks.forEach((block) => {
      expect(block).not.toContain("linear-gradient(90deg");
      expect(block).not.toContain("1px, transparent 1px");
      expect(block).not.toContain("background-size: 40px 40px");
      expect(block).not.toContain("rgba(8, 20, 34");
    });
  });

  it("keeps production SSO profile copy localized for Chinese users", () => {
    const source = appVue();

    expect(source).toContain("官网授权回调");
    expect(source).toContain("官网授权登录");
    expect(source).toContain("授权失败");
    expect(source).toContain("返回登录");
    expect(source).toContain("正式环境由官网生成短期 code 跳转登录");
    expect(source).toContain("刷新历史记录");
    expect(source).not.toContain("Official SSO");
    expect(source).not.toContain("Official SSO callback");
    expect(source).not.toContain("Authorization failed");
    expect(source).not.toContain("Back to login");
    expect(source).not.toContain("Production login is created");
    expect(source).not.toContain("Refresh history");
  });

  it("uses a dedicated soft-ink treatment for light mode settings model names", () => {
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop settings light model names v19");

    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-model-main strong", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-primary-model strong", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("color: #173f3f !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("letter-spacing: 0 !important", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("keeps light mode badges and action buttons on explicit readable colors", () => {
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop light contrast guard v20");

    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .tag-text", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("color: #075b78 !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .tag-image", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("color: #075f59 !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .tag-video", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("color: #7a4a06 !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .button-secondary", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("color: #0c5260 !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .button-primary", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("background: linear-gradient(135deg, #0a8f86, #0e67b7) !important", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("keeps the add-model dialog fully light themed in light mode", () => {
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop settings dialog light surface v21");

    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-dialog", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-dialog-workspace .wizard-step", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-dialog-section", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-dialog-actions", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .model-pick-panel", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .dialog-test-result", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .model-select-dialog .model-select-menu", overrideIndex)).toBeGreaterThan(overrideIndex);

    const block = styles.slice(overrideIndex);
    expect(block).not.toContain("#101113");
    expect(block).not.toContain("rgba(8, 16, 28");
    expect(block).not.toContain("rgba(8, 18, 31");
    expect(block).not.toContain("rgba(3, 9, 16");
  });

  it("uses polished theme-specific colors for the primary model select menu", () => {
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop model select menu polish v22");

    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .model-select-dialog .model-select-menu", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .model-select-dialog .model-select-trigger", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .model-select-dialog .model-select-search", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .model-select-dialog .model-select-option", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .model-select-dialog .model-select-option-active", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .model-select-dialog .model-select-menu", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .model-select-dialog .model-select-trigger", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .model-select-dialog .model-select-search", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .model-select-dialog .model-select-option", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .model-select-dialog .model-select-option-active", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .model-select-dialog .model-select-check", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("max-height: min(42vh, 360px) !important", overrideIndex)).toBeGreaterThan(overrideIndex);

    const nextOverrideIndex = styles.indexOf("Creative Workshop refined media gallery v23", overrideIndex);
    const block = styles.slice(overrideIndex, nextOverrideIndex > -1 ? nextOverrideIndex : undefined);
    expect(block).not.toContain("rgba(255, 255, 255, 0.055)");
    expect(block).not.toContain("#111416");
  });

  it("uses the refined media gallery and fullscreen preview controls", () => {
    const source = appVue();
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop refined media gallery v23");

    expect(source).toContain("setupMediaPreviewAnimation");
    expect(source).toContain("media-preview-toolbar");
    expect(source).toContain("asset-action-toolbar");
    expect(source).toContain("asset-action-button");
    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .message-assets", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .message-assets-multiple .message-asset-card", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .asset-action-toolbar", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .asset-action-button", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".media-preview-toolbar", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".media-preview-zoom-pill", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(
      styles.indexOf(".media-preview-backdrop .media-preview-panel .media-preview-actions.media-preview-toolbar", overrideIndex),
    ).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("grid-template-columns: repeat(4, minmax(168px, 1fr)) !important", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("uses themed surfaces for the settings model configuration list", () => {
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop settings model config list v24");

    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-list-panel", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-model-board", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-board-head", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-model-row", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-search-box", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-model-board .settings-action-button", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-empty-state", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .settings-list-panel", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .settings-model-board", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .settings-board-head", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .settings-model-row", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .settings-search-box", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .settings-model-board .settings-action-button", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("keeps inline primary model picker from falling back to large blue active blocks", () => {
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop inline primary model picker v25");

    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .inline-model-select .model-select-menu", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .inline-model-select .model-select-option", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .model-select-scrim", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .inline-model-select .model-select-option-active", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .inline-model-select .model-select-option-active", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("rgba(218, 249, 244, 0.74)", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("background: transparent !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("linear-gradient(135deg, rgb(15, 159, 150), rgb(31, 111, 235))", overrideIndex)).toBe(-1);
  });

  it("keeps settings primary model menus above the model list without clipping", () => {
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop settings model picker layer v26");

    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .settings-list-panel", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .settings-model-board", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("overflow: visible !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .settings-model-row-select-open", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .settings-model-row-select-open .model-select-menu", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .settings-model-row-select-open .model-select-scrim", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("z-index: 120 !important", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("uses the redesigned dark navigation palette for sidebar models and topbar controls", () => {
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop dark navigation palette v26");

    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .sidebar", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .sidebar-logo", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .primary-item", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .primary-item-active", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .secondary-item-active", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .sidebar-model-item", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .sidebar-model-active", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .workspace-topbar button", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .topbar-icon-button", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("#0a141f", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("uses stable avatar and icon fallbacks instead of raw nickname slicing", () => {
    const source = appVue();
    const styles = stylesCss();
    const redesign = redesignCss();
    const overrideIndex = styles.indexOf("Creative Workshop stable avatar fallbacks v27");

    expect(source).toContain("accountAvatarLabel");
    expect(source).toContain("profileAvatarLabel");
    expect(source).toContain("accountDisplayName");
    expect(source).toContain("profileDisplayName");
    expect(source).toContain("safeIdentityLabel");
    expect(source).toContain("{{ accountAvatarLabel }}");
    expect(source).toContain("{{ profileAvatarLabel }}");
    expect(source).toContain("{{ accountDisplayName }}");
    expect(source).toContain("{{ profileDisplayName }}");
    expect(source).not.toContain("auth.state.user?.nickname?.slice(0, 1)");
    expect(source).toContain("creator-model-bar");
    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .model-avatar-icon-failed img", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("display: none !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(redesign).toContain(".shell .creator-model-bar .model-avatar");
    expect(styles.indexOf(".shell .account-avatar", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("uses a calmer production-grade light treatment for settings model rows", () => {
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop settings production light pass v28");

    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-list-panel", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-model-board", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-model-row", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("background: rgba(255, 255, 255, 0.92) !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .settings-model-row-public", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("border-left: 3px solid #0d9488 !important", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("uses a guided empty canvas with a direct video model setup path", () => {
    const source = appVue();
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop guided empty canvas v29");

    expect(source).toContain("empty-canvas-actions");
    expect(source).toContain("empty-canvas-flow");
    expect(source).toContain("去设置视频模型");
    expect(source).toContain("settingsState.activeCapability = 'video'");
    expect(source).toContain("推荐模板");
    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .empty-canvas-actions", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .empty-canvas-flow", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"light\"] .empty-canvas-actions button", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell[data-theme=\"dark\"] .empty-canvas-flow span", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("uses product language instead of internal demo copy in the creative workspace", () => {
    const source = appVue();
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop copy and focus polish v30");

    expect(source).toContain("多模型创作工作台");
    expect(source).toContain("开始创作");
    expect(source).toContain("当前模型");
    expect(source).toContain("还没有保存的对话");
    expect(source).toContain("专属创作模型");
    expect(source).toContain("创作资产");
    expect(source).toContain("模型资产");
    expect(source).toContain("账户中心");
    expect(source).toContain('showToast("资料已保存")');
    expect(source).toContain("conversationStatusLabel(conversation.status)");
    expect(source).not.toContain("多模型创作调试台");
    expect(source).not.toContain("玩法说明");
    expect(source).not.toContain("No saved conversations yet.");
    expect(source).not.toContain("用户自定义模型");
    expect(source).not.toContain("Model Settings");
    expect(source).not.toContain("Profile saved");
    expect(source).not.toContain('<p class="eyebrow">Profile</p>');
    expect(source).not.toContain('conversation.status || "active"');
    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .empty-canvas-card", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .composer-topline", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .settings-hero .eyebrow", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("keeps settings model rows from looking like a button-heavy debug table", () => {
    const source = appVue();
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop settings operator rows v31");

    expect(source).toContain("settings-row-actions-primary");
    expect(source).toContain("settings-row-actions-more");
    expect(source).toContain("settings-row-action-menu");
    expect(source).toContain("操作");
    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .settings-row-actions-primary", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .settings-row-actions-more", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .settings-row-action-menu", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("grid-template-columns: repeat(2, minmax(0, 1fr))", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("separates public creator models from private settings and gives them distinct cards", () => {
    const source = appVue();
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Public model creator cards v1");

    expect(source).toContain("Boolean(auth.state.user?.isAdmin)");
    expect(source).toContain("publicModelAccent(model)");
    expect(source).toContain("publicModelCardDescription(model)");
    expect(source).toContain("model.publicTags?.slice(0, 2)");
    expect(source).toContain("public-model-card-price");
    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .sidebar-model-public", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("--public-model-accent", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".public-model-card-description", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".public-model-card-price", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("does not expose public model counts to ordinary users in settings", () => {
    const source = appVue();

    expect(source).toContain("const settingsVisibleModels = computed");
    expect(source).toContain("all: settingsVisibleModels.value.length");
    expect(source).toContain("settingsVisibleModels.value.filter((model) => model.capability === \"text\").length");
    expect(source).toContain("{{ settingsVisibleModels.length }} 个模型");
  });

  it("keeps administrator credit grants visible at the top of the workspace until dismissal", () => {
    const source = appVue();
    const styles = stylesCss();
    const noticeIndex = styles.indexOf("Persistent credit grants stay beneath the workspace controls until dismissed.");

    expect(source).toContain("nextCreditGrantNotice(auth.state.creditTransactions)");
    expect(source).toContain('class="credit-grant-notice"');
    expect(source).toContain("dismissCurrentCreditGrantNotice");
    expect(source).toContain("window.setInterval(() => void refreshCreditsQuietly(), 30_000)");
    expect(noticeIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .credit-grant-notice", noticeIndex)).toBeGreaterThan(noticeIndex);
    expect(styles.indexOf(".shell .credit-grant-notice-dismiss", noticeIndex)).toBeGreaterThan(noticeIndex);
  });

  it("keeps the empty creative canvas compact beneath the persistent model bar", () => {
    const source = appVue();
    const styles = redesignCss();

    expect(source).toContain("empty-canvas-workbench");
    expect(source).toContain('v-else-if="!activeModel" class="empty-canvas empty-canvas-workbench"');
    expect(source).toContain("empty-canvas-copy");
    expect(source).toContain("creator-model-bar");
    expect(source).not.toContain("empty-canvas-model-strip");
    expect(source).toContain("empty-canvas-primary-action");
    expect(styles).toContain(".shell .empty-canvas-workbench");
    expect(styles).toContain(".shell .empty-canvas-copy h3");
    expect(styles).toContain(".shell .empty-canvas-primary-action");
    expect(styles).toContain("width: min(680px, 100%) !important");
  });

  it("does not keep the old embedded admin shell in the creative workspace", () => {
    const source = appVue();
    const styles = stylesCss();

    expect(source).not.toContain('"admin"');
    expect(source).not.toContain("shell-admin");
    expect(styles).not.toContain(".shell-admin");
    expect(styles).not.toContain("legacy-admin-removed");
    expect(styles).not.toMatch(/\.admin-/);
    expect(styles).not.toMatch(/--admin/);
  });

  it("uses a compact mobile workbench shell instead of a squeezed desktop sidebar", () => {
    const styles = stylesCss();
    const markerIndex = styles.indexOf("Creative Workshop mobile shell containment v38");

    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf("@media (max-width: 720px)", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .sidebar", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("max-width: 100vw !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .model-list", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("overflow-x: auto !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .main", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("min-width: 0 !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .studio-ambient", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("overflow: hidden !important", markerIndex)).toBeGreaterThan(markerIndex);
  });

  it("keeps mobile settings model rows contained inside the viewport", () => {
    const styles = stylesCss();
    const markerIndex = styles.indexOf("Creative Workshop mobile shell containment v38");

    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .settings-board-head,", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .settings-model-row {", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("grid-template-columns: minmax(0, 1fr) !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .settings-model-row > *", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .settings-primary-model,", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .inline-model-select", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .settings-row-actions-primary", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .settings-row-actions-more", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("width: 100% !important", markerIndex)).toBeGreaterThan(markerIndex);
  });

  it("lifts mobile inline model menus above the settings list so switching models is not covered", () => {
    const styles = stylesCss();
    const markerIndex = styles.indexOf("Creative Workshop mobile model select overlay v39");

    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf("@media (max-width: 720px)", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .settings-model-row-select-open", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("z-index: 260 !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .settings-model-row-select-open .model-select-scrim", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("background: rgba(4, 12, 20, 0.18) !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .settings-model-row-select-open .model-select-menu", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("position: fixed !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("left: 10px !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("right: 10px !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("bottom: calc(env(safe-area-inset-bottom, 0px) + 12px) !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("max-height: min(58vh, 430px) !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("overscroll-behavior: contain !important", markerIndex)).toBeGreaterThan(markerIndex);
  });

  it("explains 4K image generation cost and keeps the toggle mobile safe", () => {
    const source = appVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf("Image 4K toggle");

    expect(source).toContain("4K 生成");
    expect(source).toContain("双倍积分");
    expect(source).toContain("扣费 = 单价 × 数量 × 2");
    expect(source).toContain("4K 需要");
    expect(source).toContain("当前不足");
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .image-options-popover .image-4k-toggle", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("justify-content: space-between !important", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf(".shell .image-options-popover .image-4k-help", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("@media (max-width: 720px)", markerIndex)).toBeGreaterThan(markerIndex);
  });

  it("shows GPT 5.5 image prompt recommendation tags after reference upload", () => {
    const source = appVue();
    const styles = stylesCss();
    const markerIndex = styles.indexOf("Image prompt recommendation tags");

    expect(source).toContain("fetchImagePromptRecommendations");
    expect(source).toContain("recordPromptLibraryEvent");
    expect(source).toContain("imageState.promptRecommendations");
    expect(source).toContain("imageState.recommendationLoading");
    expect(source).toContain("applyPromptRecommendation");
    expect(source).toContain("图片识别推荐");
    expect(source).toContain("识别中");
    expect(source).toContain("推荐标签已加入输入框");
    expect(markerIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .image-prompt-recommendations", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("flex-wrap: wrap", markerIndex)).toBeGreaterThan(markerIndex);
    expect(styles.indexOf("@media (max-width: 720px)", markerIndex)).toBeGreaterThan(markerIndex);
  });

  it("marks account pages separately from the model workspace in the sidebar", () => {
    const source = appVue();

    expect(source).toContain("primaryNavSection");
    expect(source).toContain("primary-item-active");
    expect(source).toContain("primaryNavSection === 'models'");
    expect(source).toContain("primaryNavSection === 'account'");
  });

  it("uses explicit model action menu state instead of an untracked details popup", () => {
    const source = appVue();

    expect(source).toContain("modelActionMenuState.openId");
    expect(source).toContain("settings-model-row-action-open");
    expect(source).toContain("toggleModelActionMenu(model.id, event)");
    expect(source).toContain('aria-label="关闭模型操作"');
    expect(source).not.toContain('<details class="settings-row-actions-more">');
  });

  it("loads one final redesign layer after the legacy stylesheet", () => {
    const source = mainTs();

    expect(source.indexOf('./styles.css')).toBeLessThan(source.indexOf('./workbenchRedesign.css'));
  });

  it("gives open settings action rows and menus an explicit layer", () => {
    const styles = redesignCss();

    expect(styles).toContain(".settings-model-row-action-open");
    expect(styles).toContain("z-index: 320 !important");
    expect(styles).toContain(".settings-row-action-scrim");
    expect(styles).toContain(".settings-row-actions-more-up .settings-row-action-menu");
  });

  it("keeps the model action scrim transparent when the global button hover rule applies", () => {
    const styles = redesignCss();

    expect(styles).toContain(".settings-row-action-scrim:hover:not(:disabled)");
    expect(styles).toContain("background: transparent !important");
  });

  it("uses one model-aware frame for all creator capabilities", () => {
    const source = appVue();
    const styles = redesignCss();

    expect(source).toContain("creator-model-identity");
    expect(source).toContain(':style="activeModelIdentityStyle"');
    expect(styles).toContain('.studio-panel[data-view="text"]');
    expect(styles).toContain('.studio-panel[data-view="images"]');
    expect(styles).toContain('.studio-panel[data-view="videos"]');
    expect(styles).toContain("var(--model-accent)");
  });

  it("keeps media controls and creator text contained on mobile", () => {
    const styles = redesignCss();

    expect(styles).toContain("@media (max-width: 720px)");
    expect(styles).toContain("overflow-wrap: anywhere");
    expect(styles).toContain("grid-template-columns: minmax(0, 1fr)");
  });

  it("keeps the mobile model identity, empty state, and composer in one scroll flow", () => {
    const styles = redesignCss();
    const mobileIndex = styles.lastIndexOf("@media (max-width: 720px)");

    expect(mobileIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .studio-panel {", mobileIndex)).toBeGreaterThan(mobileIndex);
    expect(styles.indexOf("display: block !important", mobileIndex)).toBeGreaterThan(mobileIndex);
    expect(styles.indexOf("overflow: visible !important", mobileIndex)).toBeGreaterThan(mobileIndex);
    const emptyStateIndex = styles.indexOf(".shell .empty-canvas-workbench {", mobileIndex);
    expect(emptyStateIndex).toBeGreaterThan(mobileIndex);
    expect(styles.slice(emptyStateIndex, emptyStateIndex + 180)).toContain("min-height: 180px !important");
    expect(styles.slice(emptyStateIndex, emptyStateIndex + 180)).not.toContain("display: none !important");
    const composerIndex = styles.indexOf(".shell .studio-panel .composer-card {", mobileIndex);
    expect(composerIndex).toBeGreaterThan(mobileIndex);
    expect(styles.slice(composerIndex, composerIndex + 180)).toContain("position: relative !important");
  });

  it("keeps tablet topbar commands on one line", () => {
    const styles = redesignCss();
    const tabletIndex = styles.indexOf("@media (max-width: 1100px)");

    expect(tabletIndex).toBeGreaterThan(-1);
    expect(styles.indexOf("white-space: nowrap !important", tabletIndex)).toBeGreaterThan(tabletIndex);
    expect(styles.indexOf(".shell .topbar-icon-button span", tabletIndex)).toBeGreaterThan(tabletIndex);
    const tabletStyles = styles.slice(tabletIndex, styles.indexOf("@media (max-width: 1024px)", tabletIndex));
    expect(tabletStyles).not.toContain(".shell .empty-canvas-workbench");
  });

  it("keeps mobile settings action sheets fixed to the viewport", () => {
    const styles = redesignCss();
    const settingsPanelIndex = styles.indexOf(".shell .settings-list-panel,");

    expect(settingsPanelIndex).toBeGreaterThan(-1);
    const containingBlockReset = styles.slice(settingsPanelIndex, settingsPanelIndex + 420);
    expect(containingBlockReset).toContain(".shell .settings-model-board");
    expect(containingBlockReset).toContain("transform: none !important");
    expect(containingBlockReset).toContain("filter: none !important");
    expect(containingBlockReset).toContain("backdrop-filter: none !important");
    expect(containingBlockReset).toContain("-webkit-backdrop-filter: none !important");
    expect(containingBlockReset).toContain("contain: none !important");
    expect(containingBlockReset).toContain("perspective: none !important");
  });

  it("forces every mobile settings model row into one explicit column", () => {
    const styles = redesignCss();
    const mobileIndex = styles.lastIndexOf("@media (max-width: 720px)");

    expect(mobileIndex).toBeGreaterThan(-1);
    const mobileStyles = styles.slice(mobileIndex);
    expect(mobileStyles).toContain('.shell[data-theme="light"] .settings-page .settings-model-row');
    expect(mobileStyles).toContain('.shell[data-theme="dark"] .settings-page .settings-model-row');
    expect(mobileStyles).toContain("grid-template-columns: minmax(0, 1fr) !important");
    expect(mobileStyles).toContain(".settings-model-row > :not(.settings-check-cell)");
    expect(mobileStyles).toContain("grid-column: 1 / -1 !important");
    expect(mobileStyles).toContain(".settings-model-row > .settings-check-cell");
    expect(mobileStyles).toContain("width: auto !important");
  });

  it("gives the profile view a dedicated responsive account-center layout", () => {
    const source = appVue();
    const styles = redesignCss();

    expect(source).toContain("profile-account-header");
    expect(source).toContain("profile-account-metrics");
    expect(source).toContain("profile-account-workspace");
    expect(source).toContain("profile-account-details");
    expect(source).toContain("profile-account-security");
    expect(source).toContain("profile-account-danger");
    expect(source).toContain("正式环境由官网生成短期 code 跳转登录，回调地址为 /auth/callback?code=xxx。");
    expect(source).not.toContain('class="settings-row-actions profile-editor-actions"');
    expect(styles).toContain("Profile account center v1");
    expect(styles).toContain("grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.75fr) !important");
    expect(styles).toContain("white-space: nowrap !important");
    expect(styles).toContain("@media (max-width: 860px)");

    const markerIndex = styles.indexOf("Profile account center v1");
    const regionSelectorIndex = styles.indexOf(".shell .profile-account-header,", markerIndex);
    const regionRule = styles.slice(regionSelectorIndex, styles.indexOf(".shell .profile-account-header {", regionSelectorIndex));
    expect(regionRule).toContain("flex: 0 0 auto !important");

    const compactIndex = styles.indexOf("@media (max-width: 860px)", markerIndex);
    const compactStyles = styles.slice(compactIndex, styles.indexOf("@media screen and (max-width: 720px)", compactIndex));
    expect(compactStyles).toContain(".shell .profile-account-metrics");
    expect(compactStyles).toContain("grid-template-columns: repeat(2, minmax(0, 1fr)) !important");
  });

  it("stabilizes every creator detail surface in the final cascade", () => {
    const styles = redesignCss();
    const markerIndex = styles.indexOf("NewUI creator detail pass v1");
    const finalStyles = styles.slice(markerIndex);

    expect(markerIndex).toBeGreaterThan(-1);
    expect(finalStyles).toContain(".shell .sidebar {");
    expect(finalStyles).toContain("width: clamp(232px, 18vw, 284px) !important");
    expect(finalStyles).toContain(".shell .message-assets {");
    expect(finalStyles).toContain("grid-template-columns: repeat(auto-fit, minmax(min(220px, 100%), 1fr)) !important");
    expect(finalStyles).toContain(".shell .asset-preview-trigger,");
    expect(finalStyles).toContain("aspect-ratio: 4 / 3 !important");
    expect(finalStyles).toContain(".shell .reference-strip {");
    expect(finalStyles).toContain("min-height: 70px !important");
    expect(finalStyles).toContain("overflow-x: auto !important");
    expect(finalStyles).toContain(".shell .reference-mention-menu {");
    expect(finalStyles).toContain("width: min(360px, calc(100vw - 24px)) !important");
    const mentionSurfaceIndex = finalStyles.indexOf(".shell .composer-surface:has(.reference-mention-menu) {");
    const mentionSurfaceRule = finalStyles.slice(mentionSurfaceIndex, finalStyles.indexOf("}", mentionSurfaceIndex));
    expect(mentionSurfaceIndex).toBeGreaterThan(-1);
    expect(mentionSurfaceRule).toContain("z-index: 90 !important");
    expect(mentionSurfaceRule).toContain("overflow: visible !important");
    expect(finalStyles).toContain(".shell .composer-pill,");
    expect(finalStyles).toContain("min-height: 40px !important");
    expect(finalStyles).toContain(".shell .settings-model-row {");
    expect(finalStyles).toContain("min-height: 72px !important");
    expect(finalStyles).toContain(".shell .profile-account-details-grid input,");
    expect(finalStyles).toContain("min-height: 42px !important");
    expect(finalStyles).toContain(".shell .settings-dialog {");
    expect(finalStyles).toContain("max-height: min(760px, calc(100dvh - 32px)) !important");
    expect(finalStyles).toContain(".shell .app-toast {");
    expect(finalStyles).toContain("max-width: min(420px, calc(100vw - 24px)) !important");
  });

  it("keeps the creator keyboard, text, motion, and phone states usable", () => {
    const styles = redesignCss();
    const markerIndex = styles.indexOf("NewUI creator detail pass v1");
    const finalStyles = styles.slice(markerIndex);

    expect(markerIndex).toBeGreaterThan(-1);
    expect(finalStyles).toContain("overflow-wrap: anywhere !important");
    expect(finalStyles).toContain(".shell :where(button, input, textarea, select, a):focus-visible");
    expect(finalStyles).toContain("@media (prefers-reduced-motion: reduce)");
    expect(finalStyles).toContain("@media (max-width: 480px)");
    expect(finalStyles).toContain("padding-bottom: max(10px, env(safe-area-inset-bottom, 0px)) !important");
    expect(finalStyles).toContain("grid-template-columns: minmax(0, 1fr) !important");
    expect(finalStyles).not.toMatch(/\.(?:newui|creator)[^{,]*orb/);
    expect(finalStyles).not.toMatch(/letter-spacing:\s*-/);
  });
});

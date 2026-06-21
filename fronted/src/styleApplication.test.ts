import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const appVue = () => readFileSync(resolve(process.cwd(), "src/App.vue"), "utf8");
const stylesCss = () => readFileSync(resolve(process.cwd(), "src/styles.css"), "utf8");
const catalogTs = () => readFileSync(resolve(process.cwd(), "src/catalog.ts"), "utf8");

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
    expect(source).toContain("hero-model-mark-label");
    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .model-avatar-icon-failed img", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("display: none !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .hero-model-mark-label", overrideIndex)).toBeGreaterThan(overrideIndex);
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

  it("turns the empty creative canvas into a compact workbench status strip", () => {
    const source = appVue();
    const styles = stylesCss();
    const overrideIndex = styles.indexOf("Creative Workshop compact creation workbench v32");

    expect(source).toContain("empty-canvas-workbench");
    expect(source).toContain("empty-canvas-model-strip");
    expect(source).toContain("empty-canvas-primary-action");
    expect(overrideIndex).toBeGreaterThan(-1);
    expect(styles.indexOf(".shell .empty-canvas-workbench", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .empty-canvas-model-strip", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell .empty-canvas-primary-action", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("min-height: 0 !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("grid-template-columns: auto minmax(0, 1fr) auto", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("max-width: 980px", overrideIndex)).toBeGreaterThan(overrideIndex);
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
});

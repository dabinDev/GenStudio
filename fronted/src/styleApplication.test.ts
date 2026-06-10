import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const appVue = () => readFileSync(resolve(process.cwd(), "src/App.vue"), "utf8");
const stylesCss = () => readFileSync(resolve(process.cwd(), "src/styles.css"), "utf8");

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
    expect(source.indexOf(".shell:not(.shell-admin) .conversation-timeline", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf(".shell:not(.shell-admin) .message-card", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf(".shell:not(.shell-admin) .composer-card", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf(".shell:not(.shell-admin) .composer-surface", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("uses wide rails for chat history and composer content", () => {
    const source = stylesCss();
    const overrideIndex = source.indexOf("Creative Workshop wide conversation rails v13");

    expect(overrideIndex).toBeGreaterThan(-1);
    expect(source.indexOf(".shell:not(.shell-admin) .conversation-timeline", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("max-width: none !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf(".shell:not(.shell-admin) .message-user", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("margin-left: auto !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf(".shell:not(.shell-admin) .composer-card", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("1480px", overrideIndex)).toBeGreaterThan(overrideIndex);
  });

  it("keeps media composer actions right aligned without stretching desktop buttons", () => {
    const source = stylesCss();
    const overrideIndex = source.indexOf("Creative Workshop composer action alignment v15");

    expect(overrideIndex).toBeGreaterThan(-1);
    expect(source.indexOf(".shell:not(.shell-admin) .composer-footer-bar", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("grid-template-columns: minmax(0, 1fr) auto !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf(".shell:not(.shell-admin) .composer-action-group", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("justify-self: end !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("margin-left: auto !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf("min-width: max-content !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(source.indexOf(".shell:not(.shell-admin) .composer-submit-button", overrideIndex)).toBeGreaterThan(overrideIndex);
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
    expect(styles.indexOf(".shell:not(.shell-admin) .composer-card", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf("background: transparent !important", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell:not(.shell-admin) .message-avatar", overrideIndex)).toBeGreaterThan(overrideIndex);
    expect(styles.indexOf(".shell:not(.shell-admin) .ai-thinking-panel", overrideIndex)).toBeGreaterThan(overrideIndex);
  });
});

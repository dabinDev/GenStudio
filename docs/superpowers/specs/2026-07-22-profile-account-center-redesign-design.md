# Profile Account Center Redesign

## Goal

Replace the visually flat profile page with a compact account center that is easy to scan, keeps actions beside the content they affect, and remains usable on desktop and mobile.

## Scope

- Redesign only the `profile` view in the creator frontend.
- Preserve the current profile-save, password-change, logout, credit, model-count, and conversation-count behavior.
- Keep the existing application shell, sidebar, top bar, light/dark themes, and backend contracts unchanged.
- Do not change the model settings page or any chat, image, or video creation workflow.

## Information Architecture

The page uses three visual levels:

1. A compact identity header containing the avatar, display name, account identifier, and credit balance.
2. A unified metrics strip for user ID, saved models, configured models, and conversation history.
3. A two-column account workspace with profile details as the primary panel and security/account actions as the secondary panel.

On narrow screens, the identity header, metrics, and account workspace stack into one column without horizontal scrolling.

## Components

### Identity Header

- Use one restrained panel instead of a large empty hero plus a separate profile card.
- Keep `个人信息` as the page title and show the account identity next to the avatar.
- Give the credit balance a distinct but non-promotional treatment so it is immediately visible.

### Metrics Strip

- Present the four account metrics in a consistent grid inside one grouped surface.
- Truncate the long user ID visually while preserving its full value through the existing content/title behavior.
- Avoid isolated nested cards and excessive shadows.

### Profile Details

- Keep nickname, phone, and avatar URL fields.
- Place `保存资料` at the bottom of this panel as its primary command.
- Keep feedback messages adjacent to the form that produced them.

### Security And Account Actions

- Keep the three password fields and `修改密码` in a dedicated security panel.
- Place `退出登录` in a visually separate danger area at the bottom of the secondary column.
- Never reuse model-list action layout classes for profile commands.
- Keep all button labels on one line at supported widths.

### Authorization Callback

- Preserve the existing production callback information and development-only controls.
- Render it as a low-priority account note below the main workspace so it does not compete with common actions.

## Visual Direction

- Quiet, work-focused account UI using neutral white/charcoal surfaces, crisp borders, and limited cyan/teal accents already present in the creator shell.
- Use an 8px maximum panel radius, restrained shadows, and clear typographic hierarchy.
- Avoid gradients as the main visual device, oversized headings, decorative cards, and page-wide empty bands.
- Keep light and dark themes equally legible.

## Data And Error Handling

All state and handlers remain unchanged. The template continues to read from the existing auth, model, credit, and conversation state. Loading, disabled, success, and error states stay attached to their current handlers; only their placement and presentation change.

## Verification

- Add a failing structural/style regression test before implementation.
- Verify the focused frontend tests and the complete frontend test suite.
- Inspect the real page at desktop and mobile widths in both light and dark themes.
- Confirm no overlap, horizontal overflow, wrapped command labels, or inherited model-row action layout.
- Run the required local Docker production build before release.
- After publishing, verify the production asset hash, profile page layout, API health, and that the API/MySQL containers were not rebuilt or restarted.

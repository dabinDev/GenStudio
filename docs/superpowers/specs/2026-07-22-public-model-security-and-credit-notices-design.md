# Public Model Security and Credit Grant Notices

## Purpose

Fix public-model authorization, make public models unmistakable in the creator
workspace, hide public models from ordinary users' settings, and notify users
when an administrator grants credits.

## Confirmed Root Causes

1. The generic `/api/models/*` routes currently treat every account with an
   admin role as able to edit a public model. This bypasses the existing
   `model:update`, `model:publish`, `model:unpublish`, and `model:delete`
   permission model for lower-privilege operator and viewer roles.
2. The creator settings list calls `filterSettingsModels` against every loaded
   model. It never removes public models for ordinary users.
3. Public-model serialization replaces `publicDescription` with an empty value
   for non-editors. The creator cannot use the administrator-authored
   description to distinguish public models.
4. Credit transactions already persist type, amount, reason, metadata, and
   creation time. They do not currently carry a user-facing grant notice or a
   persisted dismissal state.

## Scope

Included:

- Public-model authorization for every generic model mutation route.
- Creator settings visibility and editor-state hardening.
- Administrator-configured public-model accent colors and redesigned creator
  model cards for text, image, and video models.
- Persistent, dismissible credit-grant notifications for individual and batch
  administrator grants.
- Backend and frontend regression tests plus visual browser QA.

Excluded:

- Replacing the existing administrator console.
- A real-time push service. The creator will refresh credit notices at startup,
  after existing credit refreshes, and on a bounded polling interval.
- Notifications for ordinary model usage, refunds, or deductions.

## Authorization Design

Public models remain readable to all creator users and guests for generation.
Mutation is authorized per operation on the server; frontend state is never an
authorization source.

| Operation on a public model | Required permission |
| --- | --- |
| Read and generate | none |
| Edit configuration, choose primary model, or synchronize model list | `model:update` |
| Delete | `model:delete` |
| Publish | `model:publish` |
| Unpublish | `model:unpublish` |

Private models keep their current owner-only behavior. Creating a private
model remains available to a regular creator user. A request that creates a
public model requires the public publish permission in addition to the normal
create flow.

The model service will receive an explicit public-model authorization result
rather than a broad `is_admin` flag. Serialization will set `canEdit` for a
public model only when the caller has `model:update`. It will not reveal model
credentials to non-editors. Route tests will cover a normal user, operator,
viewer, admin, and super-admin where relevant.

## Creator Settings and Public Cards

The creator workspace continues to load public models so users can create with
them. Its Settings page applies a separate visibility rule:

- Ordinary users see only their own private models.
- Administrator accounts can see public models as read-only or editable based
  on the `canEdit` value returned by the server.

Each public model receives a `publicAccentColor` chosen by an administrator in
the admin model-center drawer. The control is a constrained swatch palette,
with a validated `#RRGGBB` value persisted on the model. Existing models use
capability defaults until a color is saved:

| Capability | Default accent |
| --- | --- |
| Text | cyan `#28C5FF` |
| Image | coral `#FF6B8A` |
| Video | green `#9EE841` |

The shared creator sidebar item is redesigned as a compact public-model card:

- A solid left accent rail and icon treatment use the saved accent color.
- The card labels the item as a platform model and keeps the capability label.
- It shows the administrator-provided public display name, public description,
  up to two public tags, and the configured credit price when applicable.
- The active card increases contrast and uses the same accent without changing
  its dimensions.
- Private model rows retain their quieter existing presentation.

Public descriptions and tags are intentionally safe for ordinary users and
will be returned in public serialization. Secret URLs and credentials remain
restricted to editors.

## Credit Grant Notices

Positive administrator adjustments create a notification payload inside the
existing credit transaction metadata:

```json
{
  "notification": {
    "kind": "admin_credit_grant",
    "delivery": "single",
    "dismissedAt": null
  }
}
```

Batch grants use `"delivery": "batch"`. The existing transaction reason is
the administrator-visible and creator-visible explanation. No new database
table is required.

The API exposes a CSRF-protected endpoint that only the recipient can call to
dismiss one eligible credit-grant transaction. It sets `dismissedAt` in that
transaction's metadata. The endpoint rejects another user's transaction and
non-grant transactions.

The creator auth store retains the credit transaction list already returned by
`/api/credits/me`. A pure frontend selector finds the newest undismissed grant.
The app displays it in a top-of-workspace snackbar with the grant amount,
batch or individual wording, and the reason. It has an explicit close control,
does not auto-dismiss, and advances to the next pending notice only after the
recipient dismisses the current one. It is refreshed at session initialization,
after normal credit refreshes, and at a conservative active-session interval.

## Tests and Verification

Backend tests:

- A regular user, operator, and viewer cannot mutate a public model through
  generic model routes.
- Authorized model roles can perform only their granted public-model actions.
- Public model serialization exposes safe display metadata but no credentials
  to non-editors.
- Individual and batch grants create the expected notice metadata.
- Only the credited user can dismiss an undismissed positive grant notice.

Frontend tests:

- The settings filter removes public models for non-admin users while retaining
  them for administrators.
- Public card helpers choose saved and fallback accents and safe public copy.
- Notification selection and wording handle single grants, batch grants,
  multiple pending grants, and dismissed grants.
- API and auth-store tests cover dismiss and transaction refresh behavior.

Visual QA uses a browser at desktop and mobile widths to confirm the public
model cards remain distinct, text fits, settings do not expose public models to
ordinary users, and the persistent snackbar is visible below the workspace
topbar without overlapping controls.

## Acceptance Criteria

1. No unprivileged account, including low-permission administrator roles, can
   edit, delete, publish, unpublish, synchronize, or switch a public model
   without its corresponding server-side permission.
2. Ordinary users never see public models in creator Settings, but can select
   and use them in the creator workspace.
3. Administrator-configured public models are visually distinguishable by
   color, identity, capability, tags, description, and price across text,
   image, and video workflows.
4. Positive individual and batch credit grants appear as a top-of-workspace
   snackbar until the credited user explicitly dismisses each notice.

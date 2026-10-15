# IMPLEMENTATION PROMPT: "Obsidian Ops" Redesign of AI Video Threat Recognition (Frontend)

> **To the coding agent:** You built this app. This prompt redesigns its **frontend only**. Backend, REST contract, auth flow and every existing route stay as they are. Work phase by phase (Section 8), keep `next build`, `tsc` and `eslint` green after every phase, and commit after each phase.
>
> **Rules that override everything below:**
> 1. **Inspect before assuming.** Where this prompt mentions a field, prop or endpoint shape you can't see in the brief (incident fields, rule `config` schema, pagination params, detection payload keys), open `src/types`, the API client and the existing components first. **Never invent backend fields or fake data.** If a widget needs data the API doesn't expose, derive it client-side from existing responses and label it honestly (e.g. "based on latest 200 incidents").
> 2. **Read the Next.js docs bundled in `node_modules/next/dist/docs/` (and any `AGENTS.md`/`CLAUDE.md` in the repo) before writing routing, caching or `Suspense` code.** Next 16.4 conventions differ from older versions.
> 3. **Protected media stays on authenticated blob fetching** (`useAuthenticatedBlob`). No plain `<img src>`/`<video src>` for protected files.
> 4. **`/live/capture` stays dependency-lean** (Section 4.5).
> 5. **Accessibility beats aesthetics.** If a visual effect and WCAG AA conflict, drop the effect.

---

## 1. Research digest (what we studied and what it changed)

Sources are mostly vendor documentation/marketing and design-practice articles. Treat them as pattern evidence, not benchmarks.

### 1.1 Security-product patterns → decisions

| Source | Pattern observed | Applied here |
|---|---|---|
| Verkada Command ([blog](https://verkada.com/blog/command-platform-device-user-management)) | Simplified left navigation with quick access to core areas; a Live page that merges video, alerts and access events into one real-time feed; a global Search reachable from anywhere | Slim icon rail (4.1), ⌘K command palette on every page, `/live` and dashboard feed combine incident events with camera state |
| Verkada via [RFP.wiki](https://www.rfp.wiki/vendors/verkada) | Event-linked video context shortens reconstruction of an incident | Incident detail is **evidence-first** (4.8) |
| Rhombus ([dashboard & video walls](https://www.rhombus.com/blog/customize-your-dashboard-video-walls-more-june-update), [2023 update](https://rhombus.com/blog/2023-june-product-update/), [alert trends](https://rhombus.com/blog/rhombus-systems-february-product-update/), [July 2026 console update](https://rhombus.com/blog/console-updates-july-2026/)) | Dashboard "dashlets" (live feeds, alerts, status, analytics); managing items from the timeline without leaving the player; alert-trend graphs; camera health notifications; loitering alerts with user-controlled thresholds | Composable dashboard widgets (4.2), detection timeline that acts on items in place (4.7), camera-health strip (4.9), loitering rule form exposes its threshold fields (4.11) |
| Genetec ([Plan Manager](https://resources.genetec.com/i/887787), [tiles](https://techdocs.genetec.com/r/en-US/Security-Center-User-Guide-5.12/About-tiles), [Plan Manager overview](https://www.jdsecurity.com.au/video-surveillance/video-management-systems/security-center-plan-manager)) | Floor-plan/map view with camera field-of-view and alarm locations; tile-based UIs lose spatial context; tiles use colored IDs for monitoring state and remember recent entities | **Site Twin** (Section 6): spatial view with FOV cones + threat pings; status color on camera identifiers; selection memory in the incident queue |
| Palantir Gotham ([overview](https://goldingresearch.substack.com/p/inside-palantir-gotham)) | Analyst workflow built from linked graph + map + timeline | Incident detail and Analysis report link three views: evidence, timeline, entity/track list |
| SOC UI design ([FuseLab](https://fuselabcreative.com/cybersecurity-dashboard-design/), [Skins Factory](https://www.theskinsfactory.com/uiux-design-questions-answers/why-does-visual-hierarchy-matter-in-security-operations-software), [wall-display case study](https://medium.com/@sarathb1998sb/threats-at-a-glance-soc-threat-intelligence-dashboard-case-study-cfca25f5c5eb)) | Dark theme standard for SOCs; severity encoded **twice** (color + text); color reinforced by icons/labels/shape; legibility at distance | Severity = color + icon shape + label everywhere (3.3); dark-only theme (3.1); large-type KPI tiles |

### 1.2 Technique decisions

| Topic | Finding | Decision |
|---|---|---|
| Glassmorphism ([ui-skills](https://www.ui-skills.com/skills/iart-ai/glassmorphism), [Superdesign](https://www.superdesign.dev/styles/glassmorphism), [UXMagic](https://uxmagic.ai/blog/what-is-glassmorphism), [SetProduct](https://www.setproduct.com/blog/liquid-glass-vs-glassmorphism)) | Don't stack `backdrop-filter` elements (re-blur cost compounds); a full-height glass sidebar janks on older Android; `backdrop-filter` makes the element a containing block for `position: fixed` descendants; text contrast must be tested against *real shifting content*, not a mockup; in 2026 it survives mostly as accent surfaces, not full layouts | "Glass budget" (3.4): glass only on floating layers over media/maps; **sidebar and tables are solid**; opaque fallbacks for `@supports`, `prefers-reduced-transparency`, `prefers-contrast`, and a manual "Lite" mode |
| R3F + React 19 ([v9 migration guide](https://r3f.docs.pmnd.rs/tutorials/v9-migration-guide), [scaling performance](https://r3f.docs.pmnd.rs/advanced/scaling-performance), [postprocessing issue #742](https://github.com/pmndrs/postprocessing/issues/742)) | R3F **v9** is the React 19-compatible line; on-demand rendering (`frameloop="demand"`), DPR capping, instancing and `performance` regression are the sanctioned levers; `@react-three/postprocessing` crashed the whole tree under React 19 StrictMode (the default in new Next 16 apps) until `postprocessing` v6.39.1 | R3F v9 + drei v10, **no postprocessing at all** (not needed; avoids the bug class), demand frameloop, DPR ≤ 1.5 |
| Charts ([LogRocket, updated June 2026](https://blog.logrocket.com/top-5-react-chart-libraries/), [PkgPulse](https://www.pkgpulse.com/guides/best-javascript-charting-libraries-2026)) | Recharts remains the practical default for React dashboards (SVG, SSR-friendly, v3 improves accessibility defaults) but is heavier and less granular than visx | **Recharts 3** for standard charts; hand-rolled SVG/CSS for sparkline, heatmap and detection timeline (no extra dependency) |
| Motion ([guide](https://dev.to/stacknotice/framer-motion-motion-react-animations-complete-guide-2026-3e7l)) | `framer-motion` is now the `motion` package (`motion/react`); `LazyMotion` + `m` cuts the bundle substantially | Migrate to `motion`, use `LazyMotion`/`domAnimation` + `MotionConfig reducedMotion="user"` |
| Next 16 ([static-route-runtime error doc](https://nextjs.org/docs/messages/static-route-runtime), [Cache Components](https://certificates.dev/blog/cache-components-in-nextjs)) | With Cache Components and Instant Navigations, uncached/runtime data outside `Suspense` fails prerender; `useSearchParams` needs a `Suspense` boundary; `ensureStatic = 'navigation'` isn't relaxed by `Suspense` or `instant = false` | Every URL-state hook behind `<Suspense>`; no `new Date()`/`Math.random()` in Server Components (clock/relative-time are client components); don't add `ensureStatic` anywhere |

**Unverified items you must check yourself** (research couldn't confirm): exact current versions of `three`, `@react-three/fiber`, `@react-three/drei`, `recharts`, `motion` (use `npm view <pkg> version peerDependencies`); whether Recharts 3 still needs a `react-is` override under React 19 (if `npm install` raises ERESOLVE on `react-is`, add an `overrides` entry matching the installed React version); whether `next build` on 16.4 prints per-route sizes (if not, use the Turbopack bundle analyzer or `@next/bundle-analyzer`, whichever the installed version supports).

---

## 2. Design vision: "Obsidian Ops"

**Mood:** a calm, cinematic night-shift control room. *Quiet until it matters*: chrome is near-monochrome; saturated color is reserved for state (severity, live, health) and one cyan accent. Premium through restraint, precision, depth and responsiveness, not neon.

**Five rules**
1. **Color is information.** Saturated hues appear only for severity, status, live indicators and the primary action.
2. **Severity is encoded twice or more** (color + icon shape + text label), never color alone.
3. **Depth by elevation tiers and hairline borders.** Glass is an exception for floating layers over media (3.4).
4. **Density is a setting.** Comfortable default, "Compact" toggle (row height 44px → 36px) persisted in `localStorage`.
5. **Motion = state change or new information.** Nothing decorative loops on data screens (Section 7).

**Light/dark decision:** **Dark-only** for v1. Reasons: video-centric product, SOC eye-strain norms, glass-over-video legibility, half the contrast-test surface. Tokens stay semantic so a light theme can be added later. Honor `prefers-contrast: more` with a high-contrast token override. Set `color-scheme: dark`.

---

## 3. Design system

### 3.1 Tokens (`src/app/globals.css`)

Keep existing variable names (`--background`, `--foreground`, `--primary`, `--muted`, `--border`, …) so current primitives keep working; add new ones through `@theme inline`. Values are OKLCH starting points; **`scripts/check-contrast.mjs` (Phase 0) is the authority**: adjust lightness until every pair passes.

```css
@theme inline {
  --color-background: var(--background);
  --color-surface-1: var(--surface-1);
  --color-surface-2: var(--surface-2);
  --color-surface-3: var(--surface-3);
  --color-sev-critical: var(--sev-critical);  --color-sev-critical-bg: var(--sev-critical-bg);
  --color-sev-high: var(--sev-high);          --color-sev-high-bg: var(--sev-high-bg);
  --color-sev-medium: var(--sev-medium);      --color-sev-medium-bg: var(--sev-medium-bg);
  --color-sev-low: var(--sev-low);            --color-sev-low-bg: var(--sev-low-bg);
  --color-ok: var(--ok);                      --color-ok-bg: var(--ok-bg);
  --font-sans: var(--font-geist-sans);
  --font-mono: var(--font-geist-mono);
  --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out-soft: cubic-bezier(0.65, 0, 0.35, 1);
}
:root {
  color-scheme: dark;
  --background:  oklch(0.145 0.012 260);
  --surface-1:   oklch(0.185 0.014 260);   /* cards, rail */
  --surface-2:   oklch(0.225 0.016 260);   /* raised, inputs */
  --surface-3:   oklch(0.270 0.018 260);   /* popovers, hover */
  --foreground:  oklch(0.960 0.005 260);
  --muted-foreground: oklch(0.720 0.020 260);
  --border:        oklch(1 0 0 / 0.08);
  --border-strong: oklch(1 0 0 / 0.16);
  --primary:     oklch(0.800 0.130 205);   /* cyan: brand, live, primary action */
  --primary-foreground: oklch(0.180 0.020 220);
  --ring:        oklch(0.800 0.130 205);
  --sev-critical: oklch(0.660 0.220 25);   --sev-critical-bg: oklch(0.660 0.220 25 / 0.14);
  --sev-high:     oklch(0.740 0.170 55);   --sev-high-bg:     oklch(0.740 0.170 55 / 0.14);
  --sev-medium:   oklch(0.840 0.140 92);   --sev-medium-bg:   oklch(0.840 0.140 92 / 0.14);
  --sev-low:      oklch(0.740 0.110 240);  --sev-low-bg:      oklch(0.740 0.110 240 / 0.14);
  --ok:           oklch(0.780 0.160 150);  --ok-bg:           oklch(0.780 0.160 150 / 0.14);
}
@media (prefers-contrast: more) { :root { --border: oklch(1 0 0 / 0.28); --muted-foreground: oklch(0.82 0.02 260); } }
```

Extend `src/lib/labels.ts`: each severity maps to `{ token, icon, label }`; each incident status maps to `{ variant, icon, label }`. Keep existing exports so call sites don't break.

### 3.2 Type, spacing, radius, iconography

- **Fonts:** Geist Sans + Geist Mono via `next/font` (self-hosted at build, no runtime request). Mono for IDs, track IDs, timestamps, coordinates, JSON. Enable `font-variant-numeric: tabular-nums` on all metrics and tables.
- **Scale (px/line-height):** 12/16 caption · 13/18 table/meta · 14/20 body · 16/24 lead · 20/28 h3 · 24/32 h2 · 32/40 h1 · 48/52 KPI numeral. Weights 400/500/600 only.
- **Spacing:** 4px base (4, 8, 12, 16, 24, 32, 48). Page gutter 24px desktop, 16px mobile. Radius: 6 (controls), 10 (cards), 16 (sheets/modals), 999 (pills).
- **Elevation:** `surface-1` + 1px `--border` (card) → `surface-2` (raised/input) → `surface-3` + `shadow-lg` (popover) → glass (floating over media only).
- **Icons:** `lucide-react`, 16/20px, stroke 1.75. Severity icons: critical `OctagonAlert`, high `TriangleAlert`, medium `CircleAlert`, low `Info`, ok `CircleCheck`. Lucide has no weapon glyphs: draw a small custom set in `src/components/icons/threat-icons.tsx` (20px grid, stroke 1.75, `currentColor`): firearm, blade, explosive, blunt, fire/smoke, tool, person-down, fight, crowd, zone-breach, loiter. Each takes `aria-hidden` and is always paired with a text label.

### 3.3 Status/severity language

| Severity | Token | Icon | Where shown |
|---|---|---|---|
| Critical | `--sev-critical` | `OctagonAlert` | badge: tinted `-bg` fill + 1px token border + token text/icon + label |
| High | `--sev-high` | `TriangleAlert` | same |
| Medium | `--sev-medium` | `CircleAlert` | same |
| Low | `--sev-low` | `Info` | same |
| Healthy/online | `--ok` | `CircleCheck` / dot | camera status, "all clear" |
| Offline | `--muted-foreground` | `CircleOff` | camera status |

Pending incidents get a left 3px severity-colored edge in lists. Never use severity colors for decoration.

### 3.4 Glass budget (strict)

Glass is allowed **only** on: (a) HUD chips/toolbars floating over video or the 3D scene, (b) dialogs/sheets/command palette, (c) the `/login` form card over the animated backdrop, (d) the critical-incident toast. **Not** on: sidebar, top bar, tables, cards in grids, long lists.

```css
.glass {            /* over dark UI/backdrops */
  background: oklch(0.20 0.015 260 / 0.62);
  border: 1px solid oklch(1 0 0 / 0.14);
  box-shadow: inset 0 1px 0 oklch(1 0 0 / 0.06), 0 8px 32px oklch(0 0 0 / 0.45);
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
}
.glass-hud {        /* over arbitrary VIDEO: worst case is a white frame */
  background: oklch(0.16 0.015 260 / 0.84);   /* alpha >= 0.82 keeps white text >= 4.5:1 over white */
  border: 1px solid oklch(1 0 0 / 0.16);
  backdrop-filter: blur(10px) saturate(130%);
  -webkit-backdrop-filter: blur(10px) saturate(130%);
}
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .glass, .glass-hud { background: oklch(0.18 0.015 260 / 0.96); }
}
@media (prefers-reduced-transparency: reduce), (prefers-contrast: more) {
  .glass, .glass-hud { background: var(--surface-2); backdrop-filter: none; -webkit-backdrop-filter: none; }
}
[data-perf="lite"] .glass, [data-perf="lite"] .glass-hud {
  background: oklch(0.18 0.015 260 / 0.94); backdrop-filter: none; -webkit-backdrop-filter: none;
}
```

Constraints:
- At most **3 glass elements visible in one viewport**, never nested or overlapping each other.
- Never put `position: fixed` children inside a glass parent (it becomes their containing block). Dialogs/toasts render through portals.
- Blur radius ≤ 16px. Don't animate `backdrop-filter` except a one-time 200ms entrance.
- Add a 1px border on every glass surface (it is also the contrast-edge for low-vision users).
- **Performance tier:** `usePerfTier()` (`src/lib/perf.ts`) returns `"full" | "lite"` from: user toggle (persisted `localStorage` key `perf.mode`), `navigator.connection?.saveData`, `navigator.deviceMemory <= 4`, `navigator.hardwareConcurrency <= 4`, or the 3D fallback trigger (6.5). It sets `data-perf` on `<html>`. Expose the toggle in the user menu ("Performance: Auto / Lite").

---

## 4. Per-page specifications

Global requirements for every page: skeletons that match final layout (no layout shift), per-widget `ErrorState` with retry (one failing widget never blanks the page), meaningful `EmptyState` with an action, `<h1>` per page, landmark regions, focus moves to `<h1>` on route change, any hook using `useSearchParams`/`usePathname` wrapped in `<Suspense>`.

### 4.1 App shell (`AppShell`, `AuthGuard`, new `CommandPalette`, `HotkeyProvider`, `MobileTabBar`)

- **Rail (≥1024px):** solid `surface-1`, 64px collapsed / 232px expanded (hover-expand with 150ms delay, pin toggle persisted). Groups: *Operate* (Dashboard, Live, Site, Detect, Incidents), *Configure* (Cameras, Zones, Rules), *Admin* (Users, Audit; hidden for non-admins as today). Active item: 2px primary inset bar + `surface-3` fill + `aria-current="page"`. Tooltips for collapsed labels. Pending-incident count badge on Incidents (from `/dashboard/stats`, refreshed with the feed).
- **Top bar (sticky, solid):** page title/breadcrumb; ⌘K/Ctrl-K search trigger; **system pill** (`cameras online x/y` + API reachability dot; click → `/cameras`); live clock (client-only, `tabular-nums`); user menu (name, role badge, Performance mode, Compact density, Shortcuts, Sign out).
- **Command palette** (hand-rolled on Radix Dialog; no `cmdk` dependency): searches routes, cameras (loaded list), recent incidents, actions ("New camera", "Open phone capture"). Arrow keys/Enter, `role="combobox"`+`listbox`. Glass dialog.
- **Hotkeys** (`src/lib/hotkeys.ts`, disabled inside inputs/textareas/contenteditable, never overriding browser/AT keys): `g d` Dashboard · `g l` Live · `g i` Incidents · `g s` Site · `g c` Cameras · `/` focus page search · `?` shortcuts dialog. Page-level keys in 4.7/4.8.
- **Mobile (<768px):** rail replaced by bottom tab bar (Dashboard, Live, Incidents, Detect, More→sheet), `padding-bottom: env(safe-area-inset-bottom)`, 48px targets.
- **Incident feed (`src/hooks/useIncidentFeed.ts`):** polls the existing `/incidents` (newest first) every 5s; pauses when `document.hidden`; diffs by id; exposes `{ items, newItems, lastUpdated, paused, setPaused }`. Consumers: sidebar badge, toasts, Site Twin pings, incidents page. **No backend change.** On new `high`/`critical` pending incident: custom sonner toast (glass, severity icon, thumbnail via authenticated blob, "Review" action → `/incidents/[id]`). Optional audio ping: off by default, enabled by an explicit user toggle (browsers require a gesture).
- **AuthGuard loader:** branded splash (logo + CSS radar sweep, no JS animation), `role="status"`, 150ms delay before showing to avoid flash.

### 4.2 Dashboard (`/`)

12-column grid, widgets independent (each with own loading/error):
1. **KPI strip (6 tiles):** Cameras online/total (ring gauge), **Pending** (largest, severity-tinted when > 0, links to `/incidents?status=pending`), High-risk, Last 24h (with sparkline), Verified, Dismissed. Source: `/dashboard/stats`. 48px mono numerals; count-up once on mount (Section 7).
2. **Incident trend** (8 cols): stacked area by severity; toggle 24h-hourly / 7d-daily. Source: derived from `/incidents` (fetch the newest N the API allows, target 200; caption "based on latest N incidents" if truncated). Recharts (6.6).
3. **Site Twin (compact)** (4 cols): the 3D/2D map (Section 6) at fixed 4:3, "Open full view" → `/site`.
4. **Severity distribution:** donut + legend with counts and %, each legend row with icon + label.
5. **Threat class breakdown:** horizontal bars using human labels from `labels.ts` (derive class from the incident's existing type/rule/label field; inspect types first).
6. **Camera health:** list of cameras: status dot, name, inference on/off + FPS, "last seen" only if the API provides it. Offline first.
7. **Live incident feed:** newest 8 incidents (thumbnail, severity badge, camera, relative time, status); new rows animate in (7.4); click → detail.
8. **"All clear" state:** when pending = 0, the Pending tile shows a calm `CircleCheck`, "No pending incidents", and the time of the last incident.

### 4.3 Live Stream (`/live`) *(top priority)*

Two-column hero (stacks on mobile):
- **Left: "Connect a phone camera" panel (glass over a subtle animated grid backdrop).** Large QR (`qrcode.react`, `level="M"`, **white tile with ≥ 4-module quiet zone and dark modules** for scan reliability regardless of theme; 240–280px). Below: the target URL in mono with **Copy** and **Open here** buttons. There is no backend session endpoint, so **do not fake a "phone connected" state**; show only: *Ready to scan*.
- **Right:** 3-step guide (Scan → Allow camera → Record & send) with icons, then the **HTTPS caveat as a proper `Alert`** (warning variant) with a collapsible "How to fix" (localhost vs. HTTPS tunnel/certificate) preserving the current text.
- **Below:** pipeline strip (static SVG): Record → Upload → Detect → Rules → Incident, one-line captions; decorative stagger on first view only.
- States: QR render failure → `ErrorState` with the raw URL still shown and copyable.

### 4.4 Detect (`/detect`)

- **Segmented tab control** (Radix Tabs, keep semantics) with a CSS-driven sliding indicator.
- **Video/Image tabs:** big keyboard-operable dropzone (`<button>` + hidden input; drag-over glow ring; accepts as today; client validation with specific messages for type/size). On file select: preview card (video poster frame / image thumbnail via `URL.createObjectURL`, revoke on cleanup), file name/size/duration, **Analyze** and **Remove**.
- **Progress:** upload as determinate bar from axios `onUploadProgress`, then "Analyzing" with a scan-line over the preview and stage text (Uploading → Detecting → Applying rules). **Cancel** via `AbortController`. Errors keep the file so the user can retry without re-selecting.
- **Result reveal:** verdict banner first, sections stagger in (7.7). Image tab adds a **before/after compare slider** (`role="slider"`, arrow-key operable) when annotated output exists.
- **Live Stream tab:** renders the same panel as 4.3 (shared `LiveQrCard`).

### 4.5 Phone capture (`/live/capture`) *(mobile-first, dependency-lean)*

- **Hard rules:** no `motion`, `recharts` or `three` imports; CSS transitions only; `AnalysisReport` imported without chart libraries; client JS delta ≤ +10% vs. the Phase 0 baseline.
- **Layout:** full-bleed live preview (`100dvh`, `object-fit: cover`, `playsInline muted`), safe-area padding. Two `glass-hud` elements only: **status pill** (top) and **controls bar** (bottom).
- **State machine** (explicit, typed): `idle → requesting → ready → recording → uploading → analyzing → result | error`.
  - `requesting/denied/unsupported/insecure`: a full-screen explainer with the specific cause (permission denied vs. non-HTTPS vs. no `getUserMedia`) and step-by-step recovery.
  - `ready`: 72px record button, camera-flip (toggle `facingMode`, hide if one camera), clear framing hint.
  - `recording`: button becomes stop-square, red pulse ring, elapsed `mm:ss` in the pill; `navigator.vibrate(30)` and a **Screen Wake Lock** when available (progressive enhancement, release on stop/visibility loss).
  - `uploading`: determinate progress via `onUploadProgress`; `analyzing`: indeterminate shimmer with stage text.
  - `result`: bottom sheet rises from 40% to full height with the mobile layout of `AnalysisReport` (single column, collapsible sections); **Record again** button always visible.
  - `error`: keep the recorded `Blob` in memory so **Retry upload** doesn't force re-recording.
- Targets ≥ 44×44px. Preserve existing MediaRecorder mime-type negotiation (don't regress iOS Safari).

### 4.6 `AnalysisReport` (shared component)

Order: **Verdict banner** ("No threats detected" in `--ok`, or "N weapon detections" / "Person down" in severity color) → **Totals** (KPI tiles) → **Weapon callouts** (large cards with threat icons; keep the exact labels "Firearm (gun)" and "Melee weapon (knife/blade)", plus the other `labels.ts` names) → **Findings by class** (row: icon, label, count, confidence bar + numeric %) → **Detection timeline** (4.7) → **Rule-trigger events** (severity badge, rule type, timestamp) → **Annotated frame gallery** (`DetectionFrame` grid → lightbox with ←/→/Esc, caption with timestamp and detections).
Desktop gets a sticky section nav with scroll-spy; mobile uses accordions. Add a **Copy summary** button (plain text of totals/findings). Fully usable when sections are empty (explicit "None detected").

### 4.7 `DetectionTimeline` (custom SVG)

Swimlane per class (or per track ID, toggle), x = time, marks sized by confidence, severity-colored for weapon/fall/violence flags. Hover/focus tooltip (class, confidence, track ID, time); click/Enter jumps the gallery to the nearest frame. Keyboard: Tab into the lane list, ←/→ moves between marks. Provide a visually hidden table equivalent. Respect reduced motion (no sweep).

### 4.8 Incidents (`/incidents`)

- **Toolbar (sticky):** search (`/` focuses), severity chips (All/Critical/High/Medium/Low), status tabs with counts (from `/dashboard/stats`), view toggle **Queue | Table**, density toggle, "Live · updated 3s ago" with pause button. Filters mirror to the URL (shareable; `Suspense`-wrapped).
- **Queue view (default, ≥1280px master-detail):** left list of incident cards (thumbnail via authenticated blob, severity badge, camera, rule, relative time, status; severity edge on pending), right **preview pane** showing the selected incident's primary evidence and quick actions. Below 1280px the preview pane collapses and a row opens the detail page.
- **Table view:** current table, restyled, sortable columns that the API already supports.
- **Live updates without disorientation:** auto-refresh every 5s (pause when hidden). If the user is hovering a row, has keyboard focus in the list, or scrolled > 1 screen, **do not reorder**; show a "↑ N new incidents" pill that applies on click. Otherwise new rows animate in (7.4). Selection and scroll position are preserved across refreshes.
- **Keyboard:** `j`/`k` or ↑/↓ move selection · `Enter` open · `v` verify · `d` dismiss · `[` / `]` previous/next page · `x` clear filters. **`v` and `d` open an inline confirm ("Enter to confirm · Esc to cancel")**, because the API offers no undo. Show `<kbd>` hints on the action buttons.
- Pagination preserved ("21–40 of N").

### 4.9 Incident detail (`/incidents/[id]`)

*Evidence-first* (Verkada/Gotham pattern):
- **Header:** breadcrumb, severity + status badges, **prev/next incident** (within the list context kept in `sessionStorage`), action bar **Verify / Dismiss** with shortcut hints (`v`, `d`, same inline confirm), ← back (`Esc`).
- **Main (8 cols): evidence viewer.** Large 16:9 player/image with reserved aspect ratio (no CLS), filmstrip of evidence thumbnails below (authenticated blob thumbnails; `←`/`→` change item), speed 0.5/1/2×, `,`/`.` frame-step when a video is focused, fullscreen, authenticated **Download**. Skeleton while the blob loads; explicit error with retry.
- **Side (4 cols, solid):** large severity banner, status, camera, rule, zone, absolute + relative timestamps (client-formatted), confidence if available, metadata as key/value rows with copy buttons, "Raw JSON" disclosure (mono).
- **After verify/dismiss:** badge cross-fades (7.5); toast offers **"Review next pending"**.
- **Mobile:** evidence on top full-width; **sticky bottom action bar** (thumb zone) with Verify/Dismiss; metadata in an expandable sheet.

### 4.10 Cameras (`/cameras`)

- Summary strip: online / offline / inference active counts.
- **Cards view (default) | Table view:** cards show the snapshot (`/cameras/{id}/snapshot` via authenticated blob, loaded only when visible via `IntersectionObserver`, manual **Refresh**, no auto-polling), name, source-type chip (rtsp/file/webcam/onvif), status dot with live pulse, inference `Switch` + FPS, overflow menu (Edit, Delete → confirm dialog). Table view keeps current columns for dense admin work.
- **Dialog form:** restyled; source-type-aware helper text and placeholder (e.g. `rtsp://user:pass@host:554/stream`); inline validation; submit shows pending state. All existing fields and validation preserved.
- Offline cameras sort first on the cards view.

### 4.11 Zones (`/zones`) and the polygon editor

- **Two panes:** zone list (left, with camera name and point count), editor (right). On mobile, list becomes a sheet.
- **Canvas editor (restyle + a11y, same contract: normalized polygon):** snapshot background dimmed 35%; fill `primary` @ 18%, 2px primary stroke with soft glow; vertices drawn 10px but **hit-tested at ≥ 24px** (WCAG 2.2 target size); hovering the first vertex when ≥ 3 points shows a "close" ring and snaps; other zones of the same camera render as faint outlines; DPR-crisp canvas with `ResizeObserver`; pointer events with `touch-action: none` (mobile drawing works).
- **Toolbar:** Undo (`Ctrl/Cmd+Z`), Remove last (`Backspace`), Close polygon (`Enter`), Clear (`Esc`, with confirm), icon+tooltip+shortcut. *(Nice to have, same data contract: drag a vertex to move it.)*
- **Accessible alternative:** a "Points" list under the canvas with editable numeric X/Y (0–1) per point, so zones can be authored/edited without a pointer.
- Snapshot load failure → `ErrorState` with retry; the editor stays disabled until the snapshot is loaded (as today).

### 4.12 Rules (`/rules`)

- Table restyled; severity badge, type chip with threat icon, camera/zone chips, cooldown formatted with units (stored unit unchanged), inline **Active** switch.
- **Dialog:** rule-type picker as selectable cards (icon + one-line description) for restricted-zone, loitering, person down, fight, crowd anomaly, weapon-carry. Camera select → zone select filtered by camera. **JSON config editor:** monospace textarea with live `JSON.parse` validation (inline message with position), **Format** button, and a per-type **Insert template** button. **Templates must come from the backend's actual rule-config schema/defaults found in the repo or existing form code. Do not invent keys.** If none can be found, omit the template button and say so in your final report.

### 4.13 Users (`/users`, admin-only)

Table with initials avatar (color from a small fixed palette hashed from email), role badge with icon (admin/operator/viewer), active `Switch`, dialog form (show/hide password). If the logged-in user edits themself, warn before role downgrade/deactivation. Preserve admin-only guard behavior.

### 4.14 Audit log (`/audit`, admin-only)

Log-style table: mono timestamps (absolute with relative tooltip), action chips tinted by verb (create/update/delete/verify/dismiss/login), resource-type icon, **expandable rows** showing any detail/payload the API returns (mono, copyable). Sticky filter bar (action, resource type, date range) with active-filter chips + Clear, mirrored to the URL (`Suspense`-wrapped). Pagination preserved. *(Optional, additive)* "Export current page as CSV" (client-side).

### 4.15 Login (`/login`)

- Split layout: left brand panel with a **CSS/SVG** animated radar-sweep + grid backdrop (no WebGL on the unauthenticated entry route); right glass form card.
- Email/password with show/hide, caps-lock hint, field-level errors, shake on failure (reduced-motion safe: border flash instead), submit spinner. **Demo credentials rendered as "Use demo account" chips that fill the form.** `?next=` redirect preserved; `useSearchParams` in a `Suspense` boundary. Success: 300ms "access granted" fade then navigate.

### 4.16 Site Twin (`/site`) *(new, additive route)*: see Section 6.

---

## 5. Component inventory

| Component / file | Status | Notes (glass / motion / 3D) |
|---|---|---|
| `src/app/globals.css` | changed | tokens (3.1), `.glass*`, reduced-motion/transparency rules |
| `src/lib/labels.ts` | extended | severity/status/class → `{token, icon, label}` |
| `src/lib/perf.ts`, `usePerfTier` | new | `data-perf` on `<html>`, WebGL gating |
| `src/lib/hotkeys.ts`, `HotkeyProvider`, `ShortcutsDialog` | new | |
| `src/hooks/useIncidentFeed.ts` | new | polling + diff, no API change |
| `src/hooks/useReducedMotionPref.ts` | new | wraps `matchMedia`; mirrors `MotionConfig` |
| `src/components/ui/*` (button, card, dialog, select, table, badge, input, label, alert, skeleton, separator, progress, tabs, sonner) | restyled | focus ring `--ring` 2px offset 2px; min target 24px (44px on capture); dialog = glass |
| `ui/severity-badge.tsx`, `ui/status-badge.tsx` (evolve `StatusBadges`) | new/changed | color + icon + label |
| `ui/kpi-tile.tsx`, `ui/sparkline.tsx`, `ui/ring-gauge.tsx` | new | count-up, SVG |
| `ui/segmented-control.tsx`, `ui/kbd.tsx`, `ui/dropzone.tsx`, `ui/compare-slider.tsx` | new | |
| `AppShell`, `Rail`, `TopBar`, `MobileTabBar`, `CommandPalette` | changed/new | palette = glass |
| `AuthGuard` | changed | branded splash |
| `LiveQrCard` | changed | shared by `/live` and `/detect` tab |
| `AnalysisReport`, `DetectionTimeline`, `DetectionFrame` | changed | SVG timeline; lightbox |
| `incidents/IncidentQueue`, `IncidentPreviewPane`, `EvidenceViewer`, `EvidenceFilmstrip` | new | authenticated blobs only |
| `cameras/CameraCard`, `zones/PolygonEditor` (restyle), `zones/PointsList`, `rules/ConfigEditor`, `rules/RuleTypePicker`, `audit/ExpandableRow` | new/changed | |
| `charts/TrendChart`, `SeverityDonut`, `ClassBars` (Recharts), `charts/ActivityHeatmap` (CSS grid) | new | lazy-loaded |
| `site/SiteTwin3D`, `site/SiteMap2D`, `site/SiteTwinSwitch`, `site/useCameraLayout` | new | only 3D usage in app |
| `icons/threat-icons.tsx` | new | custom SVG set |
| `app/(app)/site/page.tsx` | new route | |
| `/styleguide` (dev-only; `notFound()` in production) | new, optional | visual QA for tokens/components |

---

## 6. 3D & visualization plan

### 6.1 Where Three.js appears: **Site Twin** and nowhere else

An isometric, spatial view of the camera network with **FOV cones, live status and threat pings**, the web analogue of the floor-plan alarm view in Genetec Plan Manager. It appears (a) full-screen at `/site` and (b) compact in the dashboard (4.2).

**Considered and rejected** (state this in your final report):
- *Globe:* single-site product, backend has no geographic coordinates, it's eye candy without operational value; real VMS products use plans/maps.
- *3D incident replay:* no 3D data exists; instead the Analysis report/timeline gets 2D **track trails** (SVG polyline of bbox centers per track ID over the frame gallery), which uses data we really have.
- *MapLibre/deck.gl:* no geodata, heavy.

**Honest data constraint:** the API stores no camera positions. Positions live **client-side**: `localStorage["siteTwin.layout.v1"] = { [cameraId]: {x, z, yaw} }`, with a deterministic auto-layout (golden-angle spiral, normalized to the scene bounds) for cameras without a saved position. Show an **Edit layout** mode (drag on the ground plane, rotate with a handle/`Q`/`E`, **Reset layout**). Say plainly in the UI that layout is saved in this browser. Do not pretend this is shared state.

### 6.2 Stack

`three`, `@react-three/fiber` **v9**, `@react-three/drei` **v10**, `@types/three` (dev). R3F v8 is not React 19-compatible. **Do not install `@react-three/postprocessing`.** Pin exact installed versions in `package.json` after `npm view` checks. Import only the drei helpers used (`OrbitControls`, `Html`, `PerformanceMonitor`, optionally `Line`); avoid `drei` barrel-heavy helpers.

### 6.3 Scene design

- Perspective camera (FOV 35°) at an isometric angle; `OrbitControls` with `maxPolarAngle`, min/max distance, pan clamped to bounds, no auto-rotate.
- Ground: dark plane (`--background` tint) + thin grid lines (single `LineSegments` geometry); soft vignette via a CSS overlay (not post-processing).
- Camera node: small body mesh + FOV cone (transparent, `depthWrite: false`, ≤ 24 segments). Colors from the same CSS tokens (read once via `getComputedStyle` into `THREE.Color`, re-read on `data-perf`/theme change). Online = primary, offline = muted gray + dashed outline, **alerting = severity color + ring**.
- **Threat ping:** on a new incident from `useIncidentFeed` for camera X, spawn an expanding ring at X's node (3s life, ease-out, opacity 0.8→0). Click on a node → select camera: side panel (DOM, not WebGL) shows its name, status, snapshot (authenticated blob), recent incidents, link to `/cameras` and `/incidents?camera=…` if that param exists.
- **Labels:** drei `<Html>` only for hovered/selected/alerting nodes (≤ 5 at once), so text stays crisp and accessible.
- Meshes shared via a single geometry/material per kind; switch to `<Instances>` when cameras > 50.

### 6.4 Performance budget

| Item | Budget |
|---|---|
| Canvas | `frameloop="demand"`; invalidate only on interaction, data change, or while a ping/pulse is alive |
| DPR | `[1, 1.5]`, `performance={{ min: 0.5 }}` |
| Draw calls | < 100 for 50 cameras |
| Antialias | on desktop, off for `(pointer: coarse)` |
| Shadows / postprocessing / env maps | none |
| 3D chunk | loaded **only** on `/site` and the dashboard widget, via `next/dynamic` with `ssr: false` **inside a Client Component** wrapper, in `<Suspense>`, started after `requestIdleCallback`; target ≤ ~300 KB gzipped for the entire 3D chunk (verify with the analyzer); **must not appear in the initial JS of any other route** |
| Frame rate | ≥ 55 fps with 50 cameras on a mid-range integrated-GPU laptop |

### 6.5 Fallback (non-WebGL and low-end)

`SiteMap2D` renders the **same layout, statuses, selection and pings** as inline SVG (CSS `@keyframes` for pings). It is used when: WebGL2/WebGL unavailable (`canvas.getContext` probe in `usePerfTier`), `webglcontextlost` fires, `PerformanceMonitor` reports decline twice (toast: "Switched to 2D map for performance"), `data-perf="lite"`, or the user picks 2D via `SiteTwinSwitch`. Both views sit beside a real **camera list** (keyboard/AT-accessible); the 3D canvas itself is `aria-hidden` with `aria-describedby` pointing to that list.

### 6.6 Charts

- **Recharts 3**: `TrendChart` (stacked area by severity), `SeverityDonut`, `ClassBars` (horizontal). Why: SVG, composable, accessibility defaults (`accessibilityLayer`), widely used with this stack. Load via `next/dynamic` + skeleton; wrap in `ResponsiveContainer` with an explicit parent height to avoid CLS.
- **Custom (no dependency):** `Sparkline` (SVG path), `ActivityHeatmap` (hour × weekday CSS grid, optional on the dashboard), `DetectionTimeline` (4.7).
- Rules: series colors come from severity tokens; **direct labels or legends with icons**, never color-only; every chart has a "View as table" `<details>` with the same data; tooltips are keyboard-reachable; `isAnimationActive={!reducedMotion}`; no gradients that reduce contrast below 3:1 for graphical objects.

---

## 7. Animation spec

Library: `motion` (`motion/react`) with `LazyMotion features={domAnimation}` + `m.*` components, wrapped in `<MotionConfig reducedMotion="user">`. Migrate the few existing `framer-motion` usages to `motion/react`, then remove `framer-motion`. Everything on `/live/capture` and `/login` uses **CSS only**.

Duration tokens: **120ms** micro · **200ms** UI · **320ms** panels · **480ms** reveals · count-up **600ms**. Easings: `--ease-out-expo` for entrances, `--ease-in-out-soft` for moves. Animate **only `transform` and `opacity`** (plus `background-color`/`border-color` for highlights); never width/height/top/left.

| # | What | Trigger | Motion | Reduced-motion behavior |
|---|---|---|---|---|
| 1 | Page enter | route change | content fades + rises 8px, 200ms, `ease-out-expo`; **no exit animation** (avoids App Router conflicts) | instant |
| 2 | KPI count-up | first mount only | numerals 0→value, 600ms ease-out | instant final value |
| 3 | Online/live dot | status = online | 2s infinite ring (scale 1→2.2, opacity .6→0), `transform/opacity` only | static ring, no loop |
| 4 | New incident row | feed adds item | slide-down 240ms + background highlight fading over 2.5s; if `critical`, one 1.2s border glow ×2 (not infinite) | highlight color only, no motion |
| 5 | Status change | verify/dismiss success | badge cross-fade 160ms | instant |
| 6 | Pending-critical emphasis | critical & pending | slow 2.4s pulse on its badge; **≤ 3 such elements at once** | static emphasized border |
| 7 | Report reveal | result received | sections stagger 60ms, total ≤ 480ms | all visible at once |
| 8 | Detect processing | analyzing | scan-line sweeps preview, 1.6s linear infinite | stage text + progress only |
| 9 | Dialog / sheet | open/close | dialog: scale .98→1 + fade, 160ms; capture sheet: spring (stiffness 300, damping 30) | fade only |
| 10 | Charts | first render | draw-in 600ms once | no animation |
| 11 | Site Twin ping | new incident | ring expands 0→~3 scene units over 3s, opacity .8→0 | static highlight ring 3s |
| 12 | Site Twin select | click node | camera eases to node, 600ms `ease-in-out-soft` | jump cut |
| 13 | Toast | event | sonner defaults; critical variant slides in 200ms | fade |

**Never animate:** live-updating table cell values, loading numbers, anything that loops purely for decoration on data screens, parallax, route exits. Global CSS safety net:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.001ms !important; animation-iteration-count: 1 !important; transition-duration: 0.001ms !important; scroll-behavior: auto !important; }
}
```

---

## 8. Implementation plan (ordered phases; no calendar estimates)

**Phase 0: Baseline & guardrails.** Create a branch. Record baselines: `next build` output, bundle analysis for `/live/capture` and `/`, Lighthouse (mobile) for `/login`, `/`, `/live/capture`, `/incidents`, and screenshots of every page. Add `scripts/check-contrast.mjs` (devDependency `culori`) that converts token pairs (including glass tints over pure white and pure black frames) and asserts ≥ 4.5:1 text / ≥ 3:1 UI + large text. Add Playwright (`@playwright/test`, `@axe-core/playwright`) with a smoke-test skeleton. Add an `scripts/check-protected-media.mjs` grep that fails on `<img src=`/`<video src=` pointing at `/evidence` or `/snapshot`.

**Phase 1: Tokens & primitives.** `globals.css` tokens, fonts, glass utilities, reduced-motion/transparency rules; `usePerfTier`; restyle all primitives listed in Section 5; extend `labels.ts`; add threat icons; dev-only `/styleguide`. *Exit:* contrast script passes; build/tsc/eslint clean.

**Phase 2: Shell & entry.** `AppShell` (rail, top bar, mobile tab bar), `AuthGuard` splash, `CommandPalette`, hotkeys, `useIncidentFeed`, toasts, Login. *Exit:* all routes still reachable by role; `?next=` works.

**Phase 3: Core operations pages.** Incidents (queue/table, keyboard) → Incident detail (evidence viewer) → `AnalysisReport` + `DetectionTimeline` + `DetectionFrame` → Detect → `/live` + `LiveQrCard` → `/live/capture` (state machine, CSS-only). *Exit:* phone-capture happy path and error paths pass in Playwright with fake media device flags.

**Phase 4: Configuration pages.** Cameras (cards/table), Zones (editor restyle + points list), Rules (type picker, JSON editor), Users, Audit. *Exit:* CRUD parity checklist (Section 9) passes.

**Phase 5: Dashboard, charts, Site Twin.** Install Recharts and the R3F stack; build chart components; `SiteMap2D` first (it doubles as the fallback), then `SiteTwin3D`, `/site`, dashboard widgets. *Exit:* 3D chunk absent from other routes' initial JS; WebGL-disabled test passes.

**Phase 6: Polish & hardening.** Motion pass against the Section 7 table; `motion` migration and `framer-motion` removal; axe + keyboard audit; Lighthouse; cross-browser checks (Safari `-webkit-backdrop-filter`, iOS `getUserMedia`/MediaRecorder, Firefox); remove dead code; final report.

### Dependencies

| Package | Why | Compat note |
|---|---|---|
| `motion` (replaces `framer-motion`) | motion with `LazyMotion` | React 19 supported; test one reported StrictMode edge case in dev |
| `recharts@^3` | charts | verify React 19 peer deps; possible `react-is` override |
| `three`, `@react-three/fiber@^9`, `@react-three/drei@^10`, `@types/three` | Site Twin | R3F **9.x required for React 19**; don't add postprocessing; load only client-side |
| `culori` (dev) | contrast script | none |
| `@playwright/test`, `@axe-core/playwright` (dev) | e2e + a11y gates | none |
| `@next/bundle-analyzer` (dev, only if Turbopack analyzer isn't available) | size checks | none |

**Explicitly not adding:** `@react-three/postprocessing`, `cmdk`, `deck.gl`/`maplibre`, `gsap`, `zustand`, `lenis`, any UI kit.

### Risks and mitigations

| Risk | Mitigation |
|---|---|
| Next 16 prerender failures from runtime data (`Date`, random, `searchParams`) | clocks/relative time in Client Components; URL-state hooks in `Suspense`; no `ensureStatic` |
| R3F double-mount under StrictMode; WebGL context loss | disposal in cleanup; `webglcontextlost` → 2D fallback; no postprocessing |
| `backdrop-filter` jank / containing-block trap | glass budget (3.4); portals; Lite mode |
| 5s polling flooding the UI | pause when hidden; "N new" pill pattern; diff by id |
| iOS capture quirks (HTTPS, user gesture, mime types) | keep existing negotiation; explicit explainer states; test on real device |
| Bundle growth hurting capture page | CSS-only route; analyzer gate (+10% max) |
| Unknown backend field shapes | inspect types first; derive client-side; label derived data |

---

## 9. Acceptance criteria (all must be demonstrably met; report results)

**Build & static checks**
- `next build`, `tsc --noEmit` and `eslint` pass with **zero new warnings/errors** and zero new `any`.
- No hydration warnings or console errors in a production run (`next start`) across all routes.
- `check-protected-media` script passes (no plain `<img>`/`<video>` for protected files).

**Accessibility**
- `check-contrast.mjs`: every text/background token pair ≥ 4.5:1 (≥ 3:1 for large text, icons, control borders, chart marks), **including `.glass-hud` over a pure-white and a pure-black frame**.
- axe-core (Playwright) shows **0 serious/critical** violations on every route at 1440×900 and 390×844.
- Keyboard-only run-through of each page: no traps, visible focus (2px ring, ≥ 3:1), all shortcuts listed in the `?` dialog, interactive targets ≥ 24×24 CSS px (≥ 44px on `/live/capture`).
- With `prefers-reduced-motion: reduce` emulated: `document.getAnimations().filter(a => a.effect.getComputedTiming().iterations === Infinity).length === 0`, and count-ups/pings/reveals are instant/static.
- With `prefers-reduced-transparency`/`prefers-contrast: more` emulated: computed `backdrop-filter` is `none` on all glass elements.

**Performance**
- Lighthouse mobile (production build, default throttling): **Performance ≥ 90** on `/login` and `/live/capture`; **≥ 80** on `/` and `/incidents`; **CLS ≤ 0.05** on all four; LCP ≤ 2.5s and TBT ≤ 200ms on `/login` and `/live/capture`.
- `/live/capture`: client JS ≤ baseline +10%; module graph contains no `motion`, `recharts` or `three`.
- 3D chunk is absent from the initial JS of every route except `/site` (and loads async on the dashboard); Site Twin sustains ≥ 55 fps with 50 mock cameras on a mid-range integrated GPU; DPR ≤ 1.5.
- A script counts computed `backdrop-filter` elements in the viewport on each page: **≤ 3**.

**Fallbacks**
- With WebGL disabled (e.g. Chromium `--disable-gpu`/`--disable-webgl`), `/site` and the dashboard widget render `SiteMap2D` with the same data and **no console errors**.
- Layout persists in `localStorage`; **Reset layout** works; the UI states layout is browser-local.

**Feature parity (Playwright smoke tests, one per bullet)**
- Login success/failure and `?next=` redirect; role-based nav (operator doesn't see Users/Audit; direct URL is guarded as before).
- Dashboard stats render from `/dashboard/stats`; recent incidents link to detail.
- `/live` QR renders and encodes the `/live/capture` URL; HTTPS note visible; `/detect` Live tab shows the same card.
- `/live/capture` (fake media device): permission-denied state, record → stop → upload progress → report; failed upload retains the blob and retries.
- `/detect` video and image upload → report with totals, per-class findings, explicit weapon callouts ("Firearm (gun)", "Melee weapon (knife/blade)"), timeline, rule events, annotated frames.
- Incidents: filters (search/severity/status), 5s auto-refresh with "N new" pill, pagination, keyboard `j/k/Enter/v/d`; detail: evidence playback and authenticated download, verify/dismiss.
- Cameras CRUD (all four source types), inference toggle/FPS; Zones: draw, undo, remove, close, clear, save as normalized polygon on the authenticated snapshot, points-list editing; Rules CRUD incl. JSON config validation; Users CRUD (admin); Audit filters + pagination.

**Final report (required deliverable)** listing: installed versions (from `npm ls`), measured Lighthouse/bundle numbers vs. Phase 0 baselines, any acceptance item not met and why, which data was derived client-side, whether rule-config templates were possible, and the rejected 3D options with reasons.

---

## 10. Guardrails (do not)

- Do not change backend code, endpoints, auth storage (JWT in `localStorage`) or the axios interceptor behavior.
- Do not downgrade Next/React/Tailwind or use the pages router.
- Do not invent API fields, metrics or placeholder data; never show a fake "connected"/"live" state the system can't verify.
- Do not use glass on tables, the sidebar or in nested/overlapping layers.
- Do not add decorative infinite animations to data screens.
- Do not load Three.js, Recharts or `motion` on `/live/capture` or `/login`.
- Do not remove or rename any existing route; the only new route is `/site` (and the dev-only `/styleguide`).

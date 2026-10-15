# AI Video Threat Recognition — Frontend Strategy

**Project:** AI Video Threat Recognition  
**Owner:** Frontend Engineering  
**Status:** Draft  
**Sprint Alignment:** S0–S13 per Sprint Plan

---

## 1. Executive Summary

Build a modern, production-grade frontend for the AI Video Threat Recognition system. The frontend must support video/image upload, live streaming via QR code access, real-time threat detection visualization, scheduling, and operator review workflows. All development follows the sprint plan (S0–S13) in `AI_Video_Threat_Recognition_Fast_Ship_Sprint_Plan.html`.

---

## 2. Technology Stack

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Framework | Next.js | 14+ (App Router) | Server Components, SSR, SEO, streaming |
| Language | TypeScript | 5.x | Type safety, refactoring confidence |
| Styling | Tailwind CSS | 3.x | Utility-first, rapid UI, dark mode ready |
| Component Library | shadcn/ui | Latest | Accessible, customizable, no-lock-in |
| Icons | Lucide React | Latest | Clean, consistent iconography |
| Animations | Framer Motion | Latest | Smooth micro-interactions |
| Forms | React Hook Form + Zod | Latest | Schema validation, type safety |
| State Management | Zustand | Latest | Lightweight, server-state agnostic |
| Server State | TanStack Query (React Query) | Latest | Caching, pagination, mutations |
| HTTP Client | Axios | Latest | Interceptors, progress tracking |
| Real-time | Socket.io-client | Latest | Live alerting, WebSocket fallback |
| File Upload | UploadThing / Dropzone | Latest | Drag-and-drop, chunked uploads |
| Date Handling | date-fns | Latest | Lightweight, tree-shakeable |
| Linting | ESLint + typescript-eslint | Latest | Type-aware linting |
| Formatting | Prettier | Latest | Consistent formatting |
| Lint Config | `eslint-config-next` + `eslint-plugin-react-hooks` | | Next.js best practices |

---

## 3. Application Architecture

```
frontend/
├── app/                    # Next.js App Router
│   ├── (auth)/             # Auth group (login, register)
│   ├── (dashboard)         # Dashboard group
│   │   ├── incidents/      # Incident list + detail
│   │   ├── upload/         # Video/image upload page
│   │   ├── live/           # Live stream viewer
│   │   ├── schedule/       # Content scheduling
│   │   └── dashboard/      # Stats & overview
│   └── layout.tsx          # Root layout
├── components/             # Shared UI components
│   ├── ui/                 # shadcn/ui components
│   ├── detection/          # Detection result cards
│   ├── video/              # Video player with overlay
│   └── layout/             # Layout primitives
├── lib/                    # Utilities
│   ├── api.ts              # Axios instance + interceptors
│   ├── socket.ts           # Socket.io client
│   └── utils.ts            # Helpers (cn, formatDate, etc.)
├── hooks/                  # Custom React hooks
│   ├── useDetections.ts
│   ├── useIncidents.ts
│   └── useLiveStream.ts
├── types/                  # TypeScript type definitions
│   └── index.ts
├── store/                  # Zustand stores
│   └── useAppStore.ts
├── public/                 # Static assets
│   └── qrcode/             # QR code assets
├── eslint.config.js        # ESLint configuration
├── tailwind.config.js      # Tailwind config
├── tsconfig.json           # TypeScript config
└── next.config.js          # Next.js config
```

---

## 4. Core Features

### 4.1 Live Stream Upload (Priority: High)

**Requirement:** Users can scan a QR code with their mobile camera to access a mobile-optimized upload page and stream video live.

**Implementation:**

- **QR Code Generation:** Generate QR code pointing to `https://<domain>/live` using `qr-code-styling` or `qrcode.react`.
- **Mobile Capture Page:** Mobile-optimized page at `/live` with camera access (`navigator.mediaDevices.getUserMedia`).
- **WebRTC / HLS Upload:** Stream video chunks to backend via WebSocket or HTTP chunked upload.
- **Backend Endpoint:** `POST /api/stream` accepts chunked video data; stores temporary segments.
- **Backend Processing:** Worker processes stream chunks in real-time, emits detection triggers via WebSocket.
- **Client View:** Desktop view shows live feed with detection overlay boxes.

**API Contract:**

```http
POST /api/live/stream
Content-Type: multipart/form-data
Body: { cameraId: string, videoChunk: File }
Response: { streamId: string, streamUrl: string, sessionId: string }
```

**WebSocket Events:**

- `stream.started` — stream session created
- `detection.event` — trigger event (weapon, crowd, etc.)
- `stream.ended` — stream session closed

---

### 4.2 Video Upload

**Requirement:** Upload pre-recorded video files for threat detection analysis.

**Implementation:**

- Drag-and-drop file upload area (React Dropzone).
- File validation: `.mp4`, `.avi`, `.mov`, `.webm`; max 500MB.
- Progress bar with bytes uploaded / total.
- Background processing via `POST /api/detect`.
- Polling interval: every 2 seconds until status = `completed`.
- Display annotated frames with bounding boxes + trigger timeline.

**API Contract:**

```http
POST /api/detect
Content-Type: multipart/form-data
Body: { video: File }
Response: { total_frames, detections: [...], events: [...] }
```

**Response Model:**

```json
{
  "total_frames": 175,
  "detections": [
    {
      "timestamp": 2.4,
      "class_name": "firearm",
      "confidence": 0.515,
      "bbox": [62.7, 229.8, 138.4, 288.3],
      "is_threat": true,
      "track_id": -1,
      "weapon": true,
      "weapon_conf": 0.515,
      "frame_image": "data:image/jpeg;base64,..."
    }
  ],
  "events": [
    {
      "rule": "weapon",
      "severity": "high",
      "timestamp": 2.4,
      "tracker_ids": [-1],
      "details": {}
    }
  ]
}
```

---

### 4.3 Image Upload

**Requirement:** Upload single images for threat detection.

**Implementation:**

- Same upload UI as video, restricted to image types (`.jpg`, `.jpeg`, `.png`, `.webp`).
- Single image processed once; result shown immediately.
- Highlight detected threats with bounding boxes on the image.

**API Contract:** Same as video detection but accepts image MIME types.

---

### 4.4 Rule-Based Detection Results

**Supported Rules (from Sprint Plan):**

| Rule | Severity | Trigger Condition |
|------|----------|-------------------|
| `weapon` | High | Weapon-bearing track in zone ≥ dwell_seconds |
| `violence_detected` | High | Violence model detects fight/assault |
| `person_down` | High | Person bounding box aspect ratio > 1.5 (horizontal) |
| `crowd_anomaly` | Medium | Crowd count deviates from baseline |
| `altercation` | High | Two tracks within 80px moving together |
| `loitering` | Low | Track residency > dwell_seconds threshold |

**Detection Details Format:**

```json
{
  "timestamp": 2.4,
  "class_name": "firearm",
  "confidence": 0.515,
  "bbox": [62.7, 229.8, 138.4, 288.3],
  "is_threat": true,
  "track_id": 1,
  "weapon": true,
  "weapon_conf": 0.515,
  "fall": false,
  "violence": false
}
```

**Rule Event Format:**

```json
{
  "rule": "weapon",
  "rule_name": "Weapon Detection",
  "severity": "high",
  "timestamp": 2.4,
  "tracker_ids": [-1],
  "details": { "bbox": [62.7, 229.8, 138.4, 288.3] }
}
```

---

### 4.5 Incident Management & Review Workflow (S9)

**States:** `DETECTED` → `PENDING_REVIEW` → `VERIFIED` / `DISMISSED`

**Operator Actions:**

- Verify incident → `VERIFIED`, record `verified_by_id`, `verified_at`
- Dismiss incident → `DISMISSED`, record `verified_by_id`, `resolved_at`

**API Endpoints:**

- `GET /incidents/` — paginated list with filters (status, severity, rule_type, date range)
- `GET /incidents/{id}` — full incident details with evidence
- `POST /incidents/{id}/verify` — `{ verified: boolean }`
- `POST /incidents/{id}/dismiss`

**UI Requirements:**

- Table view with pagination, server-side filtering
- Incident detail page: video clip, snapshot, trigger details, confidence
- Audit log: who verified/dismissed and when

---

### 4.5.1 Incident List Table Columns

| ID | Event Type | Severity | Status | First Seen | Actions |
|----|-----------|----------|--------|------------|---------|
| 1024 | weapon | High | Pending Review | 2024-01-15 14:23 | [Verify] [Dismiss] |

---

### 4.5.2 Incident Detail View

- Large annotated frame (with bounding boxes)
- Trigger timeline (all detections across frames)
- Rule breakdown: which rules fired, why
- Verify / Dismiss buttons (role-gated: ADMIN / OPERATOR)
- Audit trail: who acted and when

---

### 4.6 Content Scheduling (S9/S13)

**Requirement:** Schedule video/image uploads for future processing.

**Implementation:**

- Schedule form: select file, choose date/time, select camera/zone
- Server-side cron or task queue (Celery / Redis Beat) picks up scheduled jobs
- Upload at scheduled time, run detection pipeline
- Dashboard shows scheduled vs completed jobs

**API Endpoints:**

- `POST /api/schedule/` — create scheduled upload
- `GET /api/schedule/` — list scheduled jobs
- `DELETE /api/schedule/{id}` — cancel scheduled job

**Fields:**

```json
{
  "camera_id": 1,
  "zone_id": null,
  "scheduled_at": "2025-01-15T14:00:00Z",
  "file": "file.mp4",
  "status": "pending"
}
```

---

### 4.7 Dashboard & Stats (S9)

**Dashboard Cards:**

- Total Cameras
- Online Cameras
- Total Incidents
- Pending Review
- Verified / Dismissed
- Incidents Last 24h

**API:** `GET /dashboard/stats`

---

### 4.8 Security & RBAC (S10)

**Roles:** `ADMIN`, `OPERATOR`, `VIEWER`

**Permissions:**

| Action | ADMIN | OPERATOR | VIEWER |
|--------|-------|----------|--------|
| View Dashboard | ✅ | ✅ | ✅ |
| Upload Video | ✅ | ✅ | ❌ |
| Verify/Dismiss | ✅ | ✅ | ❌ |
| Manage Rules | ✅ | ✅ | ❌ |
| Manage Users | ✅ | ❌ | ❌ |
| View Audit Log | ✅ | ✅ | ❌ |

**Auth Flow:**

1. `POST /auth/login` → returns JWT access token
2. Store token in `httpOnly` cookie or `localStorage`
3. Include `Authorization: Bearer <token>` header
4. `POST /auth/logout` → clear token

---

## 5. UI/UX Design System

### 5.1 Design Principles

- **Dark theme first** — security dashboard aesthetic
- **High contrast** — critical alerts stand out (red for threats)
- **Responsive** — works on desktop (operator) and mobile (field upload)
- **Accessible** — ARIA labels, keyboard navigation, color contrast ≥ 4.5:1
- **Fast** — < 2s initial load, skeleton skeletons for loading states

### 5.2 Color Palette

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| Primary | `#2563eb` | `#3b82f6` | Primary actions |
| Success | `#22c55e` | `#4ade80` | Verified, clear |
| Warning | `#f59e0b` | `#fbbf24` | Medium severity |
| Danger | `#ef4444` | `#f87171` | High severity, threats |
| Neutral | `#64748b` | `#94a3b8` | Secondary text |

### 5.3 Component Library (shadcn/ui)

- Button, Input, Select, Dialog, Popover, ScrollArea, Table, Badge, Alert, Progress, Sheet, Tabs, Card, Badge, Avatar, Label

---

## 6. ESLint Configuration

**File: `eslint.config.js`**

```javascript
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactPlugin from "eslint-plugin-react";
import reactHooksPlugin from "eslint-plugin-react-hooks";
import nextPlugin from "@next/eslint-plugin-next";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  reactPlugin.configs.flat.recommended,
  {
    plugins: {
      "react-hooks": reactHooksPlugin,
    },
    rules: {
      ...reactHooksPlugin.configs.recommended.rules,
      "react-hooks/exhaustive-deps": "warn",
    },
  },
  nextPlugin.configs.recommended,
  {
    ignores: ["node_modules", ".next", "out", "dist"],
    rules: {
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "react/no-unescaped-entities": "off",
      "@next/next/no-html-link-for-pages": "warn",
    },
  }
);
```

**ESLint Scripts:**

```json
"lint": "next lint",
"lint:fix": "next lint --fix"
```

---

## 7. Component Architecture

### 7.1 Detection Display Card

```
DetectionCard
├── FrameImage (annotated frame with bounding boxes)
├── DetectionHeader (timestamp, track_id, class_name)
├── ConfidenceBadge (color-coded by severity)
├── MetaBox (bbox coordinates, feature flags)
└── RuleEventTag (if part of a rule trigger)
```

### 7.2 Video Player with Annotation Overlay

- HTML5 `<video>` element
- Canvas overlay for drawing bounding boxes in real-time
- Frame scrubber to scrub through detections
- Playback speed control (0.5x, 1x, 2x)

### 7.3 Timeline View

- Horizontal timeline of all detections in the video
- Click to jump to frame
- Color-coded by rule type

---

## 8. Implementation Roadmap

| Phase | Sprint | Deliverable |
|-------|--------|-------------|
| 1 | S6–S7 | Upload page + detection display (video/image) |
| 2 | S8 | Weapon detection integration + threat badges |
| 3 | S9 | Incident list + dashboard + review workflow |
| 4 | S10 | Auth + RBAC + privacy zones |
| 5 | S11 | Live stream upload + QR code |
| 6 | S12 | Load testing UI + performance monitoring |
| 7 | S13 | Scheduling UI + runbook + final polish |

---

## 9. Quality Gates

- ESLint: `npm run lint` must pass with 0 errors
- TypeScript: `tsc --noEmit` must pass
- Prettier: All files formatted
- Accessibility: Lighthouse accessibility score ≥ 90
- Performance: Lighthouse performance ≥ 80

---

## 10. Immediate Next Steps

1. Initialize Next.js project in `frontend/`
2. Install shadcn/ui components
3. Create ESLint + Prettier configs
4. Build `UploadPage` (video + image)
5. Build `DetectionDisplay` component (annotated frames)
6. Build `IncidentsPage` (list + detail)
7. Build `Dashboard` (stats)
8. Integrate with backend `/api/detect` endpoint
9. Add live stream page with QR code
10. Add scheduling page

---

## Appendix: Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_APP_NAME=AI Video Threat Recognition
```

---

**End of Strategy Document**

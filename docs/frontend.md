# Frontend / Frontend

## 🎯 Overview / Umumiy Ko'rinish
Next.js 14+ (App Router) + TypeScript + Tailwind CSS. **Phase 3** da amalga oshiriladi. Sample demo mode — inference yo'q, faqat tayyor natijalar ko'rsatiladi.

---

## 📄 Pages / Sahifalar

| Route | Nomi | Tavsif |
|-------|------|--------|
| `/` | Landing / Bosh sahifa | Loyiha haqida, demo havolasi, hajmi |
| `/demo` | Demo / Ko'rsatish | Video upload, processing progress, natija ko'rinishi |
| `/results/[id]` | Natijalar / Tafsilot | Bitta video uchun to'liq natija: video player, timeline, events, risk |
| `/about` | Loyiha haqida | Jamoa, texnologiyalar, arxitektura diagrammasi |
| `/report` | Hisobot / PDF export | PDF generatsiya (keyingi versiyada) |

---

## 🧩 Components / Komponentlar

### 1. VideoUploader
```tsx
// Drag & drop + file input
// Validatsiya: MP4, ≤100MB, ≤2min (client-side)
// Upload progress bar
// Success → redirect to /demo?video_id=...
```

### 2. ProcessingProgress
```tsx
// Polling: GET /api/jobs/{job_id} har 1s
// Progress bar (0-100%)
// Status badge: UPLOADED | PROCESSING | COMPLETED | FAILED
// Error state: retry button
// Complete → redirect to /results/{video_id}
```

### 3. VideoPlayer
```tsx
// HTML5 <video> element
// Controls: play/pause, seek bar, volume, fullscreen
// Current time display
// Event click handler: onEventClick(start_sec) → video.currentTime = start_sec
// Annotated video URL: /api/videos/{id}/annotated.mp4
```

### 4. EventTimeline
```tsx
// Horizontal timeline (Recharts / custom SVG)
// Har bir event = colored segment [start, end]
// Hover → tooltip (label, track_id, confidence)
// Click → VideoPlayer seek
// Color coding: speeding=red, parking=orange, uturn=purple, wrong_way=blue, stop_line=yellow
```

### 5. EventList
```tsx
// Table/List view of events
// Columns: #, Label, Start, End, Duration, Track ID, Confidence
// Row click → VideoPlayer seek
// Filter by label (checkbox group)
// Sort by start_sec (default)
```

### 6. RiskChart
```tsx
// Recharts: BarChart / RadarChart
// Overall risk: Gauge (0-1)
// By category: horizontal bars
// High risk tracks: list with badges
```

### 7. EventBadge
```tsx
// Reusable badge component
// Variants: "speeding" | "illegal_parking" | "illegal_uturn" | "wrong_way" | "stop_line_crossing"
// Colors per variant
// Size: sm | md | lg
```

### 8. StatsCard
```tsx
// Metric card: title, value, delta, icon
// Used on /results/[id] and /dashboard
```

### 9. TrafficDashboard
```tsx
// Aggregate view (multiple videos)
// Grid of StatsCards: Total Videos, Total Events, Avg Risk, Processing Time
// Recent videos table with status
// Charts: Events per day, Risk distribution
```

---

## 🎬 Video Seek / Video Navigatsiya

**Asosiy funksionallik**: Event timeline yoki listda biror voqea bosilganda video avtomatik ravishda shu vaqtiqa o'tadi.

```tsx
// VideoPlayer.tsx
const handleEventClick = (startSec: number) => {
  videoRef.current.currentTime = startSec;
  videoRef.current.play();
};

// EventTimeline.tsx
<Segment 
  onClick={() => onEventClick(event.start_sec)}
  style={{ backgroundColor: getColor(event.label) }}
/>

// EventList.tsx
<Row 
  onClick={() => onEventClick(row.start_sec)}
  style={{ cursor: 'pointer' }}
/>
```

---

## 🎭 Sample Demo Mode / Demo Rejimi (MUHIM)

**Haqiqiy inference HECH QACHON browserda ishlamaydi.**

### Pre-generated Samples
```
website/
└── public/
    └── samples/
        ├── sample_1.mp4
        ├── sample_2.mp4
        ├── sample_3.mp4
        └── predictions_samples.json
```

### predictions_samples.json Structure
```json
{
  "sample_1.mp4": {
    "video_id": "sample_1",
    "duration_sec": 45.0,
    "events": [
      { "start_sec": 5.2, "end_sec": 8.7, "label": "speeding", "track_id": 1, "confidence": 0.94 },
      { "start_sec": 18.0, "end_sec": 22.5, "label": "illegal_parking", "track_id": 3, "confidence": 0.89 }
    ],
    "risk": {
      "overall_risk": 0.72,
      "by_category": { "speeding": 0.85, "illegal_parking": 0.6, "illegal_uturn": 0, "wrong_way": 0, "stop_line_crossing": 0 },
      "high_risk_tracks": [1, 3]
    }
  },
  "sample_2.mp4": { ... },
  "sample_3.mp4": { ... }
}
```

### Demo Flow
1. User `/demo` sahifasiga kiradi
2. "Try Sample" tugmalardan birini tanlaydi
3. Frontend `predictions_samples.json` dan ma'lumot oladi
4. `ProcessingProgress` komponenti **mock progress** ko'rsatadi (setTimeout bilan 0→100%)
5. Natija sahifasiga o'tadi, hamma ma'lumot JSON dan o'qiladi
6. **Hech qanday API call yo'q** (faqat static fayllar)

### Sample Video Generation (Offline)
```bash
# ffmpeg bilan namuna videolar yaratish
ffmpeg -f lavfi -i testsrc=duration=45:size=1280x720:rate=30 website/public/samples/sample_1.mp4
ffmpeg -f lavfi -i testsrc=duration=60:size=1280x720:rate=30 website/public/samples/sample_2.mp4
```

---

## 🎨 Styling / Uslub

### Tailwind Config
```js
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        primary: { 500: '#3B82F6', 600: '#2563EB' },
        danger: { 500: '#EF4444' },
        warning: { 500: '#F59E0B' },
        success: { 500: '#10B981' },
      },
    },
  },
}
```

### Event Label Colors
```ts
const EVENT_COLORS: Record<string, string> = {
  speeding: 'bg-red-500',
  illegal_parking: 'bg-orange-500',
  illegal_uturn: 'bg-purple-500',
  wrong_way: 'bg-blue-500',
  stop_line_crossing: 'bg-yellow-500',
};
```

---

## 🔧 State Management / Holat Boshqaruvi

| Holat | Yechim |
|-------|--------|
| Video upload | React state + FormData |
| Job polling | `useEffect` + `setInterval` (1s) + cleanup |
| Events data | Server Component (Next.js) / SWR |
| Video player ref | `useRef<HTMLVideoElement>` |
| Theme (dark/light) | `next-themes` |

---

## 📱 Responsive / Moslashuvchan
- **Mobile first**: Tailwind `sm:`, `md:`, `lg:`, `xl:` breakpointlari
- Video player: `aspect-video` (16:9)
- Timeline: horizontal scroll on mobile
- Tables: card layout on mobile

---

## ♿ Accessibility / Engil Foydalanish
- Semantic HTML: `<main>`, `<section>`, `<article>`
- Video: `<track kind="captions">` (keyingi versiyada)
- Keyboard navigation: Tab order, Enter/Space activation
- Color contrast: WCAG AA compliant
- ARIA labels on icon buttons

---

## 🧪 Testing / Testlash
```bash
# Unit tests (Vitest)
npm run test

# E2E tests (Playwright)
npm run test:e2e

# Visual regression (Chromatic)
npm run chromatic
```

### Key Test Scenarios
1. Upload valid MP4 → shows progress → shows results
2. Upload invalid file (AVI, >100MB) → shows error
3. Click event in timeline → video seeks correctly
4. Sample demo works without API calls
5. Responsive layout on 375px, 768px, 1440px
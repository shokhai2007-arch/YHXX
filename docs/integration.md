# Frontend ↔ Backend Integration / Frontend va Backend integratsiyasi

> **Kontekst**: Stitch'da tayyorlangan UI (4 ta sahifa HTML) Django templates formatiga o'tkazildi va
> mavjud FastAPI backend (`app/`) bilan integratsiya qilindi. Ushbu hujjat rejani, qabul qilingan
> qarorlarni va aniqlangan konsepsiya nomuvofiqliklarini yozib boradi.

---

## ✅ Qabul qilingan qarorlar

| Savol | Qaror |
|-------|-------|
| Template engine | **FastAPI + Jinja2** — Django template sintaksisi bilan deyarli bir xil (`{{ }}`, `{% for %}`, `extends/block`). Mavjud backend (`app/`), DB modellar va API endpointlar saqlab qolindi |
| Sample demo mode | **Client-side JSON** — sample kartalar `/static/samples/predictions_samples.json` dan o'qiladi, DB/API ishlatilmaydi (docs/frontend.md printsipiga mos) |
| Statik fayllar | `app/static/` (Docker volume `./app:/app/app` bilan konteynerga avtomatik kiradi) |

---

## 🧱 Amalga oshirilgan tuzilma

```
app/
├── api/
│   ├── web.py            # YANGI: sahifa routera (Jinja2Templates), 404 handler
│   ├── videos.py         # + GET /videos (list), GET /videos/{id}/file (player uchun)
│   └── ...               # mavjud API o'zgarmadi
├── templates/            # YANGI: Django uslubidagi templatelar
│   ├── base.html         # Umumiy shell (header/nav/footer, Tailwind config, Inter font)
│   ├── landing.html      # /            — hero, imkoniyatlar, violation badges
│   ├── demo.html         # /demo        — upload + sample kartalar + progress (real + mock)
│   ├── results_list.html # /results     — DB videolar ro'yxati
│   ├── results.html      # /results/{id} va /results/sample/{id} — player+timeline+risk
│   ├── report.html       # /report      — eksport (JSON/CSV API dan, PDF print fallback)
│   ├── about.html        # /about
│   └── 404.html          # maxsus 404 sahifa
└── static/
    └── samples/          # sample_1..3.mp4 + predictions_samples.json
```

**URL xaritasi**:

| Sahifa | Manba (Stitch) | Ma'lumot |
|--------|----------------|----------|
| `/` | (landing mock-up) | statik kontekst |
| `/demo` | cyberleek_demo_upload | sample metama'lumoti serverda, oqim client JS |
| `/results` | — (yangi) | DB `GET videos` |
| `/results/{video_id}` | cyberleek_natijalar_results_detail | `/events`, `/risk`, `/result` API |
| `/results/sample/{id}` | cyberleek_natijalar_results_detail | statik JSON (API yo'q) |
| `/about` | cyberleek_loyiha_haqida_about | statik kontekst |
| `/report` | cyberleek_hisobot_pdf_export | DB videos + event counts |

**Demo oqimlari**:
- Real video: `POST /api/v1/videos` → `POST /videos/{id}/process` → `GET /jobs/{id}` (1s polling) → `/results/{id}`
- Sample: kartani bosish → mock progress (setTimeout) → `/results/sample/{id}` → client-side JSON render

---

## 🔀 Aniqlangan konsepsiya nomuvofiqliklari va yechimlari

### 1. Label tizimi: frontend 5 ta ↔ engine 14 ta (MUHIM)
- **Muammo**: docs + frontend + `app/services/inference.py` 5 ta eski label ishlatgan
  (`speeding, illegal_parking, illegal_uturn, wrong_way, stop_line_crossing`), lekin
  `engine/pipeline.py` **WIUT spec bo'yicha 14 ta official class** chiqaradi
  (`accident, near_miss, red_light, wrong_way, illegal_u_turn, stopped_vehicle, jaywalking,
  failure_to_yield, illegal_turn, solid_line_crossing, stop_line, congestion, road_obstacle, fire_smoke`).
  CI (`judge-test` job) ham 14 labelni tekshiradi.
- **Yechim** (bajarildi): frontend, `predictions_samples.json`, `RiskCategory` schema,
  `inference.VALID_LABELS` (endi `engine.pipeline.CLASSES` dan import), unit testlar — barchasi 14 labelga o'tkazildi.
  Har bir labelga `event-<slug>` Tailwind rangi berildi (base.html).

### 2. Dashboard/jamlangan ko'rinish endpoint yo'q
- **Muammo**: docs/frontend.md'dagi `TrafficDashboard` (Total Videos, Events/day) uchun
  aggregate endpoint yo'q; `/results` list ham UI'da bor, backendda yo'q edi.
- **Yechim** (bajarildi): `GET /api/v1/videos` (list, limit/offset) qo'shildi;
  `/results` list sahifasi shu ma'lumot asosida render qilinadi. To'liq dashboard (Events/day chart) keyingi qadam.

### 3. Video player uchun fayl endpoint yo'q
- **Muammo**: player `annotated.mp4` ni kutgan, lekin tahlilgacha original video ko'rsatilishi kerak.
- **Yechim** (bajarildi): `GET /api/v1/videos/{id}/file` (FileResponse, range'li streaming uchun Nginx tavsiya).

### 4. Progress detalizatsiyasi: UI 5 bosqich ↔ API faqat progress %
- **Muammo**: demo UI'da Upload→Decode→Detect→Track→Done bosqichlari bor, API faqat `progress: 0-100` beradi.
- **Yechim** (bajarildi): client-side progress → bosqich mapping (p<30 Detect'dan oldin va h.k.). Haqiqiy bosqich API'si keyingi qadam.

### 5. FPS / kadr soni / ETA maydonlari
- **Muammo**: UI'da "28.4 FPS", "816/1200 kadr", ETA statik ko'rsatilgan — API'da bunday maydon yo'q.
- **Yechim** (bajarildi): mock qiymatlar client tomonda hisoblanadi; `job.metadata` maydoni keyingi qadamda qo'shilishi mumkin.

### 6. Cancel tugmasi
- **Muammo**: demo'dagi `Cancel` uchun `DELETE /jobs/{id}` yo'q. FastAPI BackgroundTasks bekor qilish (cancel) imkoniyatini bermaydi.
- **Yechim** (bajarildi): Cancel faqat UI progressini to'xtatadi. Haqiqiy cancel Celery/ARQ kerak (anti-overengineering — hozircha yo'q).

### 7. Bounding box koordinatalari API'da yo'q
- **Muammo**: results UI statik bbox pozitsiyalari bilan; haqiqiy annotated video serverda render qilinadi.
- **Yechim** (bajarildi): player ustida faqat "aktiv event" HUD overlay (vaqt oralig'i bo'yicha); aniq bbox uchun `event.metadata.bbox` keyingi qadam.

### 8. Hisobot (PDF) eksporti
- **Muammo**: UI PDF/JSON/CSV taklif qiladi; backendda faqat `result.json` fayli bor, PDF generator yo'q.
- **Yechim** (bajarildi): JSON — result endpointlardan; CSV — events endpointlardan client-side tuziladi;
  PDF — `window.print()` fallback. Keyingi qadam: `POST /api/v1/reports` (WeasyPrint).

### 9. DB portabliligi
- **Muammo**: `RiskScore.high_risk_tracks` `ARRAY(Integer)` — faqat Postgres (docs esa "SQLite → Postgres" deydi).
- **Yechim** (bajarildi): `JSON` ustun — ikkala dialectda ham ishlaydi.

### 10. Sample demo API chaqiruvlari
- **Muammo**: docs "hech qanday API call yo'q" deydi, lekin `predictions_samples.json` ildizda (serve qilinmaydi) va format boshqacha edi.
- **Yechim** (bajarildi): `/static/samples/` ga ko'chirildi, docs formatiga mos obyekt-shakl (`videos.sample_1.events[]`), static sample mp4 ham qo'shildi (ijro uchun).

### 11. Ishlab chiqarishda topilgan eskirgan testlar
- `tests/unit/test_pipeline.py` — engine'da `_generate_mock_events` metod yo'q (12 test FAIL, **avvaldan buzilgan**, engine qayta yozilganda eskirgan). Hozircha tuzatilmadi — alohida task.
- `tests/integration/*` — mavjud bo'lmagan `tests.conftest.create_test_video/job/...` helperlarini import qiladi (CI ishga tushirmaydi). Alohida task.

---

## 🐛 Prod xatosi: DatatypeMismatchError (high_risk_tracks) + raw error leak

**Simptom**: `POST /videos/{id}/process` 70% progressdan keyin FAILED; asyncpg
`DatatypeMismatchError: column "high_risk_tracks" is of type integer[] but expression is of type json`,
va to'liq SQL stack trace frontend'da "Xato: ..." sifatida ko'rinadi.

**Ildiz sabablar (2 ta)**:
1. **Schema drift**: `init_db()` faqat `create_all` qiladi — mavjad jadval ustunlarini o'zgartirmaydi.
   Model `high_risk_tracks`ni `ARRAY(Integer)`dan `JSON`ga o'tkazilgan edi (#9), ammo eski bazada
   `integer[]` qolgan edi. E2E'da faqat yangi bazada testlangani uchun ko'rinmagan.
2. **Raw error leak**: `run_inference` except bloki `str(e)`ni (SQL + parametrlar bilan) `job.error`ga
   yozgan, `demo.html` esa uni to'g'ridan-to'g'ri ko'rsatgan.

**Yechim (bajarildi)**:
1. `app/database.py` — `init_db()` ichida idempotent **schema heal** qadami: `information_schema`
   orqali ustun hali `ARRAY` bo'lsa, `ALTER ... TYPE jsonb USING to_jsonb(...)` qilinadi.
   (Diqqat: PG `integer[]::jsonb` to'g'ridan-to'g'ri cast qilmaydi — `to_jsonb()` kerak.)
2. `app/services/inference.py` — `_sanitize_job_error()`: `[SQL:` / `[parameters:` markerlarigacha
   kesib, 300 belgi bilan cheklaydi; to'liq traceback `logger.exception` orqali logga tushadi;
   `raise` olib tashlandi (BackgroundTasks'da uvicorn "Exception in ASGI application" spam'i yo'qoldi).

**Verifikatsiya**: live DB `integer[] → jsonb` o'tdi (eski qatorlar `[1,2,3]` ko'rinishida saqlandi);
e2e smoke (upload → process → COMPLETED → `/risk` `high_risk_tracks: [1, 2]`) ✓; o'zgarish tegishli
unit testlar 19/19 ✓; qolgan pytest fail'lari #11'dagi avvaldan buzilgan testlar bilan bir xil.

---

## ▶️ Ishga tushirish

```bash
# Docker (postgres + redis + backend):
make dev                      # http://localhost:8000 (UI), /docs (API)

# Lokal:
uvicorn app.main:app --reload # DATABASE_URL/.env kerak
```

## ✅ Verifikatsiya (bajarildi)
- `pytest tests/judge/` — 17/17 ✓
- `pytest tests/unit/test_risk_calculation.py` — ✓ (label migratsiyasidan keyin)
- `ruff check app/` — ✓
- Smoke-test (TestClient + SQLite): barcha sahifalar 200, 404 sahifa, sample/video results,
  `/api/v1/videos` list, static mp4/json — ✓

## 🗺️ Keyingi qadamlar (taklif)
1. Buzilgan `tests/unit/test_pipeline.py` testlarini yangi engine API'siga moslash
2. Integration testlar uchun conftest helperlarini yozish + CI'ga qo'shish
3. Job `metadata` (FPS, kadr soni, bosqich) → progress endpointiga
4. `POST /api/v1/reports` (PDF) — WeasyPrint/reportlab
5. Dashboard aggregate endpoint (`/api/v1/stats`) + `/dashboard` sahifasi

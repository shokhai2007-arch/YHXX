# AGENTS.md — CyberLeek Traffic Detection (WUIT Hackathon)

> **Tasvir**: Ushbu hujjat loyihaga yangi kodlash agentlari (siz!) qo'shilganda xato qilinmaslik uchun yaratilgan. **Architecture.md**, **Backend-API.md**, **Frontend.md** sub-hujjatlari batafsil ma'lumot beradi.

---

## 🎯 Loyiha Maqsadi
**CyberLeek** jamoasi WUIT hackathoni uchun avtomobil yo'l harakatini video orqali tahlil qiluvchi tizim yaratmoqda. Real AI model **yo'q** — faqat mock/namuna javoblar ishlatiladi.

---

## ⚡ MUHIY QOIDA: Dual-System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  JUDGE ENVIRONMENT (Baholash)                                   │
│  python run_submission.py → solution.py → detect_events()      │
│  → predictions.json  ✅  Hech qanday web/DB/Framework yo'q      │
└─────────────────────────────────────────────────────────────────┘
                              │
                    SHARED ENGINE (engine/pipeline.py)
                              │
┌─────────────────────────────────────────────────────────────────┐
│  WEBSITE / DEMO (Ko'rsatish)                                    │
│  Browser → Next.js → FastAPI → Inference Engine → Events       │
│  → Vizualizatsiya  ✅  Alohida deploy, judge bilan bog'lanmaydi │
└─────────────────────────────────────────────────────────────────┘
```

**Hech qachon** judge kodini website/backend bilan birlashtirmang. Bitta `engine/` — ikkita alohida entry point.

---

## 📁 Hujjatlar Xaritasi

| Fayl | Mazmuni |
|------|---------|
| `AGENTS.md` | Bu fayl — indeks va tezkor eslatma |
| `docs/architecture.md` | Tizim arxitekturasi, dual-system, mock AI, roadmap |
| `docs/backend-api.md` | API contract, DB schema, background jobs, validation |
| `docs/frontend.md` | Sahifalar, komponentlar, video seek, sample demo mode |
| `docs/integration.md` | Frontend↔Backend integratsiya rejasi, qarorlar, aniqlangan nomuvofiqliklar |
| `docs/compliance_analysis.md` | WIUT Hackathon talablari bilan muvofiqlik tahlili, gaplar, reja |

---

## 🔑 Tezkor Eslatmalar (Cheatsheet)

### solution.py Contract
```python
def detect_events(video_path: str) -> list[list]:
    """
    Returns: [[start_sec, end_sec, label], ...]
    Labels (14 official WIUT spec): accident, near_miss, red_light, wrong_way,
    illegal_u_turn, stopped_vehicle, jaywalking, failure_to_yield,
    illegal_turn, solid_line_crossing, stop_line, congestion,
    road_obstacle, fire_smoke
    """
    from engine.pipeline import TrafficPipeline
    return TrafficPipeline(config_path="configs/camera.yaml").process_video(video_path)
```

### Phase 1 — Core (Hozirgi vazifa)
- `solution.py`, `run_submission.py`, `evaluate.py`
- `engine/pipeline.py` — TrafficPipeline class
- `configs/camera.yaml` — lanesi/stop_lines polygons
- `requirements.txt` — Python dependencies

### Komandalar
```bash
python run_submission.py                    # Judge entry point
python evaluate.py --pred predictions.json --validate-only
pytest
ffprobe video.mp4
ffmpeg -i video.mp4 -ss 10 -frames:v 1 thumbnail.jpg
```

### Anti-Overengineering (MVP)
| ❌ Yo'q | ✅ Ha |
|---------|-------|
| Celery, Redis, Postgres, WebSocket | FastAPI BackgroundTasks + 1s polling |
| K8s, Kafka, S3, Prometheus | SQLite → Postgres keyingi safar |

---

## 🗺️ Roadmap
1. **Phase 1 Core** — `python run_submission.py` ishlaydi (mock natija)
2. **Phase 2 Backend** — FastAPI, DB, background jobs, validation
3. **Phase 3 Frontend** — Next.js, komponentlar, sample demo mode

---

## 📂 Repo Structure (Hozirgi Holat)
```
/home/neo/Projects/YHXX/
├── AGENTS.md
├── docs/
│   ├── architecture.md
│   ├── backend-api.md
│   ├── frontend.md
│   ├── integration.md
│   └── compliance_analysis.md
├── solution.py
├── run_submission.py
├── evaluate.py
├── engine/
│   └── pipeline.py
├── configs/
│   └── camera.yaml
├── requirements.txt
├── pyproject.toml
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── videos.py
│   │   ├── jobs.py
│   │   ├── events.py
│   │   ├── risk.py
│   │   ├── results.py
│   │   ├── health.py
│   │   └── web.py
│   ├── models/
│   │   ├── video.py
│   │   ├── job.py
│   │   ├── event.py
│   │   └── risk_score.py
│   ├── schemas/
│   ├── services/
│   │   └── inference.py
│   ├── utils/
│   │   └── video_utils.py
│   ├── templates/          # Jinja2 (Phase 3)
│   │   ├── base.html
│   │   ├── landing.html
│   │   ├── demo.html
│   │   ├── results.html
│   │   ├── results_list.html
│   │   ├── report.html
│   │   ├── about.html
│   │   └── 404.html
│   └── static/
│       └── samples/        # sample_1-3.mp4 + predictions_samples.json
├── models/weights/         # Phase 2 (empty - mock AI)
├── data/
│   ├── uploads/
│   ├── outputs/
│   ├── postgres/
│   └── redis/
├── tests/
│   ├── judge/
│   ├── unit/
│   └── integration/
├── Dockerfile
├── Dockerfile.dev
├── docker-compose.yml
├── Makefile
└── .github/workflows/ci.yml
```

---

## 🇺🇿 Til Qoidalari
- **Body**: Ingliz tilida
- **Section headers / comments**: O'zbek tilida (Lotin harflarida)
- Masalan: `## 📐 Architecture / Arxitektura`
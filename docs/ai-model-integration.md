# AI Model Integratsiya Hujjati / AI Model Integration Document

> **Maqsad**: Ushbu hujjat loyihada qaysi nuqtalarda mock ma'lumotlar ishlatilayotganini va qaysi komponentlarga real AI model integratsiya qilinishi kerakligini fayl/funksiya darajasida tushuntiradi. Model tanlovi (fine-tune, classical CV, hybrid) to'liq jamoaga qaratilgan — hujjat faqat integratsiya nuqtalari va I/O kontraktlarini belgilaydi.

---

## 📍 Integratsiya Nuqtalari Jadvali

| # | Komponent | Fayl:Qator | Hozirgi Mock Holati | Kerakli Real AI |
|---|-----------|------------|---------------------|-----------------|
| 1 | **Ob'ekt deteksiya** | `engine/pipeline.py:119` `_generate_mock_events` | Random bbox + label (5 ta klass: `speeding`, `illegal_parking`, `illegal_uturn`, `wrong_way`, `stop_line_crossing`) | Detection model (YOLO/RT-DETR) → `List[bbox, class_id, confidence]` |
| 2 | **Video davomiyligi** | `engine/pipeline.py:108` `_get_mock_duration` | Random/soxta soniya | `ffprobe` decoder yoki OpenCV `CAP_PROP_FRAME_COUNT / FPS` |
| 3 | **Tracking / Track ID** | `app/services/inference.py:140` | `track_id = i + 1` (har frame uchun yangi ID) | Multi-object tracker (ByteTrack/BoT-SORT) → `track_id` doimiy bo'lishi kerak |
| 4 | **Risk hisoblash** | `app/services/inference.py:59` `calculate_and_save_risk` | Har eventga `+0.2` qo'shish, `engine_version: "1.0.0-mock"` | Zone/lanes geometriyasi asosida rule-based yoki model-based risk |
| 5 | **Tezlik hisoblash** | `engine/pipeline.py` (ichida) | Hisoblanmayapti / mock | Kalibratsiya (homography) + tracker trajectory → km/soat |
| 6 | **Video annotatsiya** | `app/utils/video_utils.py:95` `create_annotated_video` | Frame markazidagi soxta bbox chizish | Real detection bbox'larini + track_id + label overlay qilish |
| 7 | **Engine versiya** | `app/services/inference.py:107` | `"1.0.0-mock"` string | Real model versiyasi / commit hash |

---

## 🔗 Input / Output Kontraktlari

Barcha AI integratsiya nuqtalari quyidagi interfeyslarga rioya qilishi kerak.

### 1. Asosiy Pipeline Girişi (`solution.py` contract)
```python
def detect_events(video_path: str) -> list[list]:
    """
    Returns: [[start_sec, end_sec, label], ...]
    Labels: speeding, illegal_parking, illegal_uturn, wrong_way, stop_line_crossing
    """
    from engine.pipeline import TrafficPipeline
    return TrafficPipeline(config_path="configs/camera.yaml").process_video(video_path)
```

### 2. `TrafficPipeline.process_video()` — Real Implementatsiya Tasviri
```python
class TrafficPipeline:
    def __init__(self, config_path: str):
        self.config = load_yaml(config_path)  # lanes, stop_lines, crosswalk, roi (1280x720)
        self.detector = Detector(weights="models/weights/detector.onnx")  # real model
        self.tracker = Tracker()  # ByteTrack/BoT-SORT
        self.event_engine = EventEngine(self.config)  # zone/lanes logic

    def process_video(self, video_path: str) -> list[list]:
        # 1. Video ochish, FPS, duration olish (real)
        # 2. Frame-by-frame inference:
        #    - detector(frame) → List[bbox, class_id, conf]
        #    - tracker.update(detections) → List[bbox, track_id, class_id]
        #    - event_engine.check(tracks) → List[Event(start, end, label, track_id, meta)]
        # 3. Events ni [[start, end, label]] formatiga o'tkazish
        # 4. return events
```

### 3. Detektor Interfeysi
```python
class Detector:
    def __call__(self, frame: np.ndarray) -> list[dict]:
        """
        Input: BGR frame (H, W, 3)
        Output: [
            {"bbox": [x1, y1, x2, y2], "class_id": int, "confidence": float},
            ...
        ]
        """
        ...

    def warmup(self): ...
```

### 4. Tracker Interfeysi
```python
class Tracker:
    def update(self, detections: list[dict]) -> list[dict]:
        """
        Input: detections from Detector
        Output: [
            {"bbox": [x1, y1, x2, y2], "track_id": int, "class_id": int, "confidence": float},
            ...
        ]
        """
        ...

    def reset(self): ...
```

### 5. Event Engine (Zone/Lane Logic)
```python
class EventEngine:
    def __init__(self, config: dict):
        self.lanes = config["lanes"]           # List[polygon]
        self.stop_lines = config["stop_lines"] # List[line]
        self.crosswalks = config["crosswalks"] # List[polygon]
        self.roi = config["roi"]               # polygon

    def check(self, tracks: list[dict]) -> list[dict]:
        """
        Input: tracks from Tracker
        Output: [
            {"track_id": int, "label": str, "start_frame": int, "end_frame": int, "meta": dict},
            ...
        ]
        Labels: speeding, illegal_parking, illegal_uturn, wrong_way, stop_line_crossing
        """
        ...
```

### 6. Risk Calculator (Backend)
```python
def calculate_risk(events: list[dict], config: dict) -> list[dict]:
    """
    Input: events from EventEngine + camera config
    Output: events with added "risk_score": float (0.0-1.0)
    """
    # Rule-based: zone ichida necha track, tezlik, devor o'tish va h.k.
    ...
```

### 7. Video Annotator
```python
def create_annotated_video(
    video_path: str,
    events: list[dict],
    output_path: str,
    config: dict
) -> None:
    """
    Input: original video + events (bbox, track_id, label) + config
    Output: annotated video written to output_path
    Draws: bbox, track_id, label, zone/lanes overlay
    """
    ...
```

---

## ⚠️ Muhim Eslatmalar / Critical Notes

### Dual-System Cheklovi
```
┌─────────────────────────────────────────────────────────────────┐
│  JUDGE ENVIRONMENT                                              │
│  python run_submission.py → solution.py → detect_events()      │
│  → predictions.json  ✅  Hech qanday web/DB/Framework yo'q      │
└─────────────────────────────────────────────────────────────────┘
                              │
                    SHARED ENGINE (engine/pipeline.py)
                              │
┌─────────────────────────────────────────────────────────────────┐
│  WEBSITE / DEMO                                                 │
│  Browser → Next.js → FastAPI → Inference Engine → Events       │
│  → Vizualizatsiya  ✅  Alohida deploy, judge bilan bog'lanmaydi │
└─────────────────────────────────────────────────────────────────┘
```
- **Bitta `engine/`** — ikkita alohida entry point (`solution.py` va FastAPI backend)
- Model **hech qachon** web/DB/Framework ga bog'liq bo'lmasligi kerak
- `solution.py` faqat `engine.pipeline.TrafficPipeline` ni import qiladi
- Model fayllari (`models/weights/`) local filesystem da bo'ladi, API token yo'q

### Lokal O'qitish / Local Training
- Jamoa **katta LLM providerlari (OpenAI, Anthropic, Google) API tokenlarini ISHLATMAYDI**
- Barcha model o'qitish/inference **lokal/private** infrastructure da amalga oshiriladi
- Dataset tayyorlash, fine-tune, export (ONNX/TensorRT) — jamoaga to'liq biriktirilgan
- Hujjatda model arxitekturasini majburlab tavsiya qilinmaydi (YOLOv8, RT-DETR, DETR, classical CV — erkin tanlov)

### Mock → Real O'tish Yo'l Xaritasi
1. `engine/detector.py` yaratish → `Detector` class + ONNX/TensorRT inference
2. `engine/tracker.py` yaratish → `Tracker` class (ByteTrack/BoT-SORT port)
3. `engine/event_engine.py` yaratish → `EventEngine` class (config.yaml geometries)
4. `engine/pipeline.py` da `_generate_mock_events` → real detector+tracker+event_engine chaqiruvi
5. `app/services/inference.py` da mock risk → `calculate_risk` real implementatsiya
6. `app/utils/video_utils.py` da mock bbox → real annotated bbox chizish
7. `models/weights/` ga export qilingan model fayllarini joylash

### Konfiguratsiya (`configs/camera.yaml`)
```yaml
# Hozirgi strukturani saqlab, real model uchun kengaytirish:
resolution: [1280, 720]
lanes:
  - id: 1
    polygon: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    direction: "forward"
stop_lines:
  - id: 1
    line: [[x1,y1], [x2,y2]]
crosswalks:
  - id: 1
    polygon: [[...]]
roi:
  polygon: [[...]]
# Kalibratsiya (tezlik uchun):
homography_matrix: [[...]]  # 3x3 matrix, pixel → real-world meters
```

---

## 📋 Tekshirish Ro'yxati (Checklist)

| Holat | Tavsif |
|-------|--------|
| ✅ Mock fayllar aniqlandi | 3 ta fayl, 7 nuqta |
| ✅ I/O kontraktlar belgilandi | 7 ta interfeys |
| ✅ Dual-system cheklovi hujjatlashtirildi | Judge va Website alohida entry point |
| ✅ Lokal o'qitish talabi belgilandi | API token yo'q, hammasi local |
| ⏳ Real modullar yaratilishi | `detector.py`, `tracker.py`, `event_engine.py` |
| ⏳ Model export va `models/weights/` ga joylash | ONNX/TensorRT formatida |
| ⏳ Pipeline real implementatsiya | Mock chaqiruvlar o'rniga real AI chaqiruvlari |

---

## 🔄 Yangilash Tarixi

| Sana | Versiya | O'zgarish |
|------|---------|-----------|
| 2026-09-23 | 1.0 | Birinchi versiya — integratsiya nuqtalari va I/O kontraktlar |

---

> **Eslatma**: Ushbu hujjat **tavsiya emas, kontrakt**. Real model tanlovi, arxitekturasi, o'qitish usuli va deploy usuli to'liq **CyberLeek jamoasiga** biriktirilgan. Hujjat faqat "qayerga" va "qanday interfeys bilan" ulanishi kerakligini belgilaydi.
# WIUT Hackathon 2026 CV Track — Compliance Analysis

> **Status**: Implementation review against official task requirements  
> **Date**: 2026-09-27  
> **Team**: CyberLeek

---

## Executive Summary

The current implementation **fully satisfies the core technical requirements** (Part A + Part B detection pipeline, judge entry points, evaluation metrics). The main gaps are in **submission package completeness** (README, predictions_samples.json) and **website content** (EDA, Report pages). CI has 2 failing checks that must be fixed.

---

## ✅ Fully Compliant

| Requirement | Implementation | Location |
|-------------|---------------|----------|
| **Part A: `detect_events(video_path)`** | `TrafficPipeline.process_video()` returns `[[start, end, label], ...]` | `engine/pipeline.py`, `solution.py:26-42` |
| **14 Official Classes** | Exact match: accident, near_miss, red_light, wrong_way, illegal_u_turn, stopped_vehicle, jaywalking, failure_to_yield, illegal_turn, solid_line_crossing, stop_line, congestion, road_obstacle, fire_smoke | `engine/pipeline.py:24-41` |
| **Part B: `RiskEstimator`** | `reset(meta)`, `step(frame, t_sec) -> float` with TTC-based risk | `engine/pipeline.py:532-691` |
| **Judge Entry Point** | `run_submission.py` processes folder, enforces 3× time budget, streams frames, writes predictions.json | `run_submission.py` |
| **Evaluation Script** | Macro F1 @ IoU {0.3, 0.5, 0.7}, chance-normalized AP, F1_alarm, mTTA | `evaluate.py` |
| **Output Format** | `{"team": "...", "videos": {"file.mp4": {"events": [], "risk": []}}}` | Matches spec exactly |
| **Mock AI Only** | Deterministic mock tracks, no external APIs, fixed seeds | `engine/pipeline.py` |
| **Hard-coded Scene** | `configs/camera.yaml` — lanes, stop lines | `configs/camera.yaml` |
| **Website: Team Page** | `/about` with members, roles, links | `app/templates/about.html` |
| **Website: Approach** | `/about` with pipeline diagram, models | `app/templates/about.html` |
| **Website: Sample Results** | `/results/sample/{id}` — player, timeline, risk curve | `app/templates/results.html` |
| **Website: Live Demo** | `/demo` — upload, progress polling, visualization | `app/templates/demo.html` |
| **Website: Report Page** | `/report` — sections for summary, events, risk, appendix | `app/templates/report.html` |

---

## ❌ Critical Gaps (Must Fix)

### 1. Missing `predictions_samples.json` (Repo Root Required)
```bash
# Required by task: repo must contain predictions_samples.json
python run_submission.py --videos samples --out predictions_samples.json
```
**Note**: Official `samples/` folder not at repo root. Current samples at `app/static/samples/`.

### 2. README.md Incomplete
**Must include:**
- [ ] Install/run instructions (incl. `weights/download.sh`)
- [ ] Architecture, models, datasets + licenses
- [ ] Fixed seeds, determinism notes
- [ ] Team members & contributions

### 3. Website: EDA Page Missing (Required)
**Required content:**
- [ ] Resolution, FPS, duration, lighting analysis
- [ ] Object counts over time by class
- [ ] Motion heatmaps
- [ ] Vehicle trajectories & lane directions
- [ ] Traffic density by time

### 4. Website: Report Page Content
**Required**: "What worked, what did not, what you would do next" — one page

### 5. CI Failing (2 Checks)
| Check | Error | Fix |
|-------|-------|-----|
| Lint | `app/main.py:1:1: I001 Import block un-sorted` | `ruff check --fix app/main.py` |
| Unit Tests | `ModuleNotFoundError: pytest-asyncio` | Add to `pyproject.toml` dependencies |

---

## ⚠️ Potential Issues

### Starter Kit Compatibility
Task requires `run_submission.py` and `evaluate.py` **"from starter kit, unchanged"**. Current versions are **enhanced** with Part B support.

**Risk**: If organizers run THEIR starter kit (basic, Part A only), our `solution.py` must still work.
- Our `solution.py` imports `RiskEstimator` from engine — OK if their runner doesn't call it
- Part B is optional per spec (default returns 0.0)

**Recommendation**: Test `solution.py` with a minimal runner that only calls `detect_events()`.

### Model Weights
Task requires `weights/` folder or `download.sh` (≤ 5 GB). We use mock AI — no weights needed.
- Create `weights/README.md` explaining mock pipeline
- Or create `download.sh` that echoes "No weights needed"

---

## 📋 Execution Plan (Priority Order)

| # | Task | Effort | Command/Location |
|---|------|--------|------------------|
| 1 | **Fix CI: Ruff import sort** | 5 min | `ruff check --fix app/main.py` |
| 2 | **Fix CI: Add missing deps to pyproject.toml** | 5 min | Add `pytest-asyncio`, `aiosqlite`, `jinja2` |
| 3 | **Generate predictions_samples.json** | 5 min | Need `samples/` folder at root or symlink |
| 4 | **Update README.md** | 20 min | `README.md` |
| 5 | **Add EDA page** | 30 min | New `app/templates/eda.html`, route in `web.py` |
| 6 | **Enhance Report page** | 15 min | Edit `app/templates/report.html` |
| 7 | **Verify minimal runner compatibility** | 10 min | Test with basic `run_submission.py` |
| 8 | **Create weights/README.md** | 5 min | `weights/README.md` |
| 9 | **Optional: Interactive timeline→video jump** | 30 min | JS in `results.html` |
| 10 | **Optional: Dashboard page** | 30 min | New template + `/api/v1/stats` |

---

## 🔧 Immediate Commands to Run

```bash
# 1. Fix Ruff import sort
ruff check --fix app/main.py

# 2. Update pyproject.toml dependencies
# Add to dependencies array:
# "pytest-asyncio==0.23.7",
# "aiosqlite==0.20.0",
# "jinja2==3.1.4",

# 3. Create samples folder at root (or symlink)
mkdir -p samples
cp app/static/samples/*.mp4 samples/
# OR
ln -s app/static/samples samples

# 4. Generate predictions_samples.json
python run_submission.py --videos samples --out predictions_samples.json

# 5. Verify tests pass
make test  # or: docker compose -f docker-compose.yml exec backend pytest tests/ -v
```

---

## 📁 File Structure for Submission

```
your-repo/
├── solution.py              # ✅ Judge entry point
├── run_submission.py        # ✅ Enhanced (verify compatibility)
├── evaluate.py              # ✅ Enhanced (verify compatibility)
├── requirements.txt         # ✅
├── pyproject.toml           # ⚠️ Fix deps
├── weights/
│   └── README.md            # ❌ Create
├── configs/
│   └── camera.yaml          # ✅
├── engine/
│   └── pipeline.py          # ✅ 14 classes + RiskEstimator
├── app/
│   ├── main.py              # ⚠️ Fix Ruff
│   ├── api/web.py           # ✅ Web UI routes
│   └── templates/           # ✅ 7 templates
│       ├── base.html
│       ├── landing.html
│       ├── demo.html
│       ├── results.html
│       ├── results_list.html
│       ├── report.html      # ⚠️ Enhance content
│       ├── about.html
│       ├── 404.html
│       └── eda.html         # ❌ Create
├── predictions_samples.json # ❌ Generate
├── README.md                # ⚠️ Complete
├── docs/
│   ├── architecture.md
│   ├── backend-api.md
│   ├── frontend.md
│   ├── integration.md
│   └── compliance_analysis.md  # This file
└── tests/                   # ✅ 125 passing
```

---

## 🎯 Success Criteria for Submission

- [ ] All CI checks pass (Lint, Unit Tests, Judge Test, Docker Build)
- [ ] `predictions_samples.json` exists at repo root
- [ ] README.md has all required sections
- [ ] Website has EDA page with sample video analysis
- [ ] Report page has "worked/didn't work/next steps"
- [ ] `solution.py` works with minimal runner (Part A only)
- [ ] Weights folder documented
- [ ] Team info updated with real names/roles

---

## 📝 Notes

- **Sample Videos**: Currently at `app/static/samples/sample_1-3.mp4` + `predictions_samples.json`. Task expects `samples/` at root.
- **Determinism**: Pipeline uses fixed seeds from video path hash — reproducible.
- **Time Budget**: `run_submission.py` enforces 3× video duration with SIGALRM.
- **Part B**: TTC-based risk from mock tracks — causal (only past frames used via track positions up to current frame).
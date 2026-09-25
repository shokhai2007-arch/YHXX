#!/usr/bin/env python3
"""
evaluate.py — Prediction Evaluation Script (WIUT Hackathon CV Track)

Compares predictions.json against ground truth using official metrics:
- Part A: Temporal IoU matching, macro F1 averaged over τ∈{0.3,0.5,0.7}
- Part B: AP (chance-normalized), F1_alarm, mTTA
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# 14 Official Event Classes (from WIUT Hackathon spec)
CLASSES = [
    "accident",
    "near_miss",
    "red_light",
    "wrong_way",
    "illegal_u_turn",
    "stopped_vehicle",
    "jaywalking",
    "failure_to_yield",
    "illegal_turn",
    "solid_line_crossing",
    "stop_line",
    "congestion",
    "road_obstacle",
    "fire_smoke",
]

VALID_LABELS = CLASSES


def validate_format(predictions: Any) -> tuple[bool, list[str]]:
    """Validate predictions format. Returns (is_valid, errors)."""
    errors = []

    if not isinstance(predictions, list):
        errors.append("Root must be a list")
        return False, errors

    for i, item in enumerate(predictions):
        if not isinstance(item, list):
            errors.append(f"Item {i}: must be a list [start, end, label]")
            continue
        if len(item) != 3:
            errors.append(f"Item {i}: must have exactly 3 elements [start, end, label]")
            continue

        start, end, label = item

        if not isinstance(start, int | float) or start < 0:
            errors.append(f"Item {i}: start_sec must be non-negative number")
        if not isinstance(end, int | float) or end < 0:
            errors.append(f"Item {i}: end_sec must be non-negative number")
        if start >= end:
            errors.append(f"Item {i}: start_sec ({start}) must be < end_sec ({end})")
        if not isinstance(label, str):
            errors.append(f"Item {i}: label must be string")
        elif label not in VALID_LABELS:
            errors.append(f"Item {i}: invalid label '{label}'. Valid: {sorted(VALID_LABELS)}")

    return len(errors) == 0, errors


def load_json(path: Path) -> Any:
    """Load JSON file with error handling."""
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)


def temporal_iou(seg1: list, seg2: list) -> float:
    """Compute temporal IoU between two segments [start, end]."""
    start1, end1 = seg1[0], seg1[1]
    start2, end2 = seg2[0], seg2[1]

    intersection = max(0, min(end1, end2) - max(start1, start2))
    union = max(end1, end2) - min(start1, start2)

    if union == 0:
        return 0.0
    return intersection / union


def match_events(gt_events: list, pred_events: list, iou_threshold: float) -> tuple[int, int, int]:
    """
    Greedy matching by IoU descending.
    Returns (TP, FP, FN).
    """
    # Build all pairs with IoU >= threshold
    pairs = []
    for i, gt in enumerate(gt_events):
        for j, pred in enumerate(pred_events):
            iou = temporal_iou(gt, pred)
            if iou >= iou_threshold:
                pairs.append((iou, i, j))

    # Sort by IoU descending
    pairs.sort(key=lambda x: x[0], reverse=True)

    matched_gt = set()
    matched_pred = set()
    tp = 0

    for iou, gt_idx, pred_idx in pairs:
        if gt_idx not in matched_gt and pred_idx not in matched_pred:
            matched_gt.add(gt_idx)
            matched_pred.add(pred_idx)
            tp += 1

    fp = len(pred_events) - len(matched_pred)
    fn = len(gt_events) - len(matched_gt)

    return tp, fp, fn


def compute_f1(tp: int, fp: int, fn: int) -> float:
    """Compute F1 score from TP, FP, FN."""
    if tp == 0 and fp == 0 and fn == 0:
        return 1.0
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def evaluate_part_a(ground_truth: dict, predictions: dict) -> dict:
    """
    Evaluate Part A: Event Detection.
    Returns dict with Score_A and per-class details.
    """
    # Collect all classes present in ground truth or predictions
    all_classes = set()
    for video_data in ground_truth.values():
        for ev in video_data.get("events", []):
            all_classes.add(ev[2])
    for video_data in predictions.get("videos", {}).values():
        for ev in video_data.get("events", []):
            all_classes.add(ev[2])

    # Only evaluate classes that are in VALID_LABELS
    eval_classes = [c for c in all_classes if c in VALID_LABELS]

    if not eval_classes:
        return {"Score_A": 0.0, "per_class": {}, "details": "No valid classes to evaluate"}

    thresholds = [0.3, 0.5, 0.7]
    class_scores = {}

    for cls in eval_classes:
        cls_f1s = []
        for tau in thresholds:
            # Pool TP, FP, FN across all videos for this class
            total_tp = total_fp = total_fn = 0
            for video_name, gt_video in ground_truth.items():
                pred_video = predictions.get("videos", {}).get(video_name, {"events": []})
                gt_cls = [ev for ev in gt_video.get("events", []) if ev[2] == cls]
                pred_cls = [ev for ev in pred_video.get("events", []) if ev[2] == cls]
                tp, fp, fn = match_events(gt_cls, pred_cls, tau)
                total_tp += tp
                total_fp += fp
                total_fn += fn
            f1 = compute_f1(total_tp, total_fp, total_fn)
            cls_f1s.append(f1)
        class_scores[cls] = {
            "f1_at_0.3": cls_f1s[0],
            "f1_at_0.5": cls_f1s[1],
            "f1_at_0.7": cls_f1s[2],
            "mean_f1": sum(cls_f1s) / len(cls_f1s),
        }

    # Score_A = macro average of mean_f1 across classes
    score_a = sum(cs["mean_f1"] for cs in class_scores.values()) / len(class_scores)

    return {
        "Score_A": score_a,
        "per_class": class_scores,
    }


def evaluate_part_b(ground_truth: dict, predictions: dict) -> dict:
    """
    Evaluate Part B: Accident Anticipation (accident events only).
    H = 5s, W = 10s, θ = 0.5
    """
    H = 5.0  # Horizon
    W = 10.0  # Alarm window
    THETA = 0.5  # Alarm threshold

    # Collect all frames with labels
    # Frame is positive if accident starts at s with s-H <= t < s
    # Frames inside any accident [s, e] are ignored
    # Frames within [s-H, e] of near_miss are ignored
    # All other frames are negative

    fps = 30.0  # Assume 30 fps (not provided in ground truth format)
    frame_labels = {}  # (video_name, frame_idx) -> label (1=pos, 0=neg, -1=ignore)
    frame_times = {}   # (video_name, frame_idx) -> t_sec

    # Process ground truth to label frames
    for video_name, gt_video in ground_truth.items():
        duration = gt_video.get("duration", 60.0)
        n_frames = int(duration * fps)

        # Get accident and near_miss events
        accidents = [ev for ev in gt_video.get("events", []) if ev[2] == "accident"]
        near_misses = [ev for ev in gt_video.get("events", []) if ev[2] == "near_miss"]

        for frame_idx in range(n_frames):
            t = frame_idx / fps
            label = 0  # Default negative

            # Check if inside any accident [s, e] -> ignore
            ignored = False
            for s, e, _ in accidents:
                if s <= t <= e:
                    ignored = True
                    break

            # Check if within [s-H, e] of near_miss -> ignore
            if not ignored:
                for s, e, _ in near_misses:
                    if s - H <= t <= e:
                        ignored = True
                        break

            if ignored:
                label = -1  # Ignore
            else:
                # Check if positive: any accident starts with s-H <= t < s
                for s, e, _ in accidents:
                    if s - H <= t < s:
                        label = 1
                        break

            frame_labels[(video_name, frame_idx)] = label
            frame_times[(video_name, frame_idx)] = t

    # Collect risk scores from predictions
    risk_scores = {}  # (video_name, frame_idx) -> score
    for video_name, pred_video in predictions.get("videos", {}).items():
        for t_sec, score in pred_video.get("risk", []):
            frame_idx = int(t_sec * fps)
            risk_scores[(video_name, frame_idx)] = score

    # Build arrays for AP calculation
    y_true = []
    y_score = []

    for key, label in frame_labels.items():
        if label == -1:  # Ignored
            continue
        score = risk_scores.get(key, 0.0)
        y_true.append(label)
        y_score.append(score)

    if not y_true:
        return {"Score_B": 0.0, "AP": 0.0, "F1_alarm": 0.0, "mTTA": 0.0}

    # Compute AP (Average Precision)
    # Sort by score descending
    sorted_indices = sorted(range(len(y_score)), key=lambda i: y_score[i], reverse=True)
    y_true_sorted = [y_true[i] for i in sorted_indices]

    # Compute precision at each recall level
    tp = 0
    fp = 0
    total_pos = sum(y_true)
    precisions = []
    recalls = []

    for label in y_true_sorted:
        if label == 1:
            tp += 1
        else:
            fp += 1
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / total_pos if total_pos > 0 else 0
        precisions.append(precision)
        recalls.append(recall)

    # AP = area under PR curve (using 11-point interpolation or all-point)
    # Use all-point interpolation (standard)
    ap_raw = 0.0
    if total_pos > 0:
        for i in range(len(precisions) - 1):
            ap_raw += precisions[i] * (recalls[i+1] - recalls[i])

    # Chance normalization
    r = total_pos / len(y_true) if len(y_true) > 0 else 0
    ap = max(0.0, (ap_raw - r) / (1 - r)) if r < 1 else 0.0

    # Alarms: maximal runs of frames with score >= THETA
    # Runs separated by < 2s are merged
    alarms = []  # (video_name, start_frame, end_frame, start_t, end_t)
    for video_name, pred_video in predictions.get("videos", {}).items():
        risk_data = pred_video.get("risk", [])
        if not risk_data:
            continue

        # Convert to frame-indexed scores
        frame_scores = {}
        for t_sec, score in risk_data:
            frame_idx = int(t_sec * fps)
            frame_scores[frame_idx] = score

        # Find runs
        in_run = False
        run_start = None
        for frame_idx in sorted(frame_scores.keys()):
            score = frame_scores[frame_idx]
            if score >= THETA and not in_run:
                in_run = True
                run_start = frame_idx
            elif score < THETA and in_run:
                in_run = False
                run_end = frame_idx - 1
                alarms.append({
                    "video": video_name,
                    "start_frame": run_start,
                    "end_frame": run_end,
                    "start_t": run_start / fps,
                    "end_t": run_end / fps,
                })

        if in_run and run_start is not None:
            # Run continues to end
            max_frame = max(frame_scores.keys())
            alarms.append({
                "video": video_name,
                "start_frame": run_start,
                "end_frame": max_frame,
                "start_t": run_start / fps,
                "end_t": max_frame / fps,
            })

    # Merge alarms separated by < 2s (within same video)
    merged_alarms = []
    for video_name in set(a["video"] for a in alarms):
        vid_alarms = [a for a in alarms if a["video"] == video_name]
        vid_alarms.sort(key=lambda a: a["start_t"])
        if not vid_alarms:
            continue
        current = vid_alarms[0]
        for alarm in vid_alarms[1:]:
            if alarm["start_t"] - current["end_t"] < 2.0:
                # Merge
                current["end_frame"] = alarm["end_frame"]
                current["end_t"] = alarm["end_t"]
            else:
                merged_alarms.append(current)
                current = alarm
        merged_alarms.append(current)

    # Match alarms to accidents
    # An alarm whose start lies in [s-W, s) of a still-unmatched accident matches it
    matched_accidents = set()
    matched_alarms = set()
    accident_ttas = []  # Time-to-accident for matched accidents

    for video_name, gt_video in ground_truth.items():
        accidents = [(ev[0], ev[1], i) for i, ev in enumerate(gt_video.get("events", [])) if ev[2] == "accident"]
        vid_alarms = [a for a in merged_alarms if a["video"] == video_name]

        for s, e, acc_idx in accidents:
            # Find earliest alarm with start in [s-W, s)
            best_alarm = None
            best_start = None
            for alarm_idx, alarm in enumerate(vid_alarms):
                if alarm_idx in matched_alarms:
                    continue
                if s - W <= alarm["start_t"] < s and (best_start is None or alarm["start_t"] < best_start):
                    best_start = alarm["start_t"]
                    best_alarm = alarm_idx

            if best_alarm is not None:
                matched_alarms.add(best_alarm)
                matched_accidents.add((video_name, acc_idx))
                tta = s - vid_alarms[best_alarm]["start_t"]
                accident_ttas.append(tta)

    # Compute metrics
    n_alarms = len(merged_alarms)
    n_accidents = len(matched_accidents)
    n_gt_accidents = sum(len([ev for ev in gt.get("events", []) if ev[2] == "accident"]) for gt in ground_truth.values())

    precision_alarm = n_accidents / n_alarms if n_alarms > 0 else 0.0
    recall_alarm = n_accidents / n_gt_accidents if n_gt_accidents > 0 else 0.0
    f1_alarm = 2 * precision_alarm * recall_alarm / (precision_alarm + recall_alarm) if (precision_alarm + recall_alarm) > 0 else 0.0

    mTTA = sum(accident_ttas) / len(accident_ttas) if accident_ttas else 0.0

    score_b = 0.4 * ap + 0.4 * f1_alarm + 0.2 * (mTTA / W)

    return {
        "Score_B": score_b,
        "AP": ap,
        "AP_raw": ap_raw,
        "F1_alarm": f1_alarm,
        "mTTA": mTTA,
        "n_alarms": n_alarms,
        "n_matched_alarms": n_accidents,
        "n_gt_accidents": n_gt_accidents,
    }


def evaluate_predictions(ground_truth: dict, predictions: dict) -> dict:
    """Main evaluation function."""
    # Part A
    part_a = evaluate_part_a(ground_truth, predictions)

    # Part B
    part_b = evaluate_part_b(ground_truth, predictions)

    # Model Score
    M = 0.7 * part_a["Score_A"] + 0.3 * part_b["Score_B"]

    return {
        "Score_A": part_a["Score_A"],
        "Score_B": part_b["Score_B"],
        "Model_Score": M,
        "Part_A_details": part_a,
        "Part_B_details": part_b,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate predictions (WIUT Hackathon)")
    parser.add_argument("--pred", required=True, help="Path to predictions.json")
    parser.add_argument("--gt", help="Path to ground_truth.json (optional)")
    parser.add_argument("--validate-only", action="store_true", help="Only validate format, no scoring")
    args = parser.parse_args()

    pred_path = Path(args.pred)
    predictions = load_json(pred_path)

    # Validate format
    is_valid, errors = validate_format([item for video_data in predictions.get("videos", {}).values() for item in video_data.get("events", [])])
    if not is_valid:
        print("Format validation FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    print("Format validation PASSED")
    total_events = sum(len(video_data.get("events", [])) for video_data in predictions.get("videos", {}).values())
    print(f"Total events: {total_events}")

    if args.validate_only:
        print("Validation only mode — exiting")
        return

    if args.gt:
        gt_path = Path(args.gt)
        ground_truth = load_json(gt_path)

        # Validate GT format (events only)
        gt_events = [item for video_data in ground_truth.values() for item in video_data.get("events", [])]
        gt_valid, gt_errors = validate_format(gt_events)
        if not gt_valid:
            print("Ground truth format invalid:", file=sys.stderr)
            for err in gt_errors:
                print(f"  - {err}", file=sys.stderr)
            sys.exit(1)

        # Evaluate
        results = evaluate_predictions(ground_truth, predictions)

        print("\n=== EVALUATION RESULTS ===")
        print(f"Score_A (Event Detection): {results['Score_A']:.4f}")
        print(f"Score_B (Accident Anticipation): {results['Score_B']:.4f}")
        print(f"Model Score (M): {results['Model_Score']:.4f}")

        print("\n--- Part A Details ---")
        for cls, scores in results['Part_A_details'].get('per_class', {}).items():
            print(f"  {cls}: F1@0.3={scores['f1_at_0.3']:.3f}, F1@0.5={scores['f1_at_0.5']:.3f}, F1@0.7={scores['f1_at_0.7']:.3f}, Mean={scores['mean_f1']:.3f}")

        print("\n--- Part B Details ---")
        pb = results['Part_B_details']
        print(f"  AP (chance-norm): {pb['AP']:.4f} (raw={pb.get('AP_raw', 0):.4f})")
        print(f"  F1_alarm: {pb['F1_alarm']:.4f}")
        print(f"  mTTA: {pb['mTTA']:.2f}s")
        print(f"  Alarms: {pb.get('n_alarms', 0)}, Matched: {pb.get('n_matched_alarms', 0)}, GT Accidents: {pb.get('n_gt_accidents', 0)}")


if __name__ == "__main__":
    main()

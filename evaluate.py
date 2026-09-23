#!/usr/bin/env python3
"""
evaluate.py — Prediction Evaluation Script

Compares predictions.json against ground truth (if provided) or validates format only.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Any


# List for deterministic ordering (matches engine/pipeline.py)
VALID_LABELS = [
    "speeding",
    "illegal_parking",
    "illegal_uturn",
    "wrong_way",
    "stop_line_crossing",
]


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
        
        if not isinstance(start, (int, float)) or start < 0:
            errors.append(f"Item {i}: start_sec must be non-negative number")
        if not isinstance(end, (int, float)) or end < 0:
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


def main():
    parser = argparse.ArgumentParser(description="Evaluate predictions")
    parser.add_argument("--pred", required=True, help="Path to predictions.json")
    parser.add_argument("--gt", help="Path to ground_truth.json (optional)")
    parser.add_argument("--validate-only", action="store_true", help="Only validate format, no scoring")
    args = parser.parse_args()

    pred_path = Path(args.pred)
    predictions = load_json(pred_path)

    # Validate format
    is_valid, errors = validate_format(predictions)
    if not is_valid:
        print("Format validation FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)
    
    print("Format validation PASSED")
    print(f"Total events: {len(predictions)}")
    
    if args.validate_only:
        print("Validation only mode — exiting")
        return

    # If ground truth provided, compute metrics
    if args.gt:
        gt_path = Path(args.gt)
        ground_truth = load_json(gt_path)
        
        gt_valid, gt_errors = validate_format(ground_truth)
        if not gt_valid:
            print("Ground truth format invalid:", file=sys.stderr)
            for err in gt_errors:
                print(f"  - {err}", file=sys.stderr)
            sys.exit(1)
        
        # Simple IoU-based matching for scoring (mock implementation)
        print("Ground truth loaded — scoring not fully implemented in mock version")
        print("Use --validate-only for format checking")


if __name__ == "__main__":
    main()
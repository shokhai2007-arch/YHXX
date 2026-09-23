#!/usr/bin/env python3
"""
run_submission.py — Judge Environment Runner

Reads video path from command line or stdin, calls solution.detect_events(),
writes predictions.json to current directory.
"""

import sys
import json
import argparse
from pathlib import Path

# Import solution module
sys.path.insert(0, str(Path(__file__).parent))
from solution import detect_events


def main():
    parser = argparse.ArgumentParser(description="Run submission on video file")
    parser.add_argument("video_path", nargs="?", help="Path to video file (MP4)")
    parser.add_argument("-o", "--output", default="predictions.json", help="Output JSON file")
    args = parser.parse_args()

    # If no video_path provided, try reading from stdin (one line)
    video_path = args.video_path
    if not video_path:
        video_path = sys.stdin.read().strip()
    
    if not video_path:
        parser.error("Video path required (argument or stdin)")

    video_path = Path(video_path)
    if not video_path.exists():
        print(f"Error: Video file not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing: {video_path}", file=sys.stderr)
    
    try:
        events = detect_events(str(video_path))
    except Exception as e:
        print(f"Error during detection: {e}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.write_text(json.dumps(events, indent=2))
    print(f"Predictions written to: {output_path}", file=sys.stderr)
    print(json.dumps(events, indent=2))


if __name__ == "__main__":
    main()
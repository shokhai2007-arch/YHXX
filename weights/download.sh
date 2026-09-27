#!/usr/bin/env bash
# weights/download.sh — No-op for mock AI implementation
# 
# This project uses a deterministic rule-based mock pipeline (engine/pipeline.py)
# that generates mock tracks from video hash and applies geometry rules.
# No external model weights are required.
#
# To swap for real AI: replace engine/pipeline.py with YOLO + ByteTrack,
# add weights here, and update this script to download them.

echo "Mock pipeline — no weights to download."
echo "Real AI would download weights here (e.g., YOLO, RT-DETR)."
exit 0

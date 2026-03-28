#!/bin/bash
# split_video.sh
# Split a long video into chunks of specified duration for parallel processing.
# Usage: ./split_video.sh <input_video> <chunk_duration_seconds> [overlap_seconds]
#
# Example: ./split_video.sh data/uploads/5f5d2a9f-b387-4572-80f7-17d524ecfc3b.mp4 600
#   → Creates chunks/5f5d2a9f-b387-4572-80f7-17d524ecfc3b/chunk_000.mp4, chunk_001.mp4, ...

set -e

INPUT="$1"
CHUNK_DURATION="${2:-600}"  # default 10 minutes
OVERLAP="${3:-0}"

if [[ -z "$INPUT" ]]; then
    echo "Usage: $0 <input_video> <chunk_duration_seconds> [overlap_seconds]"
    echo "Example: $0 video.mp4 600   # split into 10-minute chunks"
    exit 1
fi

if [[ ! -f "$INPUT" ]]; then
    echo "Error: File not found: $INPUT"
    exit 1
fi

# Derive output directory from input filename (without extension)
BASENAME=$(basename "$INPUT")
FILENAME="${BASENAME%.*}"
HASH="${FILENAME:0:36}"  # UUID-like hash

OUTPUT_DIR="data/chunks/$HASH"
mkdir -p "$OUTPUT_DIR"

echo "Input:  $INPUT"
echo "Output: $OUTPUT_DIR"
echo "Chunk:  ${CHUNK_DURATION}s (${OVERLAP}s overlap)"
echo ""

# Get total duration
DURATION=$(ffprobe -v error -show_entries format=duration \
    -of default=noprint_wrappers=1:nokey=1 "$INPUT")
echo "Total duration: ${DURATION}s ($(echo "scale=1; $DURATION/60" | bc) minutes)"

# Calculate number of chunks
# Using -ss before -i (input seeking) for fast seeking
# Using -t for duration limit
# Overlap handled by starting next chunk OVERLAP seconds before previous ends

CHUNK_NUM=0
START=0

while (( $(echo "$START < $DURATION" | bc -l) )); do
    END=$(echo "scale=6; $START + $CHUNK_DURATION" | bc -l)
    
    # Don't exceed total duration
    if (( $(echo "$END > $DURATION" | bc -l) )); then
        END="$DURATION"
    fi
    
    LEN=$(echo "scale=6; $END - $START" | bc -l)
    OUTPUT="$OUTPUT_DIR/chunk_$(printf '%03d' $CHUNK_NUM).mp4"
    
    echo "[$CHUNK_NUM] ${START}s - ${END}s (len: ${LEN}s) → $(basename "$OUTPUT")"
    
    ffmpeg -v error -y \
        -ss "$START" \
        -i "$INPUT" \
        -t "$LEN" \
        -c copy \
        -avoid_negative_ts make_zero \
        "$OUTPUT"
    
    START=$(echo "scale=6; $END - $OVERLAP" | bc -l)
    CHUNK_NUM=$((CHUNK_NUM + 1))
done

echo ""
echo "Done! Created $CHUNK_NUM chunks in $OUTPUT_DIR"

# List chunks
echo ""
echo "Chunks:"
ls -lh "$OUTPUT_DIR"

#!/usr/bin/env python3
"""
split_video.py
Split a long video into chunks of specified duration for parallel processing.

Usage:
    python split_video.py <input_video> [chunk_duration_seconds] [overlap_seconds]

Examples:
    python split_video.py data/uploads/5f5d2a9f-...mp4           # 10-min chunks, no overlap
    python split_video.py data/uploads/5f5d2a9f-...mp4 300    # 5-min chunks
    python split_video.py data/uploads/5f5d2a9f-...mp4 600 5   # 10-min chunks, 5s overlap
"""

import sys
import os
import re
import subprocess
import argparse


def get_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True, check=True
    )
    return float(result.stdout.strip())


def split_video(
    input_path: str,
    chunk_duration: float = 600.0,
    overlap: float = 0.0,
    output_dir: str = None,
    dry_run: bool = False,
):
    """
    Split video into chunks.

    Args:
        input_path: Path to input video
        chunk_duration: Duration of each chunk in seconds (default 600s = 10min)
        overlap: Overlap between chunks in seconds (default 0)
        output_dir: Output directory (default: data/chunks/<hash>/)
        dry_run: If True, only print what would be done without actually splitting
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")

    # Parse UUID-like hash from filename (first 36 chars of basename without ext)
    basename = os.path.basename(input_path)
    filename = os.path.splitext(basename)[0]
    hash_part = filename[:36]

    if output_dir is None:
        output_dir = f"data/chunks/{hash_part}"
    os.makedirs(output_dir, exist_ok=True)

    total_duration = get_duration(input_path)
    print(f"Input:    {input_path}")
    print(f"Output:   {output_dir}")
    print(f"Total:    {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
    print(f"Chunk:    {chunk_duration}s ({chunk_duration/60:.1f} minutes)")
    print(f"Overlap:  {overlap}s")
    print()

    step = chunk_duration - overlap
    if step <= 0:
        raise ValueError(f"Overlap ({overlap}s) must be less than chunk duration ({chunk_duration}s)")

    chunks = []
    start = 0.0
    chunk_num = 0

    while start < total_duration:
        end = min(start + chunk_duration, total_duration)
        length = end - start

        chunk_name = f"chunk_{chunk_num:03d}.mp4"
        chunk_path = os.path.join(output_dir, chunk_name)

        chunks.append({
            "index": chunk_num,
            "start": start,
            "end": end,
            "length": length,
            "path": chunk_path,
        })

        print(f"  Chunk {chunk_num:3d}: {start:8.1f}s - {end:8.1f}s "
              f"(len: {length:7.1f}s) → {chunk_name}")

        if not dry_run:
            cmd = [
                "ffmpeg", "-v", "error", "-y",
                "-ss", str(start),
                "-i", input_path,
                "-t", str(length),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                chunk_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  ERROR: {result.stderr.strip()}")
                raise RuntimeError(f"Failed to create {chunk_name}")
            else:
                size = os.path.getsize(chunk_path) / (1024 * 1024)
                print(f"           Created ({size:.1f} MB)")

        start += step
        chunk_num += 1

    print()
    print(f"Created {len(chunks)} chunks")

    # Print summary table
    print()
    print(f"{'#':>3}  {'Start':>8}  {'End':>8}  {'Length':>7}  {'File':>20}  {'Size'}")
    print("-" * 75)
    total_size = 0
    for c in chunks:
        size = os.path.getsize(c["path"]) / (1024 * 1024) if os.path.exists(c["path"]) else 0
        total_size += size
        print(f"{c['index']:3d}  {c['start']:8.1f}  {c['end']:8.1f}  {c['length']:7.1f}s  "
              f"{os.path.basename(c['path']):>20}  {size:6.1f} MB")
    print("-" * 75)
    print(f"{'Total':>43}  {total_size:6.1f} MB (combined)")

    # Also generate a manifest file
    manifest_path = os.path.join(output_dir, "manifest.txt")
    with open(manifest_path, "w") as f:
        f.write(f"# Chunk Manifest\n")
        f.write(f"# Source: {input_path}\n")
        f.write(f"# Total duration: {total_duration:.1f}s\n")
        f.write(f"# Chunk duration: {chunk_duration}s\n")
        f.write(f"# Overlap: {overlap}s\n")
        f.write(f"# Created: {os.popen('date').read().strip()}\n")
        f.write(f"\n")
        for c in chunks:
            f.write(f"{c['index']:03d}|{c['start']:.3f}|{c['end']:.3f}|{c['length']:.3f}|{os.path.basename(c['path'])}\n")

    print(f"\nManifest: {manifest_path}")

    return chunks


def main():
    parser = argparse.ArgumentParser(
        description="Split a video into chunks for parallel processing"
    )
    parser.add_argument("input", help="Input video file path")
    parser.add_argument(
        "--duration", "-d", type=float, default=600.0,
        help="Chunk duration in seconds (default: 600 = 10 minutes)"
    )
    parser.add_argument(
        "--overlap", "-o", type=float, default=0.0,
        help="Overlap between chunks in seconds (default: 0)"
    )
    parser.add_argument(
        "--output", "-O", default=None,
        help="Output directory (default: data/chunks/<hash>/)"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Show what would be done without actually splitting"
    )

    args = parser.parse_args()

    try:
        chunks = split_video(
            args.input,
            chunk_duration=args.duration,
            overlap=args.overlap,
            output_dir=args.output,
            dry_run=args.dry_run,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

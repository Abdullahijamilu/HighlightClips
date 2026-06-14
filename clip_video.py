#!/usr/bin/env python3
"""
YouTube Video Clipper
=====================
Downloads a single YouTube video and extracts multiple 40-60 second clips from it.

Usage:
    python clip_video.py <video_url> [options]

Examples:
    python clip_video.py https://www.youtube.com/watch?v=VIDEO_ID
    python clip_video.py https://www.youtube.com/watch?v=VIDEO_ID --clips 20 --min 40 --max 60
    python clip_video.py https://www.youtube.com/watch?v=VIDEO_ID --clips 30 --output ./my_clips
    python clip_video.py https://www.youtube.com/watch?v=VIDEO_ID --strategy spread
    python clip_video.py https://www.youtube.com/watch?v=VIDEO_ID --no-verify-ssl

Arguments:
    video_url           Full YouTube video URL
    --clips             Number of clips to extract (default: 20)
    --min               Minimum clip length in seconds (default: 40)
    --max               Maximum clip length in seconds (default: 60)
    --output            Output folder (default: ./clips)
    --strategy          How to pick clip start points:
                          spread  — evenly distributed across the video (default)
                          random  — random start points
                          start   — all clips taken from beginning of video
    --skip-intro        Seconds to skip at the start of the video (default: 30)
    --skip-outro        Seconds to skip at the end of the video (default: 30)
    --overwrite         Overwrite existing clips
    --no-verify-ssl     Disable SSL certificate verification
    --keep-source       Keep the downloaded source video (deleted by default)
"""

import argparse
import os
import random
import subprocess
import sys
import json
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    sys.exit("ERROR: yt-dlp not installed. Run: pip install yt-dlp")


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────
OUTPUT_DIR   = Path("clips")
SUCCESS_LOG  = Path("clipped_urls.txt")
FAILURE_LOG  = Path("failed_clips.txt")


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def log(msg: str):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        # Fallback for Windows consoles that can't render emoji
        safe = msg.encode("ascii", errors="replace").decode("ascii")
        print(safe, flush=True)


def get_video_duration(path: str) -> float:
    """Get duration of a video file in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")
    return float(result.stdout.strip())


def get_video_info(url: str, no_ssl: bool = False) -> dict:
    """Fetch video metadata without downloading."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "nocheckcertificate": no_ssl,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def download_video(url: str, out_path: str, no_ssl: bool = False) -> str:
    """Download 480p MP4 (sufficient for clip re-encoding). Returns path to downloaded file."""
    out_tmpl = out_path + ".%(ext)s"
    opts = {
        "quiet": False,
        "no_warnings": True,
        # Use smallest available video + audio to minimize download time.
        # Clips are re-encoded to 1080x1920 by ffmpeg anyway.
        "format": "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]/worst",
        "format_sort": ["res", "+size"],
        "outtmpl": out_tmpl,
        "merge_output_format": "mp4",
        "nocheckcertificate": no_ssl,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    # Find the file that was created
    parent = Path(out_path).parent
    stem   = Path(out_path).name
    for f in parent.iterdir():
        if f.stem == stem or f.name.startswith(stem):
            return str(f)
    raise FileNotFoundError(f"Downloaded file not found near {out_path}")


def compute_start_points(
    video_duration: float,
    clip_count: int,
    clip_min: int,
    clip_max: int,
    skip_intro: int,
    skip_outro: int,
    strategy: str,
) -> list[float]:
    """
    Calculate start timestamps for each clip.
    Returns a list of start times in seconds.
    """
    usable_start = skip_intro
    usable_end   = video_duration - skip_outro - clip_max

    if usable_end <= usable_start:
        # Video too short — use what we have
        usable_start = 0
        usable_end   = max(0, video_duration - clip_max)

    usable_range = usable_end - usable_start

    if strategy == "spread":
        if clip_count == 1:
            return [usable_start]
        step = usable_range / (clip_count - 1)
        return [usable_start + i * step for i in range(clip_count)]

    elif strategy == "random":
        if usable_range <= 0:
            return [usable_start] * clip_count
        points = sorted(random.uniform(usable_start, usable_end) for _ in range(clip_count))
        return points

    elif strategy == "start":
        # Clips taken sequentially from the beginning
        points = []
        t = usable_start
        for _ in range(clip_count):
            points.append(t)
            t += clip_min  # each clip starts right after the previous minimum
            if t > usable_end:
                t = usable_start  # wrap around
        return points

    else:
        raise ValueError(f"Unknown strategy: {strategy}")


def extract_clip(
    source: str,
    start: float,
    duration: float,
    out_path: str,
) -> bool:
    """
    Use ffmpeg to extract a clip from source.
    Seeks to start with -ss BEFORE -i for speed (keyframe seek),
    then uses -t for duration. Output is vertical-friendly 1080x1920
    if source is vertical, otherwise letterboxed.
    """
    # Scale/pad to 1080x1920 vertical format
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,"
        "format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-i", source,
        "-t", f"{duration:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-ar", "44100", "-b:a", "128k",
        "-movflags", "+faststart",
        out_path
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 5000


def format_time(seconds: float) -> str:
    """Format seconds as MM:SS for display."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Extract multiple 40-60 second clips from a single YouTube video."
    )
    parser.add_argument("url",            help="YouTube video URL")
    parser.add_argument("--clips",        type=int,   default=20,
                        help="Number of clips to extract (default: 20)")
    parser.add_argument("--min",          type=int,   default=40,
                        help="Minimum clip length in seconds (default: 40)")
    parser.add_argument("--max",          type=int,   default=60,
                        help="Maximum clip length in seconds (default: 60)")
    parser.add_argument("--output",       default="./clips",
                        help="Output folder (default: ./clips)")
    parser.add_argument("--strategy",     default="spread",
                        choices=["spread", "random", "start"],
                        help="Clip placement strategy (default: spread)")
    parser.add_argument("--skip-intro",   type=int,   default=30,
                        help="Seconds to skip at video start (default: 30)")
    parser.add_argument("--skip-outro",   type=int,   default=30,
                        help="Seconds to skip at video end (default: 30)")
    parser.add_argument("--overwrite",    action="store_true",
                        help="Overwrite existing clip files")
    parser.add_argument("--no-verify-ssl", action="store_true",
                        help="Disable SSL certificate verification")
    parser.add_argument("--keep-source",  action="store_true",
                        help="Keep the source video after clipping")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    success_log = output_dir / "clipped_log.txt"
    failure_log = output_dir / "failed_log.txt"

    print("=" * 60)
    print("  YouTube Video Clipper")
    print("=" * 60)

    # ── Fetch metadata ──
    log(f"\n📋 Fetching video info…")
    try:
        info = get_video_info(args.url, args.no_verify_ssl)
    except Exception as e:
        sys.exit(f"ERROR: Could not fetch video info: {e}")

    title    = info.get("title", "Unknown")
    duration = info.get("duration") or 0
    log(f"   Title    : {title}")
    log(f"   Duration : {format_time(duration)} ({duration:.0f}s)")

    if duration < args.min:
        sys.exit(f"ERROR: Video is only {duration:.0f}s long — too short for {args.min}s clips.")

    # ── Download source ──
    log(f"\n⬇️  Downloading source video…")
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        src_base = os.path.join(tmpdir, "source")
        try:
            src_path = download_video(args.url, src_base, args.no_verify_ssl)
        except Exception as e:
            sys.exit(f"ERROR: Download failed: {e}")

        # Use ffprobe duration (more accurate than metadata)
        actual_duration = get_video_duration(src_path)
        log(f"   Downloaded: {Path(src_path).name} ({actual_duration:.1f}s)")

        # ── Compute clip start points ──
        starts = compute_start_points(
            video_duration = actual_duration,
            clip_count     = args.clips,
            clip_min       = args.min,
            clip_max       = args.max,
            skip_intro     = args.skip_intro,
            skip_outro     = args.skip_outro,
            strategy       = args.strategy,
        )

        total     = len(starts)
        succeeded = 0
        failed    = 0

        log(f"\n✂️  Extracting {total} clips (strategy: {args.strategy})\n")

        for i, start in enumerate(starts, 1):
            # Vary clip length between min and max
            clip_dur  = random.randint(args.min, args.max)
            # Clamp so we don't go past the video
            clip_dur  = min(clip_dur, actual_duration - start)
            if clip_dur < 5:
                log(f"[{i:>3}/{total}] ⚠️  Start {format_time(start)} too close to end — skipping.")
                failed += 1
                continue

            out_name = f"clip_{i:03d}.mp4"
            out_path = str(output_dir / out_name)

            log(f"[{i:>3}/{total}] {format_time(start)} → {format_time(start + clip_dur)}  ({clip_dur}s)  →  {out_name}")

            if Path(out_path).exists() and not args.overwrite:
                log(f"         ⏭  Already exists — skipping.")
                succeeded += 1
                continue

            try:
                ok = extract_clip(src_path, start, clip_dur, out_path)
                if ok:
                    log(f"         ✓  Saved")
                    with open(success_log, "a") as f:
                        f.write(f"{out_name}  start={format_time(start)}  dur={clip_dur}s  src={args.url}\n")
                    succeeded += 1
                else:
                    raise RuntimeError("ffmpeg returned error or empty file")
            except Exception as e:
                log(f"         ✗  Failed: {e}")
                with open(failure_log, "a") as f:
                    f.write(f"{out_name}  start={format_time(start)}  error={e}\n")
                failed += 1
                if Path(out_path).exists():
                    Path(out_path).unlink()

        # ── Keep or delete source ──
        if args.keep_source:
            dest = output_dir / Path(src_path).name
            import shutil
            shutil.copy2(src_path, dest)
            log(f"\n📁 Source video kept: {dest}")
        else:
            log(f"\n🗑  Source video deleted (use --keep-source to keep it)")

    # ── Summary ──
    print("\n" + "=" * 60)
    print(f"  Done!")
    print(f"  ✓  Succeeded : {succeeded}")
    print(f"  ✗  Failed    : {failed}")
    print(f"  📂 Output    : {output_dir}/")
    print(f"  📄 Log       : {success_log}")
    print("=" * 60)


if __name__ == "__main__":
    main()

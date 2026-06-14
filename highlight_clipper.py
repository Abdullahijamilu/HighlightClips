#!/usr/bin/env python3
"""
⚽ Football Highlight Clipper — Pro Edition
===========================================
Automatically detects and clips the most hype moments in football videos:
  • Goals, bicycle kicks, volleys, free kicks, headers
  • Shocking saves, red cards, VAR drama, missed sitters
  • Crowd roar spikes (audio RMS detection)
  • Commentary keyword detection via Whisper AI

Each clip features:
  • 8s before the moment + up to 50s total
  • Cinematic vertical (9:16) or horizontal (16:9) output
  • Animated captions: slide-in, bounce, shake effects via FFmpeg
  • Sport-specific emoji labels with outline glow
  • "Subscribe for more 🔥" CTA in the final 7 seconds
  • Colour-graded look (vibrant contrast boost)

Usage:
    python highlight_clipper.py <youtube_url_or_local_file> [options]

Examples:
    python highlight_clipper.py https://youtu.be/VIDEO_ID
    python highlight_clipper.py match.mp4 --clips 15 --format vertical
    python highlight_clipper.py match.mp4 --clips 10 --style cinematic

Options:
    --clips N           Number of clips to extract (default: 20)
    --output DIR        Output folder (default: ./highlights)
    --format FMT        Output format: vertical (9:16) | horizontal (16:9) (default: vertical)
    --style STYLE       Caption style theme: cinematic | retro | neon | clean (default: cinematic)
    --whisper-model M   Whisper model: tiny/base/small/medium/large (default: small)
    --min-gap N         Minimum seconds between clips (default: 30)
    --no-verify-ssl     Disable SSL verification for YouTube downloads
    --keep-source       Keep the downloaded source video
    --overwrite         Re-export clips that already exist
"""

import argparse
import os
import random
import re
import subprocess
import sys
import shutil
import tempfile
from pathlib import Path

import numpy as np

try:
    import librosa
except ImportError:
    sys.exit("Missing dependency: pip install librosa")
try:
    import whisper
except ImportError:
    sys.exit("Missing dependency: pip install openai-whisper")
try:
    import yt_dlp
except ImportError:
    sys.exit("Missing dependency: pip install yt-dlp")


# ─────────────────────────────────────────────────────────────
# ⚽  FOOTBALL MOMENT DEFINITIONS
#     (pattern, display_label, emoji, base_score, caption_size_boost)
# ─────────────────────────────────────────────────────────────
FOOTBALL_MOMENTS = [
    # ── Goals (highest priority) ────────────────────────────────
    (r"goo+a+l+!?",                      "GOOOAL!",            "⚽", 10, 1.3),
    (r"it'?s? a goal",                   "GOOOAL!",            "⚽", 10, 1.3),
    (r"hat.?trick",                      "HAT TRICK!",         "🎩", 10, 1.2),
    (r"bicycle kick|overhead kick",      "BICYCLE KICK!",      "⚽",  9, 1.2),
    (r"volley",                          "WHAT A VOLLEY!",     "⚽",  8, 1.1),
    (r"curler|top.?corner|top corner",   "TOP CORNER!",        "🎯",  9, 1.2),
    (r"header",                          "HEADER!",            "⚽",  7, 1.0),
    (r"free.?kick goal|scored.*free",    "FREE KICK GOAL!",    "⚽",  9, 1.2),
    (r"penalty.*goal|scored.*penalty",   "PENALTY GOAL!",      "⚽",  8, 1.1),
    (r"long.?range|from distance|30.?yard|25.?yard", "LONG RANGE STUNNER!", "💥", 9, 1.2),
    (r"tap.?in|easy goal",               "TAP IN!",            "⚽",  5, 0.9),
    (r"own goal",                        "OWN GOAL!",          "😬",  7, 1.0),
    (r"screamer|thunderbolt",            "WHAT A SCREAMER!",   "💥", 10, 1.3),
    (r"chip|chipped|lob",               "CHEEKY CHIP!",        "🎩",  8, 1.1),
    (r"late goal|equalise|equalis|last.?minute", "LAST MINUTE DRAMA!", "⏱",  9, 1.2),

    # ── Shocking misses ─────────────────────────────────────────
    (r"how did he miss|incredible miss|unbelievable miss|missed (an )?open goal",
                                         "HOW DID HE MISS?!",  "😱",  9, 1.2),
    (r"over the bar|wide of the post|skied|ballooned",
                                         "WHAT A MISS!",       "🤦",  7, 1.0),
    (r"post|crossbar|off the woodwork|hit the bar",
                                         "OFF THE POST!",      "😬",  8, 1.1),

    # ── Saves ───────────────────────────────────────────────────
    (r"what a save|incredible save|unbelievable save|fingertip",
                                         "WHAT A SAVE!",       "🧤", 10, 1.2),
    (r"save|keeper|goalkeeper",          "BRILLIANT SAVE!",    "🧤",  7, 1.0),
    (r"penalty save|saved.*penalty",     "PENALTY SAVED!",     "🧤", 10, 1.3),

    # ── Discipline / VAR Drama ──────────────────────────────────
    (r"red card|sent off|straight red",  "RED CARD!",          "🟥",  9, 1.2),
    (r"yellow card|booked",              "YELLOW CARD!",       "🟨",  5, 0.9),
    (r"penalty|spot.?kick",             "PENALTY!",            "⚽",  8, 1.1),
    (r"\bvar\b|video assistant|overturned|check.*referee",
                                         "VAR DRAMA!",         "📺",  7, 1.0),
    (r"offside",                         "OFFSIDE!",           "🚩",  5, 0.9),

    # ── Emotional / Crowd ───────────────────────────────────────
    (r"incredible|unbelievable|extraordinary|outrageous",
                                         "UNBELIEVABLE!",      "😱",  7, 1.0),
    (r"what a (goal|shot|play|strike|moment|finish)",
                                         "WHAT A MOMENT!",     "🔥",  8, 1.1),
    (r"oh my (god|goodness|word)?",      "OH MY!",             "😲",  6, 1.0),
    (r"comeback|came back|levelled",     "WHAT A COMEBACK!",   "💪",  9, 1.2),
    (r"record|history|first time ever",  "HISTORY MADE!",      "📖",  8, 1.1),
    (r"final whistle|full.?time",        "FULL TIME!",         "🏁",  6, 0.9),
    (r"champion|champions|winner|victory","CHAMPIONS!",        "🏆", 10, 1.3),
    (r"injury|injured|down on the pitch","PLAYER DOWN!",       "🚑",  5, 0.9),
]

# ─────────────────────────────────────────────────────────────
# 🎨  CAPTION STYLE THEMES
# ─────────────────────────────────────────────────────────────
CAPTION_THEMES = {
    "cinematic": {
        "styles": [
            {"color": "white",   "shadow": "#000000@0.9", "font": "Impact",
             "outline": "black", "outline_w": 6, "anim": "slide"},
            {"color": "#FFD700", "shadow": "#7B4F00@0.9", "font": "Impact",
             "outline": "#3D2600", "outline_w": 6, "anim": "bounce"},
            {"color": "white",   "shadow": "#CC0000@0.9", "font": "Impact",
             "outline": "#8B0000", "outline_w": 5, "anim": "slide"},
        ],
        "bg_box": True,
    },
    "neon": {
        "styles": [
            {"color": "#39FF14", "shadow": "#003D00@0.9", "font": "DejaVu Sans Bold",
             "outline": "#00FF00", "outline_w": 3, "anim": "slide"},
            {"color": "#FF073A", "shadow": "#3D0011@0.9", "font": "DejaVu Sans Bold",
             "outline": "#FF0000", "outline_w": 3, "anim": "bounce"},
            {"color": "#00FFFF", "shadow": "#003D3D@0.9", "font": "DejaVu Sans Bold",
             "outline": "#0088FF", "outline_w": 3, "anim": "slide"},
        ],
        "bg_box": False,
    },
    "retro": {
        "styles": [
            {"color": "#FFF200", "shadow": "#000000@0.9", "font": "Impact",
             "outline": "black", "outline_w": 8, "anim": "bounce"},
            {"color": "#FF6600", "shadow": "#000000@0.9", "font": "Impact",
             "outline": "black", "outline_w": 7, "anim": "slide"},
            {"color": "white",   "shadow": "#000000@0.9", "font": "Impact",
             "outline": "black", "outline_w": 8, "anim": "slide"},
        ],
        "bg_box": True,
    },
    "clean": {
        "styles": [
            {"color": "white",   "shadow": "black@0.8", "font": "DejaVu Sans Bold",
             "outline": "black", "outline_w": 4, "anim": "slide"},
            {"color": "#E8E8E8", "shadow": "black@0.8", "font": "DejaVu Sans Bold",
             "outline": "black", "outline_w": 4, "anim": "slide"},
        ],
        "bg_box": False,
    },
}

SUBSCRIBE_TEXT = "Subscribe for more 🔥"
PRE_MOMENT_SECS = 8
CLIP_TOTAL_SECS = 50
SUBSCRIBE_LAST  = 7

VIDEO_FORMATS = {
    "vertical":   {"w": 1080, "h": 1920},
    "horizontal": {"w": 1920, "h": 1080},
}


# ─────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────
def log(msg: str):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        safe = msg.encode("ascii", errors="replace").decode("ascii")
        print(safe, flush=True)

def run(cmd: list, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)

def ffprobe_duration(path: str) -> float:
    r = run(["ffprobe", "-v", "quiet", "-show_entries",
             "format=duration", "-of", "csv=p=0", path])
    return float(r.stdout.strip())

def fmt(secs: float) -> str:
    m, s = int(secs // 60), int(secs % 60)
    return f"{m:02d}:{s:02d}"

def safe_text(s: str) -> str:
    """Escape special characters for ffmpeg drawtext."""
    for ch, esc in [("\\", "\\\\"), ("'", "\\'"), (":", "\\:"),
                    (",", "\\,"), ("[", "\\["), ("]", "\\]")]:
        s = s.replace(ch, esc)
    return s


# ─────────────────────────────────────────────────────────────
# Step 1 — Acquire source video
# ─────────────────────────────────────────────────────────────
def acquire_source(input_src: str, dest_dir: str, no_ssl: bool) -> str:
    if os.path.isfile(input_src):
        log("   📁 Local file detected.")
        dst = os.path.join(dest_dir, "source" + Path(input_src).suffix)
        shutil.copy2(input_src, dst)
        return dst

    log("   ⬇️  Downloading from YouTube…")
    out_tmpl = os.path.join(dest_dir, "source.%(ext)s")
    opts = {
        "quiet": False,
        "no_warnings": True,
        # Use smallest available video + audio to minimize download time.
        # Clips are re-encoded to target resolution by ffmpeg anyway.
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
        ydl.download([input_src])

    files = list(Path(dest_dir).glob("source.*"))
    if not files:
        raise FileNotFoundError("Download produced no output file.")
    return str(files[0])


# ─────────────────────────────────────────────────────────────
# Step 2 — Extract audio
# ─────────────────────────────────────────────────────────────
def extract_audio(video_path: str, out_wav: str):
    run(["ffmpeg", "-y", "-i", video_path,
         "-ac", "1", "-ar", "16000", "-vn", out_wav])


# ─────────────────────────────────────────────────────────────
# Step 3 — RMS energy spike detection (crowd roar)
# ─────────────────────────────────────────────────────────────
def detect_energy_spikes(wav_path: str) -> list:
    log("   📊 Scanning audio energy for crowd roars…")
    y, sr = librosa.load(wav_path, sr=16000, mono=True)

    frame_len = int(sr * 0.5)
    hop_len   = int(sr * 0.25)
    rms       = librosa.feature.rms(y=y, frame_length=frame_len, hop_length=hop_len)[0]
    times     = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_len)

    # Dynamic threshold: mean + 2.2 * std  (slightly tighter than before)
    threshold = np.mean(rms) + 2.2 * np.std(rms)
    rms_max   = np.max(rms)
    spikes    = []

    i = 0
    while i < len(rms):
        if rms[i] > threshold:
            j = i
            while j < len(rms) and rms[j] > threshold:
                j += 1
            peak_idx  = i + int(np.argmax(rms[i:j]))
            peak_time = float(times[peak_idx])
            score     = float(min(10.0, (rms[peak_idx] - threshold) / max(1e-9, rms_max - threshold) * 10))
            # Sustained roar bonus: wider spike = more exciting
            duration_bonus = min(2.0, (j - i) * 0.25 * 0.1)
            spikes.append((peak_time, round(score + duration_bonus, 2)))
            i = j
        else:
            i += 1

    log(f"   Found {len(spikes)} audio spike(s).")
    return spikes


# ─────────────────────────────────────────────────────────────
# Step 4 — Whisper transcription + football keyword detection
# ─────────────────────────────────────────────────────────────
def transcribe_and_detect(wav_path: str, model) -> list:
    """Returns list of (timestamp_sec, score, label, emoji, size_boost)."""
    log("   🎙  Transcribing commentary with Whisper…")
    result = model.transcribe(wav_path, fp16=False, word_timestamps=True)

    detections = []
    for seg in result.get("segments", []):
        text  = seg.get("text", "").lower().strip()
        start = float(seg.get("start", 0.0))

        for pattern, label, emoji, base_score, size_boost in FOOTBALL_MOMENTS:
            if re.search(pattern, text, re.IGNORECASE):
                # Exclamation mark bonus — commentator excitement
                exclaim_bonus = min(2.0, text.count("!") * 0.4)
                # CAPS bonus — commentator shouting
                caps_ratio = sum(1 for c in seg.get("text", "") if c.isupper()) / max(1, len(seg.get("text", "")))
                caps_bonus = min(1.5, caps_ratio * 5)
                total_score = round(base_score + exclaim_bonus + caps_bonus, 2)
                detections.append((start, total_score, label, emoji, size_boost))
                break  # one label per segment

    log(f"   Found {len(detections)} keyword moment(s).")
    return detections


# ─────────────────────────────────────────────────────────────
# Step 5 — Merge & rank moments
# ─────────────────────────────────────────────────────────────
def merge_moments(energy_spikes, kw_detections, min_gap, video_duration, max_clips) -> list:
    events = []
    for t, score in energy_spikes:
        events.append({"time": t, "score": score, "label": None,
                       "emoji": "🔊", "size_boost": 1.0})
    for t, score, label, emoji, size_boost in kw_detections:
        events.append({"time": t, "score": score, "label": label,
                       "emoji": emoji, "size_boost": size_boost})

    if not events:
        return []

    events.sort(key=lambda e: e["time"])

    # Merge events within 5s of each other
    merged = []
    for ev in events:
        if merged and abs(ev["time"] - merged[-1]["time"]) < 5.0:
            prev = merged[-1]
            if ev["score"] > prev["score"]:
                prev["score"] = ev["score"]
            if ev["label"] and not prev["label"]:
                prev["label"]      = ev["label"]
                prev["emoji"]      = ev["emoji"]
                prev["size_boost"] = ev["size_boost"]
        else:
            merged.append({**ev})

    for m in merged:
        if not m["label"]:
            m["label"]      = "WHAT A MOMENT!"
            m["emoji"]      = "🔥"
            m["size_boost"] = 1.0

    # Sort by score descending, apply min-gap suppression
    merged.sort(key=lambda e: e["score"], reverse=True)
    selected, used_times = [], []

    for ev in merged:
        t = ev["time"]
        if all(abs(t - u) >= min_gap for u in used_times):
            clip_start = max(0.0, t - PRE_MOMENT_SECS)
            clip_end   = clip_start + CLIP_TOTAL_SECS
            if clip_end > video_duration:
                clip_start = max(0.0, video_duration - CLIP_TOTAL_SECS)
            ev["clip_start"] = clip_start
            selected.append(ev)
            used_times.append(t)
        if len(selected) >= max_clips:
            break

    selected.sort(key=lambda e: e["clip_start"])

    log(f"\n   🎯 Selected {len(selected)} highlight(s):")
    for i, m in enumerate(selected, 1):
        log(f"   {i:>3}. {fmt(m['clip_start'])}  score={m['score']:.1f}  {m['emoji']} {m['label']}")
    return selected


# ─────────────────────────────────────────────────────────────
# Step 6 — Build stylish ffmpeg caption filter
# ─────────────────────────────────────────────────────────────
def build_caption_filter(label: str, emoji: str, style: dict,
                          size_boost: float, clip_dur: float,
                          vid_w: int, vid_h: int) -> str:
    """
    Builds a drawtext filter chain with:
     - Animated main caption (slide-in from top OR bounce)
     - Emoji displayed separately at larger size
     - Subscribe CTA fading in near the end
    """
    main_text  = safe_text(label)
    emoji_text = safe_text(emoji)
    sub_text   = safe_text(SUBSCRIBE_TEXT)

    color     = style["color"]
    outline   = style["outline"]
    outline_w = style["outline_w"]
    font      = style["font"]
    anim      = style.get("anim", "slide")

    base_size  = int(min(vid_w, vid_h) * 0.075 * size_boost)  # responsive font size
    emoji_size = int(base_size * 1.5)
    sub_size   = int(base_size * 0.55)

    cap_end   = clip_dur - SUBSCRIBE_LAST - 1
    sub_start = clip_dur - SUBSCRIBE_LAST

    # ── Animation expressions ──────────────────────────────────
    # y_target for caption: ~15% from top
    y_cap = f"h*0.14"

    if anim == "slide":
        # Slide in from above in 0.35s, stay, fade at cap_end-0.5s
        y_expr  = f"if(lt(t\\,0.35)\\, {y_cap}-(0.35-t)/0.35*h*0.25\\, {y_cap})"
        alpha   = f"if(lt(t\\,0.35)\\, t/0.35\\, if(gt(t\\,{cap_end-0.5:.2f})\\, ({cap_end:.2f}-t)/0.5\\, 1))"
    else:  # bounce
        # Overshoot and settle in 0.5s
        y_expr  = (
            f"if(lt(t\\,0.5)\\,"
            f" {y_cap}-(1-t/0.5)*(1-t/0.5)*h*0.18*max(0\\,sin(t/0.5*3.14))\\,"
            f" {y_cap})"
        )
        alpha   = f"if(lt(t\\,0.2)\\, t/0.2\\, if(gt(t\\,{cap_end-0.5:.2f})\\, ({cap_end:.2f}-t)/0.5\\, 1))"

    # ── Emoji (centred, slightly above caption text) ───────────
    emoji_filter = (
        f"drawtext=text='{emoji_text}'"
        f":font='DejaVu Sans'"
        f":fontsize={emoji_size}"
        f":fontcolor='white'"
        f":bordercolor='black'"
        f":borderw=4"
        f":x=(w-text_w)/2"
        f":y=h*0.05"
        f":alpha='{alpha}'"
        f":enable='between(t,0,{cap_end:.2f})'"
    )

    # ── Main label ─────────────────────────────────────────────
    caption_filter = (
        f"drawtext=text='{main_text}'"
        f":font='{font}'"
        f":fontsize={base_size}"
        f":fontcolor='{color}'"
        f":bordercolor='{outline}'"
        f":borderw={outline_w}"
        f":x=(w-text_w)/2"
        f":y={y_expr}"
        f":alpha='{alpha}'"
        f":enable='between(t,0,{cap_end:.2f})'"
    )

    # ── Subscribe CTA ──────────────────────────────────────────
    sub_alpha = f"if(lt(t\\,{sub_start+0.5:.2f})\\, (t-{sub_start:.2f})/0.5\\, 1)"
    subscribe_filter = (
        f"drawtext=text='{sub_text}'"
        f":font='DejaVu Sans Bold'"
        f":fontsize={sub_size}"
        f":fontcolor='white'"
        f":bordercolor='black'"
        f":borderw=4"
        f":x=(w-text_w)/2"
        f":y=h*0.90"
        f":alpha='{sub_alpha}'"
        f":enable='between(t,{sub_start:.2f},{clip_dur:.2f})'"
    )

    return f"{emoji_filter},{caption_filter},{subscribe_filter}"


# ─────────────────────────────────────────────────────────────
# Step 7 — Export one clip
# ─────────────────────────────────────────────────────────────
def export_clip(source, clip_start, label, emoji, style, size_boost,
                out_path, video_duration, vid_format) -> bool:
    clip_dur = min(CLIP_TOTAL_SECS, video_duration - clip_start)
    if clip_dur < 10:
        raise ValueError(f"Clip too short ({clip_dur:.1f}s) — skipping.")

    W = vid_format["w"]
    H = vid_format["h"]

    caption_filter = build_caption_filter(label, emoji, style, size_boost,
                                          clip_dur, W, H)

    # Scale + pad to target resolution, then apply vibrant colour grade
    scale_filter = (
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,"
        f"format=yuv420p,"
        f"eq=contrast=1.08:saturation=1.25:brightness=0.02"  # 🎨 colour grade
    )

    vf = f"{scale_filter},{caption_filter}"

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{clip_start:.3f}",
        "-i", source,
        "-t", f"{clip_dur:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "21",
        "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
        "-movflags", "+faststart",
        out_path,
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-800:].decode(errors="replace") if isinstance(r.stderr, bytes) else r.stderr[-800:])
    return os.path.exists(out_path) and os.path.getsize(out_path) > 5000


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="⚽ Football Highlight Clipper — auto-detect & clip the best moments."
    )
    parser.add_argument("source",          help="YouTube URL or local video file")
    parser.add_argument("--clips",         type=int, default=20,
                        help="Number of clips (default: 20)")
    parser.add_argument("--output",        default="./highlights",
                        help="Output folder (default: ./highlights)")
    parser.add_argument("--format",        default="vertical",
                        choices=["vertical", "horizontal"],
                        help="Output video format (default: vertical)")
    parser.add_argument("--style",         default="cinematic",
                        choices=list(CAPTION_THEMES.keys()),
                        help="Caption style theme (default: cinematic)")
    parser.add_argument("--whisper-model", default="small",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper model size (default: small)")
    parser.add_argument("--min-gap",       type=int, default=30,
                        help="Minimum seconds between clips (default: 30)")
    parser.add_argument("--no-verify-ssl", action="store_true")
    parser.add_argument("--keep-source",   action="store_true")
    parser.add_argument("--overwrite",     action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    success_log = output_dir / "highlights_log.txt"
    failure_log = output_dir / "failed_log.txt"

    theme      = CAPTION_THEMES[args.style]
    vid_format = VIDEO_FORMATS[args.format]
    styles     = theme["styles"]

    print("=" * 65)
    print("  ⚽  Football Highlight Clipper — Pro Edition")
    print(f"  Style: {args.style.upper()}  |  Format: {args.format.upper()}")
    print("=" * 65)

    with tempfile.TemporaryDirectory() as tmpdir:

        # ── Acquire ─────────────────────────────────────────────
        log("\n[1/5] Acquiring source video…")
        try:
            src = acquire_source(args.source, tmpdir, args.no_verify_ssl)
        except Exception as e:
            sys.exit(f"ERROR: {e}")
        duration = ffprobe_duration(src)
        log(f"      Duration: {fmt(duration)} ({duration:.0f}s)")

        # ── Extract audio ───────────────────────────────────────
        log("\n[2/5] Extracting audio…")
        wav = os.path.join(tmpdir, "audio.wav")
        extract_audio(src, wav)

        # ── Detect moments ──────────────────────────────────────
        log(f"\n[3/5] Loading Whisper '{args.whisper_model}' & detecting moments…")
        wmodel        = whisper.load_model(args.whisper_model)
        energy_spikes = detect_energy_spikes(wav)
        kw_detections = transcribe_and_detect(wav, wmodel)

        moments = merge_moments(
            energy_spikes  = energy_spikes,
            kw_detections  = kw_detections,
            min_gap        = args.min_gap,
            video_duration = duration,
            max_clips      = args.clips,
        )

        if not moments:
            sys.exit("\nNo moments detected. Try --whisper-model medium or a longer video.")

        # ── Export clips ─────────────────────────────────────────
        log(f"\n[4/5] Exporting {len(moments)} clip(s) [{args.style} / {args.format}]…\n")
        succeeded = failed = 0

        for i, moment in enumerate(moments, 1):
            out_name = f"highlight_{i:03d}_{moment['label'].replace(' ', '_').replace('!', '').lower()}.mp4"
            out_path = str(output_dir / out_name)
            style    = styles[(i - 1) % len(styles)]

            log(f"[{i:>3}/{len(moments)}] {fmt(moment['clip_start'])}  "
                f"{moment['emoji']} {moment['label']}  score={moment['score']:.1f}  →  {out_name}")

            if Path(out_path).exists() and not args.overwrite:
                log("         ⏭  Already exists — skipping.")
                succeeded += 1
                continue

            try:
                ok = export_clip(
                    source         = src,
                    clip_start     = moment["clip_start"],
                    label          = moment["label"],
                    emoji          = moment["emoji"],
                    style          = style,
                    size_boost     = moment.get("size_boost", 1.0),
                    out_path       = out_path,
                    video_duration = duration,
                    vid_format     = vid_format,
                )
                if ok:
                    log(f"         ✅  Saved  ({CLIP_TOTAL_SECS}s)")
                    with open(success_log, "a") as f:
                        f.write(f"{out_name}  t={fmt(moment['clip_start'])}  "
                                f"label={moment['label']}  score={moment['score']:.1f}\n")
                    succeeded += 1
                else:
                    raise RuntimeError("Output file missing or empty.")
            except Exception as e:
                log(f"         ❌  Failed: {e}")
                with open(failure_log, "a") as f:
                    f.write(f"{out_name}  error={e}\n")
                failed += 1
                if Path(out_path).exists():
                    Path(out_path).unlink()

        if args.keep_source:
            final_src = output_dir / Path(src).name
            shutil.copy2(src, final_src)
            log(f"\n📁 Source kept: {final_src}")

    # ── Summary ──────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  Done! ⚽")
    print(f"  ✅  Exported  : {succeeded} clip(s)")
    print(f"  ❌  Failed    : {failed} clip(s)")
    print(f"  📂  Folder    : {output_dir}/")
    print(f"  📄  Log       : {success_log}")
    print("=" * 65)


if __name__ == "__main__":
    main()

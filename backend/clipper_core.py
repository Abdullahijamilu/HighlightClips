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
    print("Missing dependency: pip install librosa")
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("Missing dependency: pip install faster-whisper")
try:
    import yt_dlp
except ImportError:
    print("Missing dependency: pip install yt-dlp")

# ─────────────────────────────────────────────────────────────
# ⚽  FOOTBALL MOMENT DEFINITIONS
# ─────────────────────────────────────────────────────────────
FOOTBALL_MOMENTS = [
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
    (r"how did he miss|incredible miss|unbelievable miss|missed (an )?open goal",
                                         "HOW DID HE MISS?!",  "😱",  9, 1.2),
    (r"over the bar|wide of the post|skied|ballooned",
                                         "WHAT A MISS!",       "🤦",  7, 1.0),
    (r"post|crossbar|off the woodwork|hit the bar",
                                         "OFF THE POST!",      "😬",  8, 1.1),
    (r"what a save|incredible save|unbelievable save|fingertip",
                                         "WHAT A SAVE!",       "🧤", 10, 1.2),
    (r"save|keeper|goalkeeper",          "BRILLIANT SAVE!",    "🧤",  7, 1.0),
    (r"penalty save|saved.*penalty",     "PENALTY SAVED!",     "🧤", 10, 1.3),
    (r"red card|sent off|straight red",  "RED CARD!",          "🟥",  9, 1.2),
    (r"yellow card|booked",              "YELLOW CARD!",       "🟨",  5, 0.9),
    (r"penalty|spot.?kick",             "PENALTY!",            "⚽",  8, 1.1),
    (r"\bvar\b|video assistant|overturned|check.*referee",
                                         "VAR DRAMA!",         "📺",  7, 1.0),
    (r"offside",                         "OFFSIDE!",           "🚩",  5, 0.9),
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

CAPTION_THEMES = {
    "cinematic": {
        "styles": [
            {"color": "white",   "shadow": "#000000@0.9", "font": "Impact", "outline": "black", "outline_w": 6, "anim": "slide"},
            {"color": "#FFD700", "shadow": "#7B4F00@0.9", "font": "Impact", "outline": "#3D2600", "outline_w": 6, "anim": "bounce"},
            {"color": "white",   "shadow": "#CC0000@0.9", "font": "Impact", "outline": "#8B0000", "outline_w": 5, "anim": "slide"},
        ],
        "bg_box": True,
    },
    "neon": {
        "styles": [
            {"color": "#39FF14", "shadow": "#003D00@0.9", "font": "DejaVu Sans Bold", "outline": "#00FF00", "outline_w": 3, "anim": "slide"},
            {"color": "#FF073A", "shadow": "#3D0011@0.9", "font": "DejaVu Sans Bold", "outline": "#FF0000", "outline_w": 3, "anim": "bounce"},
            {"color": "#00FFFF", "shadow": "#003D3D@0.9", "font": "DejaVu Sans Bold", "outline": "#0088FF", "outline_w": 3, "anim": "slide"},
        ],
        "bg_box": False,
    },
    "retro": {
        "styles": [
            {"color": "#FFF200", "shadow": "#000000@0.9", "font": "Impact", "outline": "black", "outline_w": 8, "anim": "bounce"},
            {"color": "#FF6600", "shadow": "#000000@0.9", "font": "Impact", "outline": "black", "outline_w": 7, "anim": "slide"},
            {"color": "white",   "shadow": "#000000@0.9", "font": "Impact", "outline": "black", "outline_w": 8, "anim": "slide"},
        ],
        "bg_box": True,
    },
    "clean": {
        "styles": [
            {"color": "white",   "shadow": "black@0.8", "font": "DejaVu Sans Bold", "outline": "black", "outline_w": 4, "anim": "slide"},
            {"color": "#E8E8E8", "shadow": "black@0.8", "font": "DejaVu Sans Bold", "outline": "black", "outline_w": 4, "anim": "slide"},
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
class ProgressLogger:
    def __init__(self, callback=None):
        self.callback = callback
    
    def log(self, msg: str, progress: int = None, stage: str = None):
        try:
            print(msg, flush=True)
        except UnicodeEncodeError:
            safe = msg.encode("ascii", errors="replace").decode("ascii")
            print(safe, flush=True)
        if self.callback:
            self.callback(msg, progress, stage)

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
    for ch, esc in [("\\", "\\\\"), ("'", "\\'"), (":", "\\:"),
                    (",", "\\,"), ("[", "\\["), ("]", "\\]")]:
        s = s.replace(ch, esc)
    return s

def acquire_source(input_src: str, dest_dir: str, no_ssl: bool, logger: ProgressLogger) -> str:
    if os.path.isfile(input_src):
        logger.log("   📁 Local file detected.")
        dst = os.path.join(dest_dir, "source" + Path(input_src).suffix)
        shutil.copy2(input_src, dst)
        return dst

    logger.log("   ⬇️  Downloading from YouTube…")
    out_tmpl = os.path.join(dest_dir, "source.%(ext)s")
    opts = {
        "quiet": False,
        "no_warnings": True,
        "format": "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]/worst",
        "format_sort": ["res", "+size"],
        "outtmpl": out_tmpl,
        "merge_output_format": "mp4",
        "nocheckcertificate": no_ssl,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
        "legacyserverconnect": True,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([input_src])

    files = list(Path(dest_dir).glob("source.*"))
    if not files:
        raise FileNotFoundError("Download produced no output file.")
    return str(files[0])

def extract_audio(video_path: str, out_wav: str):
    run(["ffmpeg", "-y", "-i", video_path,
         "-ac", "1", "-ar", "16000", "-vn", out_wav])

def detect_energy_spikes(wav_path: str, logger: ProgressLogger) -> list:
    logger.log("   📊 Scanning audio energy for crowd roars…")
    y, sr = librosa.load(wav_path, sr=16000, mono=True)

    frame_len = int(sr * 0.5)
    hop_len   = int(sr * 0.25)
    rms       = librosa.feature.rms(y=y, frame_length=frame_len, hop_length=hop_len)[0]
    times     = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_len)

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
            duration_bonus = min(2.0, (j - i) * 0.25 * 0.1)
            spikes.append((peak_time, round(score + duration_bonus, 2)))
            i = j
        else:
            i += 1

    logger.log(f"   Found {len(spikes)} audio spike(s).")
    return spikes

def transcribe_and_detect(wav_path: str, model, logger: ProgressLogger) -> list:
    logger.log("   🎙  Transcribing commentary with Whisper…")
    segments, info = model.transcribe(wav_path, beam_size=5)

    detections = []
    for seg in segments:
        text  = seg.text.lower().strip()
        start = float(seg.start)

        for pattern, label, emoji, base_score, size_boost in FOOTBALL_MOMENTS:
            if re.search(pattern, text, re.IGNORECASE):
                exclaim_bonus = min(2.0, text.count("!") * 0.4)
                caps_ratio = sum(1 for c in seg.text if c.isupper()) / max(1, len(seg.text))
                caps_bonus = min(1.5, caps_ratio * 5)
                total_score = round(base_score + exclaim_bonus + caps_bonus, 2)
                detections.append((start, total_score, label, emoji, size_boost))
                break 

    logger.log(f"   Found {len(detections)} keyword moment(s).")
    return detections

def merge_moments(energy_spikes, kw_detections, min_gap, video_duration, max_clips, logger: ProgressLogger) -> list:
    events = []
    for t, score in energy_spikes:
        events.append({"time": t, "score": score, "label": None, "emoji": "🔊", "size_boost": 1.0})
    for t, score, label, emoji, size_boost in kw_detections:
        events.append({"time": t, "score": score, "label": label, "emoji": emoji, "size_boost": size_boost})

    if not events:
        return []

    events.sort(key=lambda e: e["time"])

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
    
    logger.log(f"\n   🎯 Selected {len(selected)} highlight(s):")
    for i, m in enumerate(selected, 1):
        logger.log(f"   {i:>3}. {fmt(m['clip_start'])}  score={m['score']:.1f}  {m['emoji']} {m['label']}")
    return selected

def build_caption_filter(label: str, emoji: str, style: dict, size_boost: float, clip_dur: float, vid_w: int, vid_h: int) -> str:
    main_text  = safe_text(label)
    emoji_text = safe_text(emoji)
    sub_text   = safe_text(SUBSCRIBE_TEXT)

    color     = style["color"]
    outline   = style["outline"]
    outline_w = style["outline_w"]
    font      = style["font"]
    anim      = style.get("anim", "slide")

    base_size  = int(min(vid_w, vid_h) * 0.075 * size_boost)
    emoji_size = int(base_size * 1.5)
    sub_size   = int(base_size * 0.55)

    cap_end   = clip_dur - SUBSCRIBE_LAST - 1
    sub_start = clip_dur - SUBSCRIBE_LAST

    y_cap = f"h*0.14"

    if anim == "slide":
        y_expr  = f"if(lt(t\\,0.35)\\, {y_cap}-(0.35-t)/0.35*h*0.25\\, {y_cap})"
        alpha   = f"if(lt(t\\,0.35)\\, t/0.35\\, if(gt(t\\,{cap_end-0.5:.2f})\\, ({cap_end:.2f}-t)/0.5\\, 1))"
    else:
        y_expr  = f"if(lt(t\\,0.5)\\, {y_cap}-(1-t/0.5)*(1-t/0.5)*h*0.18*max(0\\,sin(t/0.5*3.14))\\, {y_cap})"
        alpha   = f"if(lt(t\\,0.2)\\, t/0.2\\, if(gt(t\\,{cap_end-0.5:.2f})\\, ({cap_end:.2f}-t)/0.5\\, 1))"

    emoji_filter = (
        f"drawtext=text='{emoji_text}':font='DejaVu Sans':fontsize={emoji_size}"
        f":fontcolor='white':bordercolor='black':borderw=4"
        f":x=(w-text_w)/2:y=h*0.05:alpha='{alpha}':enable='between(t,0,{cap_end:.2f})'"
    )

    caption_filter = (
        f"drawtext=text='{main_text}':font='{font}':fontsize={base_size}"
        f":fontcolor='{color}':bordercolor='{outline}':borderw={outline_w}"
        f":x=(w-text_w)/2:y={y_expr}:alpha='{alpha}':enable='between(t,0,{cap_end:.2f})'"
    )

    sub_alpha = f"if(lt(t\\,{sub_start+0.5:.2f})\\, (t-{sub_start:.2f})/0.5\\, 1)"
    subscribe_filter = (
        f"drawtext=text='{sub_text}':font='DejaVu Sans Bold':fontsize={sub_size}"
        f":fontcolor='white':bordercolor='black':borderw=4"
        f":x=(w-text_w)/2:y=h*0.90:alpha='{sub_alpha}':enable='between(t,{sub_start:.2f},{clip_dur:.2f})'"
    )

    return f"{emoji_filter},{caption_filter},{subscribe_filter}"

def export_clip(source, clip_start, label, emoji, style, size_boost, out_path, video_duration, vid_format) -> bool:
    clip_dur = min(CLIP_TOTAL_SECS, video_duration - clip_start)
    if clip_dur < 10:
        raise ValueError(f"Clip too short ({clip_dur:.1f}s) — skipping.")

    W, H = vid_format["w"], vid_format["h"]
    caption_filter = build_caption_filter(label, emoji, style, size_boost, clip_dur, W, H)

    scale_filter = (
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,"
        f"format=yuv420p,"
        f"eq=contrast=1.08:saturation=1.25:brightness=0.02"
    )

    vf = f"{scale_filter},{caption_filter}"

    cmd = [
        "ffmpeg", "-y", "-ss", f"{clip_start:.3f}", "-i", source, "-t", f"{clip_dur:.3f}",
        "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "21",
        "-c:a", "aac", "-ar", "44100", "-b:a", "192k", "-movflags", "+faststart", out_path
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        err = r.stderr[-800:].decode(errors="replace") if isinstance(r.stderr, bytes) else r.stderr[-800:]
        raise RuntimeError(err)
    return os.path.exists(out_path) and os.path.getsize(out_path) > 5000

def run_pipeline(source_url: str, output_dir: str, format_name: str, style_name: str, whisper_model_size: str, num_clips: int, min_gap: int, progress_callback=None):
    logger = ProgressLogger(progress_callback)
    theme = CAPTION_THEMES.get(style_name, CAPTION_THEMES["cinematic"])
    vid_format = VIDEO_FORMATS.get(format_name, VIDEO_FORMATS["vertical"])
    styles = theme["styles"]
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logger.log("[1/5] Acquiring source video…", 10, "downloading")
        src = acquire_source(source_url, tmpdir, no_ssl=True, logger=logger)
        duration = ffprobe_duration(src)
        
        logger.log("\n[2/5] Extracting audio…", 30, "extracting_audio")
        wav = os.path.join(tmpdir, "audio.wav")
        extract_audio(src, wav)
        
        logger.log(f"\n[3/5] Loading Whisper '{whisper_model_size}' & detecting moments…", 50, "analyzing")
        wmodel = WhisperModel(whisper_model_size, device="cpu", compute_type="int8")
        energy_spikes = detect_energy_spikes(wav, logger)
        kw_detections = transcribe_and_detect(wav, wmodel, logger)
        
        moments = merge_moments(energy_spikes, kw_detections, min_gap, duration, num_clips, logger)
        
        if not moments:
            logger.log("No moments detected.", 100, "error")
            return []
            
        logger.log(f"\n[4/5] Exporting {len(moments)} clip(s)…\n", 80, "exporting")
        
        results = []
        for i, moment in enumerate(moments, 1):
            out_name = f"highlight_{i:03d}_{moment['label'].replace(' ', '_').replace('!', '').lower()}.mp4"
            out_path = str(output_path / out_name)
            style = styles[(i - 1) % len(styles)]
            
            logger.log(f"[{i:>3}/{len(moments)}] Exporting {out_name}", 80 + int((i/len(moments))*15), "exporting")
            
            if not Path(out_path).exists():
                export_clip(src, moment["clip_start"], moment["label"], moment["emoji"], style, moment.get("size_boost", 1.0), out_path, duration, vid_format)
            
            # Use forward slashes for URLs or relative paths if this is served by a static server
            results.append({
                "file": out_name,
                "label": moment["label"],
                "score": moment["score"]
            })
            
        logger.log("Done!", 100, "completed")
        return results

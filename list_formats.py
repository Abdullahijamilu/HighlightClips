import yt_dlp

url = "https://www.youtube.com/watch?v=fd5j2xnpMKo"
ydl = yt_dlp.YoutubeDL({"quiet": True})
info = ydl.extract_info(url, download=False)

print(f"Title: {info.get('title')}")
print(f"Duration: {info.get('duration')}s")
print()
print(f"{'ID':>6}  {'Ext':>5}  {'Resolution':>12}  {'Size (MB)':>10}  {'Note'}")
print("-" * 70)

for f in info.get("formats", []):
    fid = f.get("format_id", "?")
    ext = f.get("ext", "?")
    res = f.get("resolution", "?")
    size_bytes = f.get("filesize") or f.get("filesize_approx") or 0
    size_mb = size_bytes / (1024 * 1024) if size_bytes else 0
    note = f.get("format_note", "")
    vcodec = f.get("vcodec", "none")
    acodec = f.get("acodec", "none")
    kind = "V" if vcodec != "none" else "A" if acodec != "none" else "?"
    print(f"{fid:>6}  {ext:>5}  {res:>12}  {size_mb:>9.1f}M  {kind} {note}")

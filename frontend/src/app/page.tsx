"use client";

import { useState, useEffect } from "react";

export default function Home() {
  const [url, setUrl] = useState("");
  const [inputType, setInputType] = useState<"url" | "file">("url");
  const [file, setFile] = useState<File | null>(null);
  const [numClips, setNumClips] = useState(5);
  const [style, setStyle] = useState("cinematic");
  const [format, setFormat] = useState("vertical");
  
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<any>(null);
  const [isPolling, setIsPolling] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (inputType === "url" && !url) return;
    if (inputType === "file" && !file) return;

    try {
      if (inputType === "url") {
        const res = await fetch(`${API_URL}/clip`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url,
            num_clips: numClips,
            style,
            format,
          }),
        });
        const data = await res.json();
        if (data.job_id) {
          setJobId(data.job_id);
          setIsPolling(true);
        }
      } else {
        const formData = new FormData();
        formData.append("file", file as Blob);
        formData.append("num_clips", numClips.toString());
        formData.append("style", style);
        formData.append("format", format);

        const res = await fetch(`${API_URL}/upload_clip`, {
          method: "POST",
          body: formData,
        });
        const data = await res.json();
        if (data.job_id) {
          setJobId(data.job_id);
          setIsPolling(true);
        }
      }
    } catch (err) {
      alert("Failed to connect to backend server.");
    }
  };

  useEffect(() => {
    if (!isPolling || !jobId) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/status/${jobId}`);
        const data = await res.json();
        setStatus(data);

        if (data.status === "completed" || data.status === "error") {
          setIsPolling(false);
          clearInterval(interval);
        }
      } catch (err) {
        console.error("Polling error", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [isPolling, jobId]);

  return (
    <div className="container">
      <header>
        <h1>Highlight Clipper</h1>
        <p className="subtitle">AI-Powered Football Match Analysis</p>
      </header>

      <main>
        {!jobId || status?.status === "error" || status?.status === "completed" ? (
          <form className="glass-panel" onSubmit={handleSubmit}>
            <div style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
              <button 
                type="button" 
                onClick={() => setInputType("url")}
                style={{ flex: 1, padding: "10px", borderRadius: "8px", border: "1px solid #333", background: inputType === "url" ? "#ff4d4d" : "rgba(255,255,255,0.05)", color: "white", cursor: "pointer", fontWeight: "bold" }}
              >
                Paste URL
              </button>
              <button 
                type="button" 
                onClick={() => setInputType("file")}
                style={{ flex: 1, padding: "10px", borderRadius: "8px", border: "1px solid #333", background: inputType === "file" ? "#ff4d4d" : "rgba(255,255,255,0.05)", color: "white", cursor: "pointer", fontWeight: "bold" }}
              >
                Upload Video
              </button>
            </div>

            <div className="input-group">
              {inputType === "url" ? (
                <>
                  <label>YouTube Video URL or Social Link</label>
                  <input 
                    type="text" 
                    placeholder="https://www.youtube.com/watch?v=..." 
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    required={inputType === "url"}
                  />
                </>
              ) : (
                <>
                  <label>Upload Video File (.mp4, .mov)</label>
                  <input 
                    type="file" 
                    accept="video/*"
                    onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)}
                    required={inputType === "file"}
                    style={{ padding: "10px", background: "rgba(0,0,0,0.2)", borderRadius: "8px", width: "100%", color: "white" }}
                  />
                </>
              )}
            </div>
            
            <div className="grid-2">
              <div className="input-group">
                <label>Number of Clips</label>
                <input 
                  type="number" 
                  min={1} 
                  max={20} 
                  value={numClips}
                  onChange={(e) => setNumClips(parseInt(e.target.value))}
                />
              </div>
              
              <div className="input-group">
                <label>Caption Style</label>
                <select value={style} onChange={(e) => setStyle(e.target.value)}>
                  <option value="cinematic">Cinematic (Impact font, Shadow)</option>
                  <option value="neon">Neon (Glowing outline)</option>
                  <option value="retro">Retro (Yellow/Orange thick border)</option>
                  <option value="clean">Clean (Simple & Minimal)</option>
                </select>
              </div>
            </div>

            <div className="input-group">
              <label>Video Format</label>
              <select value={format} onChange={(e) => setFormat(e.target.value)}>
                <option value="vertical">Vertical (9:16) - TikTok / Shorts</option>
                <option value="horizontal">Horizontal (16:9) - Standard</option>
              </select>
            </div>

            <button type="submit" className="btn-primary" disabled={(inputType === "url" ? !url : !file) || isPolling}>
              Generate Highlights 🔥
            </button>
            
            {status?.status === "error" && (
              <p style={{ color: "#ff4d4d", marginTop: "15px", textAlign: "center" }}>
                Error: {status.message}
              </p>
            )}
          </form>
        ) : null}

        {/* Progress Display */}
        {isPolling && status && status.status !== "completed" && (
          <div className="glass-panel progress-container">
            <h2 className="status-text pulsing">{status.stage === 'analyzing' ? 'Analyzing match...' : 'Processing...'}</h2>
            <div className="progress-bar-bg">
              <div 
                className="progress-bar-fill" 
                style={{ width: `${status.progress || 0}%` }}
              ></div>
            </div>
            <p className="status-subtext">{status.message || "Initializing..."}</p>
          </div>
        )}

        {/* Results Display */}
        {status?.status === "completed" && status.results && (
          <div>
            <h2 style={{ textAlign: "center", marginBottom: "20px" }}>Generated Highlights</h2>
            <div className="results-grid">
              {status.results.map((res: any, idx: number) => (
                <div key={idx} className="video-card">
                  <video controls preload="metadata">
                    <source src={`${API_URL}/download/${res.file}`} type="video/mp4" />
                  </video>
                  <div className="video-info">
                    <div className="video-title">{res.label}</div>
                    <div className="video-score">Hype Score: {res.score}</div>
                    <a 
                      href={`${API_URL}/download/${res.file}`} 
                      download 
                      className="btn-download"
                    >
                      Download HD
                    </a>
                  </div>
                </div>
              ))}
            </div>
            
            <div style={{ textAlign: "center", marginTop: "40px" }}>
              <button 
                className="btn-primary" 
                style={{ width: "auto", padding: "12px 30px" }}
                onClick={() => {
                  setJobId(null);
                  setStatus(null);
                  setUrl("");
                  setFile(null);
                }}
              >
                Create More Clips
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

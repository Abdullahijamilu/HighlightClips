# Football Highlight Clipper ⚽🔥

An AI-powered web application that automatically analyzes full football match videos, detects the most hype moments using crowd audio energy and commentary analysis (via OpenAI Whisper), and exports them as stylized, production-ready clips.

## Features
- **AI Commentary Detection:** Uses Whisper AI to detect keywords like "GOAL!", "RED CARD!", "VAR DRAMA!", etc.
- **Audio Energy Analysis:** Detects crowd roars using `librosa` to find hype moments.
- **Cinematic Export:** Applies high-quality color grading, custom fonts, animations (slide/bounce), and emoji labels via `ffmpeg`.
- **Vertical & Horizontal Formats:** Ready for TikTok/Shorts (9:16) or standard platforms (16:9).
- **Asynchronous Processing:** Built with a FastAPI backend and a Next.js frontend for a seamless, non-blocking user experience.

## Tech Stack
- **Frontend:** Next.js (React), Vanilla CSS (Premium Dark Mode)
- **Backend:** FastAPI (Python), uvicorn, Asyncio job queue
- **AI & Video Processing:** `openai-whisper`, `librosa`, `yt-dlp`, `ffmpeg`
- **Deployment:** Docker & Docker Compose

## Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **FFmpeg** installed and added to your system PATH.

## Quick Start (Local Development)

### 1. Start the Backend API
```bash
cd backend
pip install -r requirements.txt
python main.py
```
*The backend API will be available at http://127.0.0.1:8000*

### 2. Start the Frontend App
```bash
cd frontend
npm install
npm run dev
```
*The frontend will be available at http://localhost:3000*

## Production Deployment (Docker)
To run the entire stack in production using Docker:

```bash
docker-compose up -d --build
```

This will spin up both the FastAPI backend and the Next.js frontend, safely isolating all dependencies.

## Usage
1. Open the web app at `http://localhost:3000`.
2. Paste a YouTube URL or a path to a local video file.
3. Select your desired number of clips, format (vertical/horizontal), and caption style (Cinematic, Neon, Retro, Clean).
4. Hit **Generate Highlights** and watch the AI do the work! The progress bar will update in real-time.
5. Download your processed clips directly from the gallery.

## Disclaimer
Ensure you have the right to download and modify content if using YouTube URLs. This tool is intended for personal and educational use.

# YouTube Video Factory

AI-powered pipeline for generating complete faceless YouTube videos. Ships with **Behavioral Finance** and **Business Documentary** channels; add new channels via YAML with zero code changes.

## Prerequisites

- Python 3.10+
- FFmpeg (`brew install ffmpeg` on macOS)
- API keys: Groq, Hugging Face (required); Pexels (optional, free B-roll); Fal (optional, not used in main pipeline)

## Setup

```bash
cd /Volumes/Fun/youtube-factory
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config.env.example config.env
```

## Configuration

Edit `config.env` with your API keys (never commit this file):

```
GROQ_API_KEY=your_groq_key_here
HF_API_KEY=your_hf_token_here
PEXELS_API_KEY=          # optional — free at pexels.com/api
FAL_API_KEY=your_fal_key_here   # optional — not used in default pipeline
```

**Estimated API cost:** ~₹7–15 per 10-minute video (Groq + FLUX). Kokoro TTS and FFmpeg are free.

## Start Server

```bash
source venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8002 --reload
```

Open: http://localhost:8002/ui/ (or `/ui/index.html`)

> **Note:** Port 8000 is often taken by Cursor or other local apps. If `localhost:8000` shows a different site or 404, use **8002** (set in `config.env` as `API_PORT`).

## Workflow

1. Select channel (finance or business), enter topic, choose audio mode
2. Click **Generate Video** — script generates in background; UI polls until review is ready
3. Edit/approve script on the review page (voice + speed apply here)
4. Pipeline continues: images → thumbnail → audio → assembly
5. Download final video, thumbnail, title, description, and tags

### Human / Hybrid Voiceover

After script approval, the pipeline pauses for recording. The recorder shows scene images (or video if already assembled). Complete recording to assemble the final video.

## Add a New Channel

1. Copy `channels/finance.yaml` or `channels/business.yaml`
2. Rename to `your_niche.yaml`
3. Edit name, colors, prompts, voice, and music mappings
4. Add music MP3s to `music/your_niche/` (filenames must match YAML)
5. Restart the server — the channel appears in the UI automatically

## Music

Placeholder MP3s are included under `music/finance/` and `music/business/`. Replace with licensed tracks from the [YouTube Audio Library](https://studio.youtube.com/channel/UC/music) or a service like Epidemic Sound. Missing files are skipped gracefully.

## API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/health` | Health check |
| GET | `/channels/list` | List channels |
| GET | `/channels/{niche_id}` | Channel config |
| POST | `/channels/validate/{niche_id}` | Validate channel YAML |
| POST | `/generate/video` | Start generation (background script, stops at review) |
| GET | `/generate/script-review/{job_id}` | Get script for review |
| POST | `/generate/script-review/approve` | Approve script and continue pipeline |
| POST | `/generate/script-review/regenerate-scene` | Regenerate one scene narration |
| POST | `/generate/script-review/regenerate-full` | Regenerate full script |
| POST | `/generate/script-only` | Script only (no job) |
| POST | `/generate/thumbnail` | Standalone thumbnail |
| POST | `/generate/complete-human-recording` | Finish human/hybrid recording |
| POST | `/generate/add-particle` | Particle overlay on video |
| GET | `/audio/voices` | List TTS voices |
| GET | `/audio/devices` | List microphones |
| POST | `/audio/preview` | Preview voice sample |
| POST | `/audio/record/start` | Start scene recording |
| POST | `/audio/record/stop` | Stop and normalize recording |
| GET | `/status/{job_id}` | Job progress + cost estimate |
| GET | `/status/list/{niche_id}` | Job history for channel |

## Project Structure

```
channels/     Channel YAML configs (finance, business)
lib/          Core modules (script, image, audio, stitch, cost_tracker, etc.)
pipeline/     Orchestration (generator, status tracker)
api/          FastAPI routes
ui/           Web interface (index, review, recorder)
music/        Background music per channel
luts/         FFmpeg color grading LUTs
output/       Generated videos and job artifacts
```

## Tech Stack

| Layer | Tool |
|-------|------|
| Script | Groq LLM |
| Images | Hugging Face FLUX.1-schnell (+ optional Pexels B-roll) |
| Voice | Kokoro (local TTS) |
| Motion | FFmpeg Ken Burns |
| Assembly | FFmpeg (stitch, music, LUT) |

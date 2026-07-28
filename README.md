# YouTube Video Factory

AI-powered pipeline for generating complete faceless YouTube videos. Ships with **Behavioral Finance** and **Business Documentary** channels; add new channels with **one YAML file** — no code changes.

## What the pipeline produces

| Output | Description |
|--------|-------------|
| `final_video.mp4` | Full documentary with Ken Burns motion, music, LUT grade, **burned-in captions** |
| `captions.srt` | Uploadable subtitle file (scene-synced narration) |
| `thumbnail.png` | Channel-styled thumbnail |
| `description.txt`, `tags.txt`, `titles.txt` | YouTube metadata |

## Prerequisites

- Python 3.10+
- FFmpeg (`brew install ffmpeg` on macOS)
- API keys in `config.env`:
  - **GROQ_API_KEY** — script generation (required)
  - **HF_API_KEY** or **FAL_API_KEY** — AI images (see Image generation below)
  - **PEXELS_API_KEY** — free stock fallback (optional but recommended)

## Setup

```bash
cd /Volumes/Fun/youtube-factory
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config.env.example config.env
```

Edit `config.env` with your keys (never commit this file).

## Start server

```bash
source venv/bin/activate
uvicorn api.main:app --host 127.0.0.1 --port 8001 --reload
```

Open: **http://127.0.0.1:8001/ui/index.html**

> Port 8000 is often occupied by Cursor. Use `API_PORT` in `config.env` (default **8001**).

## Workflow

1. Select channel → enter topic → choose image layout (**per scene** for varied visuals)
2. **Generate Video** — script runs in background; UI polls until review
3. **Review** — edit script, pick voice/speed, approve
4. Pipeline: **images → thumbnail → TTS audio → assembly**
5. Download `final_video.mp4`, `captions.srt`, thumbnail, metadata

### Manual scripts (best storytelling)

For premium documentaries, write scripts in Cursor using `content_json/GENERATE.md` → load in **Manual Script Editor**. Includes `story_spine`, `stakes`, `open_loops`, and per-scene `visual_prompt` fields the pipeline expects.

```bash
python scripts/validate_content_json.py your_script.json
```

### Human / hybrid voiceover

After approval, hybrid/human modes pause at the recorder UI. Complete recording → assembly runs with your voice + optional AI scenes.

## Add a new channel (YAML only)

1. Copy `channels/_template.yaml` → `channels/your_niche.yaml`
2. Set `niche_id: your_niche` (must match filename stem)
3. Customize `script.system_prompt`, colors, voice, `captions`, `image.prompt_prefix`
4. Add music to `music/your_niche/` — files: `hook.mp3`, `act1.mp3`, `act2.mp3`, `act3.mp3`, `outro.mp3` (stems match YAML `music.*` keys)
5. Restart API — channel appears in UI via `GET /channels/list`

Optional sections (`captions`, `sfx`) merge from defaults if omitted.

Validate:

```bash
curl -X POST http://127.0.0.1:8001/channels/validate/your_niche
```

## Captions

- **Burned in** during scene assembly — synced to Kokoro TTS sentence timings
- Styled per channel in `captions:` block (font, size, colors, margin)
- `captions.srt` exported alongside each job for YouTube upload
- Disable with `captions.enabled: false` in channel YAML

## Image generation

| Priority | Provider | Setup |
|----------|----------|--------|
| 1 | FLUX via HF Inference Providers | `HF_API_KEY` with credits |
| 2 | FLUX via Fal.ai | `FAL_API_KEY` in `config.env` |
| 3 | Pexels stock | `PEXELS_API_KEY` — per-scene queries from `visual_prompt` |

Use **One image per scene** for documentaries. **One image (entire video)** uses a single hero still.

Regenerate images on an existing job: API `POST /generate/regenerate-stage` with `stage: images`.

## Story quality (AI scripts)

The script pipeline uses chunked LLM generation:

1. **Outline** — `story_spine`, `stakes`, `midpoint_reversal`, `open_loops`
2. **Hook + 3 acts + outro** — scene-by-scene with `visual_prompt` and `emotion`
3. **Story polish** — retention, cliché removal, loop closure
4. **Visual polish** — topic-specific image prompts
5. **Auto humanize** — light `[pause]` / `[breath]` pacing markers

Tune voice and rules in channel YAML `script:` block.

## Music

Place MP3/WAV under `music/{niche_id}/`. Missing tracks are skipped gracefully. Use [YouTube Audio Library](https://studio.youtube.com/channel/UC/music) or licensed sources.

## API endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/health` | Health check |
| GET | `/channels/list` | List channels |
| GET | `/channels/{niche_id}` | Channel config |
| POST | `/channels/validate/{niche_id}` | Validate channel YAML |
| POST | `/generate/video` | Start generation |
| POST | `/generate/script-review/approve` | Approve script → continue pipeline |
| POST | `/generate/regenerate-stage` | Re-run images, audio, or assembly |
| GET | `/status/{job_id}` | Job progress + cost estimate |

## Project structure

```
channels/       Channel YAML (_template.yaml to copy)
content_json/   Curated manual scripts + GENERATE.md
lib/            script, image, audio, captions, stitch, sfx
pipeline/       generator orchestration
ui/             Web UI (index, review, manual-script, recorder)
music/          Background beds per channel
output/         Job artifacts (video, captions.srt, images, audio)
```

## Tech stack

| Layer | Tool |
|-------|------|
| Script | Groq / Gemini / Ollama (`SCRIPT_PROVIDER`) |
| Images | FLUX (HF or Fal) + Pexels fallback |
| Voice | Kokoro local TTS |
| Captions | Sentence-synced ASS burn-in + SRT export |
| Motion | FFmpeg Ken Burns |
| Assembly | FFmpeg stitch, music ducking, LUT grade |

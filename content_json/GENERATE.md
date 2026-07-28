# Generate video scripts with Cursor

Use Cursor chat (not ChatGPT) to write full-length scripts as JSON files here. Cursor can write large files in chunks and save directly to disk.

## Quick start

In Cursor chat, say:

```
Generate a video script JSON for topic: Kodak bankruptcy
Niche: business
Length: 10 minutes
Save to content_json/kodak_bankruptcy.json
```

Or shorter:

```
@content_json/GENERATE.md write script JSON for: How Netflix killed Blockbuster
```

Then validate:

```bash
python scripts/validate_content_json.py kodak_bankruptcy.json
```

Import into the factory from **Manual Script Editor** → **Load from content_json** (or paste JSON).

---

## Why Cursor instead of ChatGPT?

| ChatGPT | Cursor |
|---------|--------|
| Output size limits | Writes files directly, can build in acts |
| Copy-paste JSON | Saves to `content_json/*.json` |
| One-shot only | Can resume / expand acts |

**Pacing markers** (`[pause]`, `[slow]`, etc.) are optional — the factory adds them automatically on save.

---

## Chunked workflow (for 10+ minute scripts)

If one response is too long, ask Cursor to build in steps into the **same file**:

1. **Outline** — title, description, tags, story_spine, acts plan
2. **Hook + Act 1** — merge into file
3. **Act 2** — merge into file
4. **Act 3 + outro** — merge into file
5. Run `python scripts/validate_content_json.py your_file.json`

Target per act: **3–4 scenes**, **30–45 seconds** each (~75–120 words narration per scene).

---

## JSON schema

Must match `lib/script_schema.py` → `SCRIPT_TEMPLATE`. Required:

- `title`, `description`, `tags` (list)
- `hook` with `text`, `visual_prompt`, `scene_id: "hook"`
- `acts` — 3 acts, each with `scenes[]` using `narration` (not only `text`)
- `outro` with `text`, `visual_prompt`, `scene_id: "outro"`
- Unique `scene_id` values: `hook`, `act1_scene1`, …, `outro`
- `hero_visual_prompt` — specific subjects (required for `image_layout: "one_image"`)
- `image_layout`: `"one_image"`
- `sfx_cues`: `[]` on every scene (factory can fill later)

Fetch live template: `GET http://localhost:8000/generate/script-template`

---

## Niche tone guides

**business** — MagnatesMedia / Company Man: dates, dollar figures, named executives, 3-act company story.

**finance** — behavioral finance documentary: named studies (Kahneman, Thaler), concrete scenarios, no stock picks.

---

## Filename convention

```
content_json/{topic_slug}.json
```

Examples: `kodak_bankruptcy.json`, `ikea_effect.json`, `netflix_blockbuster.json`

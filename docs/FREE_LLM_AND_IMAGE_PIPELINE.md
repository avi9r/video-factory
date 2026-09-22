# Free LLM + Free Image Generation — Reusable Pipeline Patterns

Reference extracted from **YouTube Video Factory**. Use this to rebuild the same content-generation stack in another project.

---

## 1. Architecture overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Script / text  │────▶│  Images / visuals│────▶│  Downstream     │
│  (free LLM)     │     │  (FLUX → Pexels) │     │  (TTS, video…)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                         │
   Groq / Gemini / Ollama    HF Inference → Fal → Pexels stock
```

**Design rule:** every paid/limited API has a free fallback. Never fail the pipeline because one provider is out of credits.

---

## 2. Free LLM for content generation

### 2.1 Providers (pick one via env)

| Provider | Cost | Where | Best for |
|----------|------|--------|----------|
| **Groq** (default) | Free tier (TPM limits) | `console.groq.com` | Fast cloud JSON scripts |
| **Gemini** | Free API key | `aistudio.google.com/apikey` | Larger context, JSON mode |
| **Ollama** | Fully free (local) | `localhost:11434` | Offline / no API spend |

Config pattern:

```env
SCRIPT_PROVIDER=groq          # groq | gemini | ollama
GROQ_API_KEY=...
GROQ_MODEL=openai/gpt-oss-120b
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.3
```

### 2.2 Single abstraction (copy this idea)

One function routes all text generation:

```python
def chat_completion(system_prompt, user_prompt, *, max_tokens=4096, temperature=0.7, provider=None):
    provider = provider or SCRIPT_PROVIDER
    if provider == "gemini":
        return call_gemini(...)
    if provider == "ollama":
        return call_ollama(...)
    return call_groq(...)   # default
```

- **Groq:** official `groq` SDK, chat completions, retry on `rate_limit` with exponential backoff.
- **Gemini:** REST `generateContent` with `systemInstruction` + `responseMimeType: application/json`.
- **Ollama:** POST `{OLLAMA_BASE_URL}/api/chat` with `"format": "json"`.

### 2.3 Survive free-tier TPM limits: **chunked generation**

Do **not** ask for a full 10-minute script in one call. Split into small JSON jobs:

1. **Outline** — title, story spine, stakes, midpoint reversal, open loops, act beats  
2. **Hook** — opening narration + visual prompt  
3. **Act 1 / 2 / 3** — one LLM call per act  
4. **Outro** — CTA + closing insight  
5. **Story polish** — tighten retention, kill clichés (optional; can fail soft)  
6. **Visual polish** — make image prompts topic-specific  
7. **SFX / metadata** — optional tiny annotation passes  

Each call returns **ONLY JSON**. Parse with:

- strip markdown fences  
- extract `{...}` blob  
- repair truncated JSON once, then retry with a “fix this JSON” prompt  

### 2.4 Prompt stack (reusable)

```
system_prompt   = channel/persona instructions
writing_rules   = hard “never say X” list
storytelling_rules = structure (hook → reversal → resolve)
user_prompt     = task + schema + context from previous steps
```

Pass **outline context** into every later step so the model stays on one story spine.

### 2.5 Practical free-tier tips

- Keep `max_tokens` modest per chunk (1k–3k), not 16k one-shots.  
- On Groq 429 / rate_limit: sleep `2^attempt * 5` seconds, max 3 tries.  
- Prefer models that are strong at **JSON** (Gemini JSON mime type; Ollama `format: json`).  
- Soft-fail polish passes: if polish fails, keep the unpolished draft and continue.  
- For production quality when free TPM is too small: generate scripts offline (Cursor / files) and ingest as JSON.

---

## 3. Free / low-cost image generation

### 3.1 Cascade (quality → free stock)

```
1. FLUX.1-schnell via Hugging Face Inference Providers  (HF_API_KEY)
       providers tried: fal-ai → replicate → together → nscale
2. FLUX.1-schnell via Fal.ai direct                     (FAL_API_KEY / FAL_KEY)
3. Pexels stock photo search                            (PEXELS_API_KEY)  ← truly free
4. Solid-color placeholder                              (always works)
```

Keys:

```env
HF_API_KEY=...          # huggingface.co → Inference Providers (monthly free credits; can deplete)
FAL_API_KEY=...         # fal.ai — cheap pay-as-you-go (~$0.003/image), optional
PEXELS_API_KEY=...      # pexels.com/api — free stock photos
```

### 3.2 Why the old HF Inference URL fails

Do **not** rely on:

```
https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell
https://router.huggingface.co/hf-inference/models/...   # often 410 deprecated
```

Use **`huggingface_hub.InferenceClient`** with an explicit `provider=` (e.g. `"fal-ai"`) and model `"black-forest-labs/FLUX.1-schnell"`.

If HF returns **402 Payment Required**, credits are exhausted — fall through to Fal or Pexels immediately.

### 3.3 FLUX prompt vs Pexels query (important)

| Use | Build from |
|-----|------------|
| **FLUX** | Full styled prompt: channel `prompt_prefix` + scene `visual_prompt` + lighting/mood + “no text/logos” |
| **Pexels** | Short search query from **scene subjects only** (strip style boilerplate), + short video title |

Bad Pexels query (all scenes return the same photo):

```
Ultra realistic cinematic 1080p horizontal scene. Premium business documentary...
```

Good Pexels query:

```
Blockbuster Netflix, Nineteen-nineties suburban strip mall video store
```

Also vary results with `page` / `result_index` so every scene is a different photo.

### 3.4 Layout modes

| Mode | Behavior |
|------|----------|
| `one_image` | One hero FLUX/Pexels frame for the whole video |
| `per_scene` | One unique image per scene (best for documentaries) |
| `multiple` | Main + B-roll per scene |

---

## 4. Minimal file map to copy

| Concern | Reference in this repo |
|---------|-------------------------|
| LLM router | `lib/llm.py` |
| Chunked script pipeline | `lib/script.py` → `generate_video_script()` |
| Image cascade | `lib/image.py` |
| Style / layout | `lib/image_style.py` |
| Env keys | `config.env.example` |
| Channel-specific prompts | `channels/*.yaml` (`script.system_prompt`, `image.prompt_prefix`) |

---

## 5. Skeleton for another project

```python
# 1) Text
outline = llm_json(system, outline_prompt(topic))
acts = [llm_json(system, act_prompt(act, outline)) for act in outline["acts"]]
script = assemble(outline, acts)
script = soft_polish(script)   # ignore failures

# 2) Images
for i, scene in enumerate(scenes):
    prompt = build_flux_prompt(scene["visual_prompt"], style)
    try:
        img = flux_hf_or_fal(prompt)
    except Exception:
        img = pexels(_pexels_search_query(scene["visual_prompt"], script), index=i)
    save(img, f"{scene['id']}.png")
```

Dependencies typically needed:

```
groq
httpx
huggingface_hub
Pillow
requests
fal-client          # optional
python-dotenv
```

---

## 6. Cost / limit reality check

| Step | Free path | Caveat |
|------|-----------|--------|
| Script LLM | Groq / Gemini free / Ollama | Groq TPM → **chunk calls**; Gemini quota caps |
| AI images | HF free Inference credits | Credits deplete → 402; need Fal or Pexels |
| Stock images | Pexels free API | Less precise than FLUX; query by **topic**, not style |
| TTS (this repo) | Kokoro local | Fully free; not an LLM |

**Truly zero-cost stack for a new project:**  
`SCRIPT_PROVIDER=ollama` + `PEXELS_API_KEY` only.

**Best quality still cheap:**  
Groq or Gemini for text + `FAL_API_KEY` for FLUX + Pexels as safety net.

---

## 7. Checklist when porting

- [ ] One `chat_completion()` router with provider switch  
- [ ] Chunked JSON generation under free TPM  
- [ ] Robust JSON parse + one repair retry  
- [ ] Soft-fail optional polish steps  
- [ ] Image cascade: AI → stock → placeholder  
- [ ] Separate **generation prompts** from **stock search queries**  
- [ ] Unique seed / result index per scene  
- [ ] Secrets only in env (never commit keys)  
- [ ] Channel/persona config in YAML, not hard-coded prompts  

This is the minimum pattern that made free LLM + free/cheap images reliable in this factory.

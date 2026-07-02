Create a complete YouTube Video Factory project from scratch at /Volumes/Fun/youtube-factory/

This is a FastAPI + Python project that generates complete YouTube videos 
for faceless channels using AI. Two channels initially: Psychology and Finance.
New channels can be added by simply creating a new .yaml file — zero code changes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## COMPLETE PROJECT STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/Volumes/Fun/youtube-factory/
    channels/
        psychology.yaml
        finance.yaml
    lib/
        __init__.py
        script.py
        image.py
        video.py
        audio.py
        recorder.py
        thumbnail.py
        text_overlay.py
        stitch.py
        music.py
        color_grade.py
    pipeline/
        __init__.py
        generator.py
        channel_loader.py
        status_tracker.py
    api/
        __init__.py
        main.py
        routes/
            __init__.py
            generate.py
            channels.py
            audio.py
            status.py
    ui/
        index.html
        recorder.html
        review.html
    music/
        psychology/
            dark_intro.mp3      (placeholder, user adds real files)
            tense_buildup.mp3
            revelation.mp3
            calm_outro.mp3
        finance/
            corporate_clean.mp3
            tension_build.mp3
            success_outro.mp3
            calm_background.mp3
    luts/
        cinematic_dark.cube     (placeholder ffmpeg LUT file)
        cinematic_bright.cube
    output/
        psychology/
        finance/
    config.env
    requirements.txt
    README.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## CHANNEL YAML STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Create /Volumes/Fun/youtube-factory/channels/psychology.yaml:

````yaml
name: Psychology & Human Behavior
niche_id: psychology
color_scheme:
  background: "#0A0A0F"
  primary: "#8B5CF6"
  secondary: "#6D28D9"
  text: "#FFFFFF"
  accent: "#A78BFA"

voice:
  default: "british_male_daniel"
  speed: 0.85

music:
  hook: "dark_intro"
  act1: "tense_buildup"
  act2: "revelation"
  act3: "calm_outro"
  outro: "calm_outro"
  volume: 0.12

style_lock:
  color_grade: "cinematic_dark"
  lighting: "dramatic side lighting, deep shadows"
  mood: "dark, emotional, cinematic, mysterious"
  composition: "rule of thirds, minimal, editorial"
  forbidden: "text, words, letters, watermarks, logos, signs, writing"
  always_include: "dark background, cinematic depth of field, premium quality, 8k"

script:
  system_prompt: |
    You are an expert YouTube scriptwriter specializing in psychology 
    and human behavior content for a US audience.
    Write in a dark, emotionally engaging, curiosity-driven style.
    Scripts are for faceless channels — no references to "I" or personal experience.
    Use "you" to address the viewer directly.
    No medical claims. No therapy advice.
    Hook must be shocking or deeply relatable in first 15 seconds.
    Always end with an open loop that makes viewers want more.
    
  humanization_rules:
    - "Add [pause] markers where a human would naturally pause"
    - "Add [slow] before emotionally heavy sentences"
    - "Add [fast] before rapid-fire facts"
    - "Insert [breath] every 4-5 sentences"
    - "Occasionally add [emphasis] before key words"

  intro_text: "What you are about to learn will change how you see people forever."
  outro_text: "If this resonated with you, subscribe. New psychology insights every week."

thumbnail:
  template: "dark_impact"
  font: "Montserrat-Bold"
  title_color: "#FFFFFF"
  accent_color: "#8B5CF6"
  background_style: "dark cinematic, blurred human silhouette, purple glow"

video:
  resolution: "1920x1080"
  fps: 30
  format: "mp4"
  scene_duration_min: 4
  scene_duration_max: 8
  broll_frequency: 3
  transition_type: "crossfade"
  act_transition: "black_fade"

image:
  width: 1920
  height: 1080
  prompt_prefix: |
    Ultra realistic cinematic 1080p horizontal scene. Dark luxury aesthetic.
    Dramatic side lighting. Deep shadows. Purple and black tones.
    Minimal composition. Rule of thirds. No text, no words, no letters, 
    no signs, no writing of any kind anywhere in the image.
    Premium editorial quality. 8k detail.
````

Create /Volumes/Fun/youtube-factory/channels/finance.yaml:

````yaml
name: Personal Finance & Wealth
niche_id: finance
color_scheme:
  background: "#050F0A"
  primary: "#10B981"
  secondary: "#059669"
  text: "#FFFFFF"
  accent: "#34D399"

voice:
  default: "male_deep"
  speed: 0.88

music:
  hook: "tension_build"
  act1: "corporate_clean"
  act2: "tension_build"
  act3: "success_outro"
  outro: "calm_background"
  volume: 0.10

style_lock:
  color_grade: "cinematic_bright"
  lighting: "clean professional lighting, slight warmth"
  mood: "professional, aspirational, clear, authoritative"
  composition: "clean minimal, financial aesthetic, premium"
  forbidden: "text, words, letters, watermarks, logos, signs, numbers on screen"
  always_include: "clean background, sharp focus, premium quality, 8k"

script:
  system_prompt: |
    You are an expert YouTube scriptwriter specializing in personal finance
    and wealth building for a US audience.
    Write in a clear, authoritative, aspirational style.
    Scripts are for faceless channels.
    Use "you" to address the viewer directly.
    No financial advice disclaimers needed in script — add separately.
    Hook must challenge a common money belief in first 15 seconds.
    Always end with a actionable takeaway.

  humanization_rules:
    - "Add [pause] markers where a human would naturally pause"
    - "Add [slow] before important financial concepts"
    - "Add [emphasis] before key numbers or statistics"
    - "Insert [breath] every 4-5 sentences"

  intro_text: "Most people will never be wealthy. Here is the exact reason why."
  outro_text: "Subscribe for weekly wealth strategies that actually work."

thumbnail:
  template: "clean_impact"
  font: "Montserrat-Bold"
  title_color: "#FFFFFF"
  accent_color: "#10B981"
  background_style: "clean professional, subtle green glow, premium financial aesthetic"

video:
  resolution: "1920x1080"
  fps: 30
  format: "mp4"
  scene_duration_min: 4
  scene_duration_max: 8
  broll_frequency: 3
  transition_type: "crossfade"
  act_transition: "black_fade"

image:
  width: 1920
  height: 1080
  prompt_prefix: |
    Ultra realistic cinematic 1080p horizontal scene. Clean professional aesthetic.
    Warm professional lighting. Green and dark tones.
    Minimal composition. Rule of thirds. No text, no words, no letters,
    no signs, no numbers, no writing of any kind anywhere in the image.
    Premium editorial quality. 8k detail.
````

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## CONFIG FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Create config.env:
GROQ_API_KEY=your_groq_key_here

HF_API_KEY=your_hf_token_here

FAL_API_KEY=your_fal_key_here

OUTPUT_BASE=/Volumes/Fun/youtube-factory/output

MUSIC_BASE=/Volumes/Fun/youtube-factory/music

LUT_BASE=/Volumes/Fun/youtube-factory/luts

CHANNELS_BASE=/Volumes/Fun/youtube-factory/channels

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## REQUIREMENTS.TXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
fastapi

uvicorn

pydantic

python-dotenv

groq

requests

httpx

Pillow

numpy

soundfile

sounddevice

kokoro

PyYAML

ffmpeg-python

fal-client

huggingface_hub

aiofiles

websockets

python-multipart

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## LIB LAYER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### lib/script.py

Dependencies: groq, config, yaml

Functions:

1. generate_video_script(
     topic: str,
     channel_config: dict,
     duration_minutes: int = 10
   ) -> dict

   - Load channel script system_prompt from config
   - Call Groq API: model="llama-3.1-70b-versatile"
   - System prompt from channel_config.script.system_prompt
   - User prompt:
     """
     Create a complete {duration_minutes}-minute YouTube video script about:
     "{topic}"
     
     Return ONLY valid JSON with this exact structure:
     {{
       "title": "compelling video title",
       "title_variations": ["alt title 1", "alt title 2", "alt title 3"],
       "description": "SEO-optimized YouTube description 150 words",
       "tags": ["tag1", "tag2", ... 15 tags],
       "hook": {{
         "text": "hook script 0:00-0:45",
         "visual_prompt": "scene description for image generation",
         "broll_prompt": "b-roll scene description",
         "duration_seconds": 45
       }},
       "acts": [
         {{
           "act_number": 1,
           "act_title": "The Problem",
           "scenes": [
             {{
               "scene_id": "act1_scene1",
               "narration": "exact words to speak with [pause] [slow] [fast] [breath] [emphasis] markers",
               "visual_prompt": "detailed scene description for image generation - no text in image",
               "broll_prompt": "b-roll scene description",
               "duration_seconds": 30,
               "emotion": "tension"
             }}
           ]
         }},
         {{
           "act_number": 2,
           "act_title": "The Truth",
           "scenes": [...]
         }},
         {{
           "act_number": 3,
           "act_title": "The Takeaway",
           "scenes": [...]
         }}
       ],
       "outro": {{
         "text": "outro script",
         "visual_prompt": "outro scene",
         "duration_seconds": 30
       }},
       "total_scenes": 12,
       "total_duration_seconds": 600
     }}
     """
   - Parse JSON response
   - If JSON parse fails retry once with stricter prompt
   - Apply humanization_rules from channel_config to all narration text
   - Return structured dict

2. apply_humanization(
     text: str,
     rules: list
   ) -> str
   - Apply [pause] [slow] [fast] [breath] [emphasis] markers
   - Return humanized text

3. clean_narration_for_tts(
     text: str
   ) -> str
   - Remove all markers: [pause] → " ... "
   - [slow] [fast] [breath] [emphasis] → remove tag, keep text
   - Return clean text for TTS

4. refine_script_section(
     section_text: str,
     instruction: str
   ) -> str
   - Call Groq to refine a specific section
   - Used when human reviewer requests changes
   - Return refined text

---

### lib/image.py

Dependencies: requests, huggingface_hub, Pillow, pathlib, config

Functions:

1. generate_scene_image(
     prompt: str,
     channel_config: dict,
     output_path: str,
     seed: int = None
   ) -> str
   - Prepend channel_config.image.prompt_prefix to prompt
   - Append channel_config.style_lock.forbidden and always_include rules
   - Call HF Inference API:
     url = f"https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
     headers = {"Authorization": f"Bearer {HF_API_KEY}"}
     body = {"inputs": full_prompt, "parameters": {"guidance_scale": 0.0, "num_inference_steps": 4}}
   - Handle 503 (model loading): wait 20sec, retry once
   - Save response bytes as PNG to output_path
   - Return output_path

2. generate_scene_images_batch(
     scenes: list[dict],
     channel_config: dict,
     output_dir: str
   ) -> list[str]
   - scenes: list of scene dicts with visual_prompt and scene_id
   - Generate main image + broll image per scene
   - Save as {scene_id}_main.png and {scene_id}_broll.png
   - Print progress: "Generating image 1/12..."
   - Return list of all image paths

3. _call_hf_image_api(
     prompt: str,
     timeout: int = 120
   ) -> bytes
   - Internal HTTP call to HF API
   - Returns raw image bytes

---

### lib/video.py

Dependencies: fal_client, requests, time, pathlib, config

Functions:

1. generate_scene_clip(
     prompt: str,
     channel_config: dict,
     output_path: str,
     duration_seconds: int = 5,
     seed: int = None
   ) -> str
   - Prepend channel style_lock to prompt
   - Call Fal.ai Seedance 2.0 Fast API:
     fal_client.run(
       "fal-ai/seedance-v1-lite",
       arguments={{
         "prompt": full_prompt,
         "duration": duration_seconds,
         "resolution": "1080p",
         "aspect_ratio": "16:9"
       }}
     )
   - Download result video URL to output_path
   - Return output_path

2. generate_clips_batch(
     scenes: list[dict],
     channel_config: dict,
     output_dir: str
   ) -> list[str]
   - Generate clip per scene sequentially
   - Return list of paths

Note: Video generation via Fal is OPTIONAL.
If FAL_API_KEY is empty, skip video generation entirely.
Pipeline works with images only — images held for audio duration.
Video clips are used as enhancement only when available.

---

### lib/audio.py

Dependencies: kokoro, soundfile, numpy, pathlib

VOICES dict (all 28 Kokoro voices):
````python
VOICES = {{
    "female_warm": "af_heart",
    "female_bright": "af_bella",
    "female_soft": "af_sky",
    "female_clear": "af_sarah",
    "female_energetic": "af_nova",
    "female_storyteller": "af_alloy",
    "female_young": "af_jessica",
    "female_professional": "af_river",
    "female_alloy": "af_alloy",
    "female_mellow": "af_kore",
    "female_nova": "af_nova",
    "male_deep": "am_adam",
    "male_calm": "am_michael",
    "male_warm": "am_echo",
    "male_authoritative": "am_onyx",
    "male_dramatic": "am_liam",
    "male_young": "am_fenrir",
    "male_smooth": "am_eric",
    "male_friendly": "am_santa",
    "british_female_emma": "bf_emma",
    "british_female_alice": "bf_alice",
    "british_female_isabella": "bf_isabella",
    "british_female_lily": "bf_lily",
    "british_male_george": "bm_george",
    "british_male_lewis": "bm_lewis",
    "british_male_daniel": "bm_daniel",
    "british_male_fable": "bm_fable",
    "default": "af_heart"
}}
````

Functions:

1. generate_scene_voiceover(
     text: str,
     channel_config: dict,
     output_path: str,
     voice: str = None,
     speed: float = None
   ) -> str
   - Clean text using clean_narration_for_tts()
   - voice = voice or channel_config.voice.default
   - speed = speed or channel_config.voice.speed
   - Load KPipeline(lang_code='a') lazily
   - Generate audio chunks
   - Combine with numpy
   - Save as WAV using soundfile at 24000hz
   - Return output_path

2. generate_all_voiceovers(
     scenes: list[dict],
     channel_config: dict,
     output_dir: str
   ) -> list[str]
   - Generate voiceover for each scene narration
   - Also generate hook and outro
   - Return list of wav paths

3. get_audio_duration(audio_path: str) -> float
   - Return duration in seconds using soundfile

---

### lib/recorder.py

Dependencies: sounddevice, soundfile, numpy, pathlib, threading

This module handles human voiceover recording.

Functions:

1. list_input_devices() -> list[dict]
   - Return list of available mic devices
   - Each: {{"id": int, "name": str, "channels": int}}

2. record_section(
     output_path: str,
     duration_seconds: float = None,
     device_id: int = None,
     sample_rate: int = 44100
   ) -> str
   - Record audio from mic
   - If duration_seconds given: auto-stop after duration
   - If None: record until stop_recording() called
   - Save as WAV to output_path
   - Return output_path

3. stop_recording() -> None
   - Signal active recording to stop

4. get_recording_status() -> dict
   - Return {{"recording": bool, "elapsed_seconds": float}}

5. normalize_audio(
     input_path: str,
     output_path: str,
     target_db: float = -20.0
   ) -> str
   - Normalize recorded audio levels
   - Removes too-quiet or too-loud sections
   - Return output_path

6. reduce_noise(
     input_path: str,
     output_path: str
   ) -> str
   - Basic noise reduction using numpy
   - Subtract noise floor estimated from first 0.5 seconds
   - Return output_path

---

### lib/thumbnail.py

Dependencies: Pillow, requests, pathlib, config

Thumbnail templates:
- "dark_impact": dark background, large bold text left, blurred image right
- "clean_impact": clean background, centered text, minimal
- "split_screen": left dark with text, right AI image

Functions:

1. generate_thumbnail(
     title: str,
     channel_config: dict,
     output_path: str,
     template: str = None
   ) -> str
   - template = template or channel_config.thumbnail.template
   - Generate background image via HF with channel thumbnail style prompt
   - Apply template layout using Pillow
   - Render title text with correct font and colors
   - Add channel accent color bar/elements
   - Save as PNG 1280x720 (YouTube thumbnail standard)
   - Return output_path

2. render_text_on_image(
     image_path: str,
     text: str,
     output_path: str,
     font_size: int = 72,
     color: str = "#FFFFFF",
     position: str = "center",
     max_width_percent: float = 0.8
   ) -> str
   - Load image with Pillow
   - Auto-wrap text to fit max_width
   - Render with shadow for readability
   - Save to output_path
   - Return output_path

3. add_channel_branding(
     image_path: str,
     channel_config: dict,
     output_path: str
   ) -> str
   - Add subtle color accent bar at bottom
   - Add channel color overlay
   - Return output_path

---

### lib/text_overlay.py

Dependencies: Pillow, pathlib

Functions:

1. add_lower_third(
     image_path: str,
     text: str,
     channel_config: dict,
     output_path: str
   ) -> str
   - Add subtitle-style text at bottom of image
   - Use channel primary color as background bar
   - White text on colored bar
   - Return output_path

2. create_title_card(
     text: str,
     channel_config: dict,
     output_path: str,
     duration_seconds: int = 3
   ) -> str
   - Create full black image with centered text
   - Channel colors for text
   - Used for act transitions
   - Return output_path

3. create_intro_card(channel_config: dict, output_path: str) -> str
   - Animated-style static intro card
   - Channel name placeholder text
   - Return output_path

---

### lib/stitch.py

Dependencies: subprocess, pathlib, tempfile

Functions:

1. create_scene_video(
     image_path: str,
     broll_path: str,
     audio_path: str,
     output_path: str,
     broll_at_second: int = 5,
     transition: str = "crossfade"
   ) -> str
   - Hold main image for full audio duration
   - Insert broll at broll_at_second for 3 seconds
   - Merge with audio
   - Return output_path

2. concatenate_scenes(
     scene_paths: list[str],
     output_path: str,
     transition: str = "crossfade",
     transition_duration: float = 0.5
   ) -> str
   - Join all scene videos
   - Apply transition between each
   - Use ffmpeg concat with xfade filter
   - Return output_path

3. add_act_transition(
     video_path: str,
     act_title: str,
     channel_config: dict,
     output_path: str
   ) -> str
   - Insert black fade + act title card between acts
   - Duration: 2 seconds
   - Return output_path

4. mix_background_music(
     video_path: str,
     music_path: str,
     output_path: str,
     music_volume: float = 0.12,
     fade_in: float = 2.0,
     fade_out: float = 3.0
   ) -> str
   - Mix music at low volume under voice
   - Fade in at start, fade out at end
   - Loop music if shorter than video
   - Return output_path

5. add_intro_outro(
     video_path: str,
     channel_config: dict,
     output_path: str
   ) -> str
   - Prepend 3 second intro card
   - Append 5 second outro card
   - Return output_path

6. final_render(
     video_path: str,
     output_path: str,
     resolution: str = "1920x1080",
     fps: int = 30
   ) -> str
   - Final FFmpeg pass
   - Ensure correct resolution, fps, codec
   - libx264, aac, yuv420p
   - Return output_path

---

### lib/music.py

Dependencies: pathlib, config

Functions:

1. get_music_for_act(
     niche_id: str,
     act: str,
     channel_config: dict
   ) -> str
   - act: "hook", "act1", "act2", "act3", "outro"
   - Look up music filename from channel_config.music[act]
   - Return full path to music file from MUSIC_BASE/niche_id/
   - If file doesn't exist, return None (music is optional)

2. list_available_music(niche_id: str) -> list[str]
   - Return list of available music files for channel

---

### lib/color_grade.py

Dependencies: subprocess, pathlib

Functions:

1. apply_lut(
     video_path: str,
     lut_name: str,
     output_path: str
   ) -> str
   - Apply FFmpeg LUT color grade
   - lut_path = LUT_BASE/lut_name.cube
   - If LUT file doesn't exist, skip grading, return video_path unchanged
   - FFmpeg: -vf lut3d={lut_path}
   - Return output_path

2. apply_color_correction(
     video_path: str,
     brightness: float = 0.0,
     contrast: float = 1.0,
     saturation: float = 1.0,
     output_path: str = None
   ) -> str
   - Apply basic color correction via FFmpeg eq filter
   - Return output_path

---

### pipeline/channel_loader.py

Dependencies: yaml, pathlib

Functions:

1. load_channel(niche_id: str) -> dict
   - Load channels/{niche_id}.yaml
   - Return parsed dict
   - Raise clear error if channel not found

2. list_channels() -> list[dict]
   - Scan channels/ directory
   - Return list of all loaded channel configs
   - Each: {{"niche_id": str, "name": str, "color_scheme": dict}}

3. validate_channel_config(config: dict) -> bool
   - Validate required fields exist
   - Return True if valid, raise ValueError with details if not

---

### pipeline/status_tracker.py

Dependencies: json, pathlib, datetime

Track generation job status persistently.

Functions:

1. create_job(
     job_id: str,
     niche_id: str,
     topic: str,
     audio_mode: str
   ) -> dict
   - Create job status file at output/{niche_id}/{job_id}/status.json
   - Initial status: "created"
   - Return job dict

2. update_job(
     job_id: str,
     step: str,
     status: str,
     data: dict = None
   ) -> None
   - Update status.json
   - steps: script, images, thumbnail, audio, assembly, complete, error
   - status: pending, running, complete, error

3. get_job_status(job_id: str) -> dict
   - Return current status.json contents

4. list_jobs(niche_id: str = None) -> list[dict]
   - List all jobs, optionally filtered by niche

---

### pipeline/generator.py

This is the main orchestrator. Imports from all lib modules.

Dependencies: all lib modules, status_tracker, channel_loader

Functions:

1. generate_video(
     topic: str,
     niche_id: str,
     duration_minutes: int = 10,
     audio_mode: str = "ai",
     voice: str = None,
     job_id: str = None
   ) -> dict

Full pipeline:

````python
async def generate_video(topic, niche_id, duration_minutes=10, 
                          audio_mode="ai", voice=None, job_id=None):
    
    # Setup
    channel = load_channel(niche_id)
    job_id = job_id or generate_job_id()
    job_dir = OUTPUT_BASE / niche_id / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    create_job(job_id, niche_id, topic, audio_mode)
    
    # STEP 1: Script
    update_job(job_id, "script", "running")
    script = generate_video_script(topic, channel, duration_minutes)
    save_json(job_dir / "script.json", script)
    save_text(job_dir / "description.txt", script["description"])
    save_text(job_dir / "tags.txt", "\n".join(script["tags"]))
    save_text(job_dir / "titles.txt", "\n".join(script["title_variations"]))
    update_job(job_id, "script", "complete", {{"script_path": str(job_dir/"script.json")}})
    
    # STEP 2: Images (all scenes)
    update_job(job_id, "images", "running")
    all_scenes = [script["hook"]] + [s for act in script["acts"] for s in act["scenes"]] + [script["outro"]]
    image_paths = generate_scene_images_batch(all_scenes, channel, job_dir / "images")
    update_job(job_id, "images", "complete")
    
    # STEP 3: Thumbnail
    update_job(job_id, "thumbnail", "running")
    thumbnail_path = generate_thumbnail(script["title"], channel, job_dir / "thumbnail.png")
    update_job(job_id, "thumbnail", "complete", {{"thumbnail_path": str(thumbnail_path)}})
    
    # STEP 4: Audio
    update_job(job_id, "audio", "running")
    
    if audio_mode == "ai":
        audio_paths = generate_all_voiceovers(all_scenes, channel, job_dir / "audio")
        update_job(job_id, "audio", "complete")
        # Proceed to assembly
        final_path = assemble_video(script, image_paths, audio_paths, channel, job_dir)
        
    elif audio_mode == "human":
        # Return here - wait for human recording via UI
        update_job(job_id, "audio", "pending_human", {{
            "scenes": all_scenes,
            "image_paths": image_paths,
            "job_dir": str(job_dir),
            "waiting_for": "human_voiceover"
        }})
        return {{
            "job_id": job_id,
            "status": "waiting_for_human_voiceover",
            "script": script,
            "recorder_url": f"/recorder?job_id={{job_id}}"
        }}
        
    elif audio_mode == "hybrid":
        # Generate AI first, then flag sections for human re-record
        audio_paths = generate_all_voiceovers(all_scenes, channel, job_dir / "audio")
        update_job(job_id, "audio", "pending_hybrid", {{
            "ai_audio_paths": audio_paths,
            "waiting_for": "human_review"
        }})
        return {{
            "job_id": job_id,
            "status": "waiting_for_hybrid_review",
            "script": script,
            "recorder_url": f"/recorder?job_id={{job_id}}&mode=hybrid"
        }}
    
    update_job(job_id, "assembly", "complete", {{"output_path": str(final_path)}})
    return {{
        "job_id": job_id,
        "status": "complete",
        "output_path": str(final_path),
        "thumbnail_path": str(thumbnail_path)
    }}

2. assemble_video(
     script: dict,
     image_paths: dict,
     audio_paths: dict,
     channel_config: dict,
     job_dir: Path
   ) -> str
   - Create scene video per scene (image + broll + audio)
   - Insert act transitions between acts
   - Concatenate all scenes
   - Mix background music per act
   - Add intro/outro cards
   - Apply color grade LUT
   - Final render to job_dir/final_video.mp4
   - Return output path

3. complete_human_recording(
     job_id: str,
     niche_id: str,
     audio_paths: dict
   ) -> dict
   - Called after human finishes recording all sections
   - Normalize and noise-reduce each recording
   - Load script and image paths from job status
   - Call assemble_video
   - Return final output paths

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## API LAYER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### api/main.py

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api.routes import generate, channels, audio, status
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

app = FastAPI(title="YouTube Video Factory", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], 
                   allow_methods=["*"], allow_headers=["*"])

app.mount("/ui", StaticFiles(directory="ui"), name="ui")

app.include_router(generate.router, prefix="/generate", tags=["generation"])
app.include_router(channels.router, prefix="/channels", tags=["channels"])
app.include_router(audio.router, prefix="/audio", tags=["audio"])
app.include_router(status.router, prefix="/status", tags=["status"])

@app.get("/health")
def health():
    return {{"status": "ok", "version": "1.0.0"}}

@app.get("/")
def root():
    return {{"message": "YouTube Factory API", "ui": "/ui/index.html"}}
```

### api/routes/generate.py

Routes:

POST /generate/video
  Request: GenerateVideoRequest(
    topic: str,
    niche_id: str,
    duration_minutes: int = 10,
    audio_mode: str = "ai",  # "ai", "human", "hybrid"
    voice: str = None
  )
  - Validates niche_id exists
  - Calls generator.generate_video() as background task
  - Returns: {{"job_id": str, "status": str}}

POST /generate/script-only
  Request: ScriptRequest(topic: str, niche_id: str, duration_minutes: int = 10)
  - Generates only the script
  - Returns full script dict for review

POST /generate/thumbnail
  Request: ThumbnailRequest(title: str, niche_id: str, job_id: str = None)
  - Generates thumbnail
  - Returns thumbnail path

POST /generate/complete-human-recording
  Request: CompleteRecordingRequest(job_id: str, niche_id: str, audio_paths: dict)
  - Triggers assembly after human recording complete
  - Returns final output paths

### api/routes/channels.py

Routes:

GET /channels/list
  - Returns list of all available channels

GET /channels/{niche_id}
  - Returns full channel config

POST /channels/validate/{niche_id}
  - Validates a channel yaml

### api/routes/audio.py

Routes:

GET /audio/voices
  - Returns all 28 voice options

POST /audio/record/start
  Request: RecordRequest(job_id: str, scene_id: str, device_id: int = None)
  - Starts recording for a scene
  - Returns {{"recording": true, "scene_id": str}}

POST /audio/record/stop
  Request: StopRequest(job_id: str, scene_id: str)
  - Stops recording
  - Normalizes audio
  - Returns {{"path": str, "duration": float}}

GET /audio/record/status
  - Returns current recording status

POST /audio/preview
  Request: PreviewRequest(text: str, voice: str, speed: float = 0.85)
  - Generates short TTS preview
  - Returns audio file path

### api/routes/status.py

Routes:

GET /status/{job_id}
  - Returns job status and progress

GET /status/list/{niche_id}
  - Lists all jobs for a channel

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## UI LAYER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### ui/index.html

Single page HTML+JS (no framework, pure vanilla JS).
Dark theme matching the channel aesthetic.

Sections:
1. Channel selector (Psychology / Finance + any future channels auto-loaded from API)
2. Topic input field
3. Duration selector (8, 10, 12, 15 minutes)
4. Audio mode selector:
   - AI Voiceover (voice dropdown + speed slider)
   - Human Voiceover
   - Hybrid
5. Generate button
6. Progress tracker showing steps:
   [Script] → [Images] → [Thumbnail] → [Audio] → [Assembly] → [Complete]
   Each step shows: pending / running (spinner) / complete (checkmark) / error
7. Output section when complete:
   - Video preview (HTML5 video player)
   - Thumbnail preview
   - Download buttons for video and thumbnail
   - Copy buttons for title, description, tags

Poll /status/{job_id} every 3 seconds to update progress.

### ui/recorder.html

Human voiceover recording interface.
URL: /ui/recorder.html?job_id=xxx&mode=human

Layout:
- Top: Video preview (no audio) playing current scene
- Middle: Script text for current scene (large readable font)
  - Markers shown: [pause] highlighted in yellow, [slow] in blue, [emphasis] in red
  - These are visual guides — not read aloud
- Bottom controls:
  - [▶ Play Scene] — plays video preview
  - [🔴 Record] — starts mic recording
  - [⏹ Stop] — stops recording
  - [▶ Play Back] — plays recorded audio
  - [✓ Save] — saves and moves to next scene
  - [↺ Re-record] — discard and re-record

Progress bar: "Scene 3 of 12"
Device selector: dropdown to choose mic input

After all scenes recorded:
- [Complete Recording] button
- Calls /generate/complete-human-recording
- Redirects to index.html with job_id to show final output

### ui/review.html

Script review page before generation.
Shows full script with edit capability.
Each scene narration is editable textarea.
[Regenerate Scene] button per scene calls /generate/script-only for that scene.
[Approve & Continue] triggers image + audio generation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## IMPORTANT RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. All API keys loaded from config.env via python-dotenv
2. Never hardcode API keys
3. All paths use pathlib.Path
4. Create output dirs automatically with mkdir(parents=True, exist_ok=True)
5. Every function prints clear progress logs with timestamps
6. All heavy operations (image gen, video gen, TTS) handle errors gracefully
7. If FAL_API_KEY is empty: skip video generation, use images only
8. If a music file doesn't exist: skip music, don't fail
9. If LUT file doesn't exist: skip color grade, don't fail
10. Video generation via Fal is OPTIONAL enhancement — pipeline works without it
11. Human recording mode pauses pipeline and waits — never auto-proceeds
12. All generated files saved with job_id prefix to avoid conflicts
13. lib/ has zero FastAPI dependency
14. pipeline/ imports from lib/ only
15. api/ imports from pipeline/ and lib/
16. sys.path handling in api/main.py to find lib/ and pipeline/
17. Adding a new channel = create new .yaml in channels/ = zero code changes
18. README.md must explain how to add a new channel in 5 steps

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## README.MD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Include clear sections:
- Setup instructions
- How to add API keys to config.env
- How to start the server
- How to add a new channel in 5 steps:
  1. Copy channels/psychology.yaml
  2. Rename to your_niche.yaml
  3. Edit name, colors, prompts, voice
  4. Restart server
  5. New channel appears automatically in UI
- How to add music files
- How to use human voiceover mode
````

---

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## LIB LAYER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### lib/script.py

Dependencies: groq, config, yaml

Functions:

1. generate_video_script(
     topic: str,
     channel_config: dict,
     duration_minutes: int = 10
   ) -> dict

   - Load channel script system_prompt from config
   - Call Groq API: model="llama-3.1-70b-versatile"
   - System prompt from channel_config.script.system_prompt
   - User prompt:
     """
     Create a complete {duration_minutes}-minute YouTube video script about:
     "{topic}"
     
     Return ONLY valid JSON with this exact structure:
     {{
       "title": "compelling video title",
       "title_variations": ["alt title 1", "alt title 2", "alt title 3"],
       "description": "SEO-optimized YouTube description 150 words",
       "tags": ["tag1", "tag2", ... 15 tags],
       "hook": {{
         "text": "hook script 0:00-0:45",
         "visual_prompt": "scene description for image generation",
         "broll_prompt": "b-roll scene description",
         "duration_seconds": 45
       }},
       "acts": [
         {{
           "act_number": 1,
           "act_title": "The Problem",
           "scenes": [
             {{
               "scene_id": "act1_scene1",
               "narration": "exact words to speak with [pause] [slow] [fast] [breath] [emphasis] markers",
               "visual_prompt": "detailed scene description for image generation - no text in image",
               "broll_prompt": "b-roll scene description",
               "duration_seconds": 30,
               "emotion": "tension"
             }}
           ]
         }},
         {{
           "act_number": 2,
           "act_title": "The Truth",
           "scenes": [...]
         }},
         {{
           "act_number": 3,
           "act_title": "The Takeaway",
           "scenes": [...]
         }}
       ],
       "outro": {{
         "text": "outro script",
         "visual_prompt": "outro scene",
         "duration_seconds": 30
       }},
       "total_scenes": 12,
       "total_duration_seconds": 600
     }}
     """
   - Parse JSON response
   - If JSON parse fails retry once with stricter prompt
   - Apply humanization_rules from channel_config to all narration text
   - Return structured dict

2. apply_humanization(
     text: str,
     rules: list
   ) -> str
   - Apply [pause] [slow] [fast] [breath] [emphasis] markers
   - Return humanized text

3. clean_narration_for_tts(
     text: str
   ) -> str
   - Remove all markers: [pause] → " ... "
   - [slow] [fast] [breath] [emphasis] → remove tag, keep text
   - Return clean text for TTS

4. refine_script_section(
     section_text: str,
     instruction: str
   ) -> str
   - Call Groq to refine a specific section
   - Used when human reviewer requests changes
   - Return refined text

---

### lib/image.py

Dependencies: requests, huggingface_hub, Pillow, pathlib, config

Functions:

1. generate_scene_image(
     prompt: str,
     channel_config: dict,
     output_path: str,
     seed: int = None
   ) -> str
   - Prepend channel_config.image.prompt_prefix to prompt
   - Append channel_config.style_lock.forbidden and always_include rules
   - Call HF Inference API:
     url = f"https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
     headers = {"Authorization": f"Bearer {HF_API_KEY}"}
     body = {"inputs": full_prompt, "parameters": {"guidance_scale": 0.0, "num_inference_steps": 4}}
   - Handle 503 (model loading): wait 20sec, retry once
   - Save response bytes as PNG to output_path
   - Return output_path

2. generate_scene_images_batch(
     scenes: list[dict],
     channel_config: dict,
     output_dir: str
   ) -> list[str]
   - scenes: list of scene dicts with visual_prompt and scene_id
   - Generate main image + broll image per scene
   - Save as {scene_id}_main.png and {scene_id}_broll.png
   - Print progress: "Generating image 1/12..."
   - Return list of all image paths

3. _call_hf_image_api(
     prompt: str,
     timeout: int = 120
   ) -> bytes
   - Internal HTTP call to HF API
   - Returns raw image bytes

---

### lib/video.py

Dependencies: fal_client, requests, time, pathlib, config

Functions:

1. generate_scene_clip(
     prompt: str,
     channel_config: dict,
     output_path: str,
     duration_seconds: int = 5,
     seed: int = None
   ) -> str
   - Prepend channel style_lock to prompt
   - Call Fal.ai Seedance 2.0 Fast API:
     fal_client.run(
       "fal-ai/seedance-v1-lite",
       arguments={{
         "prompt": full_prompt,
         "duration": duration_seconds,
         "resolution": "1080p",
         "aspect_ratio": "16:9"
       }}
     )
   - Download result video URL to output_path
   - Return output_path

2. generate_clips_batch(
     scenes: list[dict],
     channel_config: dict,
     output_dir: str
   ) -> list[str]
   - Generate clip per scene sequentially
   - Return list of paths

Note: Video generation via Fal is OPTIONAL.
If FAL_API_KEY is empty, skip video generation entirely.
Pipeline works with images only — images held for audio duration.
Video clips are used as enhancement only when available.

---

### lib/audio.py

Dependencies: kokoro, soundfile, numpy, pathlib

VOICES dict (all 28 Kokoro voices):
````python
VOICES = {{
    "female_warm": "af_heart",
    "female_bright": "af_bella",
    "female_soft": "af_sky",
    "female_clear": "af_sarah",
    "female_energetic": "af_nova",
    "female_storyteller": "af_alloy",
    "female_young": "af_jessica",
    "female_professional": "af_river",
    "female_alloy": "af_alloy",
    "female_mellow": "af_kore",
    "female_nova": "af_nova",
    "male_deep": "am_adam",
    "male_calm": "am_michael",
    "male_warm": "am_echo",
    "male_authoritative": "am_onyx",
    "male_dramatic": "am_liam",
    "male_young": "am_fenrir",
    "male_smooth": "am_eric",
    "male_friendly": "am_santa",
    "british_female_emma": "bf_emma",
    "british_female_alice": "bf_alice",
    "british_female_isabella": "bf_isabella",
    "british_female_lily": "bf_lily",
    "british_male_george": "bm_george",
    "british_male_lewis": "bm_lewis",
    "british_male_daniel": "bm_daniel",
    "british_male_fable": "bm_fable",
    "default": "af_heart"
}}
````

Functions:

1. generate_scene_voiceover(
     text: str,
     channel_config: dict,
     output_path: str,
     voice: str = None,
     speed: float = None
   ) -> str
   - Clean text using clean_narration_for_tts()
   - voice = voice or channel_config.voice.default
   - speed = speed or channel_config.voice.speed
   - Load KPipeline(lang_code='a') lazily
   - Generate audio chunks
   - Combine with numpy
   - Save as WAV using soundfile at 24000hz
   - Return output_path

2. generate_all_voiceovers(
     scenes: list[dict],
     channel_config: dict,
     output_dir: str
   ) -> list[str]
   - Generate voiceover for each scene narration
   - Also generate hook and outro
   - Return list of wav paths

3. get_audio_duration(audio_path: str) -> float
   - Return duration in seconds using soundfile

---

### lib/recorder.py

Dependencies: sounddevice, soundfile, numpy, pathlib, threading

This module handles human voiceover recording.

Functions:

1. list_input_devices() -> list[dict]
   - Return list of available mic devices
   - Each: {{"id": int, "name": str, "channels": int}}

2. record_section(
     output_path: str,
     duration_seconds: float = None,
     device_id: int = None,
     sample_rate: int = 44100
   ) -> str
   - Record audio from mic
   - If duration_seconds given: auto-stop after duration
   - If None: record until stop_recording() called
   - Save as WAV to output_path
   - Return output_path

3. stop_recording() -> None
   - Signal active recording to stop

4. get_recording_status() -> dict
   - Return {{"recording": bool, "elapsed_seconds": float}}

5. normalize_audio(
     input_path: str,
     output_path: str,
     target_db: float = -20.0
   ) -> str
   - Normalize recorded audio levels
   - Removes too-quiet or too-loud sections
   - Return output_path

6. reduce_noise(
     input_path: str,
     output_path: str
   ) -> str
   - Basic noise reduction using numpy
   - Subtract noise floor estimated from first 0.5 seconds
   - Return output_path

---

### lib/thumbnail.py

Dependencies: Pillow, requests, pathlib, config

Thumbnail templates:
- "dark_impact": dark background, large bold text left, blurred image right
- "clean_impact": clean background, centered text, minimal
- "split_screen": left dark with text, right AI image

Functions:

1. generate_thumbnail(
     title: str,
     channel_config: dict,
     output_path: str,
     template: str = None
   ) -> str
   - template = template or channel_config.thumbnail.template
   - Generate background image via HF with channel thumbnail style prompt
   - Apply template layout using Pillow
   - Render title text with correct font and colors
   - Add channel accent color bar/elements
   - Save as PNG 1280x720 (YouTube thumbnail standard)
   - Return output_path

2. render_text_on_image(
     image_path: str,
     text: str,
     output_path: str,
     font_size: int = 72,
     color: str = "#FFFFFF",
     position: str = "center",
     max_width_percent: float = 0.8
   ) -> str
   - Load image with Pillow
   - Auto-wrap text to fit max_width
   - Render with shadow for readability
   - Save to output_path
   - Return output_path

3. add_channel_branding(
     image_path: str,
     channel_config: dict,
     output_path: str
   ) -> str
   - Add subtle color accent bar at bottom
   - Add channel color overlay
   - Return output_path

---

### lib/text_overlay.py

Dependencies: Pillow, pathlib

Functions:

1. add_lower_third(
     image_path: str,
     text: str,
     channel_config: dict,
     output_path: str
   ) -> str
   - Add subtitle-style text at bottom of image
   - Use channel primary color as background bar
   - White text on colored bar
   - Return output_path

2. create_title_card(
     text: str,
     channel_config: dict,
     output_path: str,
     duration_seconds: int = 3
   ) -> str
   - Create full black image with centered text
   - Channel colors for text
   - Used for act transitions
   - Return output_path

3. create_intro_card(channel_config: dict, output_path: str) -> str
   - Animated-style static intro card
   - Channel name placeholder text
   - Return output_path

---

### lib/stitch.py

Dependencies: subprocess, pathlib, tempfile

Functions:

1. create_scene_video(
     image_path: str,
     broll_path: str,
     audio_path: str,
     output_path: str,
     broll_at_second: int = 5,
     transition: str = "crossfade"
   ) -> str
   - Hold main image for full audio duration
   - Insert broll at broll_at_second for 3 seconds
   - Merge with audio
   - Return output_path

2. concatenate_scenes(
     scene_paths: list[str],
     output_path: str,
     transition: str = "crossfade",
     transition_duration: float = 0.5
   ) -> str
   - Join all scene videos
   - Apply transition between each
   - Use ffmpeg concat with xfade filter
   - Return output_path

3. add_act_transition(
     video_path: str,
     act_title: str,
     channel_config: dict,
     output_path: str
   ) -> str
   - Insert black fade + act title card between acts
   - Duration: 2 seconds
   - Return output_path

4. mix_background_music(
     video_path: str,
     music_path: str,
     output_path: str,
     music_volume: float = 0.12,
     fade_in: float = 2.0,
     fade_out: float = 3.0
   ) -> str
   - Mix music at low volume under voice
   - Fade in at start, fade out at end
   - Loop music if shorter than video
   - Return output_path

5. add_intro_outro(
     video_path: str,
     channel_config: dict,
     output_path: str
   ) -> str
   - Prepend 3 second intro card
   - Append 5 second outro card
   - Return output_path

6. final_render(
     video_path: str,
     output_path: str,
     resolution: str = "1920x1080",
     fps: int = 30
   ) -> str
   - Final FFmpeg pass
   - Ensure correct resolution, fps, codec
   - libx264, aac, yuv420p
   - Return output_path

---

### lib/music.py

Dependencies: pathlib, config

Functions:

1. get_music_for_act(
     niche_id: str,
     act: str,
     channel_config: dict
   ) -> str
   - act: "hook", "act1", "act2", "act3", "outro"
   - Look up music filename from channel_config.music[act]
   - Return full path to music file from MUSIC_BASE/niche_id/
   - If file doesn't exist, return None (music is optional)

2. list_available_music(niche_id: str) -> list[str]
   - Return list of available music files for channel

---

### lib/color_grade.py

Dependencies: subprocess, pathlib

Functions:

1. apply_lut(
     video_path: str,
     lut_name: str,
     output_path: str
   ) -> str
   - Apply FFmpeg LUT color grade
   - lut_path = LUT_BASE/lut_name.cube
   - If LUT file doesn't exist, skip grading, return video_path unchanged
   - FFmpeg: -vf lut3d={lut_path}
   - Return output_path

2. apply_color_correction(
     video_path: str,
     brightness: float = 0.0,
     contrast: float = 1.0,
     saturation: float = 1.0,
     output_path: str = None
   ) -> str
   - Apply basic color correction via FFmpeg eq filter
   - Return output_path

---

### pipeline/channel_loader.py

Dependencies: yaml, pathlib

Functions:

1. load_channel(niche_id: str) -> dict
   - Load channels/{niche_id}.yaml
   - Return parsed dict
   - Raise clear error if channel not found

2. list_channels() -> list[dict]
   - Scan channels/ directory
   - Return list of all loaded channel configs
   - Each: {{"niche_id": str, "name": str, "color_scheme": dict}}

3. validate_channel_config(config: dict) -> bool
   - Validate required fields exist
   - Return True if valid, raise ValueError with details if not

---

### pipeline/status_tracker.py

Dependencies: json, pathlib, datetime

Track generation job status persistently.

Functions:

1. create_job(
     job_id: str,
     niche_id: str,
     topic: str,
     audio_mode: str
   ) -> dict
   - Create job status file at output/{niche_id}/{job_id}/status.json
   - Initial status: "created"
   - Return job dict

2. update_job(
     job_id: str,
     step: str,
     status: str,
     data: dict = None
   ) -> None
   - Update status.json
   - steps: script, images, thumbnail, audio, assembly, complete, error
   - status: pending, running, complete, error

3. get_job_status(job_id: str) -> dict
   - Return current status.json contents

4. list_jobs(niche_id: str = None) -> list[dict]
   - List all jobs, optionally filtered by niche

---

### pipeline/generator.py

This is the main orchestrator. Imports from all lib modules.

Dependencies: all lib modules, status_tracker, channel_loader

Functions:

1. generate_video(
     topic: str,
     niche_id: str,
     duration_minutes: int = 10,
     audio_mode: str = "ai",
     voice: str = None,
     job_id: str = None
   ) -> dict

Full pipeline:

````python
async def generate_video(topic, niche_id, duration_minutes=10, 
                          audio_mode="ai", voice=None, job_id=None):
    
    # Setup
    channel = load_channel(niche_id)
    job_id = job_id or generate_job_id()
    job_dir = OUTPUT_BASE / niche_id / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    create_job(job_id, niche_id, topic, audio_mode)
    
    # STEP 1: Script
    update_job(job_id, "script", "running")
    script = generate_video_script(topic, channel, duration_minutes)
    save_json(job_dir / "script.json", script)
    save_text(job_dir / "description.txt", script["description"])
    save_text(job_dir / "tags.txt", "\n".join(script["tags"]))
    save_text(job_dir / "titles.txt", "\n".join(script["title_variations"]))
    update_job(job_id, "script", "complete", {{"script_path": str(job_dir/"script.json")}})
    
    # STEP 2: Images (all scenes)
    update_job(job_id, "images", "running")
    all_scenes = [script["hook"]] + [s for act in script["acts"] for s in act["scenes"]] + [script["outro"]]
    image_paths = generate_scene_images_batch(all_scenes, channel, job_dir / "images")
    update_job(job_id, "images", "complete")
    
    # STEP 3: Thumbnail
    update_job(job_id, "thumbnail", "running")
    thumbnail_path = generate_thumbnail(script["title"], channel, job_dir / "thumbnail.png")
    update_job(job_id, "thumbnail", "complete", {{"thumbnail_path": str(thumbnail_path)}})
    
    # STEP 4: Audio
    update_job(job_id, "audio", "running")
    
    if audio_mode == "ai":
        audio_paths = generate_all_voiceovers(all_scenes, channel, job_dir / "audio")
        update_job(job_id, "audio", "complete")
        # Proceed to assembly
        final_path = assemble_video(script, image_paths, audio_paths, channel, job_dir)
        
    elif audio_mode == "human":
        # Return here - wait for human recording via UI
        update_job(job_id, "audio", "pending_human", {{
            "scenes": all_scenes,
            "image_paths": image_paths,
            "job_dir": str(job_dir),
            "waiting_for": "human_voiceover"
        }})
        return {{
            "job_id": job_id,
            "status": "waiting_for_human_voiceover",
            "script": script,
            "recorder_url": f"/recorder?job_id={{job_id}}"
        }}
        
    elif audio_mode == "hybrid":
        # Generate AI first, then flag sections for human re-record
        audio_paths = generate_all_voiceovers(all_scenes, channel, job_dir / "audio")
        update_job(job_id, "audio", "pending_hybrid", {{
            "ai_audio_paths": audio_paths,
            "waiting_for": "human_review"
        }})
        return {{
            "job_id": job_id,
            "status": "waiting_for_hybrid_review",
            "script": script,
            "recorder_url": f"/recorder?job_id={{job_id}}&mode=hybrid"
        }}
    
    update_job(job_id, "assembly", "complete", {{"output_path": str(final_path)}})
    return {{
        "job_id": job_id,
        "status": "complete",
        "output_path": str(final_path),
        "thumbnail_path": str(thumbnail_path)
    }}

2. assemble_video(
     script: dict,
     image_paths: dict,
     audio_paths: dict,
     channel_config: dict,
     job_dir: Path
   ) -> str
   - Create scene video per scene (image + broll + audio)
   - Insert act transitions between acts
   - Concatenate all scenes
   - Mix background music per act
   - Add intro/outro cards
   - Apply color grade LUT
   - Final render to job_dir/final_video.mp4
   - Return output path

3. complete_human_recording(
     job_id: str,
     niche_id: str,
     audio_paths: dict
   ) -> dict
   - Called after human finishes recording all sections
   - Normalize and noise-reduce each recording
   - Load script and image paths from job status
   - Call assemble_video
   - Return final output paths

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## API LAYER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### api/main.py

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api.routes import generate, channels, audio, status
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

app = FastAPI(title="YouTube Video Factory", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], 
                   allow_methods=["*"], allow_headers=["*"])

app.mount("/ui", StaticFiles(directory="ui"), name="ui")

app.include_router(generate.router, prefix="/generate", tags=["generation"])
app.include_router(channels.router, prefix="/channels", tags=["channels"])
app.include_router(audio.router, prefix="/audio", tags=["audio"])
app.include_router(status.router, prefix="/status", tags=["status"])

@app.get("/health")
def health():
    return {{"status": "ok", "version": "1.0.0"}}

@app.get("/")
def root():
    return {{"message": "YouTube Factory API", "ui": "/ui/index.html"}}
```

### api/routes/generate.py

Routes:

POST /generate/video
  Request: GenerateVideoRequest(
    topic: str,
    niche_id: str,
    duration_minutes: int = 10,
    audio_mode: str = "ai",  # "ai", "human", "hybrid"
    voice: str = None
  )
  - Validates niche_id exists
  - Calls generator.generate_video() as background task
  - Returns: {{"job_id": str, "status": str}}

POST /generate/script-only
  Request: ScriptRequest(topic: str, niche_id: str, duration_minutes: int = 10)
  - Generates only the script
  - Returns full script dict for review

POST /generate/thumbnail
  Request: ThumbnailRequest(title: str, niche_id: str, job_id: str = None)
  - Generates thumbnail
  - Returns thumbnail path

POST /generate/complete-human-recording
  Request: CompleteRecordingRequest(job_id: str, niche_id: str, audio_paths: dict)
  - Triggers assembly after human recording complete
  - Returns final output paths

### api/routes/channels.py

Routes:

GET /channels/list
  - Returns list of all available channels

GET /channels/{niche_id}
  - Returns full channel config

POST /channels/validate/{niche_id}
  - Validates a channel yaml

### api/routes/audio.py

Routes:

GET /audio/voices
  - Returns all 28 voice options

POST /audio/record/start
  Request: RecordRequest(job_id: str, scene_id: str, device_id: int = None)
  - Starts recording for a scene
  - Returns {{"recording": true, "scene_id": str}}

POST /audio/record/stop
  Request: StopRequest(job_id: str, scene_id: str)
  - Stops recording
  - Normalizes audio
  - Returns {{"path": str, "duration": float}}

GET /audio/record/status
  - Returns current recording status

POST /audio/preview
  Request: PreviewRequest(text: str, voice: str, speed: float = 0.85)
  - Generates short TTS preview
  - Returns audio file path

### api/routes/status.py

Routes:

GET /status/{job_id}
  - Returns job status and progress

GET /status/list/{niche_id}
  - Lists all jobs for a channel

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## UI LAYER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### ui/index.html

Single page HTML+JS (no framework, pure vanilla JS).
Dark theme matching the channel aesthetic.

Sections:
1. Channel selector (Psychology / Finance + any future channels auto-loaded from API)
2. Topic input field
3. Duration selector (8, 10, 12, 15 minutes)
4. Audio mode selector:
   - AI Voiceover (voice dropdown + speed slider)
   - Human Voiceover
   - Hybrid
5. Generate button
6. Progress tracker showing steps:
   [Script] → [Images] → [Thumbnail] → [Audio] → [Assembly] → [Complete]
   Each step shows: pending / running (spinner) / complete (checkmark) / error
7. Output section when complete:
   - Video preview (HTML5 video player)
   - Thumbnail preview
   - Download buttons for video and thumbnail
   - Copy buttons for title, description, tags

Poll /status/{job_id} every 3 seconds to update progress.

### ui/recorder.html

Human voiceover recording interface.
URL: /ui/recorder.html?job_id=xxx&mode=human

Layout:
- Top: Video preview (no audio) playing current scene
- Middle: Script text for current scene (large readable font)
  - Markers shown: [pause] highlighted in yellow, [slow] in blue, [emphasis] in red
  - These are visual guides — not read aloud
- Bottom controls:
  - [▶ Play Scene] — plays video preview
  - [🔴 Record] — starts mic recording
  - [⏹ Stop] — stops recording
  - [▶ Play Back] — plays recorded audio
  - [✓ Save] — saves and moves to next scene
  - [↺ Re-record] — discard and re-record

Progress bar: "Scene 3 of 12"
Device selector: dropdown to choose mic input

After all scenes recorded:
- [Complete Recording] button
- Calls /generate/complete-human-recording
- Redirects to index.html with job_id to show final output

### ui/review.html

Script review page before generation.
Shows full script with edit capability.
Each scene narration is editable textarea.
[Regenerate Scene] button per scene calls /generate/script-only for that scene.
[Approve & Continue] triggers image + audio generation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## IMPORTANT RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. All API keys loaded from config.env via python-dotenv
2. Never hardcode API keys
3. All paths use pathlib.Path
4. Create output dirs automatically with mkdir(parents=True, exist_ok=True)
5. Every function prints clear progress logs with timestamps
6. All heavy operations (image gen, video gen, TTS) handle errors gracefully
7. If FAL_API_KEY is empty: skip video generation, use images only
8. If a music file doesn't exist: skip music, don't fail
9. If LUT file doesn't exist: skip color grade, don't fail
10. Video generation via Fal is OPTIONAL enhancement — pipeline works without it
11. Human recording mode pauses pipeline and waits — never auto-proceeds
12. All generated files saved with job_id prefix to avoid conflicts
13. lib/ has zero FastAPI dependency
14. pipeline/ imports from lib/ only
15. api/ imports from pipeline/ and lib/
16. sys.path handling in api/main.py to find lib/ and pipeline/
17. Adding a new channel = create new .yaml in channels/ = zero code changes
18. README.md must explain how to add a new channel in 5 steps

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## README.MD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Include clear sections:
- Setup instructions
- How to add API keys to config.env
- How to start the server
- How to add a new channel in 5 steps:
  1. Copy channels/psychology.yaml
  2. Rename to your_niche.yaml
  3. Edit name, colors, prompts, voice
  4. Restart server
  5. New channel appears automatically in UI
- How to add music files
- How to use human voiceover mode
````

---

After Cursor finishes creating the project:

````bash
cd /Volumes/Fun/youtube-factory
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
````

Then open: `http://localhost:8001/ui/index.html`

How Script Review Should Work — Full Flow
User clicks Generate
        ↓
Script generated by Groq
        ↓
PAUSE — redirect to review.html
        ↓
User reads, edits, approves script
        ↓
RESUME — images + audio + assembly begin
The pipeline has a hard gate at script. Nothing generates until you approve.

The Missing API Endpoints
Add these to api/routes/generate.py:
POST /generate/script-review/approve
  Request: ApproveScriptRequest(
    job_id: str,
    niche_id: str,
    edited_script: dict,   ← full script with any edits applied
    audio_mode: str,
    voice: str = None
  )
  - Saves edited script to job_dir/script_approved.json
  - Updates job status to "script_approved"
  - Triggers next pipeline steps as background task:
    images → thumbnail → audio → assembly
  - Returns: {"job_id": str, "status": "generating"}

POST /generate/script-review/regenerate-scene
  Request: RegenerateSceneRequest(
    job_id: str,
    niche_id: str,
    scene_id: str,
    instruction: str   ← "make this more emotional" etc
  )
  - Calls script.refine_script_section()
  - Returns: {"scene_id": str, "new_narration": str}
  - Does NOT restart full generation
  - User sees updated text inline, can approve or try again

POST /generate/script-review/regenerate-full
  Request: RegenerateFullRequest(
    job_id: str,
    niche_id: str,
    topic: str,
    instruction: str = None   ← optional guidance for rewrite
  )
  - Regenerates entire script
  - Returns new script dict
  - Job stays in review state

How review.html Works With These APIs
Page loads with ?job_id=xxx
        ↓
Fetch /status/{job_id} → get script.json path
Fetch script content → render all scenes
        ↓
User sees:
  ┌─────────────────────────────────────┐
  │ HOOK                                │
  │ [editable textarea]                 │
  │ [Regenerate Scene] [instruction box]│
  ├─────────────────────────────────────┤
  │ ACT 1 — Scene 1                     │
  │ [editable textarea]                 │
  │ [Regenerate Scene]                  │
  ├─────────────────────────────────────┤
  │ ...all scenes...                    │
  └─────────────────────────────────────┘
  [↺ Regenerate Full Script]
  [✓ Approve & Generate Video]  ← calls /approve
        ↓
On Approve:
  Collect all textarea values
  Build edited_script dict
  POST /generate/script-review/approve
  Redirect to index.html?job_id=xxx
  Progress tracker takes over

Updated Pipeline Flow in generator.py
pythonasync def generate_video(...):

    # STEP 1: Script → PAUSE for review
    script = generate_video_script(topic, channel, duration_minutes)
    save_json(job_dir / "script.json", script)
    update_job(job_id, "script", "pending_review", {
        "review_url": f"/ui/review.html?job_id={job_id}"
    })
    return {
        "job_id": job_id,
        "status": "pending_script_review",
        "review_url": f"/ui/review.html?job_id={job_id}"
    }
    # Pipeline STOPS here

# Separate function called AFTER approval
async def continue_after_approval(job_id, niche_id, approved_script, audio_mode, voice):
    # STEP 2 onwards: images, thumbnail, audio, assembly
    ...

Summary of All API Routes Now
POST /generate/video                      ← starts pipeline, stops at script
GET  /generate/script-review/{job_id}     ← fetch script for review page
POST /generate/script-review/approve      ← approve + continue pipeline
POST /generate/script-review/regenerate-scene  ← regenerate one scene
POST /generate/script-review/regenerate-full   ← regenerate whole script
POST /generate/complete-human-recording   ← after human voiceover done
POST /generate/thumbnail                  ← standalone thumbnail gen
POST /generate/script-only               ← script only, no pipeline

Give this to Cursor as a follow-up in the same chat:
Add the missing script review API to the YouTube Factory project.

In api/routes/generate.py add these routes:

GET /generate/script-review/{job_id}
  - Load script from output/{niche_id}/{job_id}/script.json
  - Get niche_id from status.json in job dir
  - Return full script dict

POST /generate/script-review/approve
  Request body:
    job_id: str
    niche_id: str
    edited_script: dict
    audio_mode: str = "ai"
    voice: str = None
  - Save edited_script to output/{niche_id}/{job_id}/script_approved.json
  - Update job status: step="script", status="approved"
  - Launch background task: continue_after_approval(job_id, niche_id, edited_script, audio_mode, voice)
  - Return: {"job_id": job_id, "status": "generating"}

POST /generate/script-review/regenerate-scene
  Request body:
    job_id: str
    niche_id: str
    scene_id: str
    instruction: str
  - Load channel config for niche_id
  - Load current script from script.json
  - Find scene by scene_id
  - Call script.refine_script_section(scene.narration, instruction, channel_config)
  - Return: {"scene_id": scene_id, "new_narration": str}

POST /generate/script-review/regenerate-full
  Request body:
    job_id: str
    niche_id: str
    topic: str
    instruction: str = None
    duration_minutes: int = 10
  - Load channel config
  - Regenerate full script with optional instruction appended to prompt
  - Save new script.json overwriting old one
  - Return new full script dict

In pipeline/generator.py:

1. Modify generate_video() to STOP after script generation:
   After saving script.json:
   - update_job(job_id, "script", "pending_review")
   - Return immediately: {
       "job_id": job_id,
       "status": "pending_script_review",
       "review_url": f"/ui/review.html?job_id={job_id}",
       "script": script
     }
   - DO NOT proceed to image generation

2. Add new function continue_after_approval(
     job_id: str,
     niche_id: str,
     approved_script: dict,
     audio_mode: str = "ai",
     voice: str = None
   ) -> dict
   This runs everything AFTER script approval:
   - Load channel config
   - Set up job_dir
   - STEP 2: generate_scene_images_batch for all scenes
   - STEP 3: generate_thumbnail
   - STEP 4: based on audio_mode:
     - "ai": generate_all_voiceovers → assemble_video → return complete
     - "human": update job pending_human → return recorder_url
     - "hybrid": generate_all_voiceovers → update pending_hybrid → return recorder_url
   - STEP 5: assemble_video (if ai mode)
   - Update job status at each step
   - Return final output dict

In ui/review.html:

Complete the review page with:
- On load: fetch GET /generate/script-review/{job_id} to get script
- Render each scene as editable textarea
  Show: scene_id as label, narration as textarea, visual_prompt as small grey text
  Highlight [pause] in yellow, [slow] in blue, [emphasis] in red, [breath] in grey
  These are visual only, not editable as tags
- Per scene: "Regenerate Scene" button + instruction input
  On click: POST /generate/script-review/regenerate-scene
  Update that textarea with new_narration in response
- "Regenerate Full Script" button with instruction input
  On click: POST /generate/script-review/regenerate-full
  Re-render all textareas with new script
- Audio mode selector (ai / human / hybrid) with voice dropdown if ai selected
- "Approve & Generate Video" button
  On click:
    Collect all textarea values back into script structure
    POST /generate/script-review/approve with full edited script
    Redirect to /ui/index.html?job_id={job_id}
- Loading states on all buttons
- Dark theme matching index.html

In ui/index.html:

After POST /generate/video returns:
  If status == "pending_script_review":
    Show: "Script ready for review"
    Button: "Review Script" → opens /ui/review.html?job_id={job_id}
    Stop polling until user comes back from review
  If status == "generating":
    Start polling /status/{job_id} every 3 seconds
    Show progress steps normally


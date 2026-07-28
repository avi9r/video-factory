"""Script generation and narration processing."""

import json
import re
from datetime import datetime

from lib.llm import chat_completion

DEFAULT_WRITING_RULES = [
    "Write like a sharp documentary narrator — curious, specific, never salesy.",
    "Open with a concrete fact, person, date, or dollar amount — not a generic question.",
    "Every act must advance ONE clear story thread with cause and effect.",
    "Name real companies, studies, economists, founders, or historical moments when relevant.",
    "Use short punchy sentences mixed with longer explanatory ones.",
    "Never use: 'In today's world', 'Let's dive in', 'Buckle up', 'game-changer', "
    "'At the end of the day', 'Here's the thing', 'mind-blowing', 'you won't believe'.",
    "Avoid hollow superlatives (shocking, incredible, amazing) unless tied to a specific fact.",
    "Visual prompts describe ONE clear frame — symbolic or literal — with no on-screen text.",
    "Show emotion through concrete sensory details — never label feelings with adjectives alone.",
]


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] script: {msg}")


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_json_blob(text: str) -> str:
    text = _strip_markdown_fence(text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _close_truncated_json(text: str) -> str:
    """Best-effort close for LLM output cut off mid-string or mid-object."""
    s = text.rstrip()
    if not s:
        return "{}"

    in_string = False
    escape = False
    stack: list[str] = []
    for ch in s:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in "}]" and stack and stack[-1] == ch:
            stack.pop()

    if in_string:
        s += '"'
    s += "".join(reversed(stack))
    return s


def _parse_json_response(text: str) -> dict:
    blob = _extract_json_blob(text)
    for candidate in (blob, _close_truncated_json(blob)):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    raise json.JSONDecodeError(
        "Could not parse LLM JSON response",
        blob,
        0,
    )


def _call_llm_json(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 4096,
    label: str = "llm",
) -> dict:
    raw = _call_llm(system_prompt, user_prompt, max_tokens=max_tokens)
    try:
        return _parse_json_response(raw)
    except json.JSONDecodeError as first_err:
        _log(f"{label} JSON parse failed, retrying with repair prompt")
        repair = _call_llm(
            system_prompt,
            "Fix this malformed JSON. Return ONLY valid JSON with the same structure.\n\n"
            + raw[:14000],
            max_tokens=max_tokens,
        )
        try:
            return _parse_json_response(repair)
        except json.JSONDecodeError:
            raise first_err from None


def _call_llm(system_prompt: str, user_prompt: str, *, max_tokens: int = 4096) -> str:
    return chat_completion(system_prompt, user_prompt, max_tokens=max_tokens)


def _emotion_palette(channel_config: dict) -> list[str]:
    palette = channel_config.get("script", {}).get("emotion_palette")
    if palette:
        return palette
    return ["curiosity", "tension", "dread", "hope", "revelation", "resolve"]


def _build_system_prompt(channel_config: dict, extra_instruction: str | None = None) -> str:
    script_cfg = channel_config.get("script", {})
    parts = [script_cfg.get("system_prompt", "").strip()]
    rules = script_cfg.get("writing_rules", DEFAULT_WRITING_RULES)
    if rules:
        parts.append("\n\nWriting rules (follow strictly):\n" + "\n".join(f"- {r}" for r in rules))
    story_rules = script_cfg.get("storytelling_rules", [])
    if story_rules:
        parts.append("\n\nStorytelling rules:\n" + "\n".join(f"- {r}" for r in story_rules))
    parts.append(
        f"\n\nAllowed emotion values: {', '.join(_emotion_palette(channel_config))}"
    )
    if extra_instruction:
        parts.append(f"\n\nAdditional instruction: {extra_instruction}")
    return "\n".join(p for p in parts if p)


def _outline_context(outline: dict) -> str:
    parts = [
        f"Story spine: {outline.get('story_spine', '')}",
        f"Stakes: {outline.get('stakes', '')}",
        f"Midpoint reversal: {outline.get('midpoint_reversal', '')}",
        f"Open loops to close in Act 3: {json.dumps(outline.get('open_loops', []))}",
        f"Emotional arc: {json.dumps(outline.get('emotional_arc', []))}",
    ]
    return "\n".join(parts)


def _outline_prompt(topic: str, duration_minutes: int, channel_config: dict) -> str:
    emotions = ", ".join(_emotion_palette(channel_config))
    return f"""Plan a {duration_minutes}-minute YouTube video about: "{topic}"

Design a STORY with addictive pacing — not a listicle. One narrative spine, rising stakes, a midpoint reversal in Act 2.

Return ONLY JSON:
{{
  "title": "specific compelling title (not clickbait)",
  "title_variations": ["alt1", "alt2", "alt3"],
  "description": "SEO YouTube description ~150 words",
  "tags": ["15 relevant tags"],
  "story_spine": "one sentence: the through-line of the whole video",
  "stakes": "what the viewer loses if they ignore this",
  "midpoint_reversal": "one sentence — the counterintuitive flip in Act 2",
  "open_loops": ["question or mystery from hook that Act 3 must answer"],
  "emotional_arc": ["pick 4-6 from: {emotions}"],
  "acts": [
    {{
      "act_number": 1,
      "act_title": "Act title",
      "scene_summaries": [
        {{"scene_id": "act1_scene1", "beat": "specific beat with names/dates/facts", "target_emotion": "curiosity"}},
        {{"scene_id": "act1_scene2", "beat": "...", "target_emotion": "tension"}},
        {{"scene_id": "act1_scene3", "beat": "...", "target_emotion": "dread"}}
      ]
    }},
    {{"act_number": 2, "act_title": "...", "scene_summaries": [3-4 items with act2_sceneN ids]}},
    {{"act_number": 3, "act_title": "...", "scene_summaries": [3-4 items with act3_sceneN ids]}}
  ]
}}"""


def _hook_prompt(topic: str, outline: dict, channel_config: dict) -> str:
    emotions = ", ".join(_emotion_palette(channel_config))
    return f"""Write the hook for this video about "{topic}".

Title: {outline.get("title", topic)}
{_outline_context(outline)}

The hook must grab attention in the first 10 seconds with a SPECIFIC fact, moment, or paradox.
Open one loop from open_loops that Act 3 will close. 45 seconds max spoken.
Include [pause] only where a human would naturally pause.

Return ONLY JSON:
{{
  "scene_id": "hook",
  "text": "hook narration",
  "visual_prompt": "Close-up of a worn leather ledger on a mahogany desk, single desk lamp, rain on window — no text",
  "broll_prompt": "Hands flipping through stamped documents — no text",
  "duration_seconds": 45,
  "emotion": "one of: {emotions}",
  "narration_tone": "e.g. urgent whisper, cold precision, quiet dread"
}}

visual_prompt MUST name concrete visible subjects from the topic (people, objects, places, metaphors). Never use generic placeholders."""


def _act_prompt(topic: str, act: dict, outline: dict, channel_config: dict) -> str:
    summaries = json.dumps(act.get("scene_summaries", []), indent=2)
    act_num = act["act_number"]
    act_title = act.get("act_title", "")
    emotions = ", ".join(_emotion_palette(channel_config))
    return f"""Write Act {act_num} scenes for: "{topic}"
Act title: {act_title}
{_outline_context(outline)}

Expand beats into spoken narration. Each scene = one idea with a micro-cliffhanger or tension at the end (except final scene of Act 3).
Match target_emotion from scene summaries. Use concrete sensory details — not adjectives like "shocking" or "incredible".

Scene beats:
{summaries}

Return ONLY JSON:
{{
  "act_number": {act_num},
  "act_title": "{act_title}",
  "scenes": [
    {{
      "scene_id": "act{act_num}_scene1",
      "narration": "spoken words — natural, varied rhythm",
      "visual_prompt": "Specific frame: factory floor with workers at assembly line, morning light — no text",
      "broll_prompt": "Close-up of conveyor belt gears turning — no text",
      "duration_seconds": 30,
      "emotion": "one of: {emotions}",
      "narration_tone": "one-line delivery direction"
    }}
  ]
}}

Each visual_prompt must describe ONE literal or symbolic frame tied to the topic — name real subjects, not generic 'cinematic scene'."""


def _outro_prompt(topic: str, outline: dict, channel_config: dict) -> str:
    emotions = ", ".join(_emotion_palette(channel_config))
    return f"""Write the outro for this video about "{topic}".

Title: {outline.get("title", topic)}
{_outline_context(outline)}

Close the open loops. Land one insight the viewer takes away. No generic subscribe begging in the narration body.
30 seconds max.

Return ONLY JSON:
{{
  "scene_id": "outro",
  "text": "outro narration",
  "visual_prompt": "Wide shot of empty office at dusk, city lights through blinds — no text",
  "duration_seconds": 30,
  "emotion": "one of: {emotions}",
  "narration_tone": "one-line delivery direction"
}}"""


def _hero_visual_prompt_llm(
    topic: str,
    script: dict,
    outline: dict,
    channel_config: dict,
) -> str:
    title = script.get("title", topic)
    hook_visual = script.get("hook", {}).get("visual_prompt", "")
    act_titles = [a.get("act_title", "") for a in script.get("acts", [])]
    return f"""Write ONE hero visual prompt for the entire video background image.

Topic: "{topic}"
Title: {title}
Story spine: {outline.get("story_spine", script.get("story_spine", ""))}
Stakes: {outline.get("stakes", script.get("stakes", ""))}
Hook visual: {hook_visual}
Act themes: {", ".join(t for t in act_titles if t)}

Rules:
- ONE symbolic or literal frame that represents the whole story
- Name specific visible subjects from the topic (objects, settings, metaphors)
- No on-screen text, logos, or readable charts
- Match the channel's documentary tone

Return ONLY JSON:
{{"hero_visual_prompt": "your detailed single-frame description"}}"""


def _visual_polish_prompt(script: dict, outline: dict, *, one_image: bool) -> str:
    hero_note = (
        "- Set hero_visual_prompt: one frame summarizing the full story visually\n"
        if one_image
        else ""
    )
    return f"""Polish visual prompts in this script JSON so they match narration and topic.

Story spine: {outline.get("story_spine", script.get("story_spine", ""))}

Tasks:
- Align each visual_prompt with its scene narration — name concrete subjects
- Replace generic placeholders ("cinematic scene", "one clear scene") with specific frames
{hero_note}- Keep all scene_id values unchanged
- Keep emotion and narration_tone on every scene

Return ONLY the full script JSON:

{json.dumps(script, indent=2)[:12000]}"""


def _polish_prompt(script: dict, outline: dict) -> str:
    return f"""Polish this YouTube documentary script JSON for maximum retention and story clarity.

Story spine: {outline.get("story_spine", script.get("story_spine", ""))}
Stakes: {outline.get("stakes", script.get("stakes", ""))}
Midpoint reversal: {outline.get("midpoint_reversal", script.get("midpoint_reversal", ""))}
Open loops to close: {json.dumps(outline.get("open_loops", []))}

Tasks:
- Hook must open on a specific date, dollar amount, paradox, or decision — never a generic question
- Every scene ends with tension, an unanswered question, or a turn (except final outro)
- Act 2 must deliver the midpoint reversal with a concrete reveal
- Act 3 must close every open loop from the hook
- Use vivid sensory details and named people/companies/dates — not vague summaries
- Remove AI clichés (Let's dive in, game-changer, mind-blowing, buckle up, etc.)
- Keep all scene_id values unchanged
- Keep emotion and narration_tone on every scene

Return ONLY the full polished script JSON (same schema). Keep string values on one line.

{json.dumps(script, indent=2)[:12000]}"""


def _sfx_scene_skeleton(script: dict) -> list[dict]:
    """Minimal per-scene context for SFX annotation (keeps Groq requests small)."""
    scenes: list[dict] = []

    def _add(scene_id: str, block: dict) -> None:
        visual = str(block.get("visual_prompt", ""))[:100]
        scenes.append({
            "scene_id": scene_id,
            "emotion": block.get("emotion", ""),
            "dur": block.get("duration_seconds", 30),
            "visual": visual,
        })

    hook = script.get("hook", {})
    if hook:
        _add(hook.get("scene_id", "hook"), hook)
    for act in script.get("acts", []):
        for scene in act.get("scenes", []):
            _add(scene.get("scene_id", "scene"), scene)
    outro = script.get("outro", {})
    if outro:
        _add(outro.get("scene_id", "outro"), outro)
    return scenes


def _merge_sfx_cues(script: dict, sfx_by_scene: dict) -> dict:
    """Apply scene_id -> sfx_cues map onto the full script."""
    if not isinstance(sfx_by_scene, dict):
        return script

    hook_id = script.get("hook", {}).get("scene_id", "hook")
    if hook_id in sfx_by_scene and isinstance(script.get("hook"), dict):
        script["hook"]["sfx_cues"] = sfx_by_scene[hook_id] or []

    for act in script.get("acts", []):
        for scene in act.get("scenes", []):
            sid = scene.get("scene_id")
            if sid in sfx_by_scene:
                scene["sfx_cues"] = sfx_by_scene[sid] or []

    outro_id = script.get("outro", {}).get("scene_id", "outro")
    if outro_id in sfx_by_scene and isinstance(script.get("outro"), dict):
        script["outro"]["sfx_cues"] = sfx_by_scene[outro_id] or []

    return script


_SFX_SYSTEM_PROMPT = (
    "You assign subtle documentary sound effects. "
    "Return ONLY valid JSON — no markdown, no commentary."
)


def _sfx_annotation_prompt(scenes: list[dict], catalog_text: str, max_cues: int) -> str:
    return f"""Add sfx_cues to each scene. Sounds (id|kind|vol|tags):
{catalog_text}

kind: a=ambient bed, o=one-shot. Max {max_cues} cues per scene (empty array is fine).

Rules:
- Ambient volume 0.04-0.07, one-shot 0.06-0.10
- duration_sec must not exceed scene dur
- Match emotion and visual — not every scene needs SFX

Scenes:
{json.dumps(scenes, separators=(",", ":"))}

Return ONLY JSON: {{"hook": [{{"sound_id":"rain_light","start_offset_sec":0,"duration_sec":12,"volume":0.05}}], "act1_scene1": [], ...}}
Use exact scene_id keys from the scenes list."""


def _annotate_sfx_cues(
    script: dict,
    channel_config: dict,
) -> dict:
    from lib.sfx import catalog_compact_for_llm, sanitize_sfx_cues

    catalog_text = catalog_compact_for_llm(max_entries=48)
    if not catalog_text:
        return script

    scenes = _sfx_scene_skeleton(script)
    max_cues = channel_config.get("sfx", {}).get("max_cues_per_scene", 2)
    sfx_map = _call_llm_json(
        _SFX_SYSTEM_PROMPT,
        _sfx_annotation_prompt(scenes, catalog_text, max_cues),
        max_tokens=2048,
        label="sfx annotation",
    )
    merged = _merge_sfx_cues(script, sfx_map)
    return sanitize_sfx_cues(merged, max_cues=max_cues)


def apply_humanization(text: str, rules: list | None = None) -> str:
    """Insert light [pause]/[breath] markers — kept sparse to avoid long TTS silences."""
    if not text or not text.strip():
        return text

    text = re.sub(r"\[slow\]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[emphasis\]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(\[pause\]\s*){2,}", "[pause] ", text, flags=re.IGNORECASE)

    marker_re = re.compile(r"\[(pause|slow|fast|breath|emphasis)\]", re.IGNORECASE)
    words = len(text.split())
    if words < 6:
        return text
    if len(marker_re.findall(text)) >= max(1, words // 80):
        return text

    reveal_start = re.compile(
        r"^(But|However|Yet|Still|Then|Until|Ironically|Instead|Suddenly)\b",
        re.IGNORECASE,
    )

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    result: list[str] = []
    sentence_count = 0

    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue
        sentence_count += 1

        if reveal_start.match(s) and "[pause]" not in s[:20].lower():
            s = reveal_start.sub(lambda m: f"[pause] {m.group(1)}", s, count=1)

        result.append(s)
        if sentence_count % 6 == 0:
            result.append("[breath]")

    return " ".join(result)


def humanize_script_narration(script: dict, channel_config: dict | None = None) -> dict:
    """Apply pacing markers to all narration fields in a script."""
    rules: list = []
    if channel_config:
        rules = channel_config.get("script", {}).get("humanization_rules", [])

    if isinstance(script.get("hook"), dict) and script["hook"].get("text"):
        script["hook"]["text"] = apply_humanization(script["hook"]["text"], rules)
    for act in script.get("acts", []):
        for scene in act.get("scenes", []):
            narration = scene.get("narration") or scene.get("text")
            if narration:
                scene["narration"] = apply_humanization(narration, rules)
    if isinstance(script.get("outro"), dict) and script["outro"].get("text"):
        script["outro"]["text"] = apply_humanization(script["outro"]["text"], rules)
    return script


def clean_narration_for_tts(text: str) -> str:
    """Strip performance markers — use commas only; Kokoro treats '...' as multi-second silence."""
    text = re.sub(r"\[slow\]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[fast\]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[emphasis\]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[breath\]\s*", ", ", text, flags=re.IGNORECASE)
    text = re.sub(r"\[pause\]\s*", ", ", text, flags=re.IGNORECASE)
    text = re.sub(r"\.{3,}", ".", text)
    text = re.sub(r"\.\s*,", ".", text)
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r",\s*,+", ", ", text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _ensure_scene_ids(script: dict) -> dict:
    if "hook" in script and "scene_id" not in script["hook"]:
        script["hook"]["scene_id"] = "hook"
    if "outro" in script and "scene_id" not in script["outro"]:
        script["outro"]["scene_id"] = "outro"
    for act in script.get("acts", []):
        for i, scene in enumerate(act.get("scenes", [])):
            if "scene_id" not in scene:
                scene["scene_id"] = f"act{act.get('act_number', 0)}_scene{i + 1}"
    return script


def _humanize_script(script: dict, rules: list) -> dict:
    return humanize_script_narration(script, {"script": {"humanization_rules": rules}})


def _annotate_hero_visual(
    script: dict,
    topic: str,
    outline: dict,
    channel_config: dict,
    system_prompt: str,
) -> dict:
    raw = _call_llm(
        system_prompt,
        _hero_visual_prompt_llm(topic, script, outline, channel_config),
        max_tokens=512,
    )
    result = _parse_json_response(raw)
    prompt = str(result.get("hero_visual_prompt", "")).strip()
    if prompt:
        script["hero_visual_prompt"] = prompt
    return script


def _visual_polish_script(
    script: dict,
    outline: dict,
    system_prompt: str,
    *,
    one_image: bool,
) -> dict:
    return _call_llm_json(
        system_prompt,
        _visual_polish_prompt(script, outline, one_image=one_image),
        max_tokens=8192,
        label="visual polish",
    )


def generate_video_script(
    topic: str,
    channel_config: dict,
    duration_minutes: int = 10,
    extra_instruction: str | None = None,
    sfx_mode: str = "local",
    image_layout: str = "one_image",
) -> dict:
    """
    Generate script in multiple small LLM calls to stay within free-tier TPM limits.
    Flow: outline → hook → 3 acts → outro → polish → optional SFX annotation.
    """
    _log(f"Generating script (chunked) for topic: {topic}")
    system_prompt = _build_system_prompt(channel_config, extra_instruction)

    outline = _call_llm_json(
        system_prompt, _outline_prompt(topic, duration_minutes, channel_config),
        max_tokens=2048, label="outline",
    )
    _log("Outline complete")

    hook = _call_llm_json(
        system_prompt, _hook_prompt(topic, outline, channel_config),
        max_tokens=1024, label="hook",
    )
    _log("Hook complete")

    acts = []
    for act_plan in outline.get("acts", []):
        act_num = act_plan.get("act_number", len(acts) + 1)
        acts.append(_call_llm_json(
            system_prompt, _act_prompt(topic, act_plan, outline, channel_config),
            max_tokens=3072, label=f"act {act_num}",
        ))
        _log(f"Act {act_num} complete")

    outro = _call_llm_json(
        system_prompt, _outro_prompt(topic, outline, channel_config),
        max_tokens=1024, label="outro",
    )
    _log("Outro complete")

    total_scenes = 1 + sum(len(a.get("scenes", [])) for a in acts) + 1
    script = {
        "title": outline.get("title", topic),
        "title_variations": outline.get("title_variations", []),
        "description": outline.get("description", ""),
        "tags": outline.get("tags", []),
        "story_spine": outline.get("story_spine", ""),
        "stakes": outline.get("stakes", ""),
        "midpoint_reversal": outline.get("midpoint_reversal", ""),
        "open_loops": outline.get("open_loops", []),
        "emotional_arc": outline.get("emotional_arc", []),
        "hook": hook,
        "acts": acts,
        "outro": outro,
        "total_scenes": total_scenes,
        "total_duration_seconds": duration_minutes * 60,
    }

    if channel_config.get("script", {}).get("script_polish", True):
        _log("Running story polish pass")
        try:
            script = _call_llm_json(
                system_prompt, _polish_prompt(script, outline),
                max_tokens=8192, label="story polish",
            )
            script.setdefault("story_spine", outline.get("story_spine", ""))
        except Exception as e:
            _log(f"Story polish skipped: {e}")

    one_image = image_layout == "one_image"
    _log("Running visual polish pass")
    try:
        script = _visual_polish_script(script, outline, system_prompt, one_image=one_image)
    except Exception as e:
        _log(f"Visual polish skipped: {e}")

    if one_image:
        _log("Generating hero visual prompt")
        try:
            script = _annotate_hero_visual(script, topic, outline, channel_config, system_prompt)
        except Exception as e:
            _log(f"Hero visual prompt skipped: {e}")

    if sfx_mode == "local" and channel_config.get("sfx", {}).get("enabled", True):
        _log("Annotating SFX cues")
        try:
            script = _annotate_sfx_cues(script, channel_config)
        except Exception as e:
            _log(f"SFX annotation skipped: {e}")

    if channel_config.get("script", {}).get("auto_humanize", True):
        rules = channel_config.get("script", {}).get("humanization_rules", [])
        script = _humanize_script(script, rules)

    script = _ensure_scene_ids(script)
    _log("Script generation complete")
    return script


def refine_script_section(
    section_text: str,
    instruction: str,
    channel_config: dict | None = None,
) -> str:
    _log(f"Refining section: {instruction[:50]}...")
    system = (
        _build_system_prompt(channel_config)
        if channel_config
        else "You are an expert YouTube scriptwriter."
    )
    user = f"""Refine this narration section according to the instruction.

Instruction: {instruction}

Original text:
{section_text}

Return ONLY the refined narration text. Keep it natural and specific — avoid AI clichés."""
    return _call_llm(system, user, max_tokens=1024).strip()

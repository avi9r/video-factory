"""Script generation and narration processing."""

import json
import re
from datetime import datetime

from lib.llm import chat_completion

DEFAULT_WRITING_RULES = [
    "Write like a sharp documentary narrator — curious, specific, never salesy.",
    "Open with a concrete fact, person, date, or dollar amount — not a generic question.",
    "First 8 words of the hook must include a YEAR, a dollar amount, or a proper name.",
    "Every act must advance ONE clear story thread with cause and effect.",
    "Name real companies, studies, economists, founders, or historical moments when relevant.",
    "Each scene needs at least 2 proper nouns OR 1 quantitative claim (date, dollar, percent, count).",
    "Use short punchy sentences mixed with longer explanatory ones.",
    "Never use: 'In today's world', 'Let's dive in', 'Buckle up', 'game-changer', "
    "'At the end of the day', 'Here's the thing', 'mind-blowing', 'you won't believe', "
    "'Here's what most people don't realize', 'And that changed everything', "
    "'The writing was on the wall', 'What happens next will shock you', 'In a world where'.",
    "Avoid hollow superlatives (shocking, incredible, amazing) unless tied to a specific fact.",
    "Visual prompts describe ONE clear frame — symbolic or literal — with no on-screen text.",
    "Show emotion through concrete sensory details — never label feelings with adjectives alone.",
]

WORDS_PER_MINUTE = 140
CLICHE_PATTERNS = [
    r"in today's world",
    r"let'?s dive in",
    r"buckle up",
    r"game[- ]changer",
    r"at the end of the day",
    r"here'?s the thing",
    r"mind[- ]blowing",
    r"you won'?t believe",
    r"here'?s what most people don'?t realize",
    r"and that changed everything",
    r"the writing was on the wall",
    r"what happens next will shock you",
    r"in a world where",
]

# niche_id substring → exemplar content_json filenames
FEWSHOT_EXEMPLARS = {
    "business": ["kodak_bankruptcy.json", "blockbuster_netflix.json", "nokia_iphone.json"],
    "finance": ["anchoring_bias.json", "disposition_effect.json", "decoy_effect.json"],
    "psychology": ["anchoring_bias.json", "regret_makes_worse_investors.json"],
}


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
    temperature: float = 0.7,
) -> dict:
    raw = _call_llm(
        system_prompt, user_prompt, max_tokens=max_tokens, temperature=temperature
    )
    try:
        return _parse_json_response(raw)
    except json.JSONDecodeError as first_err:
        _log(f"{label} JSON parse failed, retrying with repair prompt")
        repair = _call_llm(
            system_prompt,
            "Fix this malformed JSON. Return ONLY valid JSON with the same structure.\n\n"
            + raw[:14000],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        try:
            return _parse_json_response(repair)
        except json.JSONDecodeError:
            raise first_err from None


def _call_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    return chat_completion(
        system_prompt, user_prompt, max_tokens=max_tokens, temperature=temperature
    )


def word_count(text: str) -> int:
    plain = re.sub(r"\[(pause|breath|slow|fast|emphasis)\]", " ", str(text or ""), flags=re.I)
    return len(plain.split())


def word_budgets(duration_minutes: int) -> dict:
    """Spoken-word targets for a documentary at ~140 wpm."""
    total = max(200, int(duration_minutes * WORDS_PER_MINUTE))
    hook = max(70, int(total * 0.08))
    outro = max(40, int(total * 0.05))
    body = max(120, total - hook - outro)
    per_act = max(80, body // 3)
    per_scene = max(70, min(120, per_act // 3))
    return {
        "total": total,
        "hook": hook,
        "outro": outro,
        "per_act": per_act,
        "per_scene": per_scene,
    }


def _budget_hint(budgets: dict) -> str:
    return (
        f"WORD BUDGETS (strict spoken words @ ~{WORDS_PER_MINUTE} wpm): "
        f"hook {budgets['hook'] - 15}-{budgets['hook'] + 15}, "
        f"each body scene {budgets['per_scene'] - 20}-{budgets['per_scene'] + 25}, "
        f"outro {budgets['outro'] - 10}-{budgets['outro'] + 15}, "
        f"total ~{budgets['total']} words."
    )


def _load_fewshot_snippets(channel_config: dict, *, max_chars: int = 1800) -> str:
    """Inject 1 hook + 1 midpoint scene from gold content_json exemplars."""
    from lib.config import PROJECT_ROOT

    niche = str(channel_config.get("niche_id", "")).lower()
    files: list[str] = []
    for key, names in FEWSHOT_EXEMPLARS.items():
        if key in niche:
            files = names
            break
    if not files:
        files = FEWSHOT_EXEMPLARS["business"]

    base = PROJECT_ROOT / "content_json"
    parts: list[str] = []
    for name in files:
        path = base / name
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        hook = data.get("hook") or {}
        hook_text = str(hook.get("text", ""))[:500]
        if hook_text:
            parts.append(f"EXEMPLAR HOOK ({name}):\n{hook_text}")
        # Midpoint-ish: first scene of act 2
        acts = data.get("acts") or []
        mid_scene = None
        for act in acts:
            if act.get("act_number") == 2 and act.get("scenes"):
                mid_scene = act["scenes"][0]
                break
        if mid_scene:
            narr = str(mid_scene.get("narration", ""))[:500]
            if narr:
                parts.append(f"EXEMPLAR ACT2 SCENE ({name}):\n{narr}")
        if parts:
            break

    blob = "\n\n".join(parts)
    if not blob:
        return ""
    return "\n\nQuality bar examples (match specificity & pacing, do NOT copy facts):\n" + blob[:max_chars]


def _prior_act_continuity(prior_act: dict | None) -> str:
    if not prior_act:
        return ""
    scenes = prior_act.get("scenes") or []
    if not scenes:
        return ""
    last = scenes[-1]
    narr = str(last.get("narration") or last.get("text") or "")[-400:]
    if not narr:
        return ""
    return (
        f"\nContinuity from previous act (do not restate; escalate from here):\n"
        f"...{narr}\n"
    )


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
    fewshot = _load_fewshot_snippets(channel_config)
    if fewshot:
        parts.append(fewshot)
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
    budgets = word_budgets(duration_minutes)
    return f"""Plan a {duration_minutes}-minute YouTube video about: "{topic}"

Design a STORY with addictive pacing — not a listicle. One narrative spine, rising stakes, a midpoint reversal in Act 2.
{_budget_hint(budgets)}

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
        {{"scene_id": "act1_scene1", "beat": "specific beat with names/dates/facts", "target_emotion": "curiosity", "target_words": {budgets['per_scene']}}},
        {{"scene_id": "act1_scene2", "beat": "...", "target_emotion": "tension", "target_words": {budgets['per_scene']}}},
        {{"scene_id": "act1_scene3", "beat": "...", "target_emotion": "dread", "target_words": {budgets['per_scene']}}}
      ]
    }},
    {{"act_number": 2, "act_title": "...", "scene_summaries": [3-4 items with act2_sceneN ids and target_words]}},
    {{"act_number": 3, "act_title": "...", "scene_summaries": [3-4 items with act3_sceneN ids and target_words]}}
  ]
}}"""


def _hook_prompt(topic: str, outline: dict, channel_config: dict, budgets: dict | None = None) -> str:
    emotions = ", ".join(_emotion_palette(channel_config))
    budgets = budgets or word_budgets(10)
    return f"""Write the hook for this video about "{topic}".

Title: {outline.get("title", topic)}
{_outline_context(outline)}
{_budget_hint(budgets)}

The hook must grab attention in the first 10 seconds with a SPECIFIC fact, moment, or paradox.
First 8 words MUST include a YEAR, a dollar amount ($), or a proper name.
Open one loop from open_loops that Act 3 will close. Target ~{budgets['hook']} spoken words.
Include [pause] only where a human would naturally pause.

Return ONLY JSON:
{{
  "scene_id": "hook",
  "text": "hook narration",
  "visual_prompt": "Close-up of a worn leather ledger on a mahogany desk, single desk lamp, rain on window — no text",
  "broll_prompt": "Hands flipping through stamped documents — no text",
  "duration_seconds": 45,
  "emotion": "one of: {emotions}",
  "narration_tone": "e.g. urgent whisper, cold precision, quiet dread",
  "opens_loop_ids": [0]
}}

visual_prompt MUST name concrete visible subjects from the topic (people, objects, places, metaphors). Never use generic placeholders."""


def _act_prompt(
    topic: str,
    act: dict,
    outline: dict,
    channel_config: dict,
    *,
    budgets: dict | None = None,
    prior_act: dict | None = None,
) -> str:
    summaries = json.dumps(act.get("scene_summaries", []), indent=2)
    act_num = act["act_number"]
    act_title = act.get("act_title", "")
    emotions = ", ".join(_emotion_palette(channel_config))
    budgets = budgets or word_budgets(10)
    midpoint_note = ""
    if act_num == 2:
        midpoint_note = (
            f"\nAct 2 MUST deliver this midpoint reversal in narration "
            f"(paraphrase, do not skip): {outline.get('midpoint_reversal', '')}\n"
            f"Mark the midpoint scene with \"is_midpoint\": true.\n"
        )
    if act_num == 3:
        midpoint_note = (
            f"\nAct 3 MUST explicitly answer each open loop: "
            f"{json.dumps(outline.get('open_loops', []))}\n"
            f"On the final content scene set \"closes_loop_ids\" to all open loop indexes.\n"
        )
    return f"""Write Act {act_num} scenes for: "{topic}"
Act title: {act_title}
{_outline_context(outline)}
{_budget_hint(budgets)}
{_prior_act_continuity(prior_act)}
{midpoint_note}
Expand beats into spoken narration. Each scene = one idea with a micro-cliffhanger or tension at the end (except final scene of Act 3).
Each scene narration ~{budgets['per_scene']} words (±25%). Match target_emotion from scene summaries.
Use concrete sensory details — not adjectives like "shocking" or "incredible".

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
      "narration_tone": "one-line delivery direction",
      "is_midpoint": false,
      "closes_loop_ids": []
    }}
  ]
}}

Each visual_prompt must describe ONE literal or symbolic frame tied to the topic — name real subjects, not generic 'cinematic scene'."""


def _outro_prompt(topic: str, outline: dict, channel_config: dict, budgets: dict | None = None) -> str:
    emotions = ", ".join(_emotion_palette(channel_config))
    budgets = budgets or word_budgets(10)
    return f"""Write the outro for this video about "{topic}".

Title: {outline.get("title", topic)}
{_outline_context(outline)}
{_budget_hint(budgets)}

Close the open loops. Land one insight the viewer takes away. No generic subscribe begging in the narration body.
Target ~{budgets['outro']} spoken words.

Return ONLY JSON:
{{
  "scene_id": "outro",
  "text": "outro narration",
  "visual_prompt": "Wide shot of empty office at dusk, city lights through blinds — no text",
  "duration_seconds": 30,
  "emotion": "one of: {emotions}",
  "narration_tone": "one-line delivery direction",
  "closes_loop_ids": [0]
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


def _visual_polish_chunk_prompt(chunk: dict, outline: dict, label: str) -> str:
    return f"""Polish visual prompts in this {label} JSON so they match narration and topic.

{_outline_context(outline)}

Tasks:
- Align each visual_prompt with its scene narration — name concrete subjects
- Replace generic placeholders with specific frames
- Keep all scene_id values unchanged
- Keep emotion and narration_tone on every scene

Return ONLY the same JSON structure for this {label}:

{json.dumps(chunk, indent=2)}"""


def _polish_chunk_prompt(chunk: dict, outline: dict, label: str) -> str:
    return f"""Polish this YouTube documentary {label} JSON for maximum retention and story clarity.

{_outline_context(outline)}

Tasks:
- Hook/openings must use a specific date, dollar amount, paradox, or decision — never a generic question
- Every scene ends with tension, an unanswered question, or a turn (except final outro)
- Act 2 must deliver the midpoint reversal with a concrete reveal
- Act 3 / outro must close every open loop from the hook
- Use vivid sensory details and named people/companies/dates — not vague summaries
- Remove AI clichés (Let's dive in, game-changer, mind-blowing, buckle up, here's what most people don't realize, etc.)
- Keep all scene_id values unchanged
- Keep emotion and narration_tone on every scene

Return ONLY the polished {label} JSON (same schema). Keep string values on one line.

{json.dumps(chunk, indent=2)}"""


def _merge_polished_hook(script: dict, polished: dict) -> None:
    if isinstance(polished, dict) and polished.get("text"):
        script["hook"] = {**script.get("hook", {}), **polished}


def _merge_polished_act(script: dict, act_number: int, polished: dict) -> None:
    if not isinstance(polished, dict):
        return
    for i, act in enumerate(script.get("acts", [])):
        if act.get("act_number") == act_number or i + 1 == act_number:
            if polished.get("scenes"):
                act["scenes"] = polished["scenes"]
            if polished.get("act_title"):
                act["act_title"] = polished["act_title"]
            return


def _merge_polished_outro(script: dict, polished: dict) -> None:
    if isinstance(polished, dict) and polished.get("text"):
        script["outro"] = {**script.get("outro", {}), **polished}


def _chunked_story_polish(script: dict, outline: dict, system_prompt: str) -> dict:
    """Polish hook/acts/outro separately so Act 3 is never truncated out of context."""
    try:
        polished_hook = _call_llm_json(
            system_prompt,
            _polish_chunk_prompt(script.get("hook", {}), outline, "hook"),
            max_tokens=2048,
            label="polish hook",
            temperature=0.3,
        )
        _merge_polished_hook(script, polished_hook)
    except Exception as e:
        _log(f"Hook polish skipped: {e}")

    for act in list(script.get("acts", [])):
        act_num = act.get("act_number", 0)
        try:
            polished_act = _call_llm_json(
                system_prompt,
                _polish_chunk_prompt(act, outline, f"act {act_num}"),
                max_tokens=4096,
                label=f"polish act {act_num}",
                temperature=0.3,
            )
            _merge_polished_act(script, act_num, polished_act)
        except Exception as e:
            _log(f"Act {act_num} polish skipped: {e}")

    try:
        polished_outro = _call_llm_json(
            system_prompt,
            _polish_chunk_prompt(script.get("outro", {}), outline, "outro"),
            max_tokens=1024,
            label="polish outro",
            temperature=0.3,
        )
        _merge_polished_outro(script, polished_outro)
    except Exception as e:
        _log(f"Outro polish skipped: {e}")

    script.setdefault("story_spine", outline.get("story_spine", ""))
    script.setdefault("stakes", outline.get("stakes", ""))
    script.setdefault("midpoint_reversal", outline.get("midpoint_reversal", ""))
    script.setdefault("open_loops", outline.get("open_loops", []))
    return script


def _chunked_visual_polish(script: dict, outline: dict, system_prompt: str, *, one_image: bool) -> dict:
    _ = one_image
    try:
        polished_hook = _call_llm_json(
            system_prompt,
            _visual_polish_chunk_prompt(script.get("hook", {}), outline, "hook"),
            max_tokens=1024,
            label="visual polish hook",
            temperature=0.3,
        )
        _merge_polished_hook(script, polished_hook)
    except Exception as e:
        _log(f"Hook visual polish skipped: {e}")

    for act in list(script.get("acts", [])):
        act_num = act.get("act_number", 0)
        try:
            polished_act = _call_llm_json(
                system_prompt,
                _visual_polish_chunk_prompt(act, outline, f"act {act_num}"),
                max_tokens=3072,
                label=f"visual polish act {act_num}",
                temperature=0.3,
            )
            _merge_polished_act(script, act_num, polished_act)
        except Exception as e:
            _log(f"Act {act_num} visual polish skipped: {e}")

    try:
        polished_outro = _call_llm_json(
            system_prompt,
            _visual_polish_chunk_prompt(script.get("outro", {}), outline, "outro"),
            max_tokens=1024,
            label="visual polish outro",
            temperature=0.3,
        )
        _merge_polished_outro(script, polished_outro)
    except Exception as e:
        _log(f"Outro visual polish skipped: {e}")
    return script


def _narration_inventory(script: dict) -> list[dict]:
    items: list[dict] = []
    hook = script.get("hook") or {}
    if hook.get("text"):
        items.append({
            "scene_id": hook.get("scene_id", "hook"),
            "kind": "hook",
            "text": hook.get("text", ""),
            "words": word_count(hook.get("text", "")),
        })
    for act in script.get("acts", []):
        for scene in act.get("scenes", []):
            narr = scene.get("narration") or scene.get("text") or ""
            items.append({
                "scene_id": scene.get("scene_id", ""),
                "kind": "scene",
                "act_number": act.get("act_number"),
                "text": narr,
                "words": word_count(narr),
                "is_midpoint": bool(scene.get("is_midpoint")),
            })
    outro = script.get("outro") or {}
    if outro.get("text"):
        items.append({
            "scene_id": outro.get("scene_id", "outro"),
            "kind": "outro",
            "text": outro.get("text", ""),
            "words": word_count(outro.get("text", "")),
        })
    return items


def _find_budget_offenders(script: dict, budgets: dict) -> list[dict]:
    offenders: list[dict] = []
    for item in _narration_inventory(script):
        if item["kind"] == "hook":
            lo, hi = budgets["hook"] * 0.75, budgets["hook"] * 1.25
        elif item["kind"] == "outro":
            lo, hi = budgets["outro"] * 0.75, budgets["outro"] * 1.3
        else:
            lo, hi = budgets["per_scene"] * 0.75, budgets["per_scene"] * 1.25
        words = item["words"]
        if words < lo or words > hi:
            offenders.append({**item, "target_lo": int(lo), "target_hi": int(hi)})
    return offenders


def _set_scene_narration(script: dict, scene_id: str, text: str) -> None:
    if scene_id == "hook" or (script.get("hook") or {}).get("scene_id") == scene_id:
        script["hook"]["text"] = text
        return
    if scene_id == "outro" or (script.get("outro") or {}).get("scene_id") == scene_id:
        script["outro"]["text"] = text
        return
    for act in script.get("acts", []):
        for scene in act.get("scenes", []):
            if scene.get("scene_id") == scene_id:
                scene["narration"] = text
                return


def _fix_word_budgets(
    script: dict,
    budgets: dict,
    channel_config: dict,
    *,
    max_fixes: int = 4,
) -> dict:
    offenders = _find_budget_offenders(script, budgets)[:max_fixes]
    for item in offenders:
        target = (item["target_lo"] + item["target_hi"]) // 2
        direction = "EXPAND" if item["words"] < item["target_lo"] else "TRIM"
        instruction = (
            f"{direction} this narration to about {target} spoken words "
            f"(currently {item['words']}). Keep facts, names, and open loops. "
            f"No AI clichés."
        )
        try:
            refined = refine_script_section(item["text"], instruction, channel_config)
            if refined and len(refined.split()) > 10:
                _set_scene_narration(script, item["scene_id"], refined)
                _log(f"Budget fix {item['scene_id']}: {item['words']} → {word_count(refined)}")
        except Exception as e:
            _log(f"Budget fix skipped for {item['scene_id']}: {e}")
    return script


def _critique_revise(
    script: dict,
    outline: dict,
    system_prompt: str,
    channel_config: dict,
) -> dict:
    inventory = [
        {
            "scene_id": i["scene_id"],
            "kind": i["kind"],
            "words": i["words"],
            "excerpt": i["text"][:280],
            "is_midpoint": i.get("is_midpoint", False),
        }
        for i in _narration_inventory(script)
    ]
    prompt = f"""Critique this documentary script for retention quality.

{_outline_context(outline)}

Scenes:
{json.dumps(inventory, indent=2)}

Return ONLY JSON:
{{
  "scores": {{
    "hook_strength": 1,
    "specificity": 1,
    "open_loop_closure": 1,
    "midpoint_delivered": 1,
    "cliche_hits": 0,
    "pacing": 1
  }},
  "must_fix": [
    {{"scene_id": "...", "issue": "...", "instruction": "precise rewrite instruction"}}
  ]
}}

Scores are 1-10 except cliche_hits 0-10. Flag at most 4 must_fix items for real problems only."""
    try:
        critique = _call_llm_json(
            system_prompt, prompt, max_tokens=2048, label="critique", temperature=0.2
        )
    except Exception as e:
        _log(f"Critique skipped: {e}")
        return script

    fixes = critique.get("must_fix") or []
    by_id = {i["scene_id"]: i["text"] for i in _narration_inventory(script)}
    for fix in fixes[:4]:
        sid = fix.get("scene_id")
        instruction = fix.get("instruction") or fix.get("issue") or ""
        if not sid or sid not in by_id or not instruction:
            continue
        try:
            refined = refine_script_section(by_id[sid], instruction, channel_config)
            if refined and len(refined.split()) > 10:
                _set_scene_narration(script, sid, refined)
                _log(f"Critique revise applied: {sid}")
        except Exception as e:
            _log(f"Critique revise skipped for {sid}: {e}")
    script["_critique_scores"] = critique.get("scores", {})
    return script


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


def _parse_humanization_rules(rules: list | None) -> dict:
    """Interpret YAML humanization_rules into pacing knobs."""
    cfg = {
        "pause_before_reveal": True,
        "breath_every_n": 5,
        "keep_slow_fast_emphasis": True,
    }
    if not rules:
        return cfg
    for rule in rules:
        text = str(rule).lower()
        if "pause" in text and ("before" in text or "turn" in text or "reveal" in text):
            cfg["pause_before_reveal"] = True
        if "breath" in text:
            m = re.search(r"every\s+(\d+)", text)
            if m:
                cfg["breath_every_n"] = max(3, min(10, int(m.group(1))))
            elif "4-5" in text or "4–5" in text:
                cfg["breath_every_n"] = 5
        if "slow" in text or "emphasis" in text or "fast" in text:
            cfg["keep_slow_fast_emphasis"] = True
    return cfg


def apply_humanization(text: str, rules: list | None = None) -> str:
    """Insert light [pause]/[breath] markers — TTS inserts timed silence for these."""
    if not text or not text.strip():
        return text

    cfg = _parse_humanization_rules(rules)
    if not cfg["keep_slow_fast_emphasis"]:
        text = re.sub(r"\[slow\]\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\[fast\]\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\[emphasis\]\s*", "", text, flags=re.IGNORECASE)

    text = re.sub(r"(\[pause\]\s*){2,}", "[pause] ", text, flags=re.IGNORECASE)
    text = re.sub(r"(\[breath\]\s*){2,}", "[breath] ", text, flags=re.IGNORECASE)

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
    breath_every = cfg["breath_every_n"]

    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue
        sentence_count += 1

        if cfg["pause_before_reveal"] and reveal_start.match(s) and "[pause]" not in s[:20].lower():
            s = reveal_start.sub(lambda m: f"[pause] {m.group(1)}", s, count=1)

        result.append(s)
        if sentence_count % breath_every == 0:
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
    # Short-form beats
    for beat in script.get("beats", []) or []:
        narration = beat.get("narration") or beat.get("text")
        if narration:
            beat["narration"] = apply_humanization(narration, rules)
    if isinstance(script.get("cta"), dict) and script["cta"].get("text"):
        script["cta"]["text"] = apply_humanization(script["cta"]["text"], rules)
    elif isinstance(script.get("cta"), str) and script.get("cta"):
        script["cta"] = apply_humanization(script["cta"], rules)
    return script


def clean_narration_for_tts(text: str) -> str:
    """Plain-text fallback for captions/preview. Audio synthesis uses parse_narration_spans."""
    text = re.sub(r"\[(pause|breath|slow|fast|emphasis)\]\s*", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\.{3,}", ".", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_cliches(text: str) -> list[str]:
    hits: list[str] = []
    lower = str(text or "").lower()
    for pattern in CLICHE_PATTERNS:
        if re.search(pattern, lower):
            hits.append(pattern)
    return hits


def hook_has_specificity_anchor(text: str) -> bool:
    """First ~8 words should contain year, $, or capitalized proper-ish token."""
    words = re.sub(r"\[(pause|breath|slow|fast|emphasis)\]", " ", str(text or ""), flags=re.I)
    words = words.split()[:8]
    head = " ".join(words)
    if re.search(r"\b(19|20)\d{2}\b", head):
        return True
    if "$" in head or re.search(r"\b\d+(\.\d+)?%\b", head):
        return True
    # Capitalized multi-letter token that isn't a sentence starter filler
    fillers = {"the", "a", "an", "in", "on", "at", "but", "and", "for", "when", "after"}
    for w in words:
        clean = re.sub(r"[^A-Za-z]", "", w)
        if len(clean) >= 2 and clean[0].isupper() and clean.lower() not in fillers:
            return True
    return False


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
    return _chunked_visual_polish(script, outline, system_prompt, one_image=one_image)


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
    Flow: outline → hook → acts → outro → chunked polish → critique → optional SFX.
    """
    _log(f"Generating script (chunked) for topic: {topic}")
    system_prompt = _build_system_prompt(channel_config, extra_instruction)
    budgets = word_budgets(duration_minutes)

    outline = _call_llm_json(
        system_prompt, _outline_prompt(topic, duration_minutes, channel_config),
        max_tokens=2048, label="outline", temperature=0.35,
    )
    _log("Outline complete")

    hook = _call_llm_json(
        system_prompt, _hook_prompt(topic, outline, channel_config, budgets),
        max_tokens=1024, label="hook", temperature=0.65,
    )
    _log("Hook complete")

    acts = []
    for act_plan in outline.get("acts", []):
        act_num = act_plan.get("act_number", len(acts) + 1)
        prior = acts[-1] if acts else None
        acts.append(_call_llm_json(
            system_prompt,
            _act_prompt(
                topic, act_plan, outline, channel_config,
                budgets=budgets, prior_act=prior,
            ),
            max_tokens=3072, label=f"act {act_num}", temperature=0.6,
        ))
        _log(f"Act {act_num} complete")

    outro = _call_llm_json(
        system_prompt, _outro_prompt(topic, outline, channel_config, budgets),
        max_tokens=1024, label="outro", temperature=0.55,
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
        "word_budget": budgets,
    }

    if channel_config.get("script", {}).get("script_polish", True):
        _log("Running chunked story polish")
        try:
            script = _chunked_story_polish(script, outline, system_prompt)
        except Exception as e:
            _log(f"Story polish skipped: {e}")

    one_image = image_layout == "one_image"
    _log("Running chunked visual polish")
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

    _log("Fixing word budgets")
    try:
        script = _fix_word_budgets(script, budgets, channel_config)
    except Exception as e:
        _log(f"Word budget fix skipped: {e}")

    if channel_config.get("script", {}).get("script_polish", True):
        _log("Running critique → revise")
        try:
            script = _critique_revise(script, outline, system_prompt, channel_config)
        except Exception as e:
            _log(f"Critique revise skipped: {e}")

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

"""
intent_translator.py — Natural-language to structured-constraint translator.

Uses NVIDIA NIM LLM to parse casual user feedback into structured constraints
that the pipeline can act on.

Intent types:
  - add_constraint     : user wants to filter/narrow results
  - reject_candidate   : user wants to exclude a specific drug
  - new_search         : user wants to analyze a new drug from scratch
  - clarification      : user is responding to a clarification question
  - general_question   : user is asking a follow-up question
  - ambiguous          : feedback is too vague — ask a clarifying question
"""

import aiohttp
import json
import os

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL   = "meta/llama-3.1-70b-instruct"


async def translate_intent(user_message, current_constraints=None,
                           current_results=None, rejected=None):
    """
    Parse a user message into a structured intent.

    Returns dict:
      {
        "intent_type": str,
        "new_constraints": dict,
        "rejected_candidates": [str],
        "clarification_needed": bool,
        "clarification_question": str or None,
        "response_message": str,
        "new_molecule": str or None  (if intent is new_search)
      }
    """
    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key or not api_key.startswith("nvapi-"):
        return _fallback_parse(user_message)

    constraints_ctx = json.dumps(current_constraints or {})
    rejected_ctx = json.dumps(rejected or [])

    # Build a summary of current results for context
    results_summary = ""
    if current_results and isinstance(current_results, dict):
        report = current_results.get("report", {})
        opps = report.get("repurposing_opportunities", [])
        if opps:
            results_summary = "Current candidates:\n" + "\n".join(
                f"  - {o.get('disease','?')}: {o.get('description','')[:80]}"
                for o in opps[:5]
            )

    prompt = f"""You are an intent parser for a drug repurposing research tool.

The user is in a conversation about drug repurposing results. They just said:

USER MESSAGE: "{user_message}"

CURRENT ACTIVE CONSTRAINTS: {constraints_ctx}
CURRENTLY REJECTED CANDIDATES: {rejected_ctx}
{results_summary}

Classify the user's intent and extract structured information.

Respond ONLY with a valid JSON object (no markdown, no extra text):

{{
  "intent_type": "add_constraint" | "reject_candidate" | "new_search" | "clarification" | "general_question" | "ambiguous",
  "new_constraints": {{}},
  "rejected_candidates": [],
  "clarification_needed": false,
  "clarification_question": null,
  "response_message": "A helpful response acknowledging what the user said and what action you're taking",
  "new_molecule": null
}}

Rules:
- "gentler on the heart" → intent_type: "add_constraint", new_constraints: {{"exclude_cardiovascular_toxicity": true}}, response_message: "Understood — excluding candidates with cardiovascular side effects..."
- "remove Metformin" / "not Metformin" → intent_type: "reject_candidate", rejected_candidates: ["Metformin"]
- "analyze Aspirin" / "try Aspirin" / "what about Aspirin" → intent_type: "new_search", new_molecule: "Aspirin"
- "must cross blood-brain barrier" → intent_type: "add_constraint", new_constraints: {{"require_bbb_crossing": true}}
- "what's the biggest risk?" → intent_type: "general_question"
- "something for sleep" (vague) → intent_type: "ambiguous", clarification_needed: true, clarification_question: "Do you mean insomnia, sleep apnea, or general sleep quality? These involve different pathways."
- "too expensive" → intent_type: "add_constraint", new_constraints: {{"exclude_high_manufacturing_cost": true}}
- Responses to previous clarification questions → intent_type: "clarification"
"""

    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": NVIDIA_MODEL,
                "max_tokens": 500,
                "temperature": 0.1,
                "messages": [{"role": "user", "content": prompt}]
            }
            async with session.post(
                NVIDIA_API_URL, headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = data["choices"][0]["message"]["content"].strip()
                    # Strip markdown fences if present
                    if "```" in text:
                        parts = text.split("```")
                        text = parts[1]
                        if text.startswith("json"):
                            text = text[4:]
                    result = json.loads(text.strip())
                    # Validate required fields
                    result.setdefault("intent_type", "general_question")
                    result.setdefault("new_constraints", {})
                    result.setdefault("rejected_candidates", [])
                    result.setdefault("clarification_needed", False)
                    result.setdefault("clarification_question", None)
                    result.setdefault("response_message", "Processing your request...")
                    result.setdefault("new_molecule", None)
                    return result
                else:
                    body = await resp.text()
                    print(f"[IntentTranslator] NVIDIA API error {resp.status}: {body[:200]}")
                    return _fallback_parse(user_message)

    except json.JSONDecodeError as e:
        print(f"[IntentTranslator] JSON parse error: {e}")
        return _fallback_parse(user_message)
    except Exception as e:
        print(f"[IntentTranslator] Error: {e}")
        return _fallback_parse(user_message)


def _fallback_parse(user_message):
    """
    Simple rule-based fallback when the LLM is unavailable.
    Handles the most common patterns.
    """
    msg = user_message.lower().strip()

    search_prefixes = [
        "analyze ", "analyse ", "try ", "search ", "check ",
        "evaluate ", "investigate ", "run pipeline for "
    ]
    for prefix in search_prefixes:
        if msg.startswith(prefix):
            molecule = user_message[len(prefix):].strip().title()
            return {
                "intent_type": "new_search",
                "new_constraints": {},
                "rejected_candidates": [],
                "clarification_needed": False,
                "clarification_question": None,
                "response_message": f"Starting analysis for {molecule}...",
                "new_molecule": molecule,
            }

    # Check for rejection
    reject_keywords = ["remove ", "exclude ", "not ", "reject ", "drop "]
    for kw in reject_keywords:
        if msg.startswith(kw):
            candidate = user_message[len(kw):].strip().title()
            return {
                "intent_type": "reject_candidate",
                "new_constraints": {},
                "rejected_candidates": [candidate],
                "clarification_needed": False,
                "clarification_question": None,
                "response_message": f"Excluding {candidate} from results.",
                "new_molecule": None,
            }

    # Check for constraint keywords
    constraint_map = {
        "heart": {"exclude_cardiovascular_toxicity": True},
        "cardio": {"exclude_cardiovascular_toxicity": True},
        "brain": {"require_bbb_crossing": True},
        "blood-brain": {"require_bbb_crossing": True},
        "bbb": {"require_bbb_crossing": True},
        "cheap": {"prefer_low_cost": True},
        "expensive": {"exclude_high_manufacturing_cost": True},
        "safe": {"prioritize_safety": True},
        "toxic": {"exclude_high_toxicity": True},
        "oral": {"prefer_oral_administration": True},
        "generic": {"prefer_generic_available": True},
        "patent": {"prefer_patent_free": True},
    }

    found_constraints = {}
    for keyword, constraint in constraint_map.items():
        if keyword in msg:
            found_constraints.update(constraint)

    if found_constraints:
        return {
            "intent_type": "add_constraint",
            "new_constraints": found_constraints,
            "rejected_candidates": [],
            "clarification_needed": False,
            "clarification_question": None,
            "response_message": f"Applied constraints: {', '.join(found_constraints.keys())}. Refining results...",
            "new_molecule": None,
        }

    # Default: treat as a general question
    return {
        "intent_type": "general_question",
        "new_constraints": {},
        "rejected_candidates": [],
        "clarification_needed": False,
        "clarification_question": None,
        "response_message": "Let me look into that for you...",
        "new_molecule": None,
    }

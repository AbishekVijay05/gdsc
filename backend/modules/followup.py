import aiohttp, json, os

# ── NVIDIA NIM API ─────────────────────────────────────────────────────────
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL   = "meta/llama-3.1-70b-instruct"

LANG_INSTRUCTIONS = {
    "en": "Respond in English.",
    "ta": "Respond in Tamil. Keep drug names, NCT numbers and technical terms in English.",
    "hi": "Respond in Hindi. Keep drug names, NCT numbers and technical terms in English.",
    "te": "Respond in Telugu. Keep drug names, NCT numbers and technical terms in English.",
    "fr": "Respond in French.",
    "es": "Respond in Spanish.",
    "de": "Respond in German.",
    "zh": "Respond in Simplified Chinese.",
    "ar": "Respond in Arabic.",
    "pt": "Respond in Portuguese.",
}


async def answer_followup(question: str, report_context: dict, language: str = "en") -> str:
    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key or not api_key.startswith("nvapi-"):
        return "NVIDIA API key not configured. Set NVIDIA_API_KEY in backend/app.py."

    molecule   = report_context.get("molecule", "the drug")
    report     = report_context.get("report", {})
    mechanism  = report_context.get("mechanism", {})
    lang_instr = LANG_INSTRUCTIONS.get(language, LANG_INSTRUCTIONS["en"])

    system_prompt = f"""You are a pharmaceutical research assistant.
The user is asking a follow-up question about a drug repurposing report for {molecule}.
{lang_instr}

Full report context:
{json.dumps(report, indent=2)[:2000]}

Biological mechanism data:
Molecular formula: {mechanism.get('molecular_formula', 'Unknown')}
Mechanism of action: {(mechanism.get('mechanism_of_action') or mechanism.get('pharmacology') or 'Unknown')[:300]}
Biological targets: {', '.join(mechanism.get('biological_targets', [])[:5])}

Answer concisely and specifically based on this data.
If the answer is not in the data, say so honestly.
Keep answers under 200 words. Be direct and cite specific data points."""

    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": NVIDIA_MODEL,
                "max_tokens": 400,
                "temperature": 0.3,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": question}
                ]
            }
            async with session.post(
                NVIDIA_API_URL, headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    return f"Could not get answer (NVIDIA API error {resp.status})."
    except Exception as e:
        return f"Error: {str(e)}"

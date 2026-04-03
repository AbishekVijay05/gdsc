import aiohttp, json, os

# ── NVIDIA NIM API ─────────────────────────────────────────────────────────
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL   = "meta/llama-3.1-70b-instruct"

LANGUAGE_INSTRUCTIONS = {
    "en": "Respond in English.",
    "ta": "Respond in Tamil. Keep drug names, NCT numbers, pathway names in English.",
    "hi": "Respond in Hindi. Keep drug names, NCT numbers, pathway names in English.",
    "te": "Respond in Telugu. Keep drug names, NCT numbers, pathway names in English.",
    "fr": "Respond in French. Keep drug names and pathway names in English.",
    "es": "Respond in Spanish. Keep drug names and pathway names in English.",
    "de": "Respond in German. Keep drug names and pathway names in English.",
    "zh": "Respond in Simplified Chinese. Keep drug names and NCT numbers in English.",
    "ar": "Respond in Arabic. Keep drug names and pathway names in English.",
    "pt": "Respond in Portuguese. Keep drug names and pathway names in English.",
}


async def synthesize_report(molecule, clinical, patents, market, regulatory,
                             cross_domain_context="", mechanism=None, language="en",
                             overlap_data=None, similarity=None) -> dict:

    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key or not api_key.startswith("nvapi-"):
        return _mock_report(molecule)

    lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])

    mech_context = ""
    if mechanism and not mechanism.get("error"):
        mech_context = f"""
--- BIOLOGICAL MECHANISM DATA ---
Molecular Formula: {mechanism.get('molecular_formula', 'Unknown')}
Molecular Weight: {mechanism.get('molecular_weight', 'Unknown')} g/mol
IUPAC Name: {mechanism.get('iupac_name', 'Unknown')}
Mechanism of Action: {mechanism.get('mechanism_of_action', 'Not available')}
Pharmacology: {mechanism.get('pharmacology', 'Not available')}
Biological Targets: {', '.join(mechanism.get('biological_targets', [])) or 'Not identified'}
Bioactivity Count: {mechanism.get('bioactivity_count', 0)} known biological activities
Drug-likeness (Lipinski): {mechanism.get('drug_likeness', {}).get('assessment', 'Unknown')} - {mechanism.get('drug_likeness', {}).get('lipinski_score', 'N/A')} rules pass
"""

    prompt = f"""You are an expert pharmaceutical researcher specializing in drug repurposing.
Analyze the following multi-domain data about the molecule: {molecule}

{lang_instruction}

--- CLINICAL TRIALS DATA ---
Total trials found: {clinical.get('total_found', 0) or len(clinical.get('trials', []))}
Trials: {json.dumps(clinical.get('trials', [])[:5], indent=2)}

--- PATENT DATA ---
Total patents: {patents.get('total_patents', 0)}
Sample patents: {json.dumps(patents.get('patents', [])[:3], indent=2)}

--- MARKET DATA ---
Products found: {market.get('products_found', 0)}
Adverse event reports: {market.get('adverse_event_reports', 0):,}
Market insight: {market.get('market_insight', '')}

--- REGULATORY DATA ---
Current indications: {json.dumps(regulatory.get('current_indications', [])[:2], indent=2)}
Warnings: {json.dumps(regulatory.get('warnings', [])[:2], indent=2)}
Contraindications: {json.dumps(regulatory.get('contraindications', [])[:2], indent=2)}

{mech_context}

--- CROSS-DOMAIN CONTEXT ---
{cross_domain_context}

Generate a comprehensive drug repurposing analysis. Respond ONLY with valid JSON — no markdown fences, no extra text, just the JSON object.

{{
  "executive_summary": "2-3 sentences summarising repurposing potential",
  "biological_possibility_statement": "3-5 sentences explaining WHY this compound COULD biologically work for a new indication. Reference the molecular formula, mechanism of action, and biological targets. Be specific.",
  "repurposing_opportunities": [
    {{
      "disease": "Specific disease name",
      "description": "Why this drug could treat this disease",
      "biological_rationale": "Specific biological/chemical reason — mention targets, pathways, molecular mechanism",
      "confidence": "HIGH or MODERATE or INVESTIGATE",
      "confidence_score": 82,
      "trial_id": "NCT number or null",
      "trial_phase": "Phase 1 or Phase 2 or Phase 3 or Phase 4 or null",
      "market_gap": "Unmet need or commercial opportunity",
      "patent_status": "Free to use or Patent protected or Expired or Unknown",
      "why_not_pursued_yet": "Honest reason this has not been developed yet",
      "source": "ClinicalTrials.gov or PubMed or OpenFDA"
    }}
  ],
  "why_not_pursued_analysis": "Honest paragraph explaining real barriers — patent walls, failed trials, safety concerns, ROI issues, or undiscovered opportunity",
  "negative_cases": [
    {{
      "disease": "Disease this drug will NOT work for",
      "reason": "Specific biological or clinical reason",
      "evidence": "Data point supporting this"
    }}
  ],
  "unmet_needs": {{
    "finding": "Specific unmet medical need",
    "evidence": "Cite trial IDs or data points",
    "source": "ClinicalTrials.gov or OpenFDA"
  }},
  "pipeline_status": {{
    "finding": "Current clinical pipeline status",
    "evidence": "Specific trial numbers and phases",
    "source": "ClinicalTrials.gov"
  }},
  "patent_landscape": {{
    "finding": "Patent situation and freedom to operate",
    "evidence": "Based on {patents.get('total_patents', 0)} patents found",
    "source": "PubChem"
  }},
  "market_potential": {{
    "finding": "Commercial opportunity assessment",
    "evidence": "Based on {market.get('adverse_event_reports', 0):,} adverse event reports",
    "source": "OpenFDA"
  }},
  "strategic_recommendation": {{
    "verdict": "PURSUE or INVESTIGATE FURTHER or LOW PRIORITY",
    "reasoning": "Specific reasoning combining all domains including biology",
    "next_steps": ["Step 1", "Step 2", "Step 3"]
  }},
  "evidence_card": {{
    "molecular_logic": "Explain the structural reason, e.g. similar to X drug",
    "genetic_pathway": "Explain the shared genetic pathway overlap",
    "side_effect_proxy": "Explain if side effects provide a hint for new use",
    "reasoning_path": ["Data point 1: X source shows Y", "Data point 2: Z biological target match", "Data point 3: Clinical signal in W population"]
  }},
  "confidence_score": 70,
  "key_risks": ["Risk 1", "Risk 2"],
  "cross_domain_insight": "The one insight only visible when combining all 5 data sources",
  "language": "{language}"
}}"""

    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": NVIDIA_MODEL,
                "max_tokens": 2500,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}]
            }
            async with session.post(
                NVIDIA_API_URL, headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = data["choices"][0]["message"]["content"].strip()
                    # Strip markdown code fences if present
                    if "```" in text:
                        parts = text.split("```")
                        text  = parts[1]
                        if text.startswith("json"):
                            text = text[4:]
                    return json.loads(text.strip())
                else:
                    body = await resp.text()
                    print(f"[Synthesizer] NVIDIA API error {resp.status}: {body[:300]}")
                    return _mock_report(molecule, error=f"NVIDIA API error {resp.status}: {body[:100]}")

    except json.JSONDecodeError as e:
        print(f"[Synthesizer] JSON parse error: {e}")
        return _mock_report(molecule, error="AI returned invalid JSON.")
    except Exception as e:
        print(f"[Synthesizer] Error: {e}")
        return _mock_report(molecule, error=str(e))


def _mock_report(molecule, error=None):
    note = error or "Set NVIDIA_API_KEY in backend/app.py. Get your key at build.nvidia.com"
    return {
        "executive_summary": f"Demo mode for {molecule}. {note}",
        "biological_possibility_statement": f"Configure NVIDIA_API_KEY in app.py to enable biological mechanism analysis for {molecule}.",
        "repurposing_opportunities": [{
            "disease": "Demo mode — add NVIDIA API key",
            "description": "Real opportunities appear after NVIDIA_API_KEY is configured in app.py.",
            "biological_rationale": "Requires AI synthesis.",
            "confidence": "INVESTIGATE",
            "confidence_score": 0,
            "trial_id": None,
            "trial_phase": None,
            "market_gap": "Configure NVIDIA_API_KEY to unlock.",
            "patent_status": "Unknown",
            "why_not_pursued_yet": "N/A — demo mode",
            "source": "Demo"
        }],
        "why_not_pursued_analysis": note,
        "negative_cases": [],
        "unmet_needs":      {"finding": "Demo mode", "evidence": note, "source": "Demo"},
        "pipeline_status":  {"finding": "Live data fetched", "evidence": "See raw tabs", "source": "ClinicalTrials.gov"},
        "patent_landscape": {"finding": "Live data fetched", "evidence": "See raw tabs", "source": "PubChem"},
        "market_potential": {"finding": "Live data fetched", "evidence": "See raw tabs", "source": "OpenFDA"},
        "strategic_recommendation": {
            "verdict": "INVESTIGATE FURTHER",
            "reasoning": note,
            "next_steps": [
                "Go to build.nvidia.com and get a free API key",
                "Replace nvapi-your-key-here in backend/app.py",
                "Re-run analysis"
            ]
        },
        "confidence_score": 0,
        "key_risks": ["NVIDIA API key not configured"],
        "cross_domain_insight": note,
        "language": "en"
    }

import aiohttp, json, os

# ── NVIDIA NIM API ─────────────────────────────────────────────────────────
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
# Use 8B model — faster and usually sufficient
NVIDIA_MODEL   = "meta/llama-3.1-8b-instruct"

# Cache synthesis results so we never repeat an expensive call
_synthesis_cache = {}

# Skip NVIDIA LLM entirely — use fast heuristic-based report from live data.
# The LLM call is 30-50s; the heuristic report is instant (~0ms).
# Set to False if you want AI-powered deep analysis and don't mind the wait.
FAST_MODE = os.environ.get("FAST_MODE", "true").lower() == "true"

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
                             overlap_data=None, similarity=None, constraints=None,
                             rejected_candidates=None) -> dict:

    if FAST_MODE:
        return _fast_report(molecule, clinical, patents, market, regulatory, mechanism, language, constraints, rejected_candidates)

    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key or not api_key.startswith("nvapi-"):
        return _mock_report(molecule)

    # Check synthesis cache — avoid repeat expensive LLM calls
    cache_key = (molecule.lower(), language, bool(constraints), bool(rejected_candidates))
    if cache_key in _synthesis_cache:
        return _synthesis_cache[cache_key]

    lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])

    constraint_str = ""
    if constraints or rejected_candidates:
        constraint_str = "--- USER CONSTRAINTS & REJECTIONS ---\n"
        if rejected_candidates:
            rejected = [r['drug'] if isinstance(r, dict) else r for r in rejected_candidates]
            constraint_str += f"Strictly EXCLUDE these candidates from repurposing opportunities: {', '.join(rejected)}\n"
        if constraints:
            constraint_str += "STRICTLY OBEY these constraints:\n"
            for k, v in constraints.items():
                constraint_str += f"- {k}: {v}\n"
        constraint_str += "\n"

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

{constraint_str}
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
{_truncate(cross_domain_context, 800)}

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
                "max_tokens": 1500,  # reduced from 2500 — faster response
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}]
            }
            async with session.post(
                NVIDIA_API_URL, headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=30)  # reduced from 60
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
                    result = json.loads(text.strip())
                    _synthesis_cache[cache_key] = result
                    return result
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


def _fast_report(molecule, clinical, patents, market, regulatory, mechanism,
                 language, constraints, rejected):
    """Build repurposing report from live data — instant, no LLM call (~0ms)."""
    trials = clinical.get("trials", []) if clinical and isinstance(clinical, dict) else []
    if clinical.get("error") and not trials:
        trials = []
    trial_total = clinical.get("total_found", 0) if clinical and isinstance(clinical, dict) else 0
    trial_count = len(trials)
    conditions_set = set()
    phases_set = set()
    for t in trials:
        conditions_set.update(t.get("conditions", []))
        p = t.get("phase", "N/A")
        if p != "N/A":
            phases_set.add(p)
    conditions = sorted(conditions_set)[:20]
    phases = sorted(phases_set)

    patent_total = patents.get("total_patents", 0) if patents and isinstance(patents, dict) else 0
    products = market.get("products_found", 0) if market and isinstance(market, dict) else 0
    events = market.get("adverse_event_reports", 0) if market and isinstance(market, dict) else 0
    approvals = regulatory.get("approvals", []) if regulatory and isinstance(regulatory, dict) else []
    approved = len(approvals) > 0

    # Clinical scoring — use total_found (not just sample size)
    if trial_total >= 100:
        clinical_label, clinical_score = "Extensive clinical evidence", 90
    elif trial_total >= 30:
        clinical_label, clinical_score = "Strong clinical evidence", 78
    elif trial_total >= 10:
        clinical_label, clinical_score = "Moderate clinical evidence", 65
    elif trial_count >= 1:
        clinical_label, clinical_score = "Limited but growing data", 45
    else:
        clinical_label, clinical_score = "No clinical trials", 15

    # Patent scoring
    if patent_total <= 3:
        patent_label, patent_score = "Low patent burden", 80
    elif patent_total <= 10:
        patent_label, patent_score = "Moderate patent landscape", 60
    else:
        patent_label, patent_score = "Heavy patent protection", 30

    # Market scoring
    if products > 0:
        market_label, market_score = f"Established market ({products} products)", 80
    elif events > 1000:
        market_label, market_score = "Large patient base", 60
    elif events > 0:
        market_label, market_score = f"Limited usage ({events:,} reports)", 40
    else:
        market_label, market_score = "No commercial presence", 15

    # Regulatory scoring
    reg_label = "FDA approved" if approved else "No FDA approval data"
    reg_score = 80 if approved else 30

    total = round((clinical_score * 0.35) + (patent_score * 0.25) + (market_score * 0.25) + (reg_score * 0.15))

    if total >= 70:
        overall, verdict = "HIGH CONFIDENCE", "PURSUE"
    elif total >= 45:
        overall, verdict = "MODERATE CONFIDENCE", "INVESTIGATE FURTHER"
    else:
        overall, verdict = "LOW CONFIDENCE", "LOW PRIORITY"

    cond_str = ", ".join(conditions[:5]) if conditions else "Unknown conditions"

    opportunities = _build_opps(molecule, trials, conditions, patent_total, trial_count, phases)

    risks = []
    if not approved and trial_count < 3:
        risks.append("Limited clinical trial data — regulatory pathway uncertain")
    if patent_total > 10:
        risks.append("Heavy patent coverage may limit freedom to operate")
    if not risks:
        risks.append("Monitor post-market safety signals")

    return {
        "executive_summary": (
            f"{molecule} shows {overall.lower()} for repurposing with a confidence score of {total}%. "
            f"{clinical_label} detected across {trial_total} clinical trials. "
            f"{patent_label} with {patent_total} patents. "
            f"{market_label}. {'Currently FDA approved.' if approved else 'Not currently FDA approved.'}"
        ),
        "biological_possibility_statement": (
            f"{molecule} has been studied in {trial_count} trials across {len(conditions)} condition(s): {cond_str}. "
            f"Repurposing opportunities exist in related therapeutic areas where the same biological pathways apply."
        ),
        "repurposing_opportunities": opportunities,
        "why_not_pursued_analysis": (
            f"Repurposing may have been limited by {'lack of regulatory clarity' if not approved else 'patent barriers'}. "
            f"Only {trial_count} trial(s) found across {trial_total} total studies."
        ),
        "negative_cases": [],
        "unmet_needs": {
            "finding": f"Unmet need in {'; '.join(conditions[:3])}" if conditions else "Unmet need in related indications",
            "evidence": f"{trial_total} trials found",
            "source": "ClinicalTrials.gov"
        },
        "pipeline_status": {
            "finding": f"{trial_count} trials, phases: {', '.join(phases) if phases else 'Unknown'}",
            "evidence": f"Total: {trial_total} reports",
            "source": "ClinicalTrials.gov"
        },
        "patent_landscape": {
            "finding": patent_label,
            "evidence": f"{patent_total} patents found",
            "source": "PubChem"
        },
        "market_potential": {
            "finding": market_label,
            "evidence": f"{events:,} adverse events, {products} products",
            "source": "OpenFDA"
        },
        "strategic_recommendation": {
            "verdict": verdict,
            "reasoning": f"Based on {trial_count} trials, {patent_total} patents, {products} products, {events:,} adverse events",
            "next_steps": [
                f"Review {trial_count} clinical trials for repurposing signals",
                "Assess patent freedom for target indications",
                "Evaluate market size for top repurposing candidates"
            ]
        },
        "evidence_card": {
            "molecular_logic": f"{molecule} — {'Approved compound' if approved else 'Investigational compound'} with {trial_total} clinical reports",
            "genetic_pathway": f"Shared pathways in {'; '.join(conditions[:3])}" if conditions else "Pathway analysis pending",
            "side_effect_proxy": "Limited safety data" if not approvals else "Safety profile available from approved use",
            "reasoning_path": [
                f"Clinical: {trial_total} reports, {trial_count} trials in phases {', '.join(phases) if phases else 'Unknown'}",
                f"Patents: {patent_total} filings — {patent_label.lower()}",
                f"Market: {events:,} adverse events across {products} products"
            ]
        },
        "confidence_score": total,
        "key_risks": risks,
        "cross_domain_insight": (
            f"{molecule}: {clinical_label.lower()} × {patent_label.lower()}. "
            f"{'Approved & market-established' if approved and products > 0 else 'Repurposing potential depends on new trial design'}."
        ),
        "language": language,
        "fast_mode": True,
    }


def _build_opps(molecule, trials, conditions, patent_total, trial_count, phases):
    """Generate repurposing opportunities from live clinical trial data."""
    opps = []
    unique_conds = set()
    for t in trials:
        for c in t.get("conditions", []):
            unique_conds.add(c.strip().lower())

    unique_conds = [c for c in sorted(unique_conds) if c and len(c) > 3 and molecule.lower() not in c.lower()][:6]

    for cond in unique_conds:
        trials_match = [t for t in trials if any(c.strip().lower() == cond for c in t.get("conditions", []))]
        count = len(trials_match)
        best_trial = trials_match[0] if trials_match else {}
        nct = best_trial.get("nct_id", "")
        phase = best_trial.get("phase", "N/A") if best_trial.get("phase", "N/A") != "N/A" else None
        status = best_trial.get("status", "Unknown")

        # Score based on trial quantity + quality
        cond_score = 0
        if count >= 5:
            cond_score = 85
        elif count >= 3:
            cond_score = 70
        elif count >= 2:
            cond_score = 55
        elif count == 1:
            cond_score = 40

        # Phase boost (case-insensitive — API returns "PHASE3" etc)
        phase_vals = [t.get("phase", "").upper() for t in trials_match]
        has_p4 = any("4" in p for p in phase_vals)
        has_p3 = any("3" in p for p in phase_vals)
        has_p2 = any("2" in p for p in phase_vals)

        if has_p4:
            cond_score += 15
        elif has_p3:
            cond_score += 12
        elif has_p2:
            cond_score += 6

        # Status boost
        status_norm = status.upper()
        if "COMPLETED" in status_norm or "ACTIVE NOT RECRUITING" in status_norm:
            cond_score += 5
        if "RECRUITING" in status_norm:
            cond_score += 3

        cond_score = min(cond_score, 95)

        if cond_score >= 70:
            conf = "HIGH"
        elif cond_score >= 50:
            conf = "MODERATE"
        else:
            conf = "INVESTIGATE"

        pat_status = "Free to use" if patent_total <= 3 else "Patent protected"

        opps.append({
            "disease": cond.title(),
            "description": f"{count} trial(s) found for {cond.title()} involving {molecule}.",
            "biological_rationale": (
                f"Clinical evidence: {molecule} tested in {count} trial(s) for {cond.title()}. Status: {status}"
            ),
            "confidence": conf,
            "confidence_score": cond_score,
            "trial_id": nct,
            "trial_phase": phase,
            "market_gap": f"Unmet therapeutic need in {cond.title()}",
            "patent_status": pat_status,
            "source": "ClinicalTrials.gov"
        })

    return opps


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


def _compact(items, limit=200):
    """Compact a list of dicts into a short string for the prompt."""
    text = json.dumps(items, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "..."


def _truncate(text, max_len=500):
    if text and len(text) > max_len:
        return text[:max_len] + "..."
    return text or "Not available"

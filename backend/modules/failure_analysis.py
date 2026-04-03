"""
failure_analysis.py — Answers the critical question judges ask:
"Why hasn't this repurposing opportunity already been pursued?"
"""

def analyze_failure_factors(molecule, clinical, patents, market, regulatory, report) -> dict:
    """
    Analyzes why a repurposing opportunity may NOT have been pursued.
    Returns barriers, risks, and a viability assessment.
    """

    barriers      = []
    risks         = []
    opportunities = []
    verdict       = "UNKNOWN"
    score         = 50

    trials        = clinical.get("trials", [])
    total_trials  = clinical.get("total_found", 0) or len(trials)
    warnings      = regulatory.get("warnings", [])
    contra        = regulatory.get("contraindications", [])
    total_patents  = patents.get("total_patents", 0)
    adverse_events = market.get("adverse_event_reports", 0)
    products       = market.get("products_found", 0)

    # ── Check for failed trials ───────────────────────────────────────────
    terminated = [t for t in trials if "terminated" in t.get("status","").lower()]
    withdrawn  = [t for t in trials if "withdrawn"  in t.get("status","").lower()]

    if terminated:
        barriers.append({
            "type":        "FAILED_TRIALS",
            "severity":    "HIGH",
            "description": f"{len(terminated)} trial(s) were terminated early — possible safety or efficacy signal",
            "trials":      [t.get("nct_id") for t in terminated[:3]]
        })
        score -= 20

    if withdrawn:
        barriers.append({
            "type":        "WITHDRAWN_TRIALS",
            "severity":    "MEDIUM",
            "description": f"{len(withdrawn)} trial(s) were withdrawn before completion",
            "trials":      [t.get("nct_id") for t in withdrawn[:3]]
        })
        score -= 10

    # ── Check for toxicity / safety warnings ─────────────────────────────
    black_box = [w for w in warnings if "black box" in str(w).lower() or "boxed" in str(w).lower()]
    if black_box:
        barriers.append({
            "type":        "BLACK_BOX_WARNING",
            "severity":    "CRITICAL",
            "description": "FDA black box warning exists — highest level of safety concern",
            "detail":      str(black_box[0])[:200] if black_box else ""
        })
        score -= 30

    if warnings and not black_box:
        risks.append({
            "type":        "SAFETY_WARNINGS",
            "severity":    "MEDIUM",
            "description": f"{len(warnings)} FDA warning(s) on label — requires careful monitoring",
        })
        score -= 10

    if contra:
        risks.append({
            "type":        "CONTRAINDICATIONS",
            "severity":    "MEDIUM",
            "description": f"{len(contra)} contraindication(s) limit patient population for repurposing"
        })
        score -= 5

    # ── Check patent barriers ─────────────────────────────────────────────
    if total_patents > 10:
        barriers.append({
            "type":        "PATENT_WALL",
            "severity":    "HIGH",
            "description": f"{total_patents} patents found — heavy IP protection may block commercialisation",
        })
        score -= 15

    elif total_patents > 5:
        risks.append({
            "type":        "PATENT_RISK",
            "severity":    "MEDIUM",
            "description": f"{total_patents} patents — licensing may be required for new indication"
        })
        score -= 7

    # ── Check market ROI signals ──────────────────────────────────────────
    if adverse_events < 1000 and products < 3:
        barriers.append({
            "type":        "LOW_MARKET_SIGNAL",
            "severity":    "MEDIUM",
            "description": "Low market usage suggests limited commercial validation or orphan disease context"
        })
        score -= 8

    # ── Check for orphan disease / rare condition opportunity ─────────────
    conditions = clinical.get("conditions_found", [])
    rare_keywords = ["rare", "orphan", "paediatric", "pediatric", "neonatal", "congenital"]
    rare_conditions = [c for c in conditions if any(k in c.lower() for k in rare_keywords)]
    if rare_conditions:
        opportunities.append({
            "type":        "RARE_DISEASE_OPPORTUNITY",
            "description": f"Rare/paediatric conditions found: {', '.join(rare_conditions[:3])}",
            "benefit":     "Orphan drug designation possible — faster approval + 7 years market exclusivity"
        })
        score += 10

    # ── Check pipeline gap ────────────────────────────────────────────────
    phase3_trials = [t for t in trials if "phase 3" in t.get("phase","").lower() or "phase3" in t.get("phase","").lower()]
    phase2_trials = [t for t in trials if "phase 2" in t.get("phase","").lower()]
    recruiting    = [t for t in trials if "recruiting" in t.get("status","").lower()]

    if phase3_trials:
        opportunities.append({
            "type":        "LATE_STAGE_EVIDENCE",
            "description": f"{len(phase3_trials)} Phase 3 trial(s) found — strong clinical evidence",
            "benefit":     "Late-stage evidence significantly reduces development risk"
        })
        score += 15

    if recruiting:
        opportunities.append({
            "type":        "ACTIVE_RESEARCH",
            "description": f"{len(recruiting)} actively recruiting trial(s) — live research ongoing",
            "benefit":     "Active clinical interest confirms viable research pathway"
        })
        score += 10

    # ── Why it might NOT have been pursued ────────────────────────────────
    why_not_pursued = []

    if total_patents > 8:
        why_not_pursued.append("Heavy patent protection makes commercialisation difficult without licensing")
    if terminated:
        why_not_pursued.append("Previous trials were terminated — prior failure may have discouraged further investment")
    if black_box:
        why_not_pursued.append("Black box safety warning raises risk threshold for new indication trials")
    if adverse_events > 500000:
        why_not_pursued.append("Already widely used — limited commercial incentive for new indication investment")
    if not why_not_pursued and total_trials < 3:
        why_not_pursued.append("Limited awareness — opportunity may be genuinely undiscovered")
    if not why_not_pursued:
        why_not_pursued.append("No clear barrier identified — this may be a genuine open opportunity")

    # ── Final verdict ─────────────────────────────────────────────────────
    score = max(0, min(100, score))
    if score >= 70:
        verdict = "VIABLE"
    elif score >= 45:
        verdict = "PROCEED WITH CAUTION"
    else:
        verdict = "HIGH BARRIERS"

    return {
        "viability_score":    score,
        "verdict":            verdict,
        "barriers":           barriers,
        "risks":              risks,
        "opportunities":      opportunities,
        "why_not_pursued":    why_not_pursued,
        "total_barriers":     len(barriers),
        "total_risks":        len(risks),
        "has_critical_barrier": any(b["severity"] == "CRITICAL" for b in barriers)
    }

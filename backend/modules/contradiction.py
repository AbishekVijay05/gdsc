"""
Contradiction detection engine.
Finds conflicts between what different domains say.
E.g. clinical says PURSUE but regulatory says HIGH RISK.
"""

def detect_contradictions(clinical, patents, market, regulatory, report):
    flags = []

    trials     = clinical.get("trials", [])
    n_trials   = clinical.get("total_found", 0) or len(trials)
    events     = market.get("adverse_event_reports", 0)
    approvals  = regulatory.get("approvals", [])
    warnings   = regulatory.get("warnings", [])
    contra     = regulatory.get("contraindications", [])
    n_patents  = patents.get("total_patents", 0)
    verdict    = (report.get("strategic_recommendation") or {}).get("verdict", "")

    # 1. Strong clinical evidence but no market presence
    late = [t for t in trials if any(p in (t.get("phase") or "")
            for p in ["3","4","PHASE3","PHASE4","PHASE_3","PHASE_4"])]
    if len(late) >= 2 and events < 500:
        flags.append({
            "type":    "CLINICAL vs MARKET",
            "level":   "warning",
            "message": f"{len(late)} late-phase trials exist but only {events:,} adverse event reports — strong science, weak commercialisation.",
            "domains": ["Clinical", "Market"]
        })

    # 2. High market usage but no active trials
    active = [t for t in trials if "RECRUIT" in (t.get("status") or "").upper()]
    if events > 10000 and len(active) == 0:
        flags.append({
            "type":    "MARKET vs CLINICAL",
            "level":   "info",
            "message": f"High market usage ({events:,} reports) but no recruiting trials — repurposing opportunity may be underexplored.",
            "domains": ["Market", "Clinical"]
        })

    # 3. Regulatory warnings exist but verdict says PURSUE
    if warnings and "PURSUE" in verdict.upper():
        flags.append({
            "type":    "REGULATORY vs STRATEGY",
            "level":   "danger",
            "message": "AI recommends PURSUE but FDA label contains safety warnings — regulatory pathway needs careful review.",
            "domains": ["Regulatory", "Strategy"]
        })

    # 4. No trials but high market — possible hidden opportunity
    if n_trials == 0 and events > 1000:
        flags.append({
            "type":    "PIPELINE GAP",
            "level":   "info",
            "message": f"High market usage ({events:,} reports) with zero clinical trials — this molecule may have untapped repurposing potential.",
            "domains": ["Clinical", "Market"]
        })

    # 5. Many patents but verdict says pursue freely
    if n_patents >= 8 and "PURSUE" in verdict.upper():
        flags.append({
            "type":    "PATENT vs STRATEGY",
            "level":   "warning",
            "message": f"{n_patents} patents found — freedom to operate must be verified before pursuing commercialisation.",
            "domains": ["Patents", "Strategy"]
        })

    # 6. Regulatory approval exists but no late phase trials
    if approvals and len(late) == 0 and n_trials > 0:
        flags.append({
            "type":    "REGULATORY vs CLINICAL",
            "level":   "info",
            "message": "Drug is FDA-approved but all trials are early-phase — repurposing into new indications is still early stage.",
            "domains": ["Regulatory", "Clinical"]
        })

    return flags

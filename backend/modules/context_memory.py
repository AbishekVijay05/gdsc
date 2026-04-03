"""
Context continuity layer.
After clinical runs, extracts key conditions and signals.
Passes them to market + regulatory for targeted follow-up.
This is what the problem statement calls 'context continuity'.
"""

def extract_clinical_context(clinical):
    """Extract key signals from clinical data to share with other agents."""
    trials  = clinical.get("trials", [])
    context = {
        "conditions_found": [],
        "phases_found":     [],
        "sponsors_found":   [],
        "has_recruiting":   False,
        "has_late_phase":   False,
        "signal_summary":   ""
    }

    all_conditions = []
    for t in trials:
        conds = t.get("conditions", [])
        all_conditions.extend(conds)
        phase = t.get("phase", "")
        if phase:
            context["phases_found"].append(phase)
        sponsor = t.get("sponsor", "")
        if sponsor:
            context["sponsors_found"].append(sponsor)
        if "RECRUIT" in (t.get("status") or "").upper():
            context["has_recruiting"] = True
        if any(p in (phase or "") for p in ["3","4","PHASE3","PHASE4"]):
            context["has_late_phase"] = True

    # Deduplicate and take top 5 conditions
    seen = set()
    for c in all_conditions:
        if c and c.lower() not in seen:
            seen.add(c.lower())
            context["conditions_found"].append(c)
    context["conditions_found"] = context["conditions_found"][:5]

    # Build a plain-English summary for the synthesizer
    if context["conditions_found"]:
        context["signal_summary"] = (
            f"Clinical agents found {len(trials)} trials targeting: "
            f"{', '.join(context['conditions_found'][:3])}. "
            f"{'Active recruiting trials exist. ' if context['has_recruiting'] else ''}"
            f"{'Late-phase (Phase 3/4) trials found — strong clinical evidence.' if context['has_late_phase'] else ''}"
        )
    else:
        context["signal_summary"] = f"Clinical agents found {len(trials)} trials but no specific conditions identified."

    return context


def enrich_market_query(molecule, clinical_context):
    """Return enriched search terms for market module based on clinical findings."""
    conditions = clinical_context.get("conditions_found", [])
    if conditions:
        return f"{molecule} " + " ".join(conditions[:2])
    return molecule


def build_synthesis_context(molecule, clinical, patents, market, regulatory, pubmed, clinical_ctx):
    """
    Build a rich context string that weaves all domain findings together.
    This is passed to the AI synthesizer so it reasons across all domains.
    """
    return f"""
MOLECULE: {molecule}

CLINICAL CONTEXT (from clinical agent):
{clinical_ctx.get('signal_summary', 'No clinical context')}
Conditions being investigated: {', '.join(clinical_ctx.get('conditions_found', [])) or 'None found'}
Has recruiting trials: {clinical_ctx.get('has_recruiting', False)}
Has late-phase trials: {clinical_ctx.get('has_late_phase', False)}

CROSS-DOMAIN SIGNALS:
- Clinical trials found: {clinical.get('total_found', 0) or len(clinical.get('trials', []))}
- Patents found: {patents.get('total_patents', 0)}
- Market products: {market.get('products_found', 0)}
- Adverse event reports (usage proxy): {market.get('adverse_event_reports', 0):,}
- FDA approvals: {len(regulatory.get('approvals', []))}
- PubMed papers on repurposing: {pubmed.get('total_found', 0)}

CONTEXT CONTINUITY NOTE:
The clinical agent found these conditions: {', '.join(clinical_ctx.get('conditions_found', [])) or 'none'}.
The market and regulatory agents were queried with this context in mind.
Cross-domain insight should specifically address whether these conditions
represent commercially viable and regulatorily feasible repurposing targets.
"""

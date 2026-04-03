"""
scorer.py — Confidence Score 2.0
Multi-dimensional: Biological + Clinical + Literature + Safety + Novelty
"""

def compute_confidence(clinical, patents, market, regulatory,
                       mechanism=None, target_overlap=None, pubmed=None) -> dict:
    scores = {}
    explanations = {}

    # 1. BIOLOGICAL SCORE (max 25)
    bio = 0
    bio_exp = []
    if target_overlap:
        sc = target_overlap.get("signal_count", 0)
        hs = target_overlap.get("has_strong_signal", False)
        pw = target_overlap.get("pathways", [])
        tg = target_overlap.get("molecular_targets", [])
        if hs:   bio += 12; bio_exp.append("Strong pathway-disease overlap confirmed")
        elif sc: bio += 6;  bio_exp.append("Moderate pathway overlap detected")
        if len(pw)>=3: bio+=6; bio_exp.append(f"{len(pw)} biological pathways identified")
        elif pw:       bio+=3; bio_exp.append(f"{len(pw)} pathway identified")
        if len(tg)>=3: bio+=5; bio_exp.append(f"{len(tg)} molecular targets mapped")
        elif tg:       bio+=2; bio_exp.append(f"{len(tg)} molecular target identified")
        if sc>=5:      bio+=2; bio_exp.append(f"{sc} disease signals detected")
    elif mechanism and not mechanism.get("error"):
        bc = mechanism.get("bioactivity_count",0)
        if bc:   bio+=8; bio_exp.append(f"{bc} bioactivities in PubChem")
        dl = mechanism.get("drug_likeness",{})
        if dl.get("lipinski_passes",0)>=3: bio+=5; bio_exp.append("Passes Lipinski rules")
        bt = mechanism.get("biological_targets",[])
        if bt:   bio+=5; bio_exp.append(f"{len(bt)} targets identified")
        if mechanism.get("mechanism_of_action"): bio+=5; bio_exp.append("Mechanism of action documented")
    scores["biological"] = min(bio, 25)
    explanations["biological"] = bio_exp or ["Biological data being retrieved"]

    # 2. CLINICAL SCORE (max 30)
    clin = 0
    clin_exp = []
    trials = clinical.get("trials",[])
    total  = clinical.get("total_found",0) or len(trials)
    if total>0:  clin+=8; clin_exp.append(f"{total} clinical trials found")
    if total>=5: clin+=5; clin_exp.append("Substantial trial pipeline")
    if total>=10:clin+=4; clin_exp.append("Extensive trial base")
    rec = [t for t in trials if "recruiting" in t.get("status","").lower()]
    if rec: clin+=6; clin_exp.append(f"{len(rec)} actively recruiting")
    p3 = [t for t in trials if "phase 3" in t.get("phase","").lower()]
    p2 = [t for t in trials if "phase 2" in t.get("phase","").lower()]
    if p3:      clin+=7; clin_exp.append(f"{len(p3)} Phase 3 trials — strong evidence")
    elif p2:    clin+=4; clin_exp.append(f"{len(p2)} Phase 2 trials — promising signal")
    scores["clinical"] = min(clin, 30)
    explanations["clinical"] = clin_exp or ["No trials found"]

    # 3. LITERATURE SCORE (max 15)
    lit = 0
    lit_exp = []
    if pubmed:
        pc = pubmed.get("total_found",0) or len(pubmed.get("papers",[]))
        rp = sum(1 for p in pubmed.get("papers",[])
                 if any(kw in (p.get("title","")+p.get("abstract","")).lower()
                        for kw in ["repurpos","off-label","new indication","novel use"]))
        if pc>0:  lit+=5; lit_exp.append(f"{pc} published papers")
        if pc>=5: lit+=3; lit_exp.append("Strong literature base")
        if rp>0:  lit+=5; lit_exp.append(f"{rp} repurposing-specific papers")
        if pc>=10:lit+=2; lit_exp.append("Extensive coverage")
    scores["literature"] = min(lit, 15)
    explanations["literature"] = lit_exp or ["Limited published literature"]

    # 4. SAFETY SCORE (max 15) — start full, deduct for risks
    safe = 15
    safe_exp = []
    warnings = regulatory.get("warnings",[])
    contra   = regulatory.get("contraindications",[])
    approvals= regulatory.get("approvals",[])
    term     = [t for t in trials if "terminated" in t.get("status","").lower()]
    if approvals: safe_exp.append("FDA approved — established safety")
    else: safe-=3; safe_exp.append("No FDA approvals found")
    bb = [w for w in warnings if "black box" in str(w).lower() or "boxed" in str(w).lower()]
    if bb:       safe-=8; safe_exp.append("BLACK BOX WARNING — critical concern")
    elif warnings:safe-=3; safe_exp.append(f"{len(warnings)} FDA warnings on label")
    if contra:   safe-=2; safe_exp.append(f"{len(contra)} contraindications")
    if term:     safe-=3; safe_exp.append(f"{len(term)} terminated trials")
    scores["safety"] = max(0, min(safe, 15))
    explanations["safety"] = safe_exp or ["No major safety signals"]

    # 5. NOVELTY SCORE (max 15)
    nov = 0
    nov_exp = []
    total_p = patents.get("total_patents",0)
    if 0 < total <= 2:  nov+=8; nov_exp.append("Very few trials — highly unexplored")
    elif total <= 5:    nov+=5; nov_exp.append("Limited trials — significant gap")
    elif total <= 10:   nov+=3; nov_exp.append("Moderate trial activity")
    if total_p==0:      nov+=5; nov_exp.append("No patents — free to commercialise")
    elif total_p<=3:    nov+=3; nov_exp.append("Few patents — manageable IP")
    adv = market.get("adverse_event_reports",0)
    if adv>10000:       nov+=2; nov_exp.append("High real-world usage confirms viability")
    scores["novelty"] = min(nov, 15)
    explanations["novelty"] = nov_exp or ["Standard novelty level"]

    total_score = sum(scores.values())
    label = ("HIGH CONFIDENCE" if total_score>=75 else
             "MODERATE CONFIDENCE" if total_score>=50 else
             "LOW CONFIDENCE" if total_score>=25 else "INSUFFICIENT DATA")

    dominant = max(scores, key=scores.get)
    explanation = (
        f"Score: {total_score}/100 — driven by "
        f"{'strong' if scores[dominant]>15 else 'moderate'} {dominant} signal"
        f"{' + pathway overlap' if scores.get('biological',0)>=10 else ''}"
        f"{' + active trials' if scores.get('clinical',0)>=15 else ''}. "
        f"Scoring modelled on patterns from known repurposed drugs (Sildenafil, Metformin, Aspirin)."
    )

    return {
        "total": total_score,
        "label": label,
        "score_explanation": explanation,
        "breakdown": {
            "biological": scores["biological"],
            "clinical":   scores["clinical"],
            "literature": scores["literature"],
            "safety":     scores["safety"],
            "novelty":    scores["novelty"],
            "patents":    min(scores["novelty"]+5, 25),
            "market":     min(scores.get("safety",0)+5, 25),
            "regulatory": min(scores["safety"], 15),
        },
        "dimension_scores":       scores,
        "dimension_explanations": explanations,
    }

"""
overlap_engine.py
Core intelligence: Drug targets ∩ Disease pathways = biological signal
This is the mechanism layer that separates hypothesis from aggregation.
"""
import aiohttp
import json

# Known disease-pathway mappings (expanded knowledge base)
DISEASE_PATHWAYS = {
    "cancer": ["mTOR","AMPK","PI3K","MAPK","p53","VEGF","CDK","BCL2","NF-kB","Wnt","Hedgehog","JAK-STAT"],
    "diabetes": ["AMPK","insulin signaling","gluconeogenesis","GLUT4","IRS1","mTOR","PPAR-gamma","GLP-1"],
    "alzheimer": ["amyloid","tau","neuroinflammation","acetylcholine","BDNF","NF-kB","oxidative stress"],
    "parkinson": ["dopamine","alpha-synuclein","mitochondrial","neuroinflammation","PINK1","Parkin"],
    "heart failure": ["renin-angiotensin","beta-adrenergic","calcium signaling","RAAS","NF-kB","fibrosis"],
    "hypertension": ["renin-angiotensin","RAAS","calcium channel","nitric oxide","sympathetic nervous"],
    "inflammation": ["NF-kB","COX","prostaglandin","cytokine","TNF-alpha","IL-6","JAK-STAT"],
    "arthritis": ["NF-kB","COX","prostaglandin","TNF-alpha","IL-1","IL-6","synovial"],
    "depression": ["serotonin","dopamine","norepinephrine","BDNF","HPA axis","neuroplasticity"],
    "anxiety": ["GABA","serotonin","HPA axis","norepinephrine","benzodiazepine"],
    "infection": ["bacterial","viral","immune","toll-like receptor","NF-kB","interferon"],
    "hiv": ["viral replication","protease","reverse transcriptase","integrase","CD4","immune"],
    "malaria": ["hemoglobin","erythrocyte","plasmodium","heme","folate"],
    "tuberculosis": ["mycobacterium","cell wall","RNA polymerase","oxidative stress"],
    "obesity": ["leptin","ghrelin","AMPK","adiponectin","lipogenesis","insulin","mTOR"],
    "liver disease": ["hepatocyte","fibrosis","oxidative stress","NF-kB","TGF-beta","lipid metabolism"],
    "kidney disease": ["fibrosis","RAAS","oxidative stress","TGF-beta","inflammation","proteinuria"],
    "lung disease": ["inflammation","fibrosis","bronchodilation","oxidative stress","mucus"],
    "asthma": ["bronchodilation","inflammation","eosinophil","IL-4","IL-5","IgE","mast cell"],
    "copd": ["inflammation","oxidative stress","protease","NF-kB","mucus","bronchodilation"],
    "autoimmune": ["immune","T-cell","B-cell","cytokine","TNF","JAK-STAT","NF-kB"],
    "multiple sclerosis": ["myelin","neuroinflammation","T-cell","cytokine","demyelination"],
    "lupus": ["immune","DNA","autoantibody","complement","NF-kB","interferon"],
    "fibrosis": ["TGF-beta","collagen","fibroblast","oxidative stress","inflammation"],
    "stroke": ["ischemia","oxidative stress","neuroinflammation","glutamate","NMDA","neuroprotection"],
    "osteoporosis": ["osteoclast","RANK","calcium","vitamin D","bone remodeling"],
    "pain": ["COX","prostaglandin","opioid","sodium channel","substance P","TRPV1"],
    "nausea": ["serotonin 5-HT3","dopamine D2","histamine","substance P","NK1"],
    "glaucoma": ["intraocular pressure","aqueous humor","trabecular","neuroprotection"],
    "erectile dysfunction": ["PDE5","nitric oxide","cGMP","smooth muscle","vasodilation"],
    "pulmonary hypertension": ["PDE5","endothelin","prostacyclin","nitric oxide","vascular remodeling"],
    "premature labour": ["prostaglandin","oxytocin","uterine contraction","calcium"],
    "patent ductus arteriosus": ["prostaglandin","PGE2","ductus arteriosus","vascular smooth muscle"],
    "neonatal": ["prostaglandin","immature organ","thermoregulation"],
    "colorectal cancer": ["COX-2","prostaglandin","NF-kB","Wnt","KRAS","p53","apoptosis"],
    "breast cancer": ["estrogen","HER2","PI3K","mTOR","CDK4/6","VEGF","apoptosis"],
    "prostate cancer": ["androgen","PSA","PI3K","mTOR","VEGF","apoptosis"],
    "leukemia": ["BCR-ABL","JAK-STAT","tyrosine kinase","apoptosis","cell cycle"],
    "lymphoma": ["B-cell","NF-kB","BCL2","CD20","apoptosis","PI3K"],
    "melanoma": ["BRAF","MEK","ERK","MAPK","PD-1","immune checkpoint","apoptosis"],
}

# Drug mechanism keywords → pathway associations
DRUG_MECHANISM_KEYWORDS = {
    "prostaglandin": ["COX","prostaglandin","inflammation","pain","fever"],
    "cox": ["COX","prostaglandin","inflammation","pain"],
    "ampk": ["AMPK","energy sensing","metabolism","mTOR"],
    "pde5": ["PDE5","cGMP","nitric oxide","vasodilation"],
    "serotonin": ["serotonin","5-HT","depression","nausea","anxiety"],
    "dopamine": ["dopamine","D2","parkinson","depression","psychosis"],
    "calcium": ["calcium channel","contraction","hypertension","arrhythmia"],
    "beta": ["beta-adrenergic","heart rate","hypertension","anxiety"],
    "ace": ["renin-angiotensin","RAAS","hypertension","heart"],
    "nmda": ["glutamate","NMDA","neuroprotection","stroke","pain"],
    "gaba": ["GABA","anxiety","epilepsy","sedation"],
    "tnf": ["TNF-alpha","inflammation","autoimmune","NF-kB"],
    "il-6": ["IL-6","cytokine","inflammation","autoimmune"],
    "vegf": ["VEGF","angiogenesis","cancer","neovascularization"],
    "mtor": ["mTOR","cancer","diabetes","aging","PI3K"],
    "nf-kb": ["NF-kB","inflammation","cancer","immune"],
    "insulin": ["insulin signaling","diabetes","glucose","GLUT4"],
    "androgen": ["androgen","testosterone","prostate","sex hormone"],
    "estrogen": ["estrogen","breast cancer","osteoporosis","hormone"],
    "opioid": ["opioid","pain","addiction","mu receptor"],
    "antibiotic": ["bacterial","cell wall","protein synthesis","DNA gyrase"],
    "antiviral": ["viral","replication","protease","nucleoside"],
    "antifungal": ["fungal","ergosterol","cell membrane","lanosterol"],
    "immunosuppressant": ["immune","T-cell","transplant","calcineurin"],
    "anticoagulant": ["coagulation","thrombin","factor xa","platelet"],
    "statin": ["HMG-CoA","cholesterol","cardiovascular","LDL"],
    "diuretic": ["sodium","kidney","fluid","electrolyte","renin"],
    "nitric oxide": ["nitric oxide","cGMP","vasodilation","endothelium"],
    "thalidomide": ["TNF-alpha","angiogenesis","immune","inflammation","teratogen"],
}

def extract_drug_pathways(mechanism_text: str, biological_targets: list) -> list:
    """Extract pathway associations from mechanism text and targets."""
    pathways = set()
    
    combined = (mechanism_text or "").lower()
    for target in (biological_targets or []):
        combined += " " + target.lower()
    
    for keyword, associated_pathways in DRUG_MECHANISM_KEYWORDS.items():
        if keyword in combined:
            pathways.update(associated_pathways)
    
    # Also extract targets directly
    for target in (biological_targets or []):
        t_lower = target.lower()
        for pathway, disease_pathways in DISEASE_PATHWAYS.items():
            for dp in disease_pathways:
                if dp.lower() in t_lower or t_lower in dp.lower():
                    pathways.add(dp)
    
    return list(pathways)

def compute_overlap(drug_pathways: list, disease_pathways: list) -> dict:
    """Compute overlap between drug pathways and disease pathways."""
    if not drug_pathways or not disease_pathways:
        return {"overlap": [], "score": 0, "strength": "NONE"}
    
    drug_set    = set(p.lower() for p in drug_pathways)
    disease_set = set(p.lower() for p in disease_pathways)
    overlap     = drug_set.intersection(disease_set)
    
    score = min(100, len(overlap) * 18 + (10 if overlap else 0))
    
    strength = "STRONG" if len(overlap) >= 3 else "MODERATE" if len(overlap) >= 1 else "WEAK"
    
    return {
        "overlap": list(overlap),
        "overlap_count": len(overlap),
        "score": score,
        "strength": strength
    }

def find_disease_pathways(disease_query: str) -> list:
    """Find pathways associated with a disease."""
    query_lower = disease_query.lower()
    matched = []
    
    for disease, pathways in DISEASE_PATHWAYS.items():
        if disease in query_lower or query_lower in disease:
            matched.extend(pathways)
    
    # Also do partial matching
    for disease, pathways in DISEASE_PATHWAYS.items():
        for word in query_lower.split():
            if len(word) > 3 and word in disease and pathways not in matched:
                matched.extend(pathways)
    
    return list(set(matched))

async def run_overlap_engine(molecule: str, mechanism: dict, clinical: dict, regulatory: dict) -> dict:
    """
    Main overlap engine — computes biological plausibility for each 
    potential repurposing target based on pathway intersection.
    """
    result = {
        "drug_pathways": [],
        "disease_overlaps": {},
        "top_biological_candidates": [],
        "overlap_summary": ""
    }
    
    if not mechanism or mechanism.get("error"):
        return result
    
    # Extract drug pathways from mechanism data
    drug_pathways = extract_drug_pathways(
        (mechanism.get("mechanism_of_action") or "") + " " + (mechanism.get("pharmacology") or ""),
        mechanism.get("biological_targets", [])
    )
    result["drug_pathways"] = drug_pathways
    
    # Get diseases from clinical trials
    conditions = set()
    for trial in (clinical.get("trials", [])[:10]):
        for cond in (trial.get("conditions", [])):
            conditions.add(cond.lower())
    
    # Also add from regulatory
    for ind in (regulatory.get("current_indications", [])[:3]):
        conditions.add(str(ind).lower())
    
    # Compute overlap for each discovered disease
    overlaps = {}
    for condition in list(conditions)[:15]:
        disease_pathways = find_disease_pathways(condition)
        if disease_pathways:
            overlap = compute_overlap(drug_pathways, disease_pathways)
            if overlap["overlap_count"] > 0:
                overlaps[condition] = {
                    "disease_pathways": disease_pathways[:8],
                    **overlap
                }
    
    result["disease_overlaps"] = overlaps
    
    # Find top biological candidates (not in current indications)
    current_inds = [str(i).lower() for i in regulatory.get("current_indications", [])]
    candidates   = []
    
    for disease, data in overlaps.items():
        is_current = any(ci in disease or disease in ci for ci in current_inds)
        if not is_current and data["score"] > 20:
            candidates.append({
                "disease":  disease,
                "overlap":  data["overlap"],
                "score":    data["score"],
                "strength": data["strength"]
            })
    
    candidates.sort(key=lambda x: x["score"], reverse=True)
    result["top_biological_candidates"] = candidates[:5]
    
    if candidates:
        top = candidates[0]
        result["overlap_summary"] = (
            f"Strongest biological signal: {molecule} targets {', '.join(top['overlap'][:3])} "
            f"which overlap with {top['disease']} pathways ({top['strength']} match, score {top['score']}/100)"
        )
    
    return result

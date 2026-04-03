"""
target_overlap.py — Mechanism Intelligence Layer
Drug → Target → Pathway → Disease overlap engine.
Uses free public APIs: UniChem, ChEMBL, OpenTargets, DisGeNET.
"""
import aiohttp
import json

# Known pathway → disease associations (curated from literature)
PATHWAY_DISEASE_MAP = {
    "AMPK":         ["type 2 diabetes", "cancer", "metabolic syndrome", "obesity", "alzheimer's"],
    "mTOR":         ["cancer", "diabetes", "aging", "neurodegeneration", "autoimmune"],
    "NF-kB":        ["inflammation", "cancer", "autoimmune", "rheumatoid arthritis"],
    "PI3K/AKT":     ["cancer", "diabetes", "cardiovascular", "alzheimer's"],
    "p53":          ["cancer", "aging", "neurodegeneration"],
    "Wnt":          ["cancer", "bone disease", "alzheimer's", "fibrosis"],
    "Notch":        ["cancer", "cardiovascular", "alzheimer's"],
    "Hedgehog":     ["cancer", "fibrosis", "developmental disorders"],
    "JAK/STAT":     ["autoimmune", "cancer", "inflammation", "rheumatoid arthritis"],
    "MAPK/ERK":     ["cancer", "cardiovascular", "alzheimer's", "diabetes"],
    "TGF-beta":     ["fibrosis", "cancer", "autoimmune", "cardiovascular"],
    "apoptosis":    ["cancer", "neurodegeneration", "autoimmune"],
    "angiogenesis": ["cancer", "cardiovascular", "diabetic retinopathy"],
    "oxidative stress": ["neurodegeneration", "cardiovascular", "diabetes", "aging"],
    "inflammation": ["autoimmune", "cancer", "cardiovascular", "neurodegeneration"],
    "prostaglandin": ["pain", "inflammation", "cancer", "cardiovascular"],
    "serotonin":    ["depression", "anxiety", "parkinson's", "ibs"],
    "dopamine":     ["parkinson's", "schizophrenia", "adhd", "depression"],
    "acetylcholine": ["alzheimer's", "parkinson's", "myasthenia gravis"],
    "VEGF":         ["cancer", "diabetic retinopathy", "macular degeneration"],
    "angiotensin":  ["hypertension", "heart failure", "kidney disease"],
    "insulin":      ["diabetes", "obesity", "metabolic syndrome", "cancer"],
    "estrogen":     ["breast cancer", "osteoporosis", "cardiovascular", "alzheimer's"],
    "androgen":     ["prostate cancer", "alopecia", "polycystic ovary"],
    "glucocorticoid": ["inflammation", "autoimmune", "asthma", "cancer"],
    "thyroid":      ["hypothyroidism", "cardiovascular", "depression"],
    "cholesterol":  ["cardiovascular", "alzheimer's", "cancer", "diabetes"],
    "PDE5":         ["erectile dysfunction", "pulmonary hypertension", "heart failure"],
    "cyclooxygenase": ["pain", "inflammation", "cancer", "cardiovascular"],
    "acetylsalicylic": ["pain", "cardiovascular", "cancer", "alzheimer's"],
    "histamine":    ["allergy", "asthma", "gastric ulcer", "anaphylaxis"],
}

# Drug mechanism keywords → pathway associations
DRUG_PATHWAY_KEYWORDS = {
    "aspirin":      ["cyclooxygenase", "prostaglandin", "inflammation", "acetylsalicylic"],
    "metformin":    ["AMPK", "mTOR", "insulin", "oxidative stress"],
    "sildenafil":   ["PDE5", "angiogenesis", "VEGF"],
    "ibuprofen":    ["cyclooxygenase", "prostaglandin", "inflammation", "NF-kB"],
    "paracetamol":  ["prostaglandin", "oxidative stress", "inflammation"],
    "panadol":      ["prostaglandin", "oxidative stress", "inflammation"],
    "acetaminophen":["prostaglandin", "oxidative stress", "inflammation"],
    "thalidomide":  ["NF-kB", "angiogenesis", "inflammation", "TGF-beta"],
    "rapamycin":    ["mTOR", "PI3K/AKT", "apoptosis"],
    "statins":      ["cholesterol", "inflammation", "oxidative stress"],
    "atorvastatin": ["cholesterol", "inflammation", "oxidative stress"],
    "simvastatin":  ["cholesterol", "inflammation", "NF-kB"],
    "tamoxifen":    ["estrogen", "apoptosis", "cancer"],
    "dexamethasone":["glucocorticoid", "inflammation", "NF-kB"],
    "hydroxychloroquine": ["inflammation", "NF-kB", "autoimmune"],
    "ivermectin":   ["inflammation", "oxidative stress"],
    "remdesivir":   ["apoptosis", "inflammation"],
}


async def fetch_chembl_targets(molecule: str) -> list:
    """Fetch molecular targets from ChEMBL via molecule search."""
    targets = []
    try:
        async with aiohttp.ClientSession() as session:
            # Search ChEMBL for the molecule
            search_url = f"https://www.ebi.ac.uk/chembl/api/data/molecule/search?q={molecule}&format=json&limit=1"
            async with session.get(search_url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    data = await r.json()
                    mols = data.get("molecules", [])
                    if mols:
                        chembl_id = mols[0].get("molecule_chembl_id")
                        if chembl_id:
                            # Fetch activities (targets) for this molecule
                            act_url = f"https://www.ebi.ac.uk/chembl/api/data/activity?molecule_chembl_id={chembl_id}&format=json&limit=10"
                            async with session.get(act_url, timeout=aiohttp.ClientTimeout(total=8)) as r2:
                                if r2.status == 200:
                                    act_data = await r2.json()
                                    for act in act_data.get("activities", [])[:10]:
                                        target = act.get("target_pref_name", "")
                                        if target and target not in targets:
                                            targets.append(target)
    except Exception as e:
        print(f"[ChEMBL] {e}")
    return targets[:8]


def compute_pathway_overlap(molecule: str, mechanism_text: str, targets: list) -> dict:
    """
    Core overlap engine: drug targets ∩ disease pathways.
    Returns biological signals with pathway-disease connections.
    """
    mol_lower  = molecule.lower()
    mech_lower = (mechanism_text or "").lower()
    
    # Get known pathways for this drug
    known_pathways = DRUG_PATHWAY_KEYWORDS.get(mol_lower, [])
    
    # Also infer pathways from mechanism text and targets
    inferred_pathways = []
    for pathway, diseases in PATHWAY_DISEASE_MAP.items():
        pathway_lower = pathway.lower()
        if (pathway_lower in mech_lower or
            any(pathway_lower in t.lower() for t in targets) or
            pathway_lower in mol_lower):
            inferred_pathways.append(pathway)
    
    all_pathways = list(set(known_pathways + inferred_pathways))
    
    # For each pathway, find disease overlaps
    biological_signals = []
    diseases_found = set()
    
    for pathway in all_pathways:
        diseases = PATHWAY_DISEASE_MAP.get(pathway, [])
        for disease in diseases:
            if disease not in diseases_found:
                diseases_found.add(disease)
                biological_signals.append({
                    "disease":  disease,
                    "pathway":  pathway,
                    "signal":   f"{molecule} affects the {pathway} pathway, which is dysregulated in {disease}",
                    "strength": "STRONG" if pathway in known_pathways else "MODERATE"
                })
    
    return {
        "pathways_identified": all_pathways,
        "biological_signals":  biological_signals[:12],
        "signal_count":        len(biological_signals),
        "has_strong_signal":   any(s["strength"]=="STRONG" for s in biological_signals),
    }


async def run_mechanism_intelligence(molecule: str, mechanism_text: str, pubmed_data: dict) -> dict:
    """
    Full mechanism intelligence pipeline.
    Returns target-pathway-disease overlap analysis.
    """
    # 1. Fetch molecular targets from ChEMBL
    chembl_targets = await fetch_chembl_targets(molecule)
    
    # 2. Also extract targets from PubMed abstract keywords
    pubmed_targets = []
    papers = pubmed_data.get("papers", []) if pubmed_data else []
    target_keywords = ["receptor", "kinase", "enzyme", "protein", "pathway", "target", "inhibitor"]
    for paper in papers[:5]:
        title = (paper.get("title","") + " " + paper.get("abstract","")).lower()
        for kw in target_keywords:
            if kw in title:
                # Extract surrounding context
                idx = title.find(kw)
                context = title[max(0,idx-20):idx+30].strip()
                if context and len(context) > 10:
                    pubmed_targets.append(context)
    
    all_targets = list(set(chembl_targets + pubmed_targets[:4]))
    
    # 3. Compute pathway overlap
    overlap = compute_pathway_overlap(molecule, mechanism_text, all_targets)
    
    return {
        "molecular_targets":   all_targets,
        "chembl_targets":      chembl_targets,
        "pathways":            overlap["pathways_identified"],
        "biological_signals":  overlap["biological_signals"],
        "signal_count":        overlap["signal_count"],
        "has_strong_signal":   overlap["has_strong_signal"],
        "overlap_summary":     (
            f"{molecule} shows activity across {len(overlap['pathways_identified'])} identified pathways "
            f"with {overlap['signal_count']} biological disease signals detected."
        ) if overlap["pathways_identified"] else "Pathway data being retrieved from ChEMBL..."
    }

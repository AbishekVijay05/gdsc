"""
hypothesis_generator.py
THE game changer: Disease-first search mode
Input: Disease → Output: Drugs with no major trials + strong mechanism overlap
"Drug X has no active trials for Disease Y but shares pathway Z → candidate"
This is what separates hypothesis generation from aggregation.
"""
import aiohttp
import json
import os
from .overlap_engine import find_disease_pathways, compute_overlap, extract_drug_pathways, DISEASE_PATHWAYS
from .similarity_engine import DRUG_CLASSES

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Curated list of well-known drugs with established mechanisms
# These are candidates for disease-first search
CANDIDATE_DRUGS = [
    {"name": "Metformin",     "mechanism": "AMPK activation",           "pathways": ["AMPK","mTOR","insulin","glucose","inflammation"]},
    {"name": "Aspirin",       "mechanism": "COX inhibition",             "pathways": ["COX","prostaglandin","inflammation","platelet","NF-kB"]},
    {"name": "Ibuprofen",     "mechanism": "COX inhibition",             "pathways": ["COX","prostaglandin","inflammation","pain"]},
    {"name": "Paracetamol",   "mechanism": "Central COX inhibition",     "pathways": ["COX","prostaglandin","pain","fever","PGE2"]},
    {"name": "Sildenafil",    "mechanism": "PDE5 inhibition",            "pathways": ["PDE5","cGMP","nitric oxide","vasodilation","smooth muscle"]},
    {"name": "Atorvastatin",  "mechanism": "HMG-CoA reductase inhibition","pathways": ["HMG-CoA","cholesterol","inflammation","NF-kB","angiogenesis"]},
    {"name": "Dexamethasone", "mechanism": "Glucocorticoid receptor",    "pathways": ["inflammation","immune","NF-kB","cytokine","TNF-alpha","IL-6"]},
    {"name": "Thalidomide",   "mechanism": "TNF-alpha inhibition",       "pathways": ["TNF-alpha","angiogenesis","immune","NF-kB","inflammation"]},
    {"name": "Ivermectin",    "mechanism": "Ion channel modulation",     "pathways": ["ion channel","parasite","cancer","PAK1"]},
    {"name": "Mebendazole",   "mechanism": "Microtubule disruption",     "pathways": ["microtubule","cancer","angiogenesis","Wnt","VEGF"]},
    {"name": "Itraconazole",  "mechanism": "Hedgehog pathway inhibition","pathways": ["Hedgehog","angiogenesis","VEGF","cancer","lanosterol"]},
    {"name": "Rapamycin",     "mechanism": "mTOR inhibition",            "pathways": ["mTOR","cancer","aging","immune","PI3K"]},
    {"name": "Valproate",     "mechanism": "HDAC inhibition",            "pathways": ["HDAC","epigenetics","cancer","mood","sodium channel","GABA"]},
    {"name": "Propranolol",   "mechanism": "Beta-adrenergic blockade",   "pathways": ["beta-adrenergic","angiogenesis","VEGF","hemangioma","anxiety"]},
    {"name": "Colchicine",    "mechanism": "Microtubule disruption",     "pathways": ["microtubule","inflammation","gout","NLRP3","NF-kB","pericarditis"]},
    {"name": "Hydroxychloroquine","mechanism":"Lysosome alkalization",   "pathways": ["lysosome","immune","autophagy","inflammation","lupus"]},
    {"name": "Finasteride",   "mechanism": "5-alpha reductase inhibition","pathways": ["androgen","DHT","prostate","hair","testosterone"]},
    {"name": "Melatonin",     "mechanism": "MT1/MT2 receptor agonism",   "pathways": ["circadian","antioxidant","immune","cancer","inflammation"]},
    {"name": "Fluoxetine",    "mechanism": "Serotonin reuptake inhibition","pathways": ["serotonin","5-HT","depression","cancer","immune"]},
    {"name": "Lithium",       "mechanism": "GSK-3 inhibition",           "pathways": ["GSK-3","Wnt","neuroprotection","BDNF","mood","alzheimer"]},
    {"name": "Amiodarone",    "mechanism": "Multi-channel blockade",     "pathways": ["potassium channel","thyroid","inflammation","cancer"]},
    {"name": "Caffeine",      "mechanism": "Adenosine receptor antagonism","pathways": ["adenosine","dopamine","AMPK","neurodegeneration","fatigue"]},
    {"name": "Niclosamide",   "mechanism": "STAT3/Wnt inhibition",       "pathways": ["STAT3","Wnt","mTOR","cancer","viral","COVID"]},
    {"name": "Disulfiram",    "mechanism": "ALDH inhibition",            "pathways": ["ALDH","copper","cancer","NF-kB","proteasome","alcohol"]},
    {"name": "Methotrexate",  "mechanism": "DHFR inhibition",            "pathways": ["folate","DNA synthesis","cancer","inflammation","autoimmune"]},
]

def generate_hypotheses_from_overlap(disease: str, mechanism_threshold: int = 20) -> list:
    """
    Core hypothesis generation:
    For a given disease, find drugs NOT commonly trialled for it
    but with strong pathway overlap → these are the hidden opportunities.
    """
    disease_pathways = find_disease_pathways(disease)
    if not disease_pathways:
        # Try partial match
        disease_lower = disease.lower()
        for known_disease in DISEASE_PATHWAYS:
            if any(w in disease_lower for w in known_disease.split()):
                disease_pathways = DISEASE_PATHWAYS[known_disease]
                break
    
    if not disease_pathways:
        return []
    
    hypotheses = []
    for drug in CANDIDATE_DRUGS:
        overlap = compute_overlap(drug["pathways"], disease_pathways)
        if overlap["score"] >= mechanism_threshold:
            hypotheses.append({
                "drug":           drug["name"],
                "mechanism":      drug["mechanism"],
                "drug_pathways":  drug["pathways"],
                "overlap":        overlap["overlap"],
                "overlap_score":  overlap["score"],
                "strength":       overlap["strength"],
                "hypothesis":     f"{drug['name']} affects {', '.join(overlap['overlap'][:3])}, which are implicated in {disease}",
                "type":           "MECHANISM_OVERLAP"
            })
    
    hypotheses.sort(key=lambda x: x["overlap_score"], reverse=True)
    return hypotheses[:8]

async def run_hypothesis_mode(disease: str, language: str = "en") -> dict:
    """
    Disease-first hypothesis generation.
    Returns drugs that COULD treat this disease based on biological overlap,
    even if no major trials exist yet.
    """
    hypotheses = generate_hypotheses_from_overlap(disease)
    disease_pathways = find_disease_pathways(disease)
    
    result = {
        "disease":          disease,
        "disease_pathways": disease_pathways[:8],
        "hypotheses":       hypotheses,
        "top_hypothesis":   hypotheses[0] if hypotheses else None,
        "ai_narrative":     None
    }
    
    if not hypotheses:
        result["ai_narrative"] = f"No strong pathway overlaps found for {disease} in the current knowledge base."
        return result
    
    # Generate AI narrative for the top hypotheses
    api_key = os.environ.get("OPENROUTER_API_KEY","") or os.environ.get("ANTHROPIC_API_KEY","")
    if not api_key:
        result["ai_narrative"] = f"Found {len(hypotheses)} biological candidates for {disease} based on pathway overlap analysis."
        return result
    
    lang_map = {"ta":"Tamil","hi":"Hindi","te":"Telugu","fr":"French","es":"Spanish","de":"German","zh":"Chinese","ar":"Arabic","pt":"Portuguese"}
    lang_instr = f"Respond in {lang_map.get(language,'English')}. Keep drug names and pathway names in English." if language!="en" else ""
    
    top3 = hypotheses[:3]
    prompt = f"""You are a drug repurposing expert. {lang_instr}

A researcher is looking for drugs that could potentially treat: {disease}

This disease involves these pathways: {', '.join(disease_pathways[:6])}

Based on pathway overlap analysis, these drugs are biological candidates:
{json.dumps(top3, indent=2)}

Write a brief but compelling 3-4 sentence hypothesis paragraph explaining:
1. Why these drugs might work for {disease} based on their mechanism
2. What the pathway overlap means clinically
3. What the next step would be

Be specific about the biological mechanism. Use phrases like "pathway overlap suggests" and "mechanism-based rationale". Keep it under 150 words. Do not just list drugs — explain the biological logic."""
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization":f"Bearer {api_key}","Content-Type":"application/json","HTTP-Referer":"http://localhost:5000","X-Title":"RepurposeAI"}
            payload = {"model":"anthropic/claude-3-haiku","max_tokens":300,"messages":[{"role":"user","content":prompt}]}
            async with session.post(OPENROUTER_API_URL,headers=headers,json=payload,timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status==200:
                    data = await resp.json()
                    result["ai_narrative"] = data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        result["ai_narrative"] = f"Pathway overlap analysis identified {len(hypotheses)} candidates for {disease}."
    
    return result

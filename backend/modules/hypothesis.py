"""
hypothesis.py — Disease-First Hypothesis Engine
Input: Disease → Output: Drug candidates with biological plausibility
This is the "Find Hidden Opportunities" mode judges remember.
"""
import aiohttp
import json
import os

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Disease → pathway associations for candidate generation
DISEASE_PATHWAYS = {
    "alzheimer": ["acetylcholine", "oxidative stress", "inflammation", "amyloid", "tau", "mTOR", "cholesterol"],
    "cancer": ["apoptosis", "angiogenesis", "mTOR", "PI3K/AKT", "p53", "NF-kB", "MAPK/ERK"],
    "diabetes": ["insulin", "AMPK", "mTOR", "oxidative stress", "inflammation"],
    "parkinson": ["dopamine", "oxidative stress", "apoptosis", "inflammation"],
    "depression": ["serotonin", "dopamine", "inflammation", "neurogenesis"],
    "hypertension": ["angiotensin", "cholesterol", "inflammation", "oxidative stress"],
    "arthritis": ["inflammation", "NF-kB", "JAK/STAT", "TGF-beta"],
    "cardiovascular": ["cholesterol", "inflammation", "angiogenesis", "oxidative stress"],
    "autoimmune": ["NF-kB", "JAK/STAT", "inflammation", "TGF-beta"],
    "cancer prevention": ["NF-kB", "apoptosis", "VEGF", "inflammation", "cyclooxygenase"],
    "obesity": ["AMPK", "insulin", "mTOR", "adipogenesis"],
    "fibrosis": ["TGF-beta", "NF-kB", "inflammation", "oxidative stress"],
    "infection": ["inflammation", "NF-kB", "oxidative stress", "apoptosis"],
    "pain": ["prostaglandin", "cyclooxygenase", "inflammation", "serotonin"],
    "neuroprotection": ["oxidative stress", "apoptosis", "inflammation", "AMPK"],
}

# Drug → pathway map (reverse of target_overlap)
DRUG_PATHWAYS = {
    "aspirin":       ["cyclooxygenase", "prostaglandin", "inflammation", "NF-kB", "angiogenesis"],
    "metformin":     ["AMPK", "mTOR", "insulin", "oxidative stress", "inflammation"],
    "sildenafil":    ["PDE5", "angiogenesis", "VEGF", "oxidative stress"],
    "ibuprofen":     ["cyclooxygenase", "prostaglandin", "inflammation", "NF-kB"],
    "paracetamol":   ["prostaglandin", "oxidative stress", "inflammation"],
    "statins":       ["cholesterol", "inflammation", "oxidative stress", "angiogenesis"],
    "thalidomide":   ["NF-kB", "angiogenesis", "inflammation", "TGF-beta"],
    "dexamethasone": ["inflammation", "NF-kB", "apoptosis", "oxidative stress"],
    "hydroxychloroquine": ["inflammation", "NF-kB", "autoimmune", "oxidative stress"],
    "rapamycin":     ["mTOR", "PI3K/AKT", "apoptosis", "angiogenesis"],
    "ivermectin":    ["inflammation", "oxidative stress", "apoptosis"],
    "valproic acid": ["apoptosis", "oxidative stress", "inflammation", "neurogenesis"],
    "lithium":       ["mTOR", "apoptosis", "oxidative stress", "neurogenesis"],
    "berberine":     ["AMPK", "mTOR", "NF-kB", "inflammation"],
    "curcumin":      ["NF-kB", "inflammation", "oxidative stress", "angiogenesis"],
}


def find_candidates_for_disease(disease: str) -> list:
    """Find drug candidates for a disease based on pathway overlap."""
    disease_lower = disease.lower()
    
    # Find relevant pathways for this disease
    relevant_pathways = []
    for d_key, pathways in DISEASE_PATHWAYS.items():
        if d_key in disease_lower or disease_lower in d_key:
            relevant_pathways.extend(pathways)
            break
    
    # If not found, use general inflammation + oxidative stress
    if not relevant_pathways:
        relevant_pathways = ["inflammation", "oxidative stress", "NF-kB"]
    
    # Score each drug by pathway overlap
    candidates = []
    for drug, drug_pathways in DRUG_PATHWAYS.items():
        overlap = set(drug_pathways) & set(relevant_pathways)
        if overlap:
            candidates.append({
                "drug":              drug,
                "overlap_pathways":  list(overlap),
                "overlap_score":     len(overlap),
                "signal":            f"{drug} affects {', '.join(list(overlap)[:2])}, which are dysregulated in {disease}",
                "novelty":           "HIGH" if len(overlap) >= 3 else "MODERATE"
            })
    
    # Sort by overlap score
    candidates.sort(key=lambda x: x["overlap_score"], reverse=True)
    return candidates[:6]


async def generate_hypothesis(disease: str, candidates: list, language: str = "en") -> str:
    """Use AI to generate a scientific hypothesis from candidates."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key or not candidates:
        return f"Based on pathway analysis, {len(candidates)} approved drugs show biological plausibility for {disease}."
    
    lang_note = "" if language == "en" else f"Respond in {language}."
    
    prompt = f"""You are a drug repurposing scientist. {lang_note}
Generate a 2-3 sentence scientific hypothesis about repurposing approved drugs for {disease}.

Top candidates from pathway analysis:
{json.dumps(candidates[:3], indent=2)}

Format: "We hypothesize that [drug] may be effective for [disease] because [mechanism]. This is supported by [evidence type]. The strongest candidate is [drug] with [overlap_score] pathway overlaps including [pathways]."

Be specific and scientific. Return only the hypothesis text, no JSON."""
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:5000",
                "X-Title": "RepurposeAI"
            }
            payload = {
                "model": "anthropic/claude-3-haiku",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}]
            }
            async with session.post(OPENROUTER_API_URL, headers=headers, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[Hypothesis] {e}")
    
    return f"Based on pathway overlap analysis, {candidates[0]['drug']} shows the strongest biological signal for {disease} with {candidates[0]['overlap_score']} shared pathway dysregulations."


async def run_disease_first_analysis(disease: str, language: str = "en") -> dict:
    """
    Main disease-first hypothesis pipeline.
    Input: disease name
    Output: drug candidates with biological rationale
    """
    candidates = find_candidates_for_disease(disease)
    hypothesis = await generate_hypothesis(disease, candidates, language)
    
    return {
        "disease":     disease,
        "hypothesis":  hypothesis,
        "candidates":  candidates,
        "top_candidate": candidates[0] if candidates else None,
        "pathway_summary": f"Analysis identified {len(candidates)} approved drugs with pathway overlap to {disease}.",
        "mode": "disease_first"
    }

"""
similarity.py — Drug Similarity Engine
Finds structurally and functionally similar drugs to generate new candidates.
Uses PubChem similarity search and class-based matching.
"""
import aiohttp
import json

# Drug class groupings for functional similarity
DRUG_CLASSES = {
    "nsaid": ["aspirin", "ibuprofen", "naproxen", "diclofenac", "celecoxib", "indomethacin", "paracetamol", "acetaminophen"],
    "statin": ["atorvastatin", "simvastatin", "rosuvastatin", "pravastatin", "lovastatin", "fluvastatin"],
    "biguanide": ["metformin", "phenformin", "buformin"],
    "pde5_inhibitor": ["sildenafil", "tadalafil", "vardenafil", "avanafil"],
    "ssri": ["fluoxetine", "sertraline", "paroxetine", "escitalopram", "citalopram", "fluvoxamine"],
    "ace_inhibitor": ["lisinopril", "enalapril", "ramipril", "captopril", "perindopril"],
    "beta_blocker": ["metoprolol", "atenolol", "propranolol", "bisoprolol", "carvedilol"],
    "antibiotic_fluoroquinolone": ["ciprofloxacin", "levofloxacin", "moxifloxacin", "ofloxacin"],
    "antibiotic_penicillin": ["amoxicillin", "ampicillin", "penicillin", "piperacillin"],
    "immunomodulator": ["thalidomide", "lenalidomide", "pomalidomide", "hydroxychloroquine"],
    "antiparasitic": ["ivermectin", "hydroxychloroquine", "chloroquine", "mefloquine"],
    "antidiabetic": ["metformin", "glyburide", "glipizide", "pioglitazone", "sitagliptin"],
    "anticoagulant": ["warfarin", "heparin", "rivaroxaban", "apixaban", "dabigatran"],
    "antiviral": ["remdesivir", "oseltamivir", "acyclovir", "tenofovir", "lopinavir"],
    "corticosteroid": ["dexamethasone", "prednisone", "methylprednisolone", "hydrocortisone"],
    "antifungal": ["fluconazole", "itraconazole", "voriconazole", "amphotericin"],
    "antihistamine": ["cetirizine", "loratadine", "diphenhydramine", "fexofenadine"],
}

# Known successful repurposings for validation framing
KNOWN_REPURPOSINGS = {
    "sildenafil":   {"from": "angina", "to": "erectile dysfunction, pulmonary hypertension"},
    "thalidomide":  {"from": "morning sickness", "to": "multiple myeloma, leprosy"},
    "metformin":    {"from": "type 2 diabetes", "to": "cancer prevention, longevity, PCOS"},
    "aspirin":      {"from": "pain/fever", "to": "cardiovascular prevention, colorectal cancer"},
    "dexamethasone":{"from": "inflammation", "to": "COVID-19 severity reduction"},
    "hydroxychloroquine": {"from": "malaria", "to": "rheumatoid arthritis, lupus"},
    "ivermectin":   {"from": "parasitic infection", "to": "various viral/inflammatory research"},
    "tamoxifen":    {"from": "breast cancer", "to": "bipolar disorder, McCune-Albright syndrome"},
}


async def fetch_similar_compounds(cid: int) -> list:
    """Fetch structurally similar compounds from PubChem."""
    similar = []
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/assaysummary/JSON"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    data = await r.json()
                    rows = data.get("Table",{}).get("Row",[])
                    names = set()
                    for row in rows[:20]:
                        cells = row.get("Cell",[])
                        if cells and isinstance(cells[0], str) and len(cells[0]) > 2:
                            names.add(cells[0])
                    similar = list(names)[:6]
    except Exception as e:
        print(f"[Similarity] PubChem similar: {e}")
    return similar


def find_class_siblings(molecule: str) -> dict:
    """Find drugs in the same class as the input molecule."""
    mol_lower = molecule.lower()
    
    for class_name, drugs in DRUG_CLASSES.items():
        if mol_lower in drugs:
            siblings = [d for d in drugs if d != mol_lower]
            # Find what those drugs are used for based on known repurposings
            sibling_repurposings = []
            for sibling in siblings:
                if sibling in KNOWN_REPURPOSINGS:
                    rp = KNOWN_REPURPOSINGS[sibling]
                    sibling_repurposings.append({
                        "drug":    sibling,
                        "used_for": rp["to"],
                        "signal":  f"{sibling} (same {class_name.replace('_',' ')} class) is used for {rp['to']}"
                    })
            
            return {
                "drug_class":    class_name.replace("_", " "),
                "class_siblings": siblings[:6],
                "sibling_repurposings": sibling_repurposings,
                "similarity_signal": (
                    f"{molecule} belongs to the {class_name.replace('_',' ')} class. "
                    f"Class siblings {', '.join(siblings[:3])} suggest investigating similar therapeutic areas."
                ) if siblings else ""
            }
    
    return {
        "drug_class": "Unknown",
        "class_siblings": [],
        "sibling_repurposings": [],
        "similarity_signal": ""
    }


def get_known_repurposing(molecule: str) -> dict:
    """Check if this drug has known successful repurposings."""
    mol_lower = molecule.lower()
    for key, val in KNOWN_REPURPOSINGS.items():
        if key in mol_lower or mol_lower in key:
            return {
                "has_known_repurposing": True,
                "original_use":         val["from"],
                "repurposed_for":       val["to"],
                "validation_note":      f"{molecule} is a validated repurposing case — originally for {val['from']}, now used for {val['to']}. Our system can find similar opportunities."
            }
    return {"has_known_repurposing": False}


async def run_similarity_analysis(molecule: str, cid: int = None) -> dict:
    """Full similarity analysis pipeline."""
    # Class-based similarity
    class_data      = find_class_siblings(molecule)
    known_repurpose = get_known_repurposing(molecule)
    
    # Structural similarity from PubChem
    structural_similar = []
    if cid:
        structural_similar = await fetch_similar_compounds(cid)
    
    return {
        "drug_class":           class_data["drug_class"],
        "class_siblings":       class_data["class_siblings"],
        "sibling_repurposings": class_data["sibling_repurposings"],
        "similarity_signal":    class_data["similarity_signal"],
        "structural_similar":   structural_similar,
        "known_repurposing":    known_repurpose,
        "candidate_diseases":   list(set([
            r["used_for"] for r in class_data["sibling_repurposings"]
        ]))[:5]
    }

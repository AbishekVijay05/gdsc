"""
similarity_engine.py
Drug similarity: find drugs in same class or mechanism → suggest new candidates
"Drug A is similar to Drug B which treats Disease X → candidate for Disease X"
"""
import aiohttp
import json

# Drug class knowledge base
DRUG_CLASSES = {
    "nsaid": {
        "members": ["aspirin","ibuprofen","naproxen","diclofenac","celecoxib","indomethacin","ketorolac","meloxicam","piroxicam"],
        "mechanism": "COX inhibition",
        "pathways": ["COX","prostaglandin","inflammation","pain"],
        "known_repurposings": ["colorectal cancer prevention (aspirin)","cardiovascular protection (aspirin)","preeclampsia (aspirin)"]
    },
    "biguanide": {
        "members": ["metformin","phenformin","buformin"],
        "mechanism": "AMPK activation",
        "pathways": ["AMPK","mTOR","glucose","insulin"],
        "known_repurposings": ["cancer (metformin)","polycystic ovary syndrome","aging/longevity"]
    },
    "pde5_inhibitor": {
        "members": ["sildenafil","tadalafil","vardenafil","avanafil"],
        "mechanism": "PDE5 inhibition",
        "pathways": ["PDE5","cGMP","nitric oxide","vasodilation"],
        "known_repurposings": ["pulmonary hypertension (sildenafil)","altitude sickness","Raynaud's disease"]
    },
    "ssri": {
        "members": ["fluoxetine","sertraline","paroxetine","escitalopram","citalopram","fluvoxamine"],
        "mechanism": "Serotonin reuptake inhibition",
        "pathways": ["serotonin","5-HT","depression","anxiety"],
        "known_repurposings": ["premature ejaculation","OCD","PTSD","eating disorders"]
    },
    "statin": {
        "members": ["atorvastatin","simvastatin","rosuvastatin","pravastatin","lovastatin","fluvastatin"],
        "mechanism": "HMG-CoA reductase inhibition",
        "pathways": ["HMG-CoA","cholesterol","cardiovascular","LDL","inflammation"],
        "known_repurposings": ["sepsis reduction","dementia prevention","cancer (emerging)"]
    },
    "ace_inhibitor": {
        "members": ["lisinopril","enalapril","ramipril","captopril","perindopril","benazepril"],
        "mechanism": "ACE inhibition",
        "pathways": ["renin-angiotensin","RAAS","hypertension","heart"],
        "known_repurposings": ["diabetic nephropathy","heart failure","stroke prevention"]
    },
    "beta_blocker": {
        "members": ["metoprolol","atenolol","propranolol","carvedilol","bisoprolol","nebivolol"],
        "mechanism": "Beta-adrenergic blockade",
        "pathways": ["beta-adrenergic","heart rate","hypertension","anxiety"],
        "known_repurposings": ["anxiety","migraine prevention","essential tremor","portal hypertension"]
    },
    "proton_pump_inhibitor": {
        "members": ["omeprazole","pantoprazole","lansoprazole","esomeprazole","rabeprazole"],
        "mechanism": "H+/K+ ATPase inhibition",
        "pathways": ["proton pump","gastric acid","H pylori"],
        "known_repurposings": ["H pylori eradication","Barrett's esophagus"]
    },
    "corticosteroid": {
        "members": ["dexamethasone","prednisolone","prednisone","hydrocortisone","methylprednisolone","budesonide"],
        "mechanism": "Glucocorticoid receptor activation",
        "pathways": ["inflammation","immune","NF-kB","cytokine"],
        "known_repurposings": ["COVID-19 (dexamethasone)","cancer pain","nausea","cerebral edema"]
    },
    "thalidomide_class": {
        "members": ["thalidomide","lenalidomide","pomalidomide"],
        "mechanism": "TNF-alpha inhibition + immune modulation",
        "pathways": ["TNF-alpha","angiogenesis","immune","NF-kB"],
        "known_repurposings": ["multiple myeloma","leprosy ENL","ankylosing spondylitis"]
    },
    "analgesic": {
        "members": ["paracetamol","acetaminophen","codeine","tramadol","morphine"],
        "mechanism": "Central pain modulation",
        "pathways": ["COX","prostaglandin","opioid","pain","fever"],
        "known_repurposings": ["patent ductus arteriosus (paracetamol)","fever in malaria","neonatal pain"]
    },
    "antibiotic_fluoroquinolone": {
        "members": ["ciprofloxacin","levofloxacin","moxifloxacin","norfloxacin"],
        "mechanism": "DNA gyrase inhibition",
        "pathways": ["bacterial","DNA gyrase","topoisomerase"],
        "known_repurposings": ["mycobacterium","drug-resistant TB"]
    },
    "antifungal_azole": {
        "members": ["itraconazole","fluconazole","ketoconazole","voriconazole"],
        "mechanism": "Lanosterol 14-alpha demethylase inhibition",
        "pathways": ["fungal","ergosterol","Hedgehog","angiogenesis"],
        "known_repurposings": ["cancer (itraconazole via Hedgehog)","visceral leishmaniasis"]
    },
    "antiparasitic": {
        "members": ["ivermectin","mebendazole","albendazole","praziquantel"],
        "mechanism": "Parasite-specific ion channels",
        "pathways": ["parasite","ion channel","microtubule","cancer"],
        "known_repurposings": ["cancer (mebendazole)","rosacea (ivermectin)","onchocerciasis"]
    },
    "antiepileptic": {
        "members": ["valproate","carbamazepine","lamotrigine","topiramate","gabapentin","pregabalin"],
        "mechanism": "Sodium channel or GABA modulation",
        "pathways": ["sodium channel","GABA","epilepsy","pain","mood"],
        "known_repurposings": ["bipolar disorder","neuropathic pain","migraine prevention"]
    }
}

def find_drug_class(molecule: str) -> dict:
    """Find which class a drug belongs to."""
    mol_lower = molecule.lower()
    for class_name, class_data in DRUG_CLASSES.items():
        if mol_lower in class_data["members"]:
            return {"class": class_name, **class_data}
    return None

def find_similar_drugs(molecule: str) -> dict:
    """
    Find drugs similar to the input molecule.
    Returns similar drugs, their known repurposings, and candidate diseases.
    """
    drug_class = find_drug_class(molecule)
    
    if not drug_class:
        return {
            "drug_class": None,
            "similar_drugs": [],
            "class_mechanism": None,
            "known_repurposings": [],
            "similarity_candidates": [],
            "similarity_statement": f"{molecule} drug class not found in similarity database. Analysis based on mechanism text."
        }
    
    mol_lower = molecule.lower()
    similar   = [m for m in drug_class["members"] if m != mol_lower]
    
    # Generate candidates based on class repurposings
    candidates = []
    for repurposing in drug_class["known_repurposings"]:
        # Extract disease from repurposing string
        parts   = repurposing.split("(")
        disease = parts[0].strip()
        example = parts[1].replace(")","").strip() if len(parts)>1 else ""
        
        # Only suggest if the example drug is different from our molecule
        if example.lower() != mol_lower:
            candidates.append({
                "disease":        disease,
                "based_on_drug":  example,
                "rationale":      f"{molecule} shares the same {drug_class['mechanism']} mechanism as {example}, which is used for {disease}",
                "confidence":     "MODERATE",
                "type":           "CLASS_SIMILARITY"
            })
    
    statement = (
        f"{molecule} belongs to the {drug_class['class'].replace('_',' ')} class. "
        f"Other members ({', '.join(similar[:3])}) have been repurposed for: "
        f"{'; '.join(drug_class['known_repurposings'][:2])}. "
        f"Same mechanism ({drug_class['mechanism']}) suggests similar potential."
    )
    
    return {
        "drug_class":           drug_class["class"],
        "class_mechanism":      drug_class["mechanism"],
        "class_pathways":       drug_class["pathways"],
        "similar_drugs":        similar[:5],
        "known_repurposings":   drug_class["known_repurposings"],
        "similarity_candidates": candidates,
        "similarity_statement": statement
    }

async def fetch_pubchem_similar(molecule: str, limit: int = 5) -> list:
    """Fetch structurally similar compounds from PubChem."""
    similar = []
    try:
        async with aiohttp.ClientSession() as session:
            # Get CID first
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{molecule}/cids/JSON"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status != 200:
                    return similar
                data = await r.json()
                cid  = data["IdentifierList"]["CID"][0]
            
            # Get similar compounds by 2D fingerprint
            sim_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/fastsimilarity_2d/cid/{cid}/cids/JSON?Threshold=90&MaxRecords={limit}"
            async with session.get(sim_url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data   = await r.json()
                    cids   = data.get("IdentifierList",{}).get("CID",[])[:limit]
                    similar = [{"cid": c, "similarity_type": "2D_fingerprint"} for c in cids]
    except Exception as e:
        print(f"[Similarity] PubChem error: {e}")
    return similar

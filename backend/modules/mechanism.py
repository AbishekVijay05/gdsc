import aiohttp
import json

async def fetch_mechanism_data(molecule: str) -> dict:
    """
    Fetches biological mechanism data for a molecule from PubChem.
    Returns molecular targets, pharmacology, and biological activity data.
    """
    result = {
        "molecule": molecule,
        "molecular_formula": None,
        "molecular_weight": None,
        "iupac_name": None,
        "pharmacology": None,
        "mechanism_of_action": None,
        "biological_targets": [],
        "known_pathways": [],
        "toxicity_signals": [],
        "bioactivity_count": 0,
        "drug_likeness": None,
        "error": None
    }

    try:
        async with aiohttp.ClientSession() as session:

            # Step 1: Get CID
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{molecule}/cids/JSON"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    result["error"] = "Compound not found in PubChem"
                    return result
                data = await r.json()
                cid = data["IdentifierList"]["CID"][0]

            # Step 2: Get full compound properties
            props_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,IUPACName,XLogP,HBondDonorCount,HBondAcceptorCount,RotatableBondCount,TPSA/JSON"
            async with session.get(props_url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    props_data = await r.json()
                    props = props_data["PropertyTable"]["Properties"][0]
                    result["molecular_formula"] = props.get("MolecularFormula")
                    result["molecular_weight"]  = props.get("MolecularWeight")
                    result["iupac_name"]        = props.get("IUPACName")

                    # Lipinski Rule of 5 — drug likeness check
                    mw     = float(props.get("MolecularWeight", 999))
                    xlogp  = float(props.get("XLogP", 99))
                    hbd    = int(props.get("HBondDonorCount", 99))
                    hba    = int(props.get("HBondAcceptorCount", 99))
                    passes = sum([mw <= 500, xlogp <= 5, hbd <= 5, hba <= 10])
                    result["drug_likeness"] = {
                        "molecular_weight": mw,
                        "logP": xlogp,
                        "h_bond_donors": hbd,
                        "h_bond_acceptors": hba,
                        "lipinski_passes": passes,
                        "lipinski_score": f"{passes}/4",
                        "assessment": "Drug-like" if passes >= 3 else "Borderline" if passes == 2 else "Poor drug-likeness"
                    }

            # Step 3: Get pharmacology description
            desc_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/description/JSON"
            async with session.get(desc_url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    desc_data = await r.json()
                    descriptions = desc_data.get("InformationList", {}).get("Information", [])
                    for d in descriptions:
                        desc_text = d.get("Description", "")
                        title     = d.get("DescriptionSourceName", "")
                        if "pharmacolog" in desc_text.lower() or "mechanism" in desc_text.lower():
                            result["mechanism_of_action"] = desc_text[:500]
                            break
                        elif "drug" in title.lower() and not result["pharmacology"]:
                            result["pharmacology"] = desc_text[:400]

            # Step 4: Get bioactivity count
            bio_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/assaysummary/JSON"
            async with session.get(bio_url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    bio_data = await r.json()
                    table    = bio_data.get("Table", {})
                    rows     = table.get("Row", [])
                    result["bioactivity_count"] = len(rows)

                    # Extract biological targets from assay data
                    targets = set()
                    for row in rows[:20]:
                        cells = row.get("Cell", [])
                        if len(cells) > 3:
                            target = cells[3] if isinstance(cells[3], str) else ""
                            if target and len(target) > 2 and target.lower() not in ["", "unspecified", "n/a"]:
                                targets.add(target)
                    result["biological_targets"] = list(targets)[:8]

    except Exception as e:
        result["error"] = str(e)

    return result

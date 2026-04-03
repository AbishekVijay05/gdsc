import aiohttp

PUBCHEM_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name"

async def fetch_patents(molecule: str) -> dict:
    # Get compound info from PubChem (free, no key needed)
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{PUBCHEM_URL}/{molecule}/JSON"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                compound_info = {}
                if resp.status == 200:
                    data = await resp.json()
                    compounds = data.get("PC_Compounds", [])
                    if compounds:
                        props = compounds[0].get("props", [])
                        for p in props:
                            urn = p.get("urn", {})
                            val = p.get("value", {})
                            if urn.get("label") == "IUPAC Name" and urn.get("name") == "Preferred":
                                compound_info["iupac_name"] = val.get("sval", "")
                            if urn.get("label") == "Molecular Formula":
                                compound_info["formula"] = val.get("sval", "")
                            if urn.get("label") == "Molecular Weight":
                                compound_info["molecular_weight"] = val.get("fval", "")
                        cid = compounds[0].get("id", {}).get("id", {}).get("cid", "")
                        compound_info["cid"] = cid

            # Fetch patent data from PubChem patent endpoint
            patents = []
            if compound_info.get("cid"):
                cid = compound_info["cid"]
                patent_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/xrefs/PatentID/JSON"
                async with session.get(patent_url, timeout=aiohttp.ClientTimeout(total=15)) as presp:
                    if presp.status == 200:
                        pdata = await presp.json()
                        patent_ids = pdata.get("InformationList", {}).get("Information", [{}])[0].get("PatentID", [])
                        for pid in patent_ids[:8]:
                            patents.append({
                                "patent_id": pid,
                                "source_url": f"https://patents.google.com/patent/{pid}"
                            })

            return {
                "status": "success",
                "compound_info": compound_info,
                "total_patents": len(patents),
                "patents": patents,
                "source": "PubChem / Google Patents",
                "source_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{molecule}",
                "google_patents_url": f"https://patents.google.com/?q={molecule}&assignee=&before=priority:20200101"
            }
    except Exception as e:
        return {
            "status": "fallback",
            "compound_info": {},
            "total_patents": 0,
            "patents": [],
            "source": "PubChem",
            "source_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{molecule}",
            "note": "Could not fetch live data. Check your internet connection."
        }

import aiohttp

OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"

async def fetch_regulatory_data(molecule: str) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            params = {
                "search": f"openfda.generic_name:{molecule}",
                "limit": 3
            }
            async with session.get(OPENFDA_LABEL_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])

                    indications = []
                    warnings = []
                    contraindications = []
                    approvals = []

                    for r in results:
                        openfda = r.get("openfda", {})
                        brand_names = openfda.get("brand_name", [])
                        application_numbers = openfda.get("application_number", [])
                        manufacturers = openfda.get("manufacturer_name", [])

                        if application_numbers:
                            for app in application_numbers[:2]:
                                approvals.append({
                                    "application_number": app,
                                    "brand_name": brand_names[0] if brand_names else "N/A",
                                    "manufacturer": manufacturers[0] if manufacturers else "N/A"
                                })

                        raw_indications = r.get("indications_and_usage", [])
                        if raw_indications:
                            text = raw_indications[0][:400]
                            indications.append(text)

                        raw_warnings = r.get("warnings", [])
                        if raw_warnings:
                            text = raw_warnings[0][:300]
                            warnings.append(text)

                        raw_contra = r.get("contraindications", [])
                        if raw_contra:
                            text = raw_contra[0][:300]
                            contraindications.append(text)

                    return {
                        "status": "success",
                        "approvals": approvals,
                        "current_indications": indications[:2],
                        "warnings": warnings[:2],
                        "contraindications": contraindications[:2],
                        "total_labels_found": len(results),
                        "source": "OpenFDA Drug Labels",
                        "source_url": f"https://open.fda.gov/apis/drug/label/",
                        "fda_label_url": f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query={molecule}"
                    }
                else:
                    return _fallback(molecule)
    except Exception as e:
        return _fallback(molecule)

def _fallback(molecule):
    return {
        "status": "fallback",
        "approvals": [],
        "current_indications": [],
        "warnings": [],
        "contraindications": [],
        "total_labels_found": 0,
        "source": "OpenFDA Drug Labels",
        "source_url": "https://open.fda.gov",
        "note": "Could not fetch live data."
    }

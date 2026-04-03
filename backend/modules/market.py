import aiohttp

OPENFDA_DRUG_URL = "https://api.fda.gov/drug/ndc.json"
OPENFDA_EVENT_URL = "https://api.fda.gov/drug/event.json"

async def fetch_market_data(molecule: str) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            # Search drug products
            params = {
                "search": f"generic_name:{molecule}",
                "limit": 5
            }
            products = []
            manufacturers = set()
            dosage_forms = set()

            async with session.get(OPENFDA_DRUG_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    for r in results:
                        brand = r.get("brand_name", "N/A")
                        generic = r.get("generic_name", "N/A")
                        mfr = r.get("labeler_name", "")
                        dosage = r.get("dosage_form", "")
                        route = r.get("route", [])
                        products.append({
                            "brand_name": brand,
                            "generic_name": generic,
                            "manufacturer": mfr,
                            "dosage_form": dosage,
                            "route": route[0] if route else "N/A"
                        })
                        if mfr:
                            manufacturers.add(mfr)
                        if dosage:
                            dosage_forms.add(dosage)

            # Get adverse event count as proxy for usage volume
            event_count = 0
            event_params = {
                "search": f"patient.drug.medicinalproduct:{molecule}",
                "limit": 1
            }
            async with session.get(OPENFDA_EVENT_URL, params=event_params, timeout=aiohttp.ClientTimeout(total=15)) as eresp:
                if eresp.status == 200:
                    edata = await eresp.json()
                    event_count = edata.get("meta", {}).get("results", {}).get("total", 0)

            return {
                "status": "success",
                "products_found": len(products),
                "products": products,
                "manufacturers": list(manufacturers),
                "dosage_forms": list(dosage_forms),
                "adverse_event_reports": event_count,
                "market_insight": _interpret_events(event_count),
                "source": "OpenFDA",
                "source_url": f"https://open.fda.gov/apis/drug/ndc/",
                "fda_search_url": f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo=&drugname={molecule}"
            }
    except Exception as e:
        return {
            "status": "fallback",
            "products_found": 0,
            "products": [],
            "manufacturers": [],
            "dosage_forms": [],
            "adverse_event_reports": 0,
            "market_insight": "Data unavailable",
            "source": "OpenFDA",
            "source_url": "https://open.fda.gov",
            "note": "Could not fetch live data."
        }

def _interpret_events(count):
    if count > 100000:
        return "Very high market usage — widely prescribed drug with large patient base"
    elif count > 10000:
        return "High market usage — significant commercial presence"
    elif count > 1000:
        return "Moderate market usage — established but niche"
    elif count > 0:
        return "Low market usage — limited commercial presence"
    else:
        return "No adverse event data found — possibly new or rare drug"

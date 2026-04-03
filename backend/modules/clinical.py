import aiohttp
import json

CLINICALTRIALS_URL = "https://clinicaltrials.gov/api/v2/studies"

async def fetch_clinical_trials(molecule: str) -> dict:
    params = {
        "query.intr": molecule,
        "pageSize": 10,
        "format": "json",
        "fields": "NCTId,BriefTitle,OverallStatus,Phase,Condition,StartDate,CompletionDate,LeadSponsorName"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(CLINICALTRIALS_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    studies = data.get("studies", [])
                    trials = []
                    for s in studies:
                        proto = s.get("protocolSection", {})
                        id_mod = proto.get("identificationModule", {})
                        status_mod = proto.get("statusModule", {})
                        design_mod = proto.get("designModule", {})
                        cond_mod = proto.get("conditionsModule", {})
                        sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
                        trials.append({
                            "nct_id": id_mod.get("nctId", "N/A"),
                            "title": id_mod.get("briefTitle", "N/A"),
                            "status": status_mod.get("overallStatus", "N/A"),
                            "phase": design_mod.get("phases", ["N/A"])[0] if design_mod.get("phases") else "N/A",
                            "conditions": cond_mod.get("conditions", []),
                            "sponsor": sponsor_mod.get("leadSponsor", {}).get("name", "N/A"),
                            "start_date": status_mod.get("startDateStruct", {}).get("date", "N/A"),
                            "source_url": f"https://clinicaltrials.gov/study/{id_mod.get('nctId', '')}"
                        })
                    return {
                        "status": "success",
                        "total_found": data.get("totalCount", 0),
                        "trials": trials,
                        "source": "ClinicalTrials.gov",
                        "source_url": f"https://clinicaltrials.gov/search?intr={molecule}"
                    }
                else:
                    return _fallback(molecule)
    except Exception as e:
        return _fallback(molecule)

def _fallback(molecule):
    return {
        "status": "fallback",
        "total_found": 0,
        "trials": [],
        "source": "ClinicalTrials.gov",
        "source_url": f"https://clinicaltrials.gov/search?intr={molecule}",
        "note": "Could not fetch live data. Check your internet connection."
    }

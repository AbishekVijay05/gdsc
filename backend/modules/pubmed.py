import aiohttp
import xml.etree.ElementTree as ET

PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

async def fetch_pubmed(molecule: str) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            # Step 1: search for IDs
            search_params = {
                "db": "pubmed", "term": f"{molecule} repurposing OR {molecule} new indication",
                "retmax": 8, "retmode": "json", "sort": "relevance"
            }
            async with session.get(PUBMED_SEARCH_URL, params=search_params, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    return _fallback(molecule)
                data = await r.json()
                ids = data.get("esearchresult", {}).get("idlist", [])
                total = int(data.get("esearchresult", {}).get("count", 0))

            if not ids:
                return {"status": "success", "total_found": 0, "papers": [], "source": "PubMed", "source_url": f"https://pubmed.ncbi.nlm.nih.gov/?term={molecule}+repurposing"}

            # Step 2: fetch summaries
            fetch_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
            async with session.get(PUBMED_FETCH_URL, params=fetch_params, timeout=aiohttp.ClientTimeout(total=15)) as r2:
                if r2.status != 200:
                    return _fallback(molecule)
                fdata = await r2.json()
                result = fdata.get("result", {})
                papers = []
                for uid in ids:
                    item = result.get(uid, {})
                    if not item:
                        continue
                    authors = item.get("authors", [])
                    author_str = authors[0].get("name", "") if authors else "N/A"
                    if len(authors) > 1:
                        author_str += f" et al."
                    papers.append({
                        "pmid": uid,
                        "title": item.get("title", "N/A"),
                        "authors": author_str,
                        "journal": item.get("fulljournalname", item.get("source", "N/A")),
                        "year": item.get("pubdate", "N/A")[:4],
                        "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/"
                    })
                return {
                    "status": "success",
                    "total_found": total,
                    "papers": papers,
                    "source": "PubMed / NCBI",
                    "source_url": f"https://pubmed.ncbi.nlm.nih.gov/?term={molecule}+repurposing"
                }
    except Exception as e:
        return _fallback(molecule)

def _fallback(molecule):
    return {
        "status": "fallback", "total_found": 0, "papers": [],
        "source": "PubMed", "source_url": f"https://pubmed.ncbi.nlm.nih.gov/?term={molecule}+repurposing",
        "note": "Could not fetch PubMed data."
    }

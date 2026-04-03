from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import asyncio, os, time, sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ── API KEY — replace with your NVIDIA NIM key ─────────────────────────────
NVIDIA_API_KEY = "nvapi-your-key-here"

# Set it in environment so all modules can access it
os.environ["NVIDIA_API_KEY"] = NVIDIA_API_KEY

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))
except Exception:
    pass

from modules.clinical        import fetch_clinical_trials
from modules.patents         import fetch_patents
from modules.market          import fetch_market_data
from modules.regulatory      import fetch_regulatory_data
from modules.synthesizer     import synthesize_report
from modules.scorer          import compute_confidence
from modules.pubmed          import fetch_pubmed
from modules.followup        import answer_followup
from modules.contradiction   import detect_contradictions
from modules.context_memory  import extract_clinical_context, build_synthesis_context
from modules.mechanism       import fetch_mechanism_data
from modules.failure_analysis import analyze_failure_factors

app = Flask(__name__,
    template_folder=os.path.join(os.path.dirname(__file__), "../frontend/templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "../frontend/static"))
CORS(app)

SUPPORTED_LANGUAGES = {
    "en": "English", "ta": "Tamil",  "hi": "Hindi",    "te": "Telugu",
    "fr": "French",  "es": "Spanish", "de": "German",   "zh": "Chinese",
    "ar": "Arabic",  "pt": "Portuguese"
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "api_key_set": bool(os.environ.get("NVIDIA_API_KEY","").startswith("nvapi-")),
        "provider": "NVIDIA NIM",
        "languages": SUPPORTED_LANGUAGES
    })


@app.route("/languages")
def languages():
    return jsonify(SUPPORTED_LANGUAGES)


@app.route("/analyze", methods=["POST"])
def analyze():
    data     = request.get_json()
    molecule = data.get("molecule", "").strip()
    language = data.get("language", "en")
    if not molecule:
        return jsonify({"error": "No molecule name provided"}), 400
    if len(molecule) > 100:
        return jsonify({"error": "Name too long"}), 400
    if language not in SUPPORTED_LANGUAGES:
        language = "en"
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_pipeline(molecule, language))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        return jsonify(result)
    except Exception as e:
        print(f"[Pipeline error] {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/compare", methods=["POST"])
def compare():
    data     = request.get_json()
    m1       = data.get("molecule1", "").strip()
    m2       = data.get("molecule2", "").strip()
    language = data.get("language", "en")
    if not m1 or not m2:
        return jsonify({"error": "Two molecules required"}), 400
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            r1, r2 = loop.run_until_complete(
                asyncio.gather(run_pipeline(m1, language), run_pipeline(m2, language)))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        s1 = r1.get("confidence", {}).get("total", 0)
        s2 = r2.get("confidence", {}).get("total", 0)
        winner = m1 if s1 >= s2 else m2
        return jsonify({"molecule1": r1, "molecule2": r2, "winner": winner})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/batch", methods=["POST"])
def batch():
    data      = request.get_json()
    molecules = [m.strip() for m in data.get("molecules", []) if m.strip()][:5]
    language  = data.get("language", "en")
    if not molecules:
        return jsonify({"error": "No molecules provided"}), 400
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(
                asyncio.gather(*[run_pipeline(m, language) for m in molecules]))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        results_sorted = sorted(
            results, key=lambda r: r.get("confidence", {}).get("total", 0), reverse=True)
        return jsonify({"results": results_sorted})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/followup", methods=["POST"])
def followup():
    data     = request.get_json()
    question = data.get("question", "").strip()
    context  = data.get("context", {})
    language = data.get("language", "en")
    if not question:
        return jsonify({"error": "No question provided"}), 400
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            answer = loop.run_until_complete(answer_followup(question, context, language))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


async def run_pipeline(molecule, language="en"):
    t0 = time.time()
    print(f"[Pipeline] Starting: {molecule} [{language}]")

    # Stage 1 — 6 agents fire simultaneously
    clinical, patents, market, regulatory, pubmed, mechanism = await asyncio.gather(
        fetch_clinical_trials(molecule),
        fetch_patents(molecule),
        fetch_market_data(molecule),
        fetch_regulatory_data(molecule),
        fetch_pubmed(molecule),
        fetch_mechanism_data(molecule)
    )

    # Stage 2 — Context memory
    clinical_ctx = extract_clinical_context(clinical)
    cross_ctx    = build_synthesis_context(
        molecule, clinical, patents, market, regulatory, pubmed, clinical_ctx)

    # Stage 3 — Confidence scoring
    confidence = compute_confidence(clinical, patents, market, regulatory, mechanism=mechanism, pubmed=pubmed)

    # Stage 4 — AI synthesis via NVIDIA NIM
    report = await synthesize_report(
        molecule, clinical, patents, market, regulatory,
        cross_ctx, mechanism=mechanism, language=language)

    if isinstance(report, dict):
        report["confidence_score"]     = confidence["total"]
        report["confidence_breakdown"] = confidence["breakdown"]
        report["confidence_label"]     = confidence["label"]

    # Stage 5 — Failure analysis
    failure_analysis = analyze_failure_factors(
        molecule, clinical, patents, market, regulatory, report)

    # Stage 6 — Contradiction detection
    contradictions = detect_contradictions(clinical, patents, market, regulatory, report)

    elapsed = round(time.time() - t0, 1)
    print(f"[Pipeline] Done in {elapsed}s: {molecule} [{language}]")

    return {
        "molecule":         molecule,
        "language":         language,
        "clinical":         clinical,
        "patents":          patents,
        "market":           market,
        "regulatory":       regulatory,
        "pubmed":           pubmed,
        "mechanism":        mechanism,
        "report":           report,
        "confidence":       confidence,
        "failure_analysis": failure_analysis,
        "contradictions":   contradictions,
        "clinical_context": clinical_ctx,
        "elapsed_seconds":  elapsed
    }


if __name__ == "__main__":
    key_ok = os.environ.get("NVIDIA_API_KEY", "").startswith("nvapi-")
    print("RepurposeAI starting...")
    print(f"   Provider : NVIDIA NIM")
    print(f"   API key  : {'set' if key_ok else 'NOT SET — replace nvapi-your-key-here in app.py'}")
    port = int(os.environ.get("PORT", 5000))
    print(f"   URL      : http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)

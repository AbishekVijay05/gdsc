from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from flask_cors import CORS
import asyncio, os, time, sys, json

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ── API KEY ─────────────────────────────
# Set it in environment so all modules can access it
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))
except Exception:
    pass

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "nvapi-your-key-here")
os.environ["NVIDIA_API_KEY"] = NVIDIA_API_KEY

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
from modules.conversation_state import (
    create_session, get_session, update_session,
    add_message, get_history, add_constraints, remove_constraint,
    get_constraints, reject_candidate as state_reject_candidate,
    get_rejected, update_agent_status, set_all_agents,
    set_pipeline_running, get_session_summary, cleanup_expired
)
from modules.intent_translator import translate_intent, _fallback_parse

# ── Common herbal/Ayurvedic name → canonical compound mapping ──────────
HERB_NAME_MAP = {
    "turmeric": "Curcumin",
    "curcuma longa": "Curcumin",
    "ashwagandha": "Withaferin A",
    "withania somnifera": "Withaferin A",
    "neem": "Azadirachtin",
    "azadirachta indica": "Azadirachtin",
    "holy basil": "Eugenol",
    "tulsi": "Eugenol",
    "ocimum sanctum": "Eugenol",
    "bacopa": "Bacopamine",
    "brahmi": "Bacopamine",
    "bacopa monnieri": "Bacopamine",
    "centella asiatica": "Asiaticoside",
    "gotu kola": "Asiaticoside",
    "triphala": "Gallic acid",
    "guggul": "Guggulsterone",
    "commiphora wightii": "Guggulsterone",
    "guduchi": "Berberine",
    "tinospora cordifolia": "Berberine",
    "amla": "Gallic acid",
    "emblica officinalis": "Gallic acid",
    "boswellia": "Boswellic acid",
    "boswellia serrata": "Boswellic acid",
    "shankhpushpi": "Scopoletin",
    "safed musli": "Diosgenin",
    "ginger": "Gingerol",
    "zingiber officinale": "Gingerol",
    "long pepper": "Piperine",
    "goldenseal": "Berberine",
    "grape seed": "Resveratrol",
    "red clover": "Genistein",
    "green tea": "Epigallocatechin",
    "licorice": "Glycyrrhizin",
    "fenugreek": "Diosgenin",
    "trigonella foenum": "Diosgenin",
}

def resolve_herb_name(name):
    """Convert common/herbal drug names to canonical compound names for API lookup."""
    return HERB_NAME_MAP.get(name.lower().strip(), name)


# ── Result cache for pipeline outputs ───────────────────────────
_pipeline_cache = {}

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
    molecule = resolve_herb_name(data.get("molecule", "").strip())
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
        import traceback
        traceback.print_exc()
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


# ── CONVERSATIONAL ENDPOINTS ────────────────────────────────────────────────

@app.route("/chat", methods=["POST"])
def chat():
    """Main conversational endpoint — handles all user messages."""
    data       = request.get_json()
    session_id = data.get("session_id", "")
    message    = data.get("message", "").strip()
    language   = data.get("language", "en")

    if not message:
        return jsonify({"error": "No message provided"}), 400

    # Create session if needed
    if not session_id or not get_session(session_id):
        session_id, session = create_session()
    else:
        session = get_session(session_id)

    # Record user message
    add_message(session_id, "user", message)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Use local fallback parser — instant, no LLM API call needed
        intent = _fallback_parse(message)
        # Enrich with session context
        session_constraints = session.get("active_constraints", {})
        rejected_list = [r["drug"] for r in session.get("rejected_candidates", [])]

        # Check if message is rejecting an already-rejected candidate
        for drug in rejected_list:
            if drug.lower() in message.lower():
                # Already rejected — inform user
                add_message(session_id, "assistant", f"{drug} has already been excluded from results.")
                return jsonify({
                    "session_id": session_id,
                    "response_type": "update",
                    "message": f"{drug} has already been excluded from results.",
                    "intent": "reject_candidate",
                    "updated_candidates": [],
                    "active_constraints": list(session_constraints.keys()),
                    "agent_status": session.get("agent_status", {}),
                    "clarification_question": None
                })

        intent_type = intent.get("intent_type", "general_question")
        response_msg = intent.get("response_message", "")
        result = None

        # ── Handle by intent type ───────────────────────────────
        if intent_type == "new_search":
            new_mol = resolve_herb_name(intent.get("new_molecule", message.split()[-1]))
            if not new_mol:
                new_mol = message
            update_session(session_id, {"molecule": new_mol})
            set_pipeline_running(session_id, True)
            set_all_agents(session_id, "searching")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(run_pipeline(
                    new_mol, 
                    language, 
                    session_id=session_id,
                    constraints=session.get("active_constraints"),
                    rejected_candidates=session.get("rejected_candidates")
                ))
            finally:
                loop.close()
                asyncio.set_event_loop(None)

            update_session(session_id, {"last_result": result, "molecule": new_mol})
            set_pipeline_running(session_id, False)
            set_all_agents(session_id, "complete")
            response_msg = intent.get("response_message", f"Analysis complete for {new_mol}.")

            add_message(session_id, "assistant", response_msg)
            return jsonify({
                "session_id": session_id,
                "response_type": "new_candidates",
                "message": response_msg,
                "intent": intent_type,
                "updated_candidates": _extract_candidates(result),
                "active_constraints": list(session.get("active_constraints", {}).keys()),
                "agent_status": session.get("agent_status", {}),
                "full_result": result,
                "clarification_question": None
            })

        elif intent_type == "add_constraint":
            new_constraints = intent.get("new_constraints", {})
            if new_constraints:
                add_constraints(session_id, new_constraints)

            # Re-filter existing results if we have them
            last_result = session.get("last_result")
            if last_result:
                filtered = _apply_constraints_to_result(
                    last_result, session.get("active_constraints", {}),
                    session.get("rejected_candidates", [])
                )
                update_session(session_id, {"last_result": filtered})
                candidates = _extract_candidates(filtered)
            else:
                candidates = []

            add_message(session_id, "assistant", response_msg)
            return jsonify({
                "session_id": session_id,
                "response_type": "update",
                "message": response_msg,
                "intent": intent_type,
                "updated_candidates": candidates,
                "active_constraints": list(get_constraints(session_id).keys()),
                "agent_status": session.get("agent_status", {}),
                "clarification_question": None
            })

        elif intent_type == "reject_candidate":
            for drug in intent.get("rejected_candidates", []):
                state_reject_candidate(session_id, drug, "User rejected")

            # Re-filter
            last_result = session.get("last_result")
            if last_result:
                filtered = _apply_constraints_to_result(
                    last_result, session.get("active_constraints", {}),
                    session.get("rejected_candidates", [])
                )
                update_session(session_id, {"last_result": filtered})
                candidates = _extract_candidates(filtered)
            else:
                candidates = []

            add_message(session_id, "assistant", response_msg)
            return jsonify({
                "session_id": session_id,
                "response_type": "update",
                "message": response_msg,
                "intent": intent_type,
                "updated_candidates": candidates,
                "active_constraints": list(get_constraints(session_id).keys()),
                "rejected_candidates": get_rejected(session_id),
                "agent_status": session.get("agent_status", {}),
                "clarification_question": None
            })

        elif intent_type == "ambiguous":
            clarification_q = intent.get("clarification_question", "Could you be more specific?")
            update_session(session_id, {"pending_clarification": clarification_q})
            add_message(session_id, "assistant", clarification_q)
            return jsonify({
                "session_id": session_id,
                "response_type": "clarification",
                "message": clarification_q,
                "intent": intent_type,
                "active_constraints": list(get_constraints(session_id).keys()),
                "agent_status": session.get("agent_status", {}),
                "clarification_question": clarification_q
            })

        else:  # general_question or clarification
            # Use the existing followup system
            context = session.get("last_result", {})
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                answer = loop.run_until_complete(answer_followup(
                    message,
                    {"molecule": session.get("molecule", ""),
                     "report": context.get("report", {}),
                     "mechanism": context.get("mechanism", {})},
                    language
                ))
            finally:
                loop.close()
                asyncio.set_event_loop(None)

            if session.get("pending_clarification"):
                update_session(session_id, {"pending_clarification": None})

            add_message(session_id, "assistant", answer)
            return jsonify({
                "session_id": session_id,
                "response_type": "answer",
                "message": answer,
                "intent": intent_type,
                "active_constraints": list(get_constraints(session_id).keys()),
                "agent_status": session.get("agent_status", {}),
                "clarification_question": None
            })

    except Exception as e:
        print(f"[Chat error] {e}")
        import traceback; traceback.print_exc()
        add_message(session_id, "assistant", f"Sorry, an error occurred: {str(e)}")
        return jsonify({
            "session_id": session_id,
            "response_type": "error",
            "message": f"Error: {str(e)}",
            "intent": "error"
        }), 500


@app.route("/chat/stream", methods=["POST"])
def chat_stream():
    """Streaming version of /chat — uses SSE to show agent progress in real time."""
    data       = request.get_json()
    session_id = data.get("session_id", "")
    message    = data.get("message", "").strip()
    language   = data.get("language", "en")

    if not message:
        return jsonify({"error": "No message provided"}), 400

    # Create session if needed
    if not session_id or not get_session(session_id):
        session_id, session = create_session()
    else:
        session = get_session(session_id)

    # Record user message
    add_message(session_id, "user", message)

    intent = _fallback_parse(message)
    intent_type = intent.get("intent_type", "general_question")
    response_msg = intent.get("response_message", "")

    # For non-search intents, return immediately (no long pipeline to stream)
    if intent_type != "new_search":
        # Handle same intents as /chat but without streaming
        if intent_type == "add_constraint":
            new_constraints = intent.get("new_constraints", {})
            if new_constraints:
                add_constraints(session_id, new_constraints)
            candidates = []
            if session.get("last_result"):
                filtered = _apply_constraints_to_result(
                    session.get("last_result"), session.get("active_constraints", {}),
                    session.get("rejected_candidates", []))
                update_session(session_id, {"last_result": filtered})
                candidates = _extract_candidates(filtered)
            add_message(session_id, "assistant", response_msg)
            result_json = json.dumps({
                "session_id": session_id, "response_type": "update",
                "message": response_msg, "intent": intent_type,
                "updated_candidates": candidates,
                "active_constraints": list(get_constraints(session_id).keys()),
                "clarification_question": None
            })
            return Response(f"data: {result_json}\n\n", mimetype="text/event-stream")

        elif intent_type == "reject_candidate":
            for drug in intent.get("rejected_candidates", []):
                state_reject_candidate(session_id, drug, "User rejected")
            candidates = []
            if session.get("last_result"):
                filtered = _apply_constraints_to_result(
                    session.get("last_result"), session.get("active_constraints", {}),
                    session.get("rejected_candidates", []))
                update_session(session_id, {"last_result": filtered})
                candidates = _extract_candidates(filtered)
            add_message(session_id, "assistant", response_msg)
            result_json = json.dumps({
                "session_id": session_id, "response_type": "update",
                "message": response_msg, "intent": intent_type,
                "updated_candidates": candidates,
                "active_constraints": list(get_constraints(session_id).keys()),
                "rejected_candidates": get_rejected(session_id),
                "clarification_question": None
            })
            return Response(f"data: {result_json}\n\n", mimetype="text/event-stream")

        elif intent_type == "ambiguous":
            cq = intent.get("clarification_question", "Could you be more specific?")
            update_session(session_id, {"pending_clarification": cq})
            add_message(session_id, "assistant", cq)
            result_json = json.dumps({
                "session_id": session_id, "response_type": "clarification",
                "message": cq, "intent": intent_type,
                "active_constraints": list(get_constraints(session_id).keys()),
                "clarification_question": cq
            })
            return Response(f"data: {result_json}\n\n", mimetype="text/event-stream")

        else:  # general_question
            context = session.get("last_result", {})
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                answer = loop.run_until_complete(answer_followup(
                    message,
                    {"molecule": session.get("molecule", ""),
                     "report": context.get("report", {}),
                     "mechanism": context.get("mechanism", {})},
                    language
                ))
            finally:
                loop.close()
                asyncio.set_event_loop(None)
            add_message(session_id, "assistant", answer)
            result_json = json.dumps({
                "session_id": session_id, "response_type": "answer",
                "message": answer, "intent": intent_type,
                "active_constraints": list(get_constraints(session_id).keys()),
                "clarification_question": None
            })
            return Response(f"data: {result_json}\n\n", mimetype="text/event-stream")

    # ── new_search intent: stream agent progress ──────────────────────
    new_mol = resolve_herb_name(intent.get("new_molecule", message.split()[-1]))
    if not new_mol:
        new_mol = message
    update_session(session_id, {"molecule": new_mol})
    add_message(session_id, "assistant", response_msg)

    def generate():
        queue = []
        set_pipeline_running(session_id, True)

        async def run_with_sse():
            events = queue  # use list as event queue
            nonlocal new_mol, language, session_id
            constraints = session.get("active_constraints")
            rejected_cands = session.get("rejected_candidates")

            async def _sse_emit(agent_name):
                events.append(json.dumps({
                    "type": "agent_complete",
                    "agent": agent_name,
                    "session_id": session_id
                }))

            # Run agents one-by-one so we can emit after each
            agent_map = [
                ("clinical", fetch_clinical_trials(new_mol)),
                ("patents", fetch_patents(new_mol)),
                ("market", fetch_market_data(new_mol)),
                ("regulatory", fetch_regulatory_data(new_mol)),
                ("pubmed", fetch_pubmed(new_mol)),
                ("mechanism", fetch_mechanism_data(new_mol)),
            ]

            results = {}
            for name, coro in agent_map:
                update_agent_status(session_id, name, "searching")
                try:
                    results[name] = await asyncio.wait_for(coro, timeout=8)
                except asyncio.TimeoutError:
                    results[name] = {"error": f"{name} timed out", "source": name}
                except Exception as e:
                    results[name] = {"error": str(e), "source": name}
                update_agent_status(session_id, name, "complete")
                events.append(json.dumps({
                    "type": "agent_complete",
                    "agent": name,
                    "session_id": session_id
                }))

            clinical = results.get("clinical", {})
            patents = results.get("patents", {})
            market = results.get("market", {})
            regulatory = results.get("regulatory", {})
            pubmed = results.get("pubmed", {})
            mechanism = results.get("mechanism", {})

            # Synthesis
            update_agent_status(session_id, "synthesizer", "synthesizing")
            events.append(json.dumps({"type": "agent_start", "agent": "synthesizer", "session_id": session_id}))

            clinical_ctx = extract_clinical_context(clinical)
            cross_ctx = build_synthesis_context(new_mol, clinical, patents, market, regulatory, pubmed, clinical_ctx)
            confidence = compute_confidence(clinical, patents, market, regulatory, mechanism=mechanism, pubmed=pubmed, constraints=constraints, rejected_candidates=rejected_cands)
            report = await synthesize_report(
                new_mol, clinical, patents, market, regulatory,
                cross_ctx, mechanism=mechanism, language=language,
                constraints=constraints, rejected_candidates=rejected_cands)

            if isinstance(report, dict):
                report["confidence_score"] = confidence["total"]
                report["confidence_breakdown"] = confidence["breakdown"]
                report["confidence_label"] = confidence["label"]

            failure_analysis = analyze_failure_factors(new_mol, clinical, patents, market, regulatory, report)
            contradictions = detect_contradictions(clinical, patents, market, regulatory, report)

            update_agent_status(session_id, "synthesizer", "complete")
            events.append(json.dumps({"type": "agent_complete", "agent": "synthesizer", "session_id": session_id}))
            set_pipeline_running(session_id, False)

            result = {
                "molecule": new_mol, "language": language,
                "clinical": clinical, "patents": patents, "market": market,
                "regulatory": regulatory, "pubmed": pubmed, "mechanism": mechanism,
                "report": report, "confidence": confidence,
                "failure_analysis": failure_analysis, "contradictions": contradictions,
                "clinical_context": clinical_ctx,
            }
            _pipeline_cache[(new_mol.lower(), language)] = result
            update_session(session_id, {"last_result": result, "molecule": new_mol})

            final_json = json.dumps({
                "type": "complete",
                "session_id": session_id,
                "response_type": "new_candidates",
                "message": f"Analysis complete for {new_mol}.",
                "updated_candidates": _extract_candidates(result),
                "active_constraints": list(session.get("active_constraints", {}).keys()),
                "agent_status": session.get("agent_status", {}),
                "full_result": result,
                "clarification_question": None
            })
            events.append(final_json)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_with_sse())
        finally:
            loop.close()

        for item in queue:
            yield f"data: {item}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/reject-candidate", methods=["POST"])
def reject_candidate_endpoint():
    """Direct candidate rejection endpoint."""
    data       = request.get_json()
    session_id = data.get("session_id", "")
    drug_name  = data.get("drug_name", "").strip()
    reason     = data.get("reason", "User rejected")

    if not session_id or not get_session(session_id):
        return jsonify({"error": "Invalid session"}), 400
    if not drug_name:
        return jsonify({"error": "No drug name provided"}), 400

    state_reject_candidate(session_id, drug_name, reason)
    session = get_session(session_id)

    # Re-filter results
    last_result = session.get("last_result")
    candidates = []
    if last_result:
        filtered = _apply_constraints_to_result(
            last_result, session.get("active_constraints", {}),
            session.get("rejected_candidates", [])
        )
        update_session(session_id, {"last_result": filtered})
        candidates = _extract_candidates(filtered)

    return jsonify({
        "status": "ok",
        "active_constraints": list(get_constraints(session_id).keys()),
        "rejected_candidates": get_rejected(session_id),
        "remaining_candidates": candidates
    })


@app.route("/session/<session_id>")
def session_status(session_id):
    """Get session state for polling (agent activity feed)."""
    summary = get_session_summary(session_id)
    if summary is None:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(summary)


@app.route("/remove-constraint", methods=["POST"])
def remove_constraint_endpoint():
    """Remove a constraint and optionally re-filter results."""
    data       = request.get_json()
    session_id = data.get("session_id", "")
    key        = data.get("constraint_key", "")

    if not session_id or not get_session(session_id):
        return jsonify({"error": "Invalid session"}), 400
    if not key:
        return jsonify({"error": "No constraint key"}), 400

    remaining = remove_constraint(session_id, key)
    session = get_session(session_id)

    # Re-filter
    last_result = session.get("last_result")
    candidates = []
    if last_result:
        filtered = _apply_constraints_to_result(
            last_result, session.get("active_constraints", {}),
            session.get("rejected_candidates", [])
        )
        update_session(session_id, {"last_result": filtered})
        candidates = _extract_candidates(filtered)

    return jsonify({
        "status": "ok",
        "active_constraints": list(remaining.keys()),
        "remaining_candidates": candidates
    })


# ── HELPER FUNCTIONS ────────────────────────────────────────────────────────

async def _safe(coro, name):
    """Wrap a coroutine with a timeout — if it fails, return error dict instead of hanging."""
    try:
        return await asyncio.wait_for(coro, timeout=8)
    except asyncio.TimeoutError:
        print(f"[Pipeline] {name} timed out, skipping")
        return {"error": f"{name} timed out", "source": name}
    except Exception as e:
        print(f"[Pipeline] {name} failed: {e}")
        return {"error": str(e), "source": name}


@app.route("/clear-cache", methods=["POST"])
def clear_cache():
    global _pipeline_cache
    count = len(_pipeline_cache)
    _pipeline_cache = {}
    return jsonify({"cleared": count})

def _extract_candidates(result):
    """Extract candidate list from pipeline result for chat responses."""
    if not result or not isinstance(result, dict):
        return []
    report = result.get("report", {})
    if not isinstance(report, dict):
        return []
    opps = report.get("repurposing_opportunities", [])
    return [{
        "disease": o.get("disease", "Unknown"),
        "description": o.get("description", ""),
        "confidence": o.get("confidence", "INVESTIGATE"),
        "confidence_score": o.get("confidence_score", 0),
        "biological_rationale": o.get("biological_rationale", ""),
        "patent_status": o.get("patent_status", "Unknown"),
        "trial_id": o.get("trial_id"),
        "trial_phase": o.get("trial_phase"),
        "source": o.get("source", ""),
    } for o in opps if o.get("disease", "").lower() not in ["demo mode — add nvidia api key"]]


def _apply_constraints_to_result(result, constraints, rejected_candidates):
    """Filter pipeline results based on active constraints and rejections."""
    if not result or not isinstance(result, dict):
        return result

    result = dict(result)  # shallow copy
    report = result.get("report", {})
    if not isinstance(report, dict):
        return result

    report = dict(report)
    opps = report.get("repurposing_opportunities", [])

    rejected_names = [r["drug"].lower() for r in rejected_candidates] if rejected_candidates else []

    filtered_opps = []
    for opp in opps:
        disease = (opp.get("disease", "") or "").lower()
        desc = (opp.get("description", "") or "").lower()
        bio = (opp.get("biological_rationale", "") or "").lower()
        combined = disease + " " + desc + " " + bio

        # Skip rejected candidates
        if any(name in disease for name in rejected_names):
            continue

        # Apply constraint filters
        skip = False
        for key, val in (constraints or {}).items():
            if key == "exclude_cardiovascular_toxicity" and val:
                if any(w in combined for w in ["cardio", "heart", "cardiac", "cardiovascular"]):
                    skip = True
            elif key == "require_bbb_crossing" and val:
                if "brain" not in combined and "neuro" not in combined and "cns" not in combined:
                    skip = True
            elif key == "exclude_high_toxicity" and val:
                if any(w in combined for w in ["toxic", "toxicity", "severe"]):
                    skip = True
            elif key == "prefer_patent_free" and val:
                patent_status = (opp.get("patent_status", "") or "").lower()
                if "protected" in patent_status:
                    skip = True
        if not skip:
            filtered_opps.append(opp)

    report["repurposing_opportunities"] = filtered_opps
    result["report"] = report
    return result


async def run_pipeline(molecule, language="en", session_id=None, constraints=None, rejected_candidates=None):
    t0 = time.time()
    cache_key = (molecule.lower(), language)

    # Check result cache — returns instantly if already analyzed
    if cache_key in _pipeline_cache:
        print(f"[Pipeline] Cache hit: {molecule} [{language}]")
        return _pipeline_cache[cache_key]

    print(f"[Pipeline] Starting: {molecule} [{language}]")

    # Update agent statuses if session exists
    if session_id:
        update_agent_status(session_id, "clinical", "searching")
        update_agent_status(session_id, "patents", "searching")
        update_agent_status(session_id, "market", "searching")
        update_agent_status(session_id, "regulatory", "searching")
        update_agent_status(session_id, "pubmed", "searching")
        update_agent_status(session_id, "mechanism", "searching")
    update_agent_status(session_id, "synthesizer", "idle")

    # Stage 1 — 6 agents fire simultaneously with individual timeouts
    clinical, patents, market, regulatory, pubmed, mechanism = await asyncio.gather(
        _safe(fetch_clinical_trials(molecule), "Clinical"),
        _safe(fetch_patents(molecule), "Patents"),
        _safe(fetch_market_data(molecule), "Market"),
        _safe(fetch_regulatory_data(molecule), "Regulatory"),
        _safe(fetch_pubmed(molecule), "PubMed"),
        _safe(fetch_mechanism_data(molecule), "Mechanism"),
    )

    if session_id:
        update_agent_status(session_id, "clinical", "complete")
        update_agent_status(session_id, "patents", "complete")
        update_agent_status(session_id, "market", "complete")
        update_agent_status(session_id, "regulatory", "complete")
        update_agent_status(session_id, "pubmed", "complete")
        update_agent_status(session_id, "mechanism", "complete")
        update_agent_status(session_id, "synthesizer", "synthesizing")

    # Stage 2 — Context memory
    clinical_ctx = extract_clinical_context(clinical)
    cross_ctx    = build_synthesis_context(
        molecule, clinical, patents, market, regulatory, pubmed, clinical_ctx)

    # Stage 3 — Confidence scoring
    confidence = compute_confidence(clinical, patents, market, regulatory, mechanism=mechanism, pubmed=pubmed, constraints=constraints, rejected_candidates=rejected_candidates)

    # Stage 4 — AI synthesis via NVIDIA NIM
    report = await synthesize_report(
        molecule, clinical, patents, market, regulatory,
        cross_ctx, mechanism=mechanism, language=language,
        constraints=constraints, rejected_candidates=rejected_candidates)

    if isinstance(report, dict):
        report["confidence_score"]     = confidence["total"]
        report["confidence_breakdown"] = confidence["breakdown"]
        report["confidence_label"]     = confidence["label"]

    # Stage 5 — Failure analysis
    failure_analysis = analyze_failure_factors(
        molecule, clinical, patents, market, regulatory, report)

    # Stage 6 — Contradiction detection
    contradictions = detect_contradictions(clinical, patents, market, regulatory, report)

    if session_id:
        update_agent_status(session_id, "synthesizer", "complete")

    elapsed = round(time.time() - t0, 1)
    print(f"[Pipeline] Done in {elapsed}s: {molecule} [{language}]")

    result = {
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

    # Cache result for instant repeat lookups
    _pipeline_cache[cache_key] = result
    return result


if __name__ == "__main__":
    key_ok = os.environ.get("NVIDIA_API_KEY", "").startswith("nvapi-")
    print("RepurposeAI starting...")
    print(f"   Provider : NVIDIA NIM")
    print(f"   API key  : {'set' if key_ok else 'NOT SET — replace nvapi-your-key-here in app.py'}")
    port = int(os.environ.get("PORT", 5000))
    print(f"   URL      : http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)

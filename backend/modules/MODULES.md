# Backend Modules

Directory of the repurposing analysis pipeline. 18 `.py` files organised into five layers.

## Data Fetchers (external APIs)

| File | Purpose | API Source |
|---|---|---|
| **clinical.py** | Fetches clinical trials for a drug molecule (trial ID, phase, status, conditions, sponsor) | ClinicalTrials.gov API v2 |
| **pubmed.py** | Searches for published papers on drug repurposing for a molecule (title, authors, journal, year) | PubMed E-utilities (NCBI) |
| **patents.py** | Gets compound info (formula, weight, IUPAC) and associated patent IDs | PubChem + Google Patents |
| **market.py** | Fetches drug products, manufacturers, dosage forms, and adverse event count as a usage proxy | OpenFDA (NDC + Event APIs) |
| **regulatory.py** | Gets FDA label data: approved indications, warnings, contraindications, application numbers | OpenFDA Drug Label API |
| **mechanism.py** | Fetches molecular properties, pharmacology, biological targets, and Lipinski drug-likeness score from PubChem | PubChem PUG REST API |

## Biological Intelligence

| File | Purpose |
|---|---|
| **overlap_engine.py** | Core mechanism layer — extracts drug pathways from mechanism text and biological targets, finds disease pathways from a curated knowledge base, computes biological plausibility via pathway intersection (drug targets ∩ disease pathways). Identifies top repurposing candidates not already in current indications. |
| **target_overlap.py** | Mechanism intelligence layer — fetches molecular targets from ChEMBL, infers pathways from mechanism text, maps pathways to diseases via a curated `PATHWAY_DISEASE_MAP`. Produces pathway-disease biological signals with strength ratings. |
| **similarity_engine.py** | Drug similarity engine — classifies a drug into a known class (NSAID, statin, SSRI, etc.), finds class siblings and their known repurposings, generates candidate diseases based on shared mechanisms, and fetches structurally similar compounds from PubChem 2D fingerprint. |
| **similarity.py** | Simpler similarity engine — finds class siblings via `DRUG_CLASSES`, known successful repurposings for validation framing, and structurally similar compounds from PubChem. Used for candidate generation and validation. |

## Hypothesis Generation

| File | Purpose |
|---|---|
| **hypothesis_generator.py** | **Disease-first mode** — input a disease, output drugs with strong pathway overlap but no major trials. Uses a curated list of 25 well-known drugs with established mechanisms, computes overlap scores, and generates an AI narrative (via OpenRouter/Claude) explaining the biological logic. |
| **hypothesis.py** | Another disease-first engine with a smaller drug/pathway database. Scores candidates by pathway overlap, uses AI (OpenRouter) to generate a 2–3 sentence scientific hypothesis. Simpler/lighter alternative to `hypothesis_generator.py`. |

## Synthesis & Scoring

| File | Purpose |
|---|---|
| **scorer.py** | Multi-dimensional confidence score (0–100): **Biological** (25), **Clinical** (30), **Literature** (15), **Safety** (15), **Novelty** (15). Each dimension has sub-scoring with explanations. Produces label: HIGH / MODERATE / LOW CONFIDENCE or INSUFFICIENT DATA. |
| **synthesizer.py** | AI report synthesizer — takes all domain data and feeds it to NVIDIA's Llama 70B to generate a comprehensive JSON repurposing analysis: executive summary, biological possibility statement, opportunities, negative cases, strategic recommendation, evidence card, risks, and a "why not pursued" analysis. Falls back to a mock report if no API key is configured. |

## Cross-cutting Analysis

| File | Purpose |
|---|---|
| **context_memory.py** | Context continuity layer — extracts signals from clinical results (conditions, phases, sponsors) and passes them to market/regulatory for targeted follow-up. Builds a rich cross-domain context string for the synthesizer so AI reasons across all domains. |
| **contradiction.py** | Detects conflicts between domains — e.g., clinical shows strong evidence but market shows no activity, or AI says PURSUE but FDA has warnings. Returns typed flags with severity levels: warning, danger, info. |
| **failure_analysis.py** | Answers "why hasn't this been pursued?" — analyses barriers (terminated trials, black box warnings, patent walls), risks, opportunities (rare disease, late-stage evidence), computes a viability score with verdict: VIABLE / PROCEED WITH CAUTION / HIGH BARRIERS. |
| **followup.py** | Interactive Q&A — takes follow-up questions about a generated report and answers them using NVIDIA's Llama 70B with full report context. Supports 9 languages (English, Tamil, Hindi, Telugu, French, Spanish, German, Chinese, Arabic, Portuguese). |

## Pipeline Flow

```
Molecule input
   │
   ├──→ clinical.py ──────┐
   ├──→ pubmed.py ────────┤
   ├──→ patents.py ───────┤
   ├──→ market.py ────────┤   ← context_memory.py threads context
   ├──→ regulatory.py ────┤
   └──→ mechanism.py ─────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   overlap_engine.py   similarity_engine.py   scorer.py
   target_overlap.py   similarity.py         (multi-dim score)
          │                   │
          └────────┬──────────┘
                   ▼
          synthesizer.py ────→ full JSON report
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
  contradiction  failure   followup
  .py           analysis   .py
                 .py
```

# 🧬 RepurposeAI — Drug Repurposing Intelligence Platform

An autonomous AI research platform that finds drug repurposing opportunities by orchestrating 4 research agents simultaneously across clinical, patent, market and regulatory domains.

---

## 🚀 How to run (3 steps)

### Step 1 — Get your free API key
Go to https://console.anthropic.com → sign up → create API key → copy it

### Step 2 — Add your API key
Open the `.env` file and replace `your_api_key_here` with your actual key:
```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
```

### Step 3 — Run the app

**Mac/Linux:**
```bash
chmod +x run.sh
./run.sh
```

**Windows:**
Double-click `run.bat`

**Or manually:**
```bash
pip install -r requirements.txt
cd backend
python app.py
```

Then open your browser at: **http://localhost:5000**

---

## 📁 Project structure

```
drug-repurposing-platform/
├── backend/
│   ├── app.py                  ← Main Flask server
│   └── modules/
│       ├── clinical.py         ← ClinicalTrials.gov API
│       ├── patents.py          ← PubChem / Google Patents
│       ├── market.py           ← OpenFDA market data
│       ├── regulatory.py       ← FDA drug labels
│       └── synthesizer.py      ← Claude AI synthesis
├── frontend/
│   ├── templates/index.html    ← Main page
│   └── static/
│       ├── css/style.css       ← All styling
│       └── js/main.js          ← All frontend logic
├── .env                        ← Your API keys (never share this)
├── requirements.txt            ← Python dependencies
├── run.sh                      ← Mac/Linux starter
└── run.bat                     ← Windows starter
```

---

## 🎯 Demo drugs to try

| Drug | Why it's good for demo |
|------|----------------------|
| **Aspirin** | Huge data, well-known repurposing history |
| **Metformin** | Active cancer repurposing research |
| **Sildenafil** | Famous repurposing story (heart → Viagra) |
| **Thalidomide** | Controversial repurposing history |
| **Ibuprofen** | Rich regulatory and market data |

---

## 🔧 No API key? No problem

The app works WITHOUT an API key — it will still:
- ✅ Fetch real data from ClinicalTrials.gov
- ✅ Fetch real patent data from PubChem
- ✅ Fetch real market data from OpenFDA
- ✅ Fetch real regulatory data from FDA

It will show a demo/placeholder for the AI synthesis section only.

---

## 📊 Data sources used

| Module | Source | API |
|--------|--------|-----|
| Clinical | ClinicalTrials.gov | Free, no key |
| Patents | PubChem NCBI | Free, no key |
| Market | OpenFDA NDC | Free, no key |
| Regulatory | OpenFDA Labels | Free, no key |
| Synthesis | Anthropic Claude | Free tier available |

---

Built for the Developer Student Community Hackathon 2025

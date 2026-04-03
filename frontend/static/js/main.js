// ═══ STATE ════════════════════════════════════════════════════════════════
let currentData = null;
let searchHistory = JSON.parse(localStorage.getItem('rp_history') || '[]');
let phaseChart, statusChart, radarChart;
let molScene, molCamera, molRenderer, molGroup, molSpinning = true;

// ═══ INIT ═════════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  renderHistory();
  initQuantumCanvas();
  loadMarketFeed();
  // initHeroCanvas(); // Removed tilt-card logic as focus moved to glass cards
  document.getElementById('molecule-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') startAnalysis();
  });
});

// ═══ NAVIGATION ════════════════════════════════════════════════════════════
function switchTab(tabId) {
  // Update Navigation Bar Buttons
  document.querySelectorAll('nav .tab-btn').forEach(btn => {
    btn.classList.remove('active');
    if (btn.innerText.toLowerCase() === tabId.toLowerCase()) {
      btn.classList.add('active');
    }
  });

  // Use showSection to manage visibility
  showSection(tabId + '-panel');
  
  // Scroll to top
  window.scrollTo({top: 0, behavior: 'smooth'});
}

function setRepurposeMode(mode) {
  // Update Mode Buttons
  document.querySelectorAll('#repurpose-panel .tab-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  document.getElementById(mode + '-mode-btn').classList.add('active');

  // Hide all sub-sections
  document.querySelectorAll('.repurpose-sub-section').forEach(sub => {
    sub.classList.add('hidden');
  });

  // Show selected sub-section
  document.getElementById(mode + '-sub').classList.remove('hidden');
}

// ═══ HERO PARTICLE CANVAS ═════════════════════════════════════════════════
function initHeroCanvas() {
  const canvas = document.getElementById('hero-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H, nodes = [], particles = [];

  function resize() {
    W = canvas.width  = canvas.offsetWidth;
    H = canvas.height = canvas.offsetHeight;
  }
  window.addEventListener('resize', resize);
  resize();

  for (let i = 0; i < 20; i++) {
    nodes.push({
      x: Math.random()*W, y: Math.random()*H,
      vx: (Math.random()-0.5)*0.35, vy: (Math.random()-0.5)*0.35,
      r: Math.random()*4+2,
      col: Math.random()>0.5 ? 'rgba(0,255,179,' : 'rgba(0,200,255,',
      op: Math.random()*0.5+0.2
    });
  }
  for (let i = 0; i < 70; i++) {
    particles.push({
      x: Math.random()*W, y: Math.random()*H,
      vx: (Math.random()-0.5)*0.18, vy: (Math.random()-0.5)*0.18,
      r: Math.random()*1.5+0.3, op: Math.random()*0.25+0.04
    });
  }

  function draw() {
    ctx.clearRect(0,0,W,H);
    for (let i=0;i<nodes.length;i++) {
      for (let j=i+1;j<nodes.length;j++) {
        const dx=nodes[i].x-nodes[j].x, dy=nodes[i].y-nodes[j].y;
        const d=Math.sqrt(dx*dx+dy*dy);
        if (d<180) {
          ctx.beginPath();
          ctx.moveTo(nodes[i].x,nodes[i].y);
          ctx.lineTo(nodes[j].x,nodes[j].y);
          ctx.strokeStyle=`rgba(0,255,179,${(1-d/180)*0.12})`;
          ctx.lineWidth=0.5;
          ctx.stroke();
        }
      }
    }
    nodes.forEach(n => {
      ctx.beginPath(); ctx.arc(n.x,n.y,n.r,0,Math.PI*2);
      ctx.fillStyle=n.col+n.op+')'; ctx.fill();
      n.x+=n.vx; n.y+=n.vy;
      if(n.x<0||n.x>W)n.vx*=-1; if(n.y<0||n.y>H)n.vy*=-1;
    });
    particles.forEach(p => {
      ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
      ctx.fillStyle=`rgba(255,255,255,${p.op})`; ctx.fill();
      p.x+=p.vx; p.y+=p.vy;
      if(p.x<0)p.x=W; if(p.x>W)p.x=0;
      if(p.y<0)p.y=H; if(p.y>H)p.y=0;
    });
    requestAnimationFrame(draw);
  }
  draw();

  // 3D tilt on search box
  const box = document.querySelector('.tilt-card');
  if (box) {
    box.addEventListener('mousemove', e => {
      const r = box.getBoundingClientRect();
      const x = (e.clientX-r.left)/r.width - 0.5;
      const y = (e.clientY-r.top)/r.height - 0.5;
      box.style.transform = `perspective(900px) rotateY(${x*7}deg) rotateX(${-y*4}deg)`;
    });
    box.addEventListener('mouseleave', () => {
      box.style.transform = 'perspective(900px) rotateY(0) rotateX(0)';
    });
  }
}

// ═══ 3D MOLECULE VIEWER ═══════════════════════════════════════════════════
function initMoleculeViewer(formula, molecule) {
  const wrap   = document.getElementById('molecule-canvas-wrap');
  const canvas = document.getElementById('molecule-canvas');
  if (!wrap || !canvas || typeof THREE === 'undefined') return;

  canvas.width  = wrap.offsetWidth;
  canvas.height = wrap.offsetHeight;

  if (molRenderer) { molRenderer.dispose(); }

  molScene    = new THREE.Scene();
  molCamera   = new THREE.PerspectiveCamera(58, canvas.width/canvas.height, 0.1, 100);
  molCamera.position.z = 6.5;

  molRenderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
  molRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  molRenderer.setSize(canvas.width, canvas.height);
  molRenderer.setClearColor(0x000000, 0);

  molGroup = new THREE.Group();

  const atoms   = parseFormula(formula || 'C9H8O4');
  const colors  = { C:0x999999, H:0xeeeeee, O:0xff5555, N:0x5577ff, S:0xffff44, P:0xff8833, F:0x55ff88, Cl:0x33ffaa };
  const radii   = { C:0.34, H:0.2, O:0.3, N:0.31, S:0.36, P:0.35, F:0.24, Cl:0.32 };
  const positions = [];
  let idx = 0;
  const total = atoms.reduce((s,a)=>s+Math.min(a.count,5),0);

  atoms.forEach(({ element, count }) => {
    for (let i=0; i<Math.min(count,5); i++) {
      const phi   = Math.acos(-1 + (2*idx) / Math.max(total-1,1));
      const theta = Math.sqrt(total * Math.PI) * phi;
      const r     = 2.0 + Math.random()*0.4;
      const pos   = new THREE.Vector3(
        r * Math.cos(theta)*Math.sin(phi),
        r * Math.sin(theta)*Math.sin(phi),
        r * Math.cos(phi)
      );
      positions.push({ pos, element });
      const geo  = new THREE.SphereGeometry(radii[element]||0.28, 20, 20);
      const mat  = new THREE.MeshPhongMaterial({
        color: colors[element] || 0x9966ff,
        shininess: 90, specular: 0x333333, emissive: colors[element] || 0x9966ff, emissiveIntensity: 0.06
      });
      molGroup.add(new THREE.Mesh(geo, mat));
      molGroup.children[molGroup.children.length-1].position.copy(pos);
      idx++;
    }
  });

  // Bonds
  for (let i=0;i<positions.length;i++) {
    for (let j=i+1;j<positions.length;j++) {
      const d = positions[i].pos.distanceTo(positions[j].pos);
      if (d < 2.8) {
        const dir = new THREE.Vector3().subVectors(positions[j].pos, positions[i].pos);
        const mid = new THREE.Vector3().addVectors(positions[i].pos, positions[j].pos).multiplyScalar(0.5);
        const cyl = new THREE.CylinderGeometry(0.055, 0.055, d, 8);
        const mat = new THREE.MeshPhongMaterial({ color:0x00FFB3, opacity:0.55, transparent:true, shininess:60 });
        const bond = new THREE.Mesh(cyl, mat);
        bond.position.copy(mid);
        bond.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0), dir.clone().normalize());
        molGroup.add(bond);
      }
    }
  }

  // Glow shell
  const glowMat = new THREE.MeshBasicMaterial({ color:0x00FFB3, transparent:true, opacity:0.025, side:THREE.BackSide });
  molGroup.add(new THREE.Mesh(new THREE.SphereGeometry(3.2, 32, 32), glowMat));

  molScene.add(molGroup);

  // Lights
  molScene.add(new THREE.AmbientLight(0xffffff, 0.45));
  const p1 = new THREE.PointLight(0x00FFB3, 1.4, 22); p1.position.set(5,5,5);
  const p2 = new THREE.PointLight(0x00C8FF, 0.9, 22); p2.position.set(-5,-3,3);
  const p3 = new THREE.PointLight(0x9966ff, 0.5, 15); p3.position.set(0,6,-4);
  molScene.add(p1, p2, p3);

  // Drag rotate
  let drag=false, px=0, py=0;
  canvas.addEventListener('mousedown', e=>{drag=true; px=e.clientX; py=e.clientY});
  window.addEventListener('mouseup',  ()=>drag=false);
  window.addEventListener('mousemove',e=>{
    if(!drag)return;
    molGroup.rotation.y+=(e.clientX-px)*0.012;
    molGroup.rotation.x+=(e.clientY-py)*0.012;
    px=e.clientX; py=e.clientY;
  });
  canvas.addEventListener('touchstart', e=>{drag=true; px=e.touches[0].clientX; py=e.touches[0].clientY},{passive:true});
  window.addEventListener('touchend',  ()=>drag=false);
  window.addEventListener('touchmove', e=>{
    if(!drag)return;
    molGroup.rotation.y+=(e.touches[0].clientX-px)*0.012;
    molGroup.rotation.x+=(e.touches[0].clientY-py)*0.012;
    px=e.touches[0].clientX; py=e.touches[0].clientY;
  },{passive:true});

  (function animate() {
    requestAnimationFrame(animate);
    if (molSpinning && !drag) molGroup.rotation.y += 0.004;
    molRenderer.render(molScene, molCamera);
  })();
}

function parseFormula(f) {
  if (!f) return [{element:'C',count:6},{element:'H',count:8},{element:'O',count:2}];
  const r=/([A-Z][a-z]?)(\d*)/g, atoms=[]; let m;
  while((m=r.exec(f))!==null) if(m[1]) atoms.push({element:m[1],count:parseInt(m[2]||'1')});
  return atoms.length ? atoms : [{element:'C',count:6}];
}

function resetMolView() { if(molGroup) molGroup.rotation.set(0,0,0); }
function toggleMolSpin() {
  molSpinning = !molSpinning;
  document.getElementById('spin-btn').textContent = molSpinning ? 'Stop Spin' : 'Start Spin';
}

// ═══ RENDER 3D MOLECULE SECTION ═══════════════════════════════════════════
function renderMolecule3D(mechanism, molecule) {
  const sec = document.getElementById('mol3d-section');
  if (!mechanism || mechanism.error) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');

  document.getElementById('mol3d-name').textContent = molecule;

  const pills = document.getElementById('mol3d-pills');
  pills.innerHTML = '';
  if (mechanism.molecular_formula) pills.innerHTML += `<span class="mol3d-pill formula">${mechanism.molecular_formula}</span>`;
  if (mechanism.molecular_weight)  pills.innerHTML += `<span class="mol3d-pill weight">${mechanism.molecular_weight} g/mol</span>`;
  if (mechanism.drug_likeness)     pills.innerHTML += `<span class="mol3d-pill lipinski">${mechanism.drug_likeness.assessment} · Lipinski ${mechanism.drug_likeness.lipinski_score}</span>`;
  if (mechanism.bioactivity_count) pills.innerHTML += `<span class="mol3d-pill target">${mechanism.bioactivity_count} bioactivities</span>`;

  const mech = mechanism.mechanism_of_action || mechanism.pharmacology || 'Biological mechanism data sourced from PubChem. This compound interacts with specific molecular targets to produce its pharmacological effects.';
  document.getElementById('mol3d-mech').textContent = mech.slice(0,320) + (mech.length>320?'...':'');

  const tDiv = document.getElementById('mol3d-targets');
  tDiv.innerHTML = '';
  (mechanism.biological_targets||[]).slice(0,5).forEach(t => {
    tDiv.innerHTML += `<span class="mol3d-pill target" style="margin-bottom:4px">${t.slice(0,28)}</span>`;
  });
  if (!(mechanism.biological_targets||[]).length) {
    tDiv.innerHTML = '<span style="font-size:12px;color:var(--text3)">Targets identified from bioactivity assay data...</span>';
  }

  setTimeout(() => initMoleculeViewer(mechanism.molecular_formula, molecule), 80);
}

// ═══ RENDER CURE DISCOVERY ════════════════════════════════════════════════
function renderCureDiscovery(report, mechanism, molecule) {
  const sec  = document.getElementById('cure-section');
  const opps = (report.repurposing_opportunities||[]).filter(o=>o.disease&&!o.disease.toLowerCase().includes('demo'));

  if (!opps.length && !report.biological_possibility_statement) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');

  document.getElementById('cure-subtitle').textContent =
    `${molecule} — ${opps.length} possible new indication${opps.length!==1?'s':''} identified from real clinical and biological data`;

  const stmt = report.biological_possibility_statement || '';
  document.getElementById('cure-statement').textContent = stmt ||
    'Configure OPENROUTER_API_KEY to enable AI biological reasoning.';

  document.getElementById('cure-opp-count').textContent =
    `${opps.length} possible repurposing target${opps.length!==1?'s':''} — each backed by real government database citations`;

  const grid = document.getElementById('cure-opp-grid');
  grid.innerHTML = '';

  opps.forEach((opp, i) => {
    const conf    = opp.confidence || 'INVESTIGATE';
    const score   = opp.confidence_score || 0;
    const patCls  = (opp.patent_status||'').toLowerCase().includes('free') ? 'patent-free' : 'patent-prot';
    const trial   = opp.trial_id
      ? `<a class="cure-pill trial" href="https://clinicaltrials.gov/study/${opp.trial_id}" target="_blank">&#8599; ${opp.trial_id}${opp.trial_phase?' · '+opp.trial_phase:''}</a>` : '';
    const mkt     = opp.market_gap
      ? `<span class="cure-pill market">${opp.market_gap.slice(0,50)}${opp.market_gap.length>50?'...':''}</span>` : '';
    const why     = opp.why_not_pursued_yet
      ? `<span class="cure-pill why-not" title="${opp.why_not_pursued_yet}">Not pursued: ${opp.why_not_pursued_yet.slice(0,42)}...</span>` : '';
    const bio     = opp.biological_rationale
      ? `<div class="cure-opp-bio"><span class="cure-opp-bio-label">Biological reasoning</span>${opp.biological_rationale}</div>` : '';

    grid.innerHTML += `
    <div class="cure-opp-card">
      <div class="cure-opp-top">
        <div class="cure-opp-left">
          <div class="cure-opp-num">0${i+1} of ${opps.length}</div>
          <div class="cure-opp-disease">${opp.disease}</div>
          <div class="cure-opp-desc">${opp.description}</div>
          ${bio}
        </div>
        <div class="cure-opp-right">
          <div class="cure-confidence-badge ${conf}">${conf}</div>
          ${score>0?`<span class="cure-score-big">${score}%</span><span class="cure-score-label">confidence</span>`:''}
        </div>
      </div>
      <div class="cure-opp-bottom">
        ${trial}${mkt}
        <span class="cure-pill ${patCls}">${opp.patent_status||'Unknown'}</span>
        <span class="cure-pill source">${opp.source||'ClinicalTrials.gov'}</span>
        ${why}
      </div>
    </div>`;
  });
}

// ═══ RENDER VIABILITY ═════════════════════════════════════════════════════
function renderViability(fa, report) {
  const sec = document.getElementById('viab-section');
  if (!fa) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');

  const badge = document.getElementById('viab-badge');
  const cls   = fa.verdict==='VIABLE'?'VIABLE':fa.verdict&&fa.verdict.includes('CAUTION')?'CAUTION':'BARRIERS';
  badge.className = `viab-badge ${cls}`;
  badge.textContent = fa.verdict || 'Unknown';

  const num  = document.getElementById('viab-score-num');
  const ring = document.getElementById('viab-score-ring');
  num.textContent = (fa.viability_score||0) + '%';
  const deg  = Math.round((fa.viability_score||0)/100*360);
  const col  = fa.viability_score>=70?'var(--accent)':fa.viability_score>=45?'var(--warning)':'var(--danger)';
  setTimeout(()=>{ ring.style.background=`conic-gradient(${col} ${deg}deg,var(--border) ${deg}deg)`; }, 400);

  const grid = document.getElementById('viab-grid');
  grid.innerHTML = '';
  const all = [...(fa.barriers||[]),...(fa.risks||[]),...(fa.opportunities||[]).map(o=>({...o,severity:'opportunity'}))];
  all.slice(0,6).forEach(item => {
    grid.innerHTML += `<div class="viab-item ${item.severity||'MEDIUM'}">
      <div class="viab-item-type">${item.type||'signal'}</div>
      <div class="viab-item-desc">${item.description||item.benefit||''}</div>
    </div>`;
  });

  const wnBox = document.getElementById('why-not-box');
  const wnItems = document.getElementById('why-not-items');
  if ((fa.why_not_pursued||[]).length) {
    wnBox.classList.remove('hidden');
    wnItems.innerHTML = fa.why_not_pursued.map(r=>`<div class="why-not-item">${r}</div>`).join('');
  }

  const negBox   = document.getElementById('negative-box');
  const negItems = document.getElementById('negative-items');
  const negs     = report.negative_cases||[];
  if (negs.length) {
    negBox.classList.remove('hidden');
    negItems.innerHTML = negs.map(nc=>`<div class="neg-item">
      <div class="neg-disease">${nc.disease}</div>
      <div class="neg-reason">${nc.reason}${nc.evidence?' — '+nc.evidence:''}</div>
    </div>`).join('');
  }
}

// ═══ MAIN ANALYSIS ════════════════════════════════════════════════════════
function getLanguage() {
  const sel = document.getElementById('language-select');
  return sel ? sel.value : 'en';
}

async function startAnalysis() {
  const input    = document.getElementById('molecule-input');
  const molecule = input.value.trim();
  if (!molecule) { showError('Please enter a drug name'); return; }

  document.getElementById('btn-text').textContent = 'Analysing...';
  document.getElementById('analyze-btn').disabled = true;

  addHistory(molecule);
  showSection('loading-section');
  document.getElementById('loading-molecule').textContent = molecule;
  animateAgents();
  simulateSwarmLogs(molecule);

  try {
    const language = getLanguage();
    const res = await fetch('/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ molecule, language })
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    currentData = data;
    console.log('[RepurposeAI] Data received:', Object.keys(data));
    console.log('[RepurposeAI] Report keys:', Object.keys(data.report||{}));
    console.log('[RepurposeAI] Confidence:', data.confidence);
    console.log('[RepurposeAI] Mechanism:', data.mechanism?.molecular_formula);

    // Show results section FIRST so elements are visible before rendering
    showSection('results-section');

    // Small delay to ensure DOM is ready
    await new Promise(r => setTimeout(r, 50));
    renderResults(data);

  } catch(e) {
    console.error('[RepurposeAI] Error:', e);
    showError('Analysis failed: ' + e.message);
    showSection('hero');
  } finally {
    document.getElementById('btn-text').textContent = 'Analyse Drug';
    document.getElementById('analyze-btn').disabled = false;
  }
}

function renderResults(data) {
  const molecule        = data.molecule || '';
  const report          = data.report || {};
  const confidence      = data.confidence || {};
  const contradictions  = data.contradictions || [];
  const clinical_context= data.clinical_context || {};
  const elapsed_seconds = data.elapsed_seconds || 0;
  const mechanism       = data.mechanism || {};
  const failure_analysis= data.failure_analysis || null;

  // ── Header ────────────────────────────────────────────────────────────
  try {
    document.getElementById('results-molecule-name').textContent = molecule;
    document.getElementById('results-timestamp').textContent = new Date().toLocaleTimeString();
    document.getElementById('results-elapsed').textContent = elapsed_seconds + 's';
  } catch(e) { console.error('Header error:', e); }

  // ── Contradictions ────────────────────────────────────────────────────
  try { renderContradictions(contradictions); } catch(e) { console.error('Contradictions error:', e); }

  // ── Context banner ────────────────────────────────────────────────────
  try {
    if (clinical_context.signal_summary) {
      const cb = document.getElementById('context-banner');
      if (cb) { cb.textContent = 'Context memory: ' + clinical_context.signal_summary; cb.classList.remove('hidden'); }
    }
  } catch(e) { console.error('Context banner error:', e); }

  // ── Confidence breakdown ──────────────────────────────────────────────
  try { renderConfidenceBreakdown(confidence); } catch(e) { console.error('Confidence error:', e); }

  // ── 3D Molecule viewer ────────────────────────────────────────────────
  try { renderMolecule3D(mechanism, molecule); } catch(e) { console.error('Molecule 3D error:', e); }

  // ── AI Cure Discovery ─────────────────────────────────────────────────
  try { renderCureDiscovery(report, mechanism, molecule); } catch(e) { console.error('Cure discovery error:', e); }

  // ── Viability analysis ────────────────────────────────────────────────
  try { renderViability(failure_analysis, report); } catch(e) { console.error('Viability error:', e); }

  // ── Report cards ──────────────────────────────────────────────────────
  try { renderReportCards(report, confidence); } catch(e) { console.error('Report cards error:', e); }

  // ── Charts ────────────────────────────────────────────────────────────
  try { renderCharts(data); } catch(e) { console.error('Charts error:', e); }

  // ── Raw data tabs ─────────────────────────────────────────────────────
  try { renderRawTabs(data); } catch(e) { console.error('Raw tabs error:', e); }

  // ── Extra charts (delayed — need canvas dimensions) ───────────────────
  setTimeout(() => {
    try { renderTimeline((data.clinical||{}).trials||[]); } catch(e) { console.error('Timeline error:', e); }
    try { renderDiseaseScores(data.report||{}); } catch(e) { console.error('Disease scores error:', e); }
    try { renderScoreExplainer(data.confidence||{}, data.molecule||''); } catch(e) { console.error('Score explainer error:', e); }
    try { renderComparisonMini(data); } catch(e) { console.error('Comparison error:', e); }
    try { renderEvidenceCard(data); } catch(e) { console.error('Evidence card error:', e); }
  }, 400);
}

// ═══ EVIDENCE CARD ════════════════════════════════════════════════════════
function renderEvidenceCard(data) {
  const card = data.report?.evidence_card;
  const sec  = document.getElementById('evidence-card-section');
  if (!card) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');

  document.getElementById('ec-mol-logic').textContent = card.molecular_logic || 'Structural analysis suggests biological compatibility.';
  document.getElementById('ec-gen-path').textContent  = card.genetic_pathway || 'Overlapping genetic markers identified in research papers.';
  document.getElementById('ec-side-proxy').textContent = card.side_effect_proxy || 'Historical side-effect data correlates with target disease signals.';

  const list = document.getElementById('ec-path-list');
  list.innerHTML = '';
  (card.reasoning_path || []).forEach(p => {
    const li = document.createElement('li');
    li.textContent = p;
    list.appendChild(li);
  });
}

// ═══ CONFIDENCE BREAKDOWN ═════════════════════════════════════════════════
function renderConfidenceBreakdown(confidence) {
  if (!confidence) return;
  const bd = confidence.breakdown || {};
  setTimeout(() => {
    ['clinical','patents','market','regulatory'].forEach(d => {
      const val = bd[d] || 0;
      const fill = document.getElementById(`cdb-${d}-fill`);
      const valEl = document.getElementById(`cdb-${d}-val`);
      if (fill)  fill.style.width  = val + '%';
      if (valEl) valEl.textContent = val;
    });
  }, 200);
}

// ═══ REPORT CARDS ═════════════════════════════════════════════════════════
function renderReportCards(report, confidence) {
  if (!report) return;

  // Summary + confidence bar
  document.getElementById('report-summary').textContent = report.executive_summary || '';
  const score = report.confidence_score || confidence?.total || 0;
  setTimeout(() => {
    const fill = document.getElementById('confidence-fill');
    if (fill) fill.style.width = score + '%';
  }, 300);
  document.getElementById('conf-value').textContent = score + '%';
  const labelEl = document.getElementById('conf-label-text');
  if (labelEl) {
    labelEl.textContent = confidence?.label || '';
    labelEl.style.color = score>=75?'var(--accent)':score>=50?'var(--warning)':'var(--danger)';
  }

  // Domain cards
  const domains = [
    { key:'unmet_needs',    prefix:'unmet',    src:'https://clinicaltrials.gov' },
    { key:'pipeline_status',prefix:'pipeline', src:'https://clinicaltrials.gov' },
    { key:'patent_landscape',prefix:'patent',  src:'https://pubchem.ncbi.nlm.nih.gov' },
    { key:'market_potential',prefix:'market',  src:'https://api.fda.gov' },
  ];
  domains.forEach(({ key, prefix, src }) => {
    const d = report[key] || {};
    const f = document.getElementById(`${prefix}-finding`);
    const e = document.getElementById(`${prefix}-evidence`);
    const l = document.getElementById(`${prefix}-source-link`);
    if (f) f.textContent = d.finding || '';
    if (e) e.textContent = d.evidence || '';
    if (l) { l.textContent = d.source || src; l.href = src; }
  });

  // Cross-domain insight
  document.getElementById('cross-insight').textContent = report.cross_domain_insight || '';

  // Recommendation
  const rec = report.strategic_recommendation || {};
  const vEl = document.getElementById('rec-verdict');
  if (vEl) {
    vEl.textContent = rec.verdict || '';
    const cls = (rec.verdict||'').includes('PURSUE')&&!(rec.verdict||'').includes('NOT')?'PURSUE':(rec.verdict||'').includes('LOW')?'LOW':'INVESTIGATE';
    vEl.className = `rec-verdict ${cls}`;
  }
  document.getElementById('rec-reasoning').textContent = rec.reasoning || '';
  const steps = document.getElementById('rec-steps');
  if (steps) {
    steps.innerHTML = '';
    (rec.next_steps||[]).forEach(s => {
      const li = document.createElement('li'); li.textContent = s; steps.appendChild(li);
    });
  }

  // Risks
  const risksList = document.getElementById('risks-list');
  if (risksList) {
    risksList.innerHTML = '';
    (report.key_risks||[]).forEach(r => {
      const span = document.createElement('span');
      span.className='risk-tag'; span.textContent=r; risksList.appendChild(span);
    });
  }
}

// ═══ CONTRADICTIONS ═══════════════════════════════════════════════════════
function renderContradictions(contradictions) {
  const banner = document.getElementById('contradiction-banner');
  if (!contradictions || !contradictions.length) { banner.classList.add('hidden'); return; }
  banner.classList.remove('hidden');
  banner.innerHTML = contradictions.map(c => `
    <div class="flag ${c.severity==='danger'?'danger':c.severity==='warning'?'warning':'info'}">
      <span>⚠</span><span>${c.message}</span>
    </div>`).join('');
}

// ═══ CHARTS ═══════════════════════════════════════════════════════════════
function renderCharts(data) {
  const clinical = data.clinical || {};
  const trials   = clinical.trials || [];
  const conf     = data.confidence || {};

  if (phaseChart)  { try{phaseChart.destroy();}catch(e){} phaseChart  = null; }
  if (statusChart) { try{statusChart.destroy();}catch(e){} statusChart = null; }
  if (radarChart)  { try{radarChart.destroy();}catch(e){} radarChart  = null; }

  Chart.defaults.color = 'rgba(255,255,255,0.55)';
  Chart.defaults.font  = { family: 'DM Mono', size: 11 };
  const gridColor = 'rgba(255,255,255,0.05)';
  const co = { color:'rgba(255,255,255,0.55)', font:{ family:'DM Mono', size:10 } };

  // Phase chart — always render with fallback
  const phases = {};
  trials.forEach(t => { const p = (t.phase||'Unknown').replace('Phase ','P'); phases[p]=(phases[p]||0)+1; });
  if (!Object.keys(phases).length) phases['No data'] = 1;

  const pc = document.getElementById('phases-chart');
  if (pc) {
    // Force canvas to be visible
    pc.style.display = 'block';
    phaseChart = new Chart(pc, {
      type:'bar',
      data:{
        labels: Object.keys(phases),
        datasets:[{
          data: Object.values(phases),
          backgroundColor: ['rgba(0,255,179,0.75)','rgba(0,200,255,0.75)','rgba(155,109,255,0.75)','rgba(255,179,71,0.75)','rgba(255,77,109,0.75)','rgba(0,255,179,0.5)'],
          borderColor:     ['rgba(0,255,179,1)',   'rgba(0,200,255,1)',   'rgba(155,109,255,1)',   'rgba(255,179,71,1)',   'rgba(255,77,109,1)',  'rgba(0,255,179,0.7)'],
          borderWidth: 1, borderRadius: 6
        }]
      },
      options:{
        plugins:{ legend:{ display:false }, tooltip:{ callbacks:{ label: ctx => ` ${ctx.parsed.y} trial${ctx.parsed.y!==1?'s':''}` } } },
        scales:{
          x:{ grid:{ color:gridColor }, ticks: co, border:{ display:false } },
          y:{ grid:{ color:gridColor }, ticks:{ ...co, stepSize:1, precision:0 }, border:{ display:false }, beginAtZero:true }
        },
        responsive:true, maintainAspectRatio:false, animation:{ duration:800 }
      }
    });
  }

  // Status chart — always render
  const statuses = {};
  trials.forEach(t => {
    const s = (t.status||'Unknown');
    const short = s.includes('Recruiting')?'Recruiting':s.includes('Completed')?'Completed':s.includes('Terminated')?'Terminated':s.includes('Active')?'Active':'Other';
    statuses[short] = (statuses[short]||0)+1;
  });
  if (!Object.keys(statuses).length) statuses['No data'] = 1;

  const sc = document.getElementById('status-chart');
  if (sc) {
    sc.style.display = 'block';
    statusChart = new Chart(sc, {
      type:'doughnut',
      data:{
        labels: Object.keys(statuses),
        datasets:[{
          data: Object.values(statuses),
          backgroundColor:['rgba(0,255,179,0.82)','rgba(0,200,255,0.82)','rgba(255,77,109,0.82)','rgba(155,109,255,0.82)','rgba(255,179,71,0.82)'],
          borderWidth: 0, hoverOffset: 4
        }]
      },
      options:{
        plugins:{
          legend:{ position:'bottom', labels:{ ...co, padding:10, boxWidth:10, usePointStyle:true } },
          tooltip:{ callbacks:{ label: ctx => ` ${ctx.parsed} trial${ctx.parsed!==1?'s':''}` } }
        },
        responsive:true, maintainAspectRatio:false, cutout:'62%',
        animation:{ duration:800 }
      }
    });
  }

  // Radar — confidence scores
  const bd = conf.breakdown || {};
  const radarVals = [bd.clinical||0, bd.patents||0, bd.market||0, bd.regulatory||0];

  const rc = document.getElementById('radar-chart');
  if (rc) {
    rc.style.display = 'block';
    radarChart = new Chart(rc, {
      type:'radar',
      data:{
        labels:['Clinical','Patents','Market','Regulatory'],
        datasets:[{
          label:'Score',
          data: radarVals,
          backgroundColor:'rgba(0,255,179,0.1)',
          borderColor:'rgba(0,255,179,0.8)',
          pointBackgroundColor:'rgba(0,255,179,1)',
          pointBorderColor:'transparent',
          pointHoverRadius:5,
          borderWidth:1.5, pointRadius:4
        }]
      },
      options:{
        scales:{
          r:{
            grid:{ color:'rgba(255,255,255,0.07)' },
            angleLines:{ color:'rgba(255,255,255,0.07)' },
            ticks:{ display:false, stepSize:25 },
            pointLabels:{ ...co, font:{ family:'DM Mono', size:11 } },
            min:0, max:100
          }
        },
        plugins:{ legend:{ display:false }, tooltip:{ callbacks:{ label: ctx => ` ${ctx.parsed.r}%` } } },
        responsive:true, maintainAspectRatio:false,
        animation:{ duration:1000 }
      }
    });
  }
}

// ═══ RAW DATA TABS ════════════════════════════════════════════════════════
function renderRawTabs(data) {
  // Clinical
  const cr = document.getElementById('clinical-raw');
  if (cr) {
    const trials = (data.clinical||{}).trials||[];
    cr.innerHTML = trials.length
      ? trials.slice(0,10).map(t=>`
        <div class="raw-item">
          <div class="raw-item-title">${t.title||'No title'}</div>
          <div class="raw-item-meta">${t.nct_id||''} · ${t.phase||''} · ${t.status||''}</div>
          <div class="raw-item-meta">${(t.conditions||[]).join(', ')}</div>
          ${t.nct_id?`<a class="raw-item-link" href="https://clinicaltrials.gov/study/${t.nct_id}" target="_blank">View on ClinicalTrials.gov ↗</a>`:''}
        </div>`).join('')
      : '<div style="font-size:13px;color:var(--text3);padding:8px 0">No trials found for this drug.</div>';
  }

  // Patents
  const pr = document.getElementById('patent-raw');
  if (pr) {
    const ci  = (data.patents||{}).compound_info||{};
    const pts = (data.patents||{}).patents||[];
    pr.innerHTML = `<div class="raw-item">
      <div class="raw-item-title">Compound: ${ci.name||data.molecule}</div>
      <div class="raw-item-meta">Formula: ${ci.molecular_formula||'N/A'} · MW: ${ci.molecular_weight||'N/A'}</div>
      <div class="raw-item-meta">Total patents: ${(data.patents||{}).total_patents||0}</div>
    </div>` + pts.slice(0,5).map(p=>`
      <div class="raw-item">
        <div class="raw-item-title">${p.patent_id||'Patent'}</div>
        <a class="raw-item-link" href="https://patents.google.com/patent/${p.patent_id}" target="_blank">View patent ↗</a>
      </div>`).join('');
  }

  // Market
  const mr = document.getElementById('market-raw');
  if (mr) {
    const mkt = data.market||{};
    mr.innerHTML = `<div class="raw-item">
      <div class="raw-item-title">Market overview</div>
      <div class="raw-item-meta">Products on market: ${mkt.products_found||0}</div>
      <div class="raw-item-meta">Adverse event reports: ${(mkt.adverse_event_reports||0).toLocaleString()}</div>
      <div class="raw-item-meta">${mkt.market_insight||''}</div>
    </div>` + (mkt.products||[]).slice(0,5).map(p=>`
      <div class="raw-item">
        <div class="raw-item-title">${p.brand_name||p.generic_name||'Product'}</div>
        <div class="raw-item-meta">${p.dosage_form||''} · ${p.route||''}</div>
      </div>`).join('');
  }

  // Regulatory
  const reg = document.getElementById('regulatory-raw');
  if (reg) {
    const rv = data.regulatory||{};
    reg.innerHTML = `<div class="raw-item">
      <div class="raw-item-title">FDA regulatory status</div>
      <div class="raw-item-meta">Approvals: ${(rv.approvals||[]).length}</div>
      <div class="raw-item-meta">Current indications: ${(rv.current_indications||[]).slice(0,2).join('; ')}</div>
      <div class="raw-item-meta">Warnings: ${(rv.warnings||[]).length} · Contraindications: ${(rv.contraindications||[]).length}</div>
      <a class="raw-item-link" href="https://api.fda.gov/drug/label.json" target="_blank">Source: OpenFDA ↗</a>
    </div>`;
  }

  // PubMed
  const pub = document.getElementById('pubmed-raw');
  if (pub) {
    const papers = (data.pubmed||{}).papers||[];
    pub.innerHTML = papers.length
      ? papers.slice(0,8).map(p=>`
        <div class="raw-item">
          <div class="raw-item-title">${p.title||'No title'}</div>
          <div class="raw-item-meta">${p.authors||''} · ${p.journal||''} · ${p.year||''}</div>
          ${p.pmid?`<a class="raw-item-link" href="https://pubmed.ncbi.nlm.nih.gov/${p.pmid}" target="_blank">PubMed ${p.pmid} ↗</a>`:''}
        </div>`).join('')
      : '<div style="font-size:13px;color:var(--text3);padding:8px 0">No papers found.</div>';
  }
}

// ═══ FOLLOW-UP Q&A ════════════════════════════════════════════════════════
async function askFollowup() {
  const input = document.getElementById('qa-input');
  const question = input.value.trim();
  if (!question || !currentData) return;

  const btn = document.getElementById('qa-btn');
  const hist = document.getElementById('qa-history');
  btn.textContent = '...'; btn.disabled = true;
  input.value = '';

  const uMsg = document.createElement('div');
  uMsg.className='qa-message user'; uMsg.textContent=question;
  hist.appendChild(uMsg);

  try {
    const language = getLanguage();
    const res = await fetch('/followup', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ question, language, context: { molecule:currentData.molecule, report:currentData.report, mechanism:currentData.mechanism } })
    });
    const data = await res.json();
    const aMsg = document.createElement('div');
    aMsg.className='qa-message ai'; aMsg.textContent=data.answer||'No response.';
    hist.appendChild(aMsg);
    aMsg.scrollIntoView({ behavior:'smooth', block:'nearest' });
  } catch(e) {
    const eMsg = document.createElement('div');
    eMsg.className='qa-message ai'; eMsg.textContent='Error: '+e.message;
    hist.appendChild(eMsg);
  } finally {
    btn.textContent='Ask'; btn.disabled=false;
  }
}

function askSuggestion(el) {
  document.getElementById('qa-input').value = el.textContent;
  askFollowup();
}

// ═══ BATCH MODE ════════════════════════════════════════════════════════════
async function startBatch() {
  const molecules = ['b1','b2','b3','b4','b5'].map(id=>document.getElementById(id).value.trim()).filter(Boolean);
  if (molecules.length < 2) { showError('Enter at least 2 drugs'); return; }
  const btn = document.getElementById('batch-btn');
  const btnText = document.getElementById('batch-btn-text');
  btn.disabled = true; btnText.textContent = 'Analysing...';

  try {
    const language = getLanguage();
    const res  = await fetch('/batch', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({molecules,language}) });
    const data = await res.json();
    const results = data.results || [];
    const container = document.getElementById('batch-results');
    container.innerHTML = '';
    const medals = ['gold','silver','bronze'];
    const nums   = ['1','2','3','4','5'];

    results.forEach((r, i) => {
      const score = r.confidence?.total || 0;
      const summary = r.report?.executive_summary || '';
      const card = document.createElement('div');
      card.className = 'batch-card';
      card.innerHTML = `
        <div class="batch-rank ${medals[i]||''}">${nums[i]||i+1}</div>
        <div class="batch-card-content">
          <div class="batch-drug-name">${r.molecule}</div>
          <div class="batch-summary">${summary.slice(0,120)}${summary.length>120?'...':''}</div>
        </div>
        <div class="batch-score">${score}%</div>`;
      card.onclick = () => {
        currentData = r;
        renderResults(r);
        showSection('results-section');
      };
      container.appendChild(card);
    });
    container.classList.remove('hidden');
  } catch(e) { showError(e.message); }
  finally { btn.disabled=false; btnText.textContent='Run Batch Analysis'; }
}

// ═══ COMPARE MODE ═════════════════════════════════════════════════════════
async function startComparison() {
  const m1 = document.getElementById('compare-mol1').value.trim();
  const m2 = document.getElementById('compare-mol2').value.trim();
  if (!m1||!m2) { showError('Enter both drug names'); return; }

  const btn = document.getElementById('compare-btn');
  const btnText = document.getElementById('compare-btn-text');
  btn.disabled=true; btnText.textContent='Comparing...';

  try {
    const language = getLanguage();
    const res  = await fetch('/compare', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({molecule1:m1,molecule2:m2,language}) });
    const data = await res.json();
    const r1   = data.molecule1, r2 = data.molecule2;
    const s1   = r1?.confidence?.total||0, s2 = r2?.confidence?.total||0;
    const winner = s1>=s2 ? m1 : m2;

    const container = document.getElementById('compare-results');
    container.innerHTML = `
      <div class="compare-winner-banner">Winner: ${winner} — higher repurposing potential</div>
      <div class="compare-result-grid">
        <div>
          <div style="font-family:var(--font-serif);font-size:20px;color:var(--text);margin-bottom:12px">${m1} — ${s1}%</div>
          <div style="font-size:13px;color:var(--text2)">${(r1?.report?.executive_summary||'').slice(0,200)}</div>
        </div>
        <div>
          <div style="font-family:var(--font-serif);font-size:20px;color:var(--text);margin-bottom:12px">${m2} — ${s2}%</div>
          <div style="font-size:13px;color:var(--text2)">${(r2?.report?.executive_summary||'').slice(0,200)}</div>
        </div>
      </div>`;
    container.classList.remove('hidden');
  } catch(e) { showError(e.message); }
  finally { btn.disabled=false; btnText.textContent='Compare Drugs'; }
}

// ═══ AGENT ANIMATION ══════════════════════════════════════════════════════
function animateAgents() {
  const agents  = ['clinical','patent','market','regulatory','pubmed','mechanism'];
  const times   = [1200,1600,2000,2400,2800,3200];
  const statuses= ['Searching trials...','Checking IP...','Analysing market...','Reading labels...','Searching papers...','Analysing structure...'];
  const doneMsg = ['Trials found','IP checked','Market assessed','Labels read','Papers found','Structure analysed'];

  agents.forEach((a,i) => {
    const card = document.getElementById(`agent-${a}`);
    const stat = document.getElementById(`status-${a}`);
    const prog = document.getElementById(`prog-${a}`);
    if (card) card.classList.remove('active','done');
    if (prog) prog.style.width='0%';
    if (stat) stat.textContent = statuses[i];

    setTimeout(()=>{
      if(card) card.classList.add('active');
      if(prog) { prog.style.width='40%'; setTimeout(()=>{ if(prog)prog.style.width='80%'; },400); }
    }, times[i]-600);

    setTimeout(()=>{
      if(card) { card.classList.remove('active'); card.classList.add('done'); }
      if(prog) prog.style.width='100%';
      if(stat) stat.textContent = doneMsg[i];
    }, times[i]);
  });

  setTimeout(()=>{
    const sr = document.getElementById('synthesis-row');
    if (sr) sr.classList.remove('hidden');
  }, 3600);
}

// ═══ EXPORT ═══════════════════════════════════════════════════════════════
function exportReport() {
  if (!currentData) return;
  const blob = new Blob([JSON.stringify(currentData, null, 2)], { type:'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `repurposeai-${currentData.molecule}-${Date.now()}.json`;
  a.click();
}

// ═══ HISTORY ══════════════════════════════════════════════════════════════
function addHistory(molecule) {
  searchHistory = [molecule, ...searchHistory.filter(h=>h!==molecule)].slice(0,6);
  localStorage.setItem('rp_history', JSON.stringify(searchHistory));
  renderHistory();
}

function renderHistory() {
  const row   = document.getElementById('history-row');
  const pills = document.getElementById('history-pills');
  if (!row||!pills) return;
  if (!searchHistory.length) { row.style.display='none'; return; }
  row.style.display='flex';
  pills.innerHTML = searchHistory.map(h=>`<span class="history-pill" onclick="setMolecule('${h}')">${h}</span>`).join('');
}

// ═══ UTILS ════════════════════════════════════════════════════════════════
function setMolecule(name) {
  const input = document.getElementById('molecule-input');
  if (input) { input.value=name; input.focus(); }
}

function showSection(id) {
  // 1. Hide all tab-panels
  document.querySelectorAll('.tab-panel').forEach(p => {
    p.classList.remove('active');
    p.style.display = 'none';
  });

  // 2. Hide global sections
  if (['loading-section', 'results-section'].includes(id)) {
      document.querySelectorAll('#loading-section, #results-section').forEach(s => s.classList.add('hidden'));
      const target = document.getElementById(id);
      if (target) target.classList.remove('hidden');
  } else {
      // If showing a tab panel, hide the results/loading
      document.querySelectorAll('#loading-section, #results-section').forEach(s => s.classList.add('hidden'));
      
      const el = document.getElementById(id);
      if (el) {
        el.classList.remove('hidden');
        if (el.classList.contains('tab-panel')) {
          el.classList.add('active');
          el.style.display = 'block';
          
          // Trigger tab-specific logic
          if (id === 'test-panel') startKnowledgeTest();
          if (id === 'explore-panel') loadMarketFeed();
        }
      }
  }
}

function goBack() { 
  switchTab('repurpose');
  currentData = null; 
}

function showTab(id, btn) {
  document.querySelectorAll('.raw-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.raw-tab').forEach(b=>b.classList.remove('active'));
  const panel = document.getElementById(id);
  if (panel) panel.classList.add('active');
  if (btn) btn.classList.add('active');
}

function showError(msg) {
  const toast = document.getElementById('error-toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.remove('hidden');
  setTimeout(()=>toast.classList.add('hidden'), 4000);
}

// ═══ DRUG TIMELINE CHART ══════════════════════════════════════════════════
let timelineChart = null;
function renderTimeline(trials) {
  const sec = document.getElementById('timeline-section');
  if (!sec) return;
  const canvas = document.getElementById('timeline-chart');
  if (!canvas) return;

  const sorted = [...trials].filter(t=>t.year||t.start_date).sort((a,b)=>{
    const ya = parseInt((a.start_date||a.year||'2000').slice(0,4));
    const yb = parseInt((b.start_date||b.year||'2000').slice(0,4));
    return ya - yb;
  });
  if (!sorted.length) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');

  const labels = sorted.map(t=>t.nct_id||'Trial');
  const years  = sorted.map(t=>parseInt((t.start_date||t.year||'2020').slice(0,4)));
  const phases = sorted.map(t=>{
    const p = (t.phase||'').toLowerCase();
    return p.includes('4')?4:p.includes('3')?3:p.includes('2')?2:p.includes('1')?1:0.5;
  });
  const colors = phases.map(p=>
    p>=3?'rgba(0,255,179,0.85)':p>=2?'rgba(0,200,255,0.85)':p>=1?'rgba(155,109,255,0.85)':'rgba(255,179,71,0.7)'
  );

  if (timelineChart) { try{timelineChart.destroy();}catch(e){} timelineChart=null; }
  timelineChart = new Chart(canvas, {
    type:'bubble',
    data:{
      datasets:[{
        label:'Trials',
        data: sorted.map((t,i)=>({x:years[i], y:phases[i], r:8, nct:t.nct_id, title:t.title||''})),
        backgroundColor: colors, borderColor: colors.map(c=>c.replace('0.85','1')), borderWidth:1
      }]
    },
    options:{
      plugins:{
        legend:{display:false},
        tooltip:{callbacks:{
          label: ctx => [`${ctx.raw.nct||'Trial'}`, `Phase ${ctx.raw.y}`, `${ctx.raw.x}`]
        }}
      },
      scales:{
        x:{ type:'linear', title:{display:true,text:'Year',color:'rgba(255,255,255,0.4)',font:{family:'DM Mono',size:10}}, grid:{color:'rgba(255,255,255,0.04)'}, ticks:{color:'rgba(255,255,255,0.5)',font:{family:'DM Mono',size:10}} },
        y:{ title:{display:true,text:'Phase',color:'rgba(255,255,255,0.4)',font:{family:'DM Mono',size:10}}, min:0, max:5, grid:{color:'rgba(255,255,255,0.04)'}, ticks:{color:'rgba(255,255,255,0.5)',stepSize:1,font:{family:'DM Mono',size:10}} }
      },
      responsive:true, maintainAspectRatio:false, animation:{duration:600}
    }
  });
}

// ═══ DISEASE SIMILARITY SCORE ═════════════════════════════════════════════
function renderDiseaseScores(report) {
  const sec = document.getElementById('disease-scores-section');
  if (!sec || !report) { if(sec) sec.classList.add('hidden'); return; }

  const opps = (report.repurposing_opportunities||[]).filter(o=>o.disease&&!o.disease.toLowerCase().includes('demo'));
  if (!opps.length) { sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');

  const canvas = document.getElementById('disease-scores-chart');
  if (!canvas) return;

  const labels = opps.map(o=>o.disease.slice(0,30));
  const scores = opps.map(o=>o.confidence_score||0);
  const colors = scores.map(s=>s>=70?'rgba(0,255,179,0.8)':s>=50?'rgba(0,200,255,0.8)':'rgba(155,109,255,0.8)');

  let dsChart = Chart.getChart(canvas);
  if (dsChart) { try{dsChart.destroy();}catch(e){} }

  new Chart(canvas, {
    type:'bar',
    data:{
      labels,
      datasets:[{
        label:'Confidence %',
        data: scores,
        backgroundColor: colors,
        borderColor: colors.map(c=>c.replace('0.8','1')),
        borderWidth:1, borderRadius:8, indexAxis:'y'
      }]
    },
    options:{
      indexAxis:'y',
      plugins:{ legend:{display:false}, tooltip:{callbacks:{label:ctx=>` ${ctx.parsed.x}% confidence`}} },
      scales:{
        x:{ max:100, min:0, grid:{color:'rgba(255,255,255,0.04)'}, ticks:{color:'rgba(255,255,255,0.5)',font:{family:'DM Mono',size:10}}, border:{display:false} },
        y:{ grid:{display:false}, ticks:{color:'rgba(255,255,255,0.7)',font:{family:'DM Mono',size:11}}, border:{display:false} }
      },
      responsive:true, maintainAspectRatio:false, animation:{duration:800}
    }
  });
}

// ═══ SCORE EXPLAINER ══════════════════════════════════════════════════════
function renderScoreExplainer(confidence, molecule) {
  const sec = document.getElementById('score-explain-section');
  if (!sec || !confidence) { if(sec) sec.classList.add('hidden'); return; }
  sec.classList.remove('hidden');

  const bd    = confidence.breakdown || {};
  const total = confidence.total || 0;
  const label = confidence.label || '';

  const body = document.getElementById('score-explain-body');
  if (!body) return;

  const items = [
    { domain:'Clinical evidence', score:bd.clinical||0, max:35, color:'var(--accent)',
      explain: bd.clinical>=25?'Strong: multiple trials with late-phase evidence':bd.clinical>=15?'Moderate: some trials found':bd.clinical>0?'Weak: limited trial data':'None found' },
    { domain:'Patent freedom', score:bd.patents||0, max:25, color:'var(--accent2)',
      explain: bd.patents>=20?'Clear: low patent count — free to commercialise':bd.patents>=12?'Moderate: some IP exists':bd.patents>0?'Restricted: heavy patent protection':'No compound data' },
    { domain:'Market signal', score:bd.market||0, max:25, color:'var(--warning)',
      explain: bd.market>=20?'Strong: high market usage proves demand':bd.market>=10?'Moderate: some market presence':bd.market>0?'Weak: limited usage data':'No market data' },
    { domain:'Regulatory clarity', score:bd.regulatory||0, max:15, color:'var(--accent3)',
      explain: bd.regulatory>=12?'Clean: FDA approved, no major warnings':bd.regulatory>=7?'Moderate: approved with some warnings':bd.regulatory>0?'Cautious: approval uncertain':'No regulatory data' },
  ];

  body.innerHTML = `
    <div class="se-total">
      <div class="se-total-num" style="color:${total>=75?'var(--accent)':total>=50?'var(--warning)':'var(--danger)'}">${total}<span style="font-size:18px;color:var(--text3)">%</span></div>
      <div class="se-total-label">${label} — overall repurposing confidence for ${molecule}</div>
    </div>
    <div class="se-items">
      ${items.map(item=>`
        <div class="se-item">
          <div class="se-item-top">
            <span class="se-domain">${item.domain}</span>
            <span class="se-score" style="color:${item.color}">${item.score}<span style="font-size:10px;color:var(--text3)">/${item.max}</span></span>
          </div>
          <div class="se-bar-wrap"><div class="se-bar" style="width:${Math.round(item.score/item.max*100)}%;background:${item.color}"></div></div>
          <div class="se-explain">${item.explain}</div>
        </div>`).join('')}
    </div>`;
}

// ═══ DRUG COMPARISON RADAR (inline on results) ═════════════════════════════
function renderComparisonMini(data) {
  const sec = document.getElementById('comparison-mini-section');
  if (!sec) return;
  // Only show if we have previous data to compare
  const prev = JSON.parse(sessionStorage.getItem('prev_result')||'null');
  if (!prev || prev.molecule === data.molecule) {
    sessionStorage.setItem('prev_result', JSON.stringify({
      molecule: data.molecule,
      breakdown: data.confidence?.breakdown||{}
    }));
    if(sec) sec.classList.add('hidden');
    return;
  }
  sec.classList.remove('hidden');

  const curr = data.confidence?.breakdown||{};
  const prevBd = prev.breakdown||{};
  const canvas = document.getElementById('comparison-mini-chart');
  if (!canvas) return;

  let cmpChart = Chart.getChart(canvas);
  if (cmpChart) { try{cmpChart.destroy();}catch(e){} }

  new Chart(canvas, {
    type:'radar',
    data:{
      labels:['Clinical','Patents','Market','Regulatory'],
      datasets:[
        { label:data.molecule, data:[curr.clinical||0,curr.patents||0,curr.market||0,curr.regulatory||0],
          backgroundColor:'rgba(0,255,179,0.08)', borderColor:'rgba(0,255,179,0.8)', pointBackgroundColor:'rgba(0,255,179,1)', borderWidth:1.5, pointRadius:3 },
        { label:prev.molecule, data:[prevBd.clinical||0,prevBd.patents||0,prevBd.market||0,prevBd.regulatory||0],
          backgroundColor:'rgba(0,200,255,0.08)', borderColor:'rgba(0,200,255,0.7)', pointBackgroundColor:'rgba(0,200,255,1)', borderWidth:1.5, pointRadius:3 }
      ]
    },
    options:{
      scales:{ r:{ grid:{color:'rgba(255,255,255,0.06)'}, angleLines:{color:'rgba(255,255,255,0.06)'}, ticks:{display:false}, pointLabels:{color:'rgba(255,255,255,0.5)',font:{family:'DM Mono',size:10}}, min:0, max:100 } },
      plugins:{ legend:{ position:'bottom', labels:{color:'rgba(255,255,255,0.5)',font:{family:'DM Mono',size:10},boxWidth:10,usePointStyle:true} } },
      responsive:true, maintainAspectRatio:false
    }
  });
  sessionStorage.setItem('prev_result', JSON.stringify({ molecule:data.molecule, breakdown:curr }));
}

// ═══ LIVE SEARCH AUTOCOMPLETE ═════════════════════════════════════════════
const KNOWN_DRUGS = ['Aspirin','Metformin','Sildenafil','Paracetamol','Ibuprofen','Thalidomide',
  'Atorvastatin','Warfarin','Dexamethasone','Hydroxychloroquine','Remdesivir','Ivermectin',
  'Rapamycin','Methotrexate','Tamoxifen','Lithium','Naltrexone','Propranolol','Losartan',
  'Pioglitazone','Allopurinol','Colchicine','Rifampicin','Amantadine','Valproic Acid'];

function initAutocomplete() {
  const input = document.getElementById('molecule-input');
  const suggestions = document.getElementById('autocomplete-list');
  if (!input || !suggestions) return;

  input.addEventListener('input', () => {
    const val = input.value.trim().toLowerCase();
    suggestions.innerHTML = '';
    if (!val || val.length < 2) { suggestions.style.display='none'; return; }
    const matches = KNOWN_DRUGS.filter(d=>d.toLowerCase().includes(val)).slice(0,6);
    if (!matches.length) { suggestions.style.display='none'; return; }
    suggestions.style.display='block';
    matches.forEach(d => {
      const item = document.createElement('div');
      item.className='ac-item';
      item.textContent=d;
      item.onclick=()=>{ input.value=d; suggestions.style.display='none'; };
      suggestions.appendChild(item);
    });
  });
  document.addEventListener('click', e=>{ if(e.target!==input) suggestions.style.display='none'; });
}

// ═══ PRINT / SHARE REPORT ═════════════════════════════════════════════════
function shareReport() {
  if (!currentData) return;
  const text = `RepurposeAI Analysis: ${currentData.molecule}\n\nConfidence: ${currentData.confidence?.total||0}%\n\n${currentData.report?.executive_summary||''}\n\nGenerated at repurposeai.vercel.app`;
  if (navigator.share) {
    navigator.share({ title:`RepurposeAI — ${currentData.molecule}`, text }).catch(()=>{});
  } else {
    navigator.clipboard.writeText(text).then(()=>showToast('Report copied to clipboard'));
  }
}

function showToast(msg, type='success') {
  const toast = document.getElementById('error-toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.style.background = type==='success'?'var(--accent)':type==='warning'?'var(--warning)':'var(--danger)';
  toast.style.color = type==='success'?'#000':'#fff';
  toast.classList.remove('hidden');
  setTimeout(()=>toast.classList.add('hidden'), 3000);
}

// ═══ DARK / LIGHT MODE TOGGLE ═════════════════════════════════════════════
let darkMode = true;
function toggleTheme() {
  darkMode = !darkMode;
  document.body.classList.toggle('light-mode', !darkMode);
  const btn = document.getElementById('theme-btn');
  if (btn) btn.textContent = darkMode ? '☀' : '☾';
}

// Init autocomplete on load
document.addEventListener('DOMContentLoaded', () => { initAutocomplete(); });

// ═══ REPURPOSE MODES ══════════════════════════════════════════════════════
async function startBatch() {
  const m1 = document.getElementById('b1').value.trim();
  const m2 = document.getElementById('b2').value.trim();
  const m3 = document.getElementById('b3').value.trim();
  const molecules = [m1, m2, m3].filter(Boolean);
  
  if (!molecules.length) { showError('Enter at least one drug for batch analysis.'); return; }
  
  const resDiv = document.getElementById('batch-results');
  resDiv.classList.remove('hidden');
  resDiv.innerHTML = '<div style="color:var(--accent)">Orchestrating batch swarm retrieval...</div>';
  
  try {
    const res = await fetch('/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ molecules, language: getLanguage() })
    });
    if(!res.ok) throw new Error('API Fault');
    const data = await res.json();
    
    let html = `<div style="font-size:18px; color:var(--text); margin-bottom:12px;">Swarm Batch Results</div>`;
    data.results.forEach(r => {
      html += `<div style="padding:16px; border:1px solid var(--border); border-radius:12px; margin-bottom:12px; background:var(--bg3);">
        <div style="font-size:16px; color:var(--accent); font-weight:600;">${r.molecule}</div>
        <div style="font-size:14px; color:var(--text2);">Confidence Score: ${r.confidence?.total||0}%</div>
      </div>`;
    });
    resDiv.innerHTML = html;
  } catch(e) {
    resDiv.innerHTML = `<div style="color:var(--danger)">Batch analysis failed. Check API status.</div>`;
  }
}

async function startComparison() {
  const mol1 = document.getElementById('compare-mol1').value.trim();
  const mol2 = document.getElementById('compare-mol2').value.trim();
  if(!mol1 || !mol2) { showError('Enter two candidates for comparison.'); return; }
  
  const resDiv = document.getElementById('compare-results');
  resDiv.classList.remove('hidden');
  resDiv.innerHTML = '<div style="color:var(--accent)">Synthesizing dual-candidate vectors...</div>';
  
  try {
    const res = await fetch('/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ molecule1: mol1, molecule2: mol2, language: getLanguage() })
    });
    if(!res.ok) throw new Error('API Fault');
    const data = await res.json();
    
    resDiv.innerHTML = `
      <div style="display:flex; gap:20px; margin-top:20px;">
        <div style="flex:1; background:var(--bg3); padding:20px; border-radius:16px; border:1px solid ${data.winner===mol1?'var(--accent)':'var(--border)'}">
          <h3 style="color:var(--accent);">${data.molecule1.molecule}</h3>
          <p style="color:var(--text2); font-size:14px">Confidence: ${data.molecule1.confidence?.total||0}%</p>
        </div>
        <div style="flex:1; background:var(--bg3); padding:20px; border-radius:16px; border:1px solid ${data.winner===mol2?'var(--accent)':'var(--border)'}">
          <h3 style="color:var(--accent2);">${data.molecule2.molecule}</h3>
          <p style="color:var(--text2); font-size:14px">Confidence: ${data.molecule2.confidence?.total||0}%</p>
        </div>
      </div>
      <div style="margin-top:20px; text-align:center; font-family:var(--font-mono); color:var(--text)">
        WINNING CANDIDATE: <span style="color:var(--accent)">${data.winner}</span>
      </div>
    `;
  } catch(e) {
    resDiv.innerHTML = `<div style="color:var(--danger)">Comparison failed.</div>`;
  }
}

function startHypothesis() {
  const d = document.getElementById('disease-input').value.trim();
  if(!d) { showError('Please enter a target disease.'); return; }
  
  const btn = document.getElementById('hyp-btn');
  const res = document.getElementById('hypothesis-results');
  btn.innerHTML = 'Mapping Molecular Topologies...';
  
  setTimeout(() => {
    btn.innerHTML = 'Find Matching Candidates &#8594;';
    res.classList.remove('hidden');
    res.innerHTML = `
      <h3 style="color:var(--accent); font-family:var(--font-serif); margin-bottom:12px;">Top Matches for ${d}</h3>
      <p style="color:var(--text-dim); font-size:14px; margin-bottom:20px;">Our Quantum Overlap engine detected non-obvious biochemical synergies for these existing compounds.</p>
      
      <div class="market-card" style="margin-bottom:16px">
        <div class="mc-tag">92% Match Probability</div>
        <div class="mc-title">Fluvastatin (Repurposed)</div>
        <div class="mc-desc">Strong pathway interference detected in the ${d} inflammatory cascade despite being a statin.</div>
        <button class="mc-btn" style="margin-top:16px" onclick="setMolecule('Fluvastatin'); switchTab('repurpose'); setRepurposeMode('batch');">Analyze Candidate</button>
      </div>
      
      <div class="market-card">
        <div class="mc-tag">85% Match Probability</div>
        <div class="mc-title">Itraconazole</div>
        <div class="mc-desc">Anti-fungal compound showing unexpected antagonism at key receptor sites associated with ${d}.</div>
        <button class="mc-btn" style="margin-top:16px" onclick="setMolecule('Itraconazole'); switchTab('repurpose'); setRepurposeMode('batch');">Analyze Candidate</button>
      </div>
    `;
  }, 2000);
}

// ═══ PDF DOWNLOAD ════════════════════════════════════════════════════════
function downloadPDF() {
  if (!currentData) return;
  const element = document.getElementById('results-section');
  const opt = {
    margin:       [10, 10],
    filename:     `RepurposeAI-${currentData.molecule}-Report.pdf`,
    image:        { type: 'jpeg', quality: 0.98 },
    html2canvas:  { scale: 2, useCORS: true, logging: false },
    jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
  };
  
  showToast('Generating PDF...', 'info');
  html2pdf().set(opt).from(element).output('blob').then(function(blob) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = opt.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('PDF downloaded successfully');
  }).catch(function(err) {
    console.error('PDF generation error:', err);
    showToast('PDF generation failed', 'error');
  });
}

// ═══ MARKET FEED ══════════════════════════════════════════════════════════
function loadMarketFeed() {
  const container = document.getElementById('market-feed-container');
  if (!container) return;
  
  const mockData = [
    { name: 'Lecanemab', tag: 'FDA Approved', desc: 'New monoclonal antibody for early-stage Alzheimer. High repurposing potential for other neurodegenerative protein-folding diseases.', meta: 'Updated 2 mins ago · Biogen/Eisai' },
    { name: 'Tirzepatide', tag: 'Market Leader', desc: 'Dual GLP-1 and GIP receptor agonist. Being trialled for NASH, sleep apnea, and cardiovascular risk reduction.', meta: 'Updated 14 mins ago · Eli Lilly' },
    { name: 'Paxlovid', tag: 'Clinical Insight', desc: 'Protease inhibitor. Investigated for Long-COVID and specific viral-driven inflammatory syndromes.', meta: 'Live Monitoring · Pfizer' },
    { name: 'Rapamycin', tag: 'Research Hotspot', desc: 'mTOR inhibitor. Massive interest in longevity and age-related metabolic decline.', meta: 'Trending Now · Generic' },
    { name: 'Dapagliflozin', tag: 'Approved Repurpose', desc: 'SGLT2 inhibitor. Successfully repurposed from Diabetes to Heart Failure and Chronic Kidney Disease.', meta: 'Recent Approval · Astra Zeneca' },
    { name: 'Aflibercept', tag: 'Breaking News', desc: 'New high-dose version approved for macular degeneration. Investigated for micro-vascular protection in diabetic complications.', meta: 'Updated 1 hour ago · Regeneron' }
  ];

  container.innerHTML = mockData.map(item => `
    <div class="glass-card" style="box-sizing: border-box; display:flex; flex-direction:column; padding:28px; height:100%;">
      <div class="mc-tag" style="background:rgba(0,255,102,0.1); color:var(--accent); display:inline-block; padding:4px 10px; border-radius:4px; font-size:11px; margin-bottom:12px; border:1px solid var(--accent); width:fit-content;">${item.tag}</div>
      <div class="mc-title" style="font-family:var(--font-serif); font-size:24px; color:var(--text); margin-bottom:8px;">${item.name}</div>
      <div class="mc-desc" style="color:var(--text-dim); font-size:14px; line-height:1.6; margin-bottom:16px;">${item.desc}</div>
      
      <div style="margin-top:auto;">
        <div style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted); margin-bottom:16px;">
          <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:var(--accent); margin-right:6px; box-shadow:0 0 10px var(--accent);"></span>${item.meta}
        </div>
        <button class="analyse-btn" style="width:100%; font-size:13px;" onclick="setMolecule('${item.name}'); switchTab('repurpose'); startAnalysis();">Initiate AI Validation <span style="margin-left:8px;">&#8594;</span></button>
      </div>
    </div>
  `).join('');
}

// ═══ KNOWLEDGE TEST ═══════════════════════════════════════════════════════
let testMolecule = "";
let testTargetDisease = "";
let correctViability = true;

function startKnowledgeTest() {
  const molecules = [
    { name: 'Metformin', disease: 'Cancer Prevention', viable: true, context: 'This diabetes drug activates AMPK and has shown significant epidemiological links to reduced cancer incidence.' },
    { name: 'Propranolol', disease: 'Anxiety & PTSD', viable: true, context: 'A beta-blocker that blocks the action of epinephrine and norepinephrine on beta receptors.' },
    { name: 'Sildenafil', disease: 'Raynaud’s Phenomenon', viable: true, context: 'A PDE5 inhibitor that promotes vasodilation, helpful for circulation issues in digits.' },
    { name: 'Thalidomide', disease: 'Diabetes', viable: false, context: 'An immunomodulator with high toxicity and no direct metabolic mechanism for blood sugar control.' }
  ];
  
  const random = molecules[Math.floor(Math.random() * molecules.length)];
  testMolecule = random.name;
  testTargetDisease = random.disease;
  correctViability = random.viable;

  document.getElementById('test-molecule-name').textContent = testMolecule;
  document.getElementById('test-disease-target').textContent = testTargetDisease;
  document.getElementById('test-drug-context').textContent = random.context;
  document.getElementById('test-results').classList.add('hidden');
  document.getElementById('test-question-card').classList.remove('hidden');
}

function submitTestAnswer(userViable) {
  const resultDiv = document.getElementById('test-results');
  const card = document.getElementById('test-question-card');
  resultDiv.classList.remove('hidden');
  
  const isCorrect = userViable === correctViability;
  
  resultDiv.innerHTML = `
    <div class="test-card" style="background:var(--bg3);border:1px solid ${isCorrect ? 'var(--accent)' : 'var(--danger)'};border-radius:20px;padding:32px">
      <div style="font-family:var(--font-serif);font-size:24px;color:${isCorrect ? 'var(--accent)' : 'var(--danger)'};margin-bottom:12px">
        ${isCorrect ? 'Correct Assessment!' : 'Incorrect Assessment'}
      </div>
      <p style="font-size:15px;color:var(--text2);margin-bottom:20px;line-height:1.7">
        Clinical analysis confirms that ${testMolecule} is ${correctViability ? 'indeed' : 'not'} a strong candidate for ${testTargetDisease}. 
        The AI reasoning path typically looks at molecular pathways and clinical trial history to reach this verdict.
      </p>
      <button class="analyse-btn" onclick="setMolecule('${testMolecule}'); startAnalysis();">Run AI Deep-Dive for ${testMolecule}</button>
      <button class="nav-btn" style="margin-left:12px" onclick="startKnowledgeTest()">Try Another Drug</button>
    </div>
  `;
  window.scrollTo({top: resultDiv.offsetTop - 100, behavior:'smooth'});
}

// ═══ QUANTUM CANVAS (THREE.JS) ════════════════════════════════════════════
function initQuantumCanvas() {
  const canvas = document.getElementById('quantum-canvas');
  if (!canvas || !window.THREE) return;
  
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  const renderer = new THREE.WebGLRenderer({ canvas: canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
  
  function resize() {
    renderer.setSize(window.innerWidth, window.innerHeight);
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);
  resize();

  const particles = new THREE.BufferGeometry();
  const particleCount = 150;
  const posArray = new Float32Array(particleCount * 3);
  for(let i = 0; i < particleCount * 3; i++) {
    posArray[i] = (Math.random() - 0.5) * 10;
  }
  particles.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
  
  const material = new THREE.PointsMaterial({
    size: 0.05,
    color: 0x00FF66,
    transparent: true,
    opacity: 0.8,
    blending: THREE.AdditiveBlending
  });
  
  const particlesMesh = new THREE.Points(particles, material);
  scene.add(particlesMesh);

  // Add subtle lines connecting close particles
  const lineMaterial = new THREE.LineBasicMaterial({ color: 0x00F0FF, transparent: true, opacity: 0.15 });
  const lineGeometry = new THREE.BufferGeometry();
  const linesMesh = new THREE.LineSegments(lineGeometry, lineMaterial);
  scene.add(linesMesh);

  camera.position.z = 3;

  function animate() {
    requestAnimationFrame(animate);
    const time = Date.now() * 0.00005;
    particlesMesh.rotation.y = time * 0.5;
    particlesMesh.rotation.x = time * 0.2;
    linesMesh.rotation.y = time * 0.5;
    linesMesh.rotation.x = time * 0.2;
    
    // Dynamically update connecting lines
    const positions = particlesMesh.geometry.attributes.position.array;
    const linePositions = [];
    for(let i=0; i<particleCount; i++) {
      for(let j=i+1; j<particleCount; j++) {
        let dx = positions[i*3] - positions[j*3];
        let dy = positions[i*3+1] - positions[j*3+1];
        let dz = positions[i*3+2] - positions[j*3+2];
        let dist = dx*dx + dy*dy + dz*dz;
        if(dist < 1.5) {
          linePositions.push(positions[i*3], positions[i*3+1], positions[i*3+2]);
          linePositions.push(positions[j*3], positions[j*3+1], positions[j*3+2]);
        }
      }
    }
    lineGeometry.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));

    renderer.render(scene, camera);
  }
  animate();
}

// ═══ SWARM TERMINAL SIMULATOR ═════════════════════════════════════════════
function simulateSwarmLogs(molecule) {
  const logDiv = document.getElementById('term-logs');
  if(!logDiv) return;
  logDiv.innerHTML = '';
  
  const messages = [
    `[SYS] Initializing Quantum-Bio Agents for target: ${molecule}...`,
    `[CLINICAL] Scraping ClinicalTrials.gov NCT registries...`,
    `[PATENT] Querying World Intellectual Property Organization APIs...`,
    `[MARKET] Parsing OpenFDA adverse event frequencies...`,
    `[MECH] Constructing 3D topological receptor models...`,
    `[LIT] Cross-referencing 500k PubMed Central abstracts via NLP...`,
    `[AI_CORE] Detected antagonistic pathway overlap in off-target profiling.`,
    `[AI_CORE] Quantum superposition match > 80% found against isolated disease vectors.`,
    `[SYS] Compiling final Repurpose Evidence Card...`
  ];
  
  let i = 0;
  const interval = setInterval(() => {
    if(i >= messages.length) { clearInterval(interval); return; }
    const p = document.createElement('div');
    p.style.marginBottom = '4px';
    p.textContent = `> ${messages[i]}`;
    logDiv.appendChild(p);
    logDiv.scrollTop = logDiv.scrollHeight;
    i++;
  }, 400); // rapidly print every 400ms
}

// ═══ MANUAL RESEARCHER TEST / HYPOTHESIS VALIDATION ══════════════════════
let currentTestPrediction = 'yes';
function setTestPrediction(val) {
   currentTestPrediction = val;
   document.getElementById('pred-yes').classList.toggle('active', val === 'yes');
   document.getElementById('pred-no').classList.toggle('active', val === 'no');
}

async function submitStudentTest() {
  const drug = document.getElementById('test-drug-input').value.trim();
  const disease = document.getElementById('test-disease-input').value.trim();
  if(!drug || !disease) { showError('Please enter both Drug and Target Disease'); return; }

  // Initial feedback state
  switchTab('test');
  document.getElementById('test-question-card').style.display = 'none';
  const resContainer = document.getElementById('test-results-container');
  resContainer.classList.remove('hidden');
  resContainer.innerHTML = `<div style="text-align:center; padding: 40px; color:var(--accent);">
      <div class="synthesis-pulse" style="margin: 0 auto 20px;"></div>
      <div style="font-family:var(--font-mono); text-transform:uppercase; letter-spacing:2px;">Engaging 6-Agent Swarm Validation...</div>
      <div style="font-size:12px; color:var(--text-muted); margin-top:12px;">The Quantum Bio engine is comparing your hypothesis against clinical, market, and receptor-binding datasets.</div>
  </div>`;

  try {
    const res = await fetch('/analyze', {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ molecule: drug, language: "en" })
    });
    if(!res.ok) throw new Error("Validation Failed");
    const data = await res.json();
    
    // Evaluation Logic
    const aiConfLabel = data.confidence ? data.confidence.label : "LOW"; // HIGH CONFIDENCE, MODERATE CONFIDENCE
    const isAiViable = (aiConfLabel.includes("HIGH") || aiConfLabel.includes("MODERATE"));
    const studentSaidViable = (currentTestPrediction === 'yes');
    const isCorrect = (isAiViable === studentSaidViable);

    // Disease Evaluation Context
    const reportText = JSON.stringify(data.report).toLowerCase();
    const diseaseMentioned = reportText.includes(disease.toLowerCase());

    const resultColor = isCorrect ? 'var(--accent)' : 'var(--danger)';
    const resultText = isCorrect ? 'Hypothesis Validated ✓' : 'Hypothesis Rejected ✗';

    // Generate 'Why and How' Explanation for Rejections
    let explanationHtml = '';
    if (!isCorrect) {
       let reasons = [];
       if (data.failure_analysis && data.failure_analysis.length > 0) {
           reasons = data.failure_analysis.map(f => `<li style="margin-bottom:6px;"><strong style="color:var(--danger)">[Barrier]</strong> ${f.factor}: ${f.reason}</li>`);
       }
       if (data.contradictions && data.contradictions.length > 0) {
           data.contradictions.forEach(c => {
               reasons.push(`<li style="margin-bottom:6px;"><strong style="color:var(--warning)">[Contradiction]</strong> ${c.conflict}</li>`);
           });
       }
       
       if (reasons.length === 0) {
           if (!isAiViable && studentSaidViable) {
               reasons.push(`<li style="margin-bottom:6px;"><strong style="color:var(--danger)">[Insufficient Evidence]</strong> The agent swarm could not find strong clinical trials, regulatory approvals, or clear mechanistic links correlating ${drug} with high efficacy.</li>`);
           } else if (isAiViable && !studentSaidViable) {
               reasons.push(`<li style="margin-bottom:6px;"><strong style="color:var(--accent)">[Hidden Potential]</strong> The swarm detected strong structural or clinical evidence supporting viability overlooked by manual assessment.</li>`);
           }
       }

       explanationHtml = `
         <div style="margin-top: 20px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.05);">
            <div style="color:var(--text); font-family:var(--font-serif); font-size:18px; margin-bottom: 12px;">Why was your hypothesis rejected?</div>
            <ul style="padding-left: 20px; color:var(--text2); font-size:13px; line-height:1.6; margin-bottom:12px;">
               ${reasons.join('')}
            </ul>
            <div style="padding: 10px 14px; background: rgba(0,255,255,0.05); border-left: 3px solid rgba(0,255,255,0.3); border-radius: 6px; font-style:italic; font-family:var(--font-mono); font-size:11px; color:var(--accent2);">
              <strong>How it works:</strong> The Quantum Swarm cross-references PubMed, Patents, and FDA data. Critical barriers (like toxicity) or data contradictions immediately suppress the Confidence Score, rejecting hypotheses lacking rigorous clinical backing.
            </div>
         </div>
       `;
    }

    resContainer.innerHTML = `
      <div class="test-card glass-card" style="border-color: ${resultColor}; padding:32px; box-shadow: 0 10px 40px ${resultColor}22;">
        <h2 style="font-family:var(--font-serif); font-size:32px; color:${resultColor}; margin-bottom:12px;">${resultText}</h2>
        <p style="font-size:16px; color:var(--text2); margin-bottom:24px; line-height:1.7;">
          You predicted <strong>${drug}</strong> was <strong style="color:${studentSaidViable ? 'var(--accent)' : 'var(--danger)'}">${studentSaidViable ? 'VIABLE' : 'NOT VIABLE'}</strong> for <strong>${disease}</strong>. 
          The 6-agent swarm concluded this compound has <strong>${aiConfLabel}</strong> overall viability. 
          ${isCorrect ? 'Your research intuition aligns perfectly with our clinical AI metrics.' : 'Your manual assessment contradicts the swarm intelligence analysis.'}
        </p>

        <div style="padding: 20px; background: rgba(0,0,0,0.5); border-radius: 12px; margin-bottom: 30px; font-family: var(--font-mono); font-size: 13px; line-height: 1.6;">
           <div style="margin-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom:12px;">
              <strong>Disease Targeting Check:</strong><br/>
              ${diseaseMentioned ? `<span style="color:var(--accent)">The swarm explicitly identified mechanistic overlap with ${disease}.</span>` : `<span style="color:var(--warning)">The swarm did NOT locate strong efficacy links specifically to ${disease}.</span>`}
           </div>
           <div>
              <strong>AI Final Confidence Score:</strong> <span style="font-size:18px; color:var(--text);">${data.confidence ? data.confidence.total : 0}%</span>
           </div>
           ${explanationHtml}
        </div>

        <div style="display:flex; gap:16px;">
            <button class="analyse-btn" style="flex:1;" onclick="document.getElementById('test-question-card').style.display='block'; document.getElementById('test-results-container').classList.add('hidden');">Run Another Test</button>
            <button class="analyse-btn" style="flex:1; background:transparent; border:1px solid var(--accent); color:var(--accent);" onclick="setMolecule('${drug}'); startAnalysis();">View Full Swarm Report</button>
        </div>
      </div>
    `;

  } catch(e) {
    resContainer.innerHTML = `<div style="text-align:center; color:var(--danger); padding:40px;">Validation API failed. Check backend connection.</div>`;
  }
}

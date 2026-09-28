/* ============================================================================
   Domino Analyzer Pro — app.js (v3)
   Sections: state · utils · persistence · setup · render · modals ·
             attribution · play flow (timeline) · API · results · init

   Semua perhitungan berat (Monte-Carlo, skoring, ranking) dilakukan engine
   C++ lewat POST /api/analyze — file ini hanya UI + orkestrasi.
   v3: atribusi kartu per lawan, profil kekayaan angka, timeline undo,
   autosave + export/import, banner menang, alur PASS, cancel analisis,
   confidence interval, PWA, aksesibilitas.
   ========================================================================== */
'use strict';

/* ---- state ---- */
const state = {
  myHand: [],        // ["3-5", ...]
  boardTiles: [],    // { tile:[a,b], origKey, owner, source }
  allPlayed: [],     // semua key yang ada di papan
  playedBy: [],      // paralel allPlayed: "me"|"opp1".."opp4"|"unknown"
  opponents: [],     // { passes:[{left,right,boardLen}], eliminated:[num] }
  pending: null,     // { key, source } menunggu pilihan ujung
  pendingAttrib: null, // { key } menunggu atribusi pemain
  isAnalyzing: false,
  liveMode: false,   // mode analisis otomatis (play/stop)
  pendingRun: false, // ada permintaan analisis menunggu yang sedang berjalan
  abortCtl: null,    // AbortController analisis berjalan
  lastAnalysis: null,// respons engine terakhir (untuk panel profil lawan)
  timeline: [],      // snapshot untuk undo global (maks 100)
};

const SEED = 20240922; // deterministik: input sama -> hasil sama
const STORAGE_KEY = 'domino-analyzer-v3';
const $ = (id) => document.getElementById(id);

// Escape nilai dinamis sebelum masuk innerHTML — pertahanan XSS untuk data
// sesi terimpor/pesan error server yang tidak kita kendalikan.
function esc(v) {
  return String(v).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ---- utils: tiles & pips ---- */
const PIPS = {
  0:[0,0,0,0,0,0,0,0,0], 1:[0,0,0,0,1,0,0,0,0], 2:[0,0,1,0,0,0,1,0,0],
  3:[0,0,1,0,1,0,1,0,0], 4:[1,0,1,0,0,0,1,0,1], 5:[1,0,1,0,1,0,1,0,1],
  6:[1,0,1,1,0,1,1,0,1],
};

function getAllTiles() {
  const t = [];
  for (let i = 0; i <= 6; i++)
    for (let j = i; j <= 6; j++) t.push([i, j]);
  return t;
}
const tileKey = (t) => `${Math.min(t[0], t[1])}-${Math.max(t[0], t[1])}`;
const parseKey = (k) => k.split('-').map(Number);
const tileValue = (k) => { const [a, b] = parseKey(k); return a + b; };
const handValue = (arr) => arr.reduce((s, k) => s + tileValue(k), 0);
const arrToSet = (arr) => Object.fromEntries(arr.map((k) => [k, true]));
const tileLabel = (k) => { const [a, b] = parseKey(k); return `kartu ${a} ${b}`; };

function renderPipsHTML(val, prefix) {
  const p = PIPS[val];
  let h = `<div class="${prefix}-half">`;
  for (let i = 0; i < 9; i++) h += `<div class="${prefix}-pip${p[i] ? '' : ' off'}"></div>`;
  return h + '</div>';
}

function getLeftEnd() {
  return state.boardTiles.length ? state.boardTiles[0].tile[0] : -1;
}
function getRightEnd() {
  return state.boardTiles.length ? state.boardTiles[state.boardTiles.length - 1].tile[1] : -1;
}
function getAllUsedKeys() {
  const used = arrToSet(state.myHand);
  state.allPlayed.forEach((k) => { used[k] = true; });
  return used;
}
function getRemainingTiles() {
  const used = getAllUsedKeys();
  return getAllTiles().filter((t) => !used[tileKey(t)]);
}
function getMaxCardsPerPlayer(numPlayers) {
  return Math.floor(28 / numPlayers);
}
function boneyardCount() {
  const numPlayers = parseInt($('playerCount').value, 10);
  const cardsPerPlayer = parseInt($('cardsPerPlayer').value, 10);
  return Math.max(0, 28 - numPlayers * cardsPerPlayer);
}

/* ---- persistence (autosave + export/import) ---- */
function serializeState() {
  return {
    version: 3,
    setup: {
      playerCount: $('playerCount').value,
      cardsPerPlayer: $('cardsPerPlayer').value,
      simCount: $('simCount').value,
      nextSeat: $('nextSeat').value,
      deadlockRule: $('deadlockRule').value,
      tieRule: $('tieRule').value,
      cangkulMode: $('cangkulMode').value,
      adversarial: $('adversarial').checked,
    },
    state: {
      myHand: state.myHand,
      boardTiles: state.boardTiles,
      allPlayed: state.allPlayed,
      playedBy: state.playedBy,
      opponents: state.opponents,
    },
  };
}
function saveState() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(serializeState())); } catch (e) { /* private mode */ }
}
function restoreFrom(obj) {
  if (!obj || obj.version !== 3 || !obj.state || !obj.setup) return false;
  const s = obj.state;
  if (!Array.isArray(s.myHand) || !Array.isArray(s.allPlayed)) return false;
  // Data sesi (file impor / localStorage) TIDAK dipercaya: validasi nilai dulu
  // sebelum menyentuh state apa pun — kunci hanya "lo-hi" 0..6, angka 0..6,
  // playedBy hanya label pemain sah (mencegah XSS & crash PIPS[NaN]).
  const isTile = (k) => typeof k === 'string' && /^[0-6]-[0-6]$/.test(k);
  const isN06 = (v) => Number.isInteger(v) && v >= 0 && v <= 6;
  if (!s.myHand.every(isTile) || !s.allPlayed.every(isTile)) return false;
  if (Array.isArray(s.boardTiles) && !s.boardTiles.every((bt) =>
    bt && typeof bt === 'object' && Array.isArray(bt.tile) &&
    bt.tile.length === 2 && bt.tile.every(isN06) &&
    (bt.origKey === undefined || isTile(bt.origKey)))) return false;
  if (Array.isArray(s.playedBy) && s.playedBy.length === s.allPlayed.length &&
      !s.playedBy.every((w) => w === 'me' || w === 'unknown' ||
        (typeof w === 'string' && /^opp[1-4]$/.test(w)))) return false;
  if (Array.isArray(s.opponents) && !s.opponents.every((o) =>
    o && typeof o === 'object' &&
    Array.isArray(o.passes) && o.passes.every((p) =>
      p && typeof p === 'object' && isN06(p.left) && isN06(p.right)) &&
    Array.isArray(o.eliminated) && o.eliminated.every(isN06))) return false;
  $('playerCount').value = String(obj.setup.playerCount || 4);
  updateCardsPerPlayerOptions();
  $('cardsPerPlayer').value = String(obj.setup.cardsPerPlayer || 7);
  $('simCount').value = String(obj.setup.simCount || 2000);
  updateCardsPerPlayerOptions(); // re-populate nextSeat for this player count
  $('nextSeat').value = String(obj.setup.nextSeat || 1);
  if (obj.setup.deadlockRule) $('deadlockRule').value = obj.setup.deadlockRule;
  if (obj.setup.tieRule) $('tieRule').value = obj.setup.tieRule;
  if (obj.setup.cangkulMode) $('cangkulMode').value = obj.setup.cangkulMode;
  $('adversarial').checked = !!obj.setup.adversarial;
  state.myHand = s.myHand;
  state.boardTiles = Array.isArray(s.boardTiles) ? s.boardTiles : [];
  state.allPlayed = s.allPlayed;
  state.playedBy = Array.isArray(s.playedBy) && s.playedBy.length === s.allPlayed.length
    ? s.playedBy : s.allPlayed.map(() => 'unknown');
  state.opponents = Array.isArray(s.opponents) ? s.opponents : [];
  initOpponents();
  updateSetupInfo();
  updateAll();
  return true;
}
function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) restoreFrom(JSON.parse(raw));
  } catch (e) { /* korup — mulai bersih */ }
}

/* ---- timeline (undo global yang konsisten, termasuk PASS) ---- */
function pushSnapshot() {
  state.timeline.push(JSON.stringify({
    myHand: state.myHand,
    boardTiles: state.boardTiles,
    allPlayed: state.allPlayed,
    playedBy: state.playedBy,
    opponents: state.opponents,
  }));
  if (state.timeline.length > 100) state.timeline.shift();
}
/* ---- mode analisis LIVE (v3.2): play/stop, auto re-run tiap info baru ---- */
function setLiveMode(on) {
  state.liveMode = on;
  const btn = $('analyzeBtn');
  const chip = $('liveChip');
  const hdr = $('headerLive');
  btn.classList.toggle('running', on);
  chip.classList.toggle('active', on);
  if (hdr) {
    hdr.classList.toggle('on', on);
    hdr.classList.toggle('paused', !on);
    hdr.textContent = on ? '🔴 LIVE' : '⏸ LIVE';
  }
  if (on) {
    btn.textContent = '⏸ Jeda Live';
    runAnalysis();
  } else {
    btn.textContent = '▶️ Analisis Live';
    if (state.abortCtl) state.abortCtl.abort(); // hentikan run yang berjalan
  }
}

function undoLastAction() {
  if (state.isAnalyzing || state.timeline.length === 0) return;
  const snap = JSON.parse(state.timeline.pop());
  state.myHand = snap.myHand;
  state.boardTiles = snap.boardTiles;
  state.allPlayed = snap.allPlayed;
  state.playedBy = snap.playedBy;
  state.opponents = snap.opponents;
  state.lastAnalysis = null;
  updateAll();
  runAnalysis(); // live: undo ikut memicu analisis ulang
}

/* ---- setup ---- */
function initOpponents() {
  const numOpp = parseInt($('playerCount').value, 10) - 1;
  const next = [];
  for (let i = 0; i < numOpp; i++) {
    next.push(state.opponents[i] || { passes: [], eliminated: [] });
  }
  state.opponents = next;
}

function updateCardsPerPlayerOptions() {
  const numPlayers = parseInt($('playerCount').value, 10);
  const maxCards = getMaxCardsPerPlayer(numPlayers);
  const sel = $('cardsPerPlayer');
  const oldVal = parseInt(sel.value, 10);

  sel.innerHTML = '';
  for (let c = 3; c <= maxCards; c++) {
    const opt = document.createElement('option');
    opt.value = c;
    opt.textContent = c + (c === maxCards ? ' (maks)' : '');
    sel.appendChild(opt);
  }
  sel.value = oldVal >= 3 && oldVal <= maxCards ? oldVal : maxCards;

  // nextSeat: 1..numPlayers-1 (Lawan k main setelah saya)
  const ns = $('nextSeat');
  const oldNs = parseInt(ns.value, 10);
  ns.innerHTML = '';
  for (let p = 1; p < numPlayers; p++) {
    const opt = document.createElement('option');
    opt.value = p;
    opt.textContent = `Lawan ${p}`;
    ns.appendChild(opt);
  }
  ns.value = oldNs >= 1 && oldNs < numPlayers ? oldNs : 1;

  updateSetupInfo();
  initOpponents();
}

function updateSetupInfo() {
  const numPlayers = parseInt($('playerCount').value, 10);
  const cardsPerPlayer = parseInt($('cardsPerPlayer').value, 10);
  const distributed = numPlayers * cardsPerPlayer;
  const bone = Math.max(0, 28 - distributed);

  const useCangkul = $('cangkulMode').value === 'ya';
  let info = `${numPlayers} pemain × ${cardsPerPlayer} kartu = ${distributed} dibagikan`;
  if (bone > 0) {
    info += useCangkul ? ` | Cangkul: ${bone} kartu (aktif)` : ` | Cangkul: TIDAK — ${bone} kartu mati`;
  } else {
    info += ' | Semua kartu terpakai (tanpa sisa)';
  }
  info += ` (maks ${getMaxCardsPerPlayer(numPlayers)}/pemain)`;
  $('setupInfo').textContent = info;
}

/* ---- quality banner ---- */
function analyzeHandQuality(handArr) {
  if (handArr.length === 0) return null;
  const counts = [0, 0, 0, 0, 0, 0, 0];
  let doubles = 0, totalValue = 0;
  handArr.forEach((k) => {
    const [a, b] = parseKey(k);
    counts[a]++; counts[b]++;
    if (a === b) doubles++;
    totalValue += a + b;
  });
  const maxCount = Math.max(...counts);
  const maxNum = counts.indexOf(maxCount);
  let quality, qualityClass, message;
  if (maxCount >= 5) {
    quality = '🌟 SANGAT BAGUS & BERUNTUNG'; qualityClass = 'excellent';
    message = `Anda punya ${maxCount} kartu angka ${maxNum}! Dominasi total — kuasai ujung papan dengan angka ${maxNum}.`;
  } else if (maxCount >= 4) {
    quality = '✅ KARTU BAGUS'; qualityClass = 'good';
    message = `Anda punya ${maxCount} kartu angka ${maxNum}. Modal bagus untuk mendominasi permainan!`;
  } else if (doubles >= 4) {
    quality = '⚠️ KARTU JELEK (BANYAK BALAK)'; qualityClass = 'bad';
    message = `Anda punya ${doubles} balak! Prioritaskan buang balak secepatnya, siapkan strategi "adu".`;
  } else if (maxCount >= 3) {
    quality = '👍 KARTU LUMAYAN'; qualityClass = 'normal';
    message = `Anda punya ${maxCount} kartu angka ${maxNum}. Cukup untuk mengontrol satu ujung papan.`;
  } else {
    quality = '📊 KARTU STANDAR'; qualityClass = 'normal';
    message = 'Tidak ada dominasi khusus. Buang kartu besar & balak duluan, siapkan untuk kondisi "adu".';
  }
  return { counts, doubles, totalValue, maxCount, maxNum, quality, qualityClass, message };
}

function updateQualityBanner() {
  const banner = $('qualityBanner');
  const q = analyzeHandQuality(state.myHand);
  if (!q) { banner.classList.remove('active'); return; }
  banner.className = `quality-banner active ${q.qualityClass}`;
  banner.innerHTML = `<strong>${q.quality}</strong><br>${q.message}` +
    (q.doubles > 0 ? `<br>⚡ Balak: ${q.doubles} | Total mata: ${q.totalValue}` : '');
}

/* ---- render: papan ---- */
function updateBoardDisplay() {
  const chain = $('boardChain');
  const leftTag = $('leftEndTag');
  const rightTag = $('rightEndTag');
  const status = $('boardStatus');
  const le = getLeftEnd(), re = getRightEnd();

  if (le !== -1) { leftTag.textContent = `Kiri: ${le}`; leftTag.classList.remove('empty'); }
  else { leftTag.textContent = 'Kiri: -'; leftTag.classList.add('empty'); }
  if (re !== -1) { rightTag.textContent = `Kanan: ${re}`; rightTag.classList.remove('empty'); }
  else { rightTag.textContent = 'Kanan: -'; rightTag.classList.add('empty'); }

  $('boneyardChip').textContent = `📦 ${boneyardCount()}`;

  if (state.boardTiles.length === 0) {
    chain.innerHTML = '<div class="board-empty"><div class="icon">🎲</div>' +
      '<div>Papan kosong — pilih kartu dari tangan Anda</div></div>';
    status.textContent = 'Menunggu kartu pertama...';
    return;
  }

  const html = state.boardTiles.map((bt) => {
    const [a, b] = bt.tile;
    const ownerClass = bt.owner === 'me' ? 'my-tile' : bt.owner === 'opp' ? 'opp-tile' : 'first-tile';
    const orientClass = a === b ? 'vertical' : 'horizontal';
    const divider = a === b
      ? '<div class="board-divider-v"></div>'
      : '<div class="board-divider-h"></div>';
    return `<div class="board-tile ${orientClass} ${ownerClass}">` +
      `<div class="board-tile-inner">${renderPipsHTML(a, 'b')}${divider}${renderPipsHTML(b, 'b')}</div></div>`;
  }).join('');

  chain.innerHTML = html;
  status.textContent = `${state.boardTiles.length} kartu di papan`;
  const scroll = $('boardScroll');
  setTimeout(() => { scroll.scrollLeft = scroll.scrollWidth; }, 50);
}

/* ---- render: tangan ---- */
function updateHandDisplay() {
  const container = $('handTiles');
  const countEl = $('handCount');
  const cardsPerPlayer = parseInt($('cardsPerPlayer').value, 10);

  countEl.textContent = `${state.myHand.length}/${cardsPerPlayer} kartu`;
  countEl.style.color = state.myHand.length > cardsPerPlayer ? '#f85149' : '#8b949e';

  if (state.myHand.length === 0) {
    container.innerHTML = '<span class="placeholder">Klik "+ Pilih Kartu Saya" untuk menambahkan kartu</span>';
    $('winBanner').classList.toggle('active', state.boardTiles.length > 0);
    return;
  }
  $('winBanner').classList.remove('active');

  const le = getLeftEnd(), re = getRightEnd();
  const isFirstMove = le === -1 && re === -1;

  container.innerHTML = state.myHand.map((key) => {
    const [a, b] = parseKey(key);
    const playable = isFirstMove || a === le || b === le || a === re || b === re;
    const cls = playable ? 'playable' : 'unplayable';
    return `<div class="hand-card ${cls}" data-key="${esc(key)}" role="button" tabindex="0" aria-label="${esc(tileLabel(key))}${playable ? ', bisa dimainkan' : ', tidak bisa dimainkan'}">` +
      `${renderPipsHTML(a, 'h')}<div class="h-div"></div>${renderPipsHTML(b, 'h')}</div>`;
  }).join('');

  container.querySelectorAll('.hand-card').forEach((el) => {
    el.addEventListener('click', () => {
      if (!state.isAnalyzing) handleCardPlay(el.dataset.key, 'hand');
    });
  });
}

/* ---- render: lawan ---- */
function getPossibleCardsForOpponent(oppIdx, unknownKeys) {
  const elim = state.opponents[oppIdx].eliminated;
  return unknownKeys.filter((k) => {
    const [a, b] = parseKey(k);
    return !elim.includes(a) && !elim.includes(b);
  });
}

function markOpponentPass(oppIdx) {
  const le = getLeftEnd(), re = getRightEnd();
  if (le === -1 && re === -1) {
    alert('Papan masih kosong — belum bisa mencatat PASS!');
    return;
  }
  pushSnapshot();
  const opp = state.opponents[oppIdx];
  opp.passes.push({ left: le, right: re, boardLen: state.boardTiles.length });
  if (le !== -1 && !opp.eliminated.includes(le)) opp.eliminated.push(le);
  if (re !== -1 && !opp.eliminated.includes(re)) opp.eliminated.push(re);
  updateOpponentsDisplay();
  runAnalysis(); // live: hasil ikut ter-update otomatis
}

function updateOpponentsDisplay() {
  const container = $('opponentsContainer');
  const numPlayers = parseInt($('playerCount').value, 10);
  const cardsPerPlayer = parseInt($('cardsPerPlayer').value, 10);
  const numOpp = numPlayers - 1;
  const distributed = numPlayers * cardsPerPlayer;
  // Kartu lawan TERSEMBUNYI: kartu yang sudah main dikurangi yang jelas milik
  // lawan (atribusi oppN) — kartu itu adalah kartu lawan, bukan kartu rahasia.
  const attribOpp = state.playedBy.filter((w) => w && w.startsWith('opp')).length;
  const totalOppCardsNow = Math.max(
    0,
    distributed - state.myHand.length - (state.allPlayed.length - attribOpp)
  );
  const perOpp = Math.floor(totalOppCardsNow / numOpp);

  const used = getAllUsedKeys();
  const unknownKeys = getAllTiles()
    .map(tileKey)
    .filter((k) => !used[k]);

  const le = getLeftEnd(), re = getRightEnd();
  const boardActive = !(le === -1 && re === -1);
  const engineOpps = state.lastAnalysis && Array.isArray(state.lastAnalysis.opponents)
    ? state.lastAnalysis.opponents : null;

  const html = [];
  for (let i = 0; i < numOpp; i++) {
    const opp = state.opponents[i];
    const hasPass = opp.passes.length > 0;
    const possible = getPossibleCardsForOpponent(i, unknownKeys);
    const cardCount = i === numOpp - 1
      ? totalOppCardsNow - perOpp * (numOpp - 1)
      : perOpp;

    // held-known dari atribusi kartu lawan
    const heldKeys = [];
    state.allPlayed.forEach((k, idx) => {
      if (state.playedBy[idx] === `opp${i + 1}`) heldKeys.push(k);
    });

    let h = `<div class="opp-card${hasPass ? ' has-pass' : ''}">`;
    h += '<div class="opp-card-header">';
    h += `<div class="opp-name">👤 Lawan ${i + 1}</div>`;
    h += `<div class="opp-card-count">${cardCount} kartu</div>`;
    h += '</div>';
    h += '<div class="opp-actions">';
    h += `<button class="opp-btn opp-btn-pass" data-opp="${i}" data-action="pass"${boardActive ? '' : ' disabled'}>⏭ PASS / LEWAT</button>`;
    h += `<button class="opp-btn opp-btn-undo" data-opp="${i}" data-action="undo"${hasPass ? '' : ' disabled'}>↺ Undo</button>`;
    h += '</div>';

    if (hasPass) {
      h += '<div class="opp-elim"><div class="opp-elim-label">❌ PASTI TIDAK PUNYA angka:</div>';
      opp.eliminated.slice().sort((a, b) => a - b).forEach((n) => {
        h += `<span class="elim-chip">${esc(n)}</span>`;
      });
      h += '</div>';
      h += `<div class="opp-passlog">Riwayat pass: ${opp.passes.map((p) => `[${esc(p.left)}|${esc(p.right)}]`).join(' → ')}</div>`;
    }
    if (heldKeys.length > 0) {
      h += '<div style="margin-top:3px;"><span class="opp-elim-label">🎯 Kartu yang dipastikan dimainkan:</span> ';
      heldKeys.forEach((k) => {
        const [x, y] = parseKey(k);
        h += `<span class="opp-held-chip">${x}|${y}</span> `;
      });
      h += '</div>';
    }

    // profil kekayaan angka dari analisis engine terakhir
    if (engineOpps && engineOpps[i]) {
      const prof = engineOpps[i];
      const domBits = (prof.dominant || []).map((d) =>
        `<span class="wd">${d.num}</span> <span class="wm">(~${d.expected.toFixed(1)} kartu, ${d.pct.toFixed(0)}%)</span>`
      ).join(' • ');
      if (domBits) {
        h += `<div class="opp-wealth">🔮 Diduga kuasai: ${domBits}`;
        if (prof.doublesExpected > 0.15) h += ` • balak ≈ ${prof.doublesExpected.toFixed(1)}`;
        h += '</div>';
      }
    }

    // kandidat kartu yang mungkin dipegang lawan ini (v3.1) — klik = dia yang main
    const cand = computeOppCandidates(i, unknownKeys);
    h += `<div class="opp-cand-label">🎴 Kemungkinan kartu (${cand.length}) — klik = dia yang main: <span class="cand-hint-red">🟥 merah = bisa dimainkan sekarang</span></div>`;
    h += '<div class="opp-cand-grid">';
    if (cand.length === 0) {
      h += '<span style="font-size:0.55rem;color:#f85149;">tidak ada kartu yang mungkin — cek data PASS</span>';
    } else {
      cand.forEach((k) => {
        const [x, y] = parseKey(k);
        // glowing merah: kartu ini SAAT INI bisa dibenturkan ke ujung papan
        const playableNow = !boardActive || x === le || y === le || x === re || y === re;
        h += `<div class="opp-cand-card${playableNow ? ' glow-playable' : ''}" data-key="${k}" data-opp="${i}" role="button" tabindex="0" aria-label="${tileLabel(k)}, Lawan ${i + 1}${playableNow ? ', bisa dimainkan saat ini' : ''}">` +
          `${renderPipsHTML(x, 'r')}<div class="r-div"></div>${renderPipsHTML(y, 'r')}</div>`;
      });
    }
    h += '</div>';

    h += `<div class="opp-info">📊 Filter PASS: <strong>${possible.length}</strong> dari ${unknownKeys.length} kartu unknown`;
    if (hasPass && unknownKeys.length > 0) {
      const reducedPct = Math.round((1 - possible.length / unknownKeys.length) * 100);
      h += ` (tereliminasi ${reducedPct}%)`;
    }
    h += '</div></div>';
    html.push(h);
  }

  container.innerHTML = html.join('');
  container.querySelectorAll('.opp-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.dataset.opp, 10);
      if (btn.dataset.action === 'pass') markOpponentPass(idx);
      else undoLastAction();
    });
  });
  container.querySelectorAll('.opp-cand-card').forEach((el) => {
    el.addEventListener('click', () => {
      if (!state.isAnalyzing) handleOppCardPlay(el.dataset.key, parseInt(el.dataset.opp, 10));
    });
  });
}

/* ---- render: peta angka & kartu sisa ---- */
function buildNumberMap() {
  const map = {};
  for (let n = 0; n <= 6; n++) map[n] = { mine: 0, out: 0, unknown: 0 };
  state.myHand.forEach((k) => {
    const [a, b] = parseKey(k);
    map[a].mine++; map[b].mine++;
  });
  state.allPlayed.forEach((k) => {
    const [a, b] = parseKey(k);
    map[a].out++; map[b].out++;
  });
  for (let n = 0; n <= 6; n++) map[n].unknown = 7 - map[n].mine - map[n].out;
  return map;
}

function updateNumberMap() {
  const map = buildNumberMap();
  const le = getLeftEnd(), re = getRightEnd();
  let html = '';
  for (let n = 0; n <= 6; n++) {
    const m = map[n];
    const exhausted = m.unknown === 0 && m.mine === 0;
    const cls = m.mine >= 3 ? 'mine-dominant' : exhausted ? 'exhausted' : '';
    const mineW = (m.mine / 7) * 100;
    const outW = (m.out / 7) * 100;
    const onBoardMark = n === le || n === re ? ' 📍' : '';
    html += `<div class="nummap-cell ${cls}">`;
    html += `<div class="nm-num">${n}${onBoardMark}</div>`;
    html += `<div class="nm-bar"><div class="nm-seg-mine" style="width:${mineW}%"></div><div class="nm-seg-out" style="width:${outW}%"></div></div>`;
    html += `<div class="nm-info">✋${m.mine} ✅${m.out} ❓${m.unknown}</div>`;
    html += '</div>';
  }
  $('nummapGrid').innerHTML = html;
}

function updateRemainingDisplay() {
  const container = $('remainingTiles');
  const header = $('remainingHeader');
  const remaining = getRemainingTiles();
  $('remainingCount').textContent = remaining.length;
  const useCangkul = $('cangkulMode').value === 'ya';
  const bone = boneyardCount();

  // Mode A: semua kartu terbagi habis -> tidak ada sisa; kartu ada di kolom lawan
  if (bone === 0) {
    header.innerHTML = '📦 Kartu Sisa (<span id="remainingCount">0</span>) — semua kartu ada di tangan pemain → lihat kolom Lawan';
    container.innerHTML = '<span class="placeholder" style="font-size:0.65rem;">Tidak ada kartu sisa/cangkul. Kartu kandidat tiap lawan tampil di kolomnya masing-masing.</span>';
    return;
  }

  // Mode C: cangkul TIDAK dipakai -> tampilkan kandidat kartu yang paling mungkin mati
  if (!useCangkul) {
    header.innerHTML = `💀 Kartu Sisa Mati — tidak pernah disambar (<span id="remainingCount">${remaining.length}</span>)`;
    const dead = (state.lastAnalysis && state.lastAnalysis.deadTiles) || [];
    const byNum = (state.lastAnalysis && state.lastAnalysis.deadByNumber) || null;
    let html = '';
    if (dead.length > 0) {
      html += '<div class="dead-nums">';
      for (let n = 0; n <= 6; n++) {
        html += `<span class="dead-num-chip">${n}: ±${(byNum ? byNum[n] : 0).toFixed(1)} mati</span>`;
      }
      html += '</div>';
      html += '<div class="remaining-tiles-dead">';
      dead.forEach((d) => {
        const pct = (d.prob * 100);
        const cls = pct >= 50 ? 'dead-likely' : pct >= 25 ? 'dead-mid' : '';
        html += `<div class="remaining-card ${cls}" aria-label="${tileLabel(d.key)}, kemungkinan mati ${pct.toFixed(0)} persen">` +
          `${renderPipsHTML(d.a, 'r')}<div class="r-div"></div>${renderPipsHTML(d.b, 'r')}</div>`;
      });
      html += '</div>';
    } else {
      html = '<span class="placeholder" style="font-size:0.65rem;">Klik 🔬 Analisis untuk menghitung kandidat kartu mati (berbasis data PASS & atribusi).</span>';
    }
    container.innerHTML = html;
    return;
  }

  // Mode B: cangkul aktif -> klik kartu = kartu lawan nyamber (atribusi)
  header.innerHTML = `📦 Kartu Cangkul — klik = kartu lawan nyamber dari sini (<span id="remainingCount">${remaining.length}</span>)`;
  if (remaining.length === 0) {
    container.innerHTML = '<span class="placeholder" style="font-size:0.65rem;">Cangkul sudah habis disambar.</span>';
    return;
  }
  container.innerHTML = remaining.map((tile) => {
    const [a, b] = tile;
    return `<div class="remaining-card" data-key="${tileKey(tile)}" role="button" tabindex="0" aria-label="${tileLabel(tileKey(tile))}">` +
      `${renderPipsHTML(a, 'r')}<div class="r-div"></div>${renderPipsHTML(b, 'r')}</div>`;
  }).join('');

  container.querySelectorAll('.remaining-card').forEach((el) => {
    el.addEventListener('click', () => {
      if (!state.isAnalyzing) openAttribModal(el.dataset.key);
    });
  });
}

function updateAll() {
  updateBoardDisplay();
  updateHandDisplay();
  updateRemainingDisplay();
  updateNumberMap();
  updateQualityBanner();
  updateOpponentsDisplay();
  saveState();
}

/* ---- modal: pilih kartu tangan ---- */
function openHandModal() {
  const grid = $('handModalGrid');
  const used = getAllUsedKeys();
  const handSet = arrToSet(state.myHand);
  const cardsPerPlayer = parseInt($('cardsPerPlayer').value, 10);

  grid.innerHTML = getAllTiles().map((tile) => {
    const key = tileKey(tile);
    const isUsed = used[key] && !handSet[key];
    const isSelected = !!handSet[key];
    const cls = isUsed ? 'used' : isSelected ? 'selected' : '';
    return `<div class="modal-tile ${cls}" data-key="${key}" role="button" aria-label="${tileLabel(key)}">` +
      `${renderPipsHTML(tile[0], 'mt')}<div class="mt-div"></div>${renderPipsHTML(tile[1], 'mt')}</div>`;
  }).join('');

  grid.querySelectorAll('.modal-tile').forEach((el) => {
    el.addEventListener('click', () => {
      const key = el.dataset.key;
      if (el.classList.contains('used')) return;
      const idx = state.myHand.indexOf(key);
      if (idx >= 0) {
        state.myHand.splice(idx, 1);
      } else {
        if (state.myHand.length >= cardsPerPlayer) {
          alert(`Maksimal ${cardsPerPlayer} kartu per pemain!`);
          return;
        }
        state.myHand.push(key);
      }
      openHandModal();
      updateAll();
      runAnalysis(); // live: begitu tangan diisi -> analisis mode kartu pertama
    });
  });

  $('handModal').classList.add('active');
}

/* ---- quick-input kartu (v3.2): dua kolom angka, urutan bebas ---- */
function qiSanitize(raw) {
  // hanya digit pertama yang dianggap; di luar 0..6 dianggap tidak valid
  const digits = String(raw).replace(/[^0-9]/g, '');
  if (!digits) return { ok: false, val: 0 };
  const val = parseInt(digits[0], 10);
  return { ok: val >= 0 && val <= 6, val };
}

function qiFlashError(el) {
  el.classList.add('qi-error');
  setTimeout(() => el.classList.remove('qi-error'), 700);
}

function applyQuickInput() {
  const lEl = $('qiLeft'), rEl = $('qiRight');
  const L = qiSanitize(lEl.value);
  const R = qiSanitize(rEl.value);
  if (!L.ok) { qiFlashError(lEl); return; }
  if (!R.ok) { qiFlashError(rEl); return; }
  const key = `${Math.min(L.val, R.val)}-${Math.max(L.val, R.val)}`;

  const cardsPerPlayer = parseInt($('cardsPerPlayer').value, 10);
  const idx = state.myHand.indexOf(key);
  if (idx >= 0) {
    state.myHand.splice(idx, 1); // toggle: kartu sudah ada -> keluarkan
  } else {
    if (state.myHand.length >= cardsPerPlayer) {
      alert(`Maksimal ${cardsPerPlayer} kartu per pemain!`);
      return;
    }
    state.myHand.push(key);
  }

  openHandModal(); // re-render grid (seleksi & used ter-update)
  updateAll();
  runAnalysis(); // live: mode kartu pertama jalan sejak kartu pertama diketik
  // siap entri berikutnya: nilai terpilih otomatis, fokus kembali ke kiri
  lEl.value = '';
  rEl.value = '';
  lEl.focus();
}

function initQuickInput() {
  $('qiAdd').addEventListener('click', applyQuickInput);
  ['qiLeft', 'qiRight'].forEach((id) => {
    const el = $(id);
    // blok input tidak-valid sebelum terjadi (ketik 7/9 -> dibuang)
    el.addEventListener('input', () => {
      const digits = el.value.replace(/[^0-9]/g, '').slice(0, 1);
      if (digits && parseInt(digits, 10) > 6) {
        qiFlashError(el);
        el.value = '';
        return;
      }
      if (el.value !== digits) el.value = digits;
      // auto-lompat ke kolom kanan setelah 1 digit sah
      if (digits && id === 'qiLeft' && parseInt(digits, 10) >= 0) $('qiRight').focus();
    });
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); applyQuickInput(); }
    });
  });
}

function closeHandModal() {
  $('handModal').classList.remove('active');
  updateAll();
}

/* ---- modal: pilih ujung ---- */
function showEndChoice(key, source, a, b, who) {
  state.pending = { key, source, who: who || null };
  const le = getLeftEnd(), re = getRightEnd();
  const newLeftIfLeft = a === le ? b : a;
  const newRightIfRight = a === re ? b : a;

  $('endChoiceTile').innerHTML =
    `<div class="preview-tile">${renderPipsHTML(a, 'p')}<div class="p-div"></div>${renderPipsHTML(b, 'p')}</div>`;
  $('resultLeft').textContent = `→ Kiri jadi ${newLeftIfLeft}`;
  $('resultRight').textContent = `→ Kanan jadi ${newRightIfRight}`;
  $('endChoiceModal').classList.add('active');
}

function chooseEnd(side) {
  if (!state.pending) return;
  const { key, source, who } = state.pending;
  state.pending = null;
  $('endChoiceModal').classList.remove('active');
  executePlay(key, source, side, who);
}

/* ---- main kartu dari kolom lawan (v3.1) ---- */
function computeOppCandidates(oppIdx, unknownKeys) {
  const elim = state.opponents[oppIdx].eliminated;
  // kartu yang sudah dipastikan dimainkan lawan LAIN tidak mungkin dipegang lawan ini
  const knownElsewhere = {};
  state.allPlayed.forEach((k, idx) => {
    const w = state.playedBy[idx];
    if (w && w.startsWith('opp')) {
      const p = parseInt(w.slice(3), 10) - 1;
      if (p !== oppIdx) knownElsewhere[k] = true;
    }
  });
  return unknownKeys.filter((k) => {
    if (knownElsewhere[k]) return false;
    const [a, b] = parseKey(k);
    return !elim.includes(a) && !elim.includes(b);
  });
}

function handleOppCardPlay(key, oppIdx) {
  const who = `opp${oppIdx + 1}`;
  const [a, b] = parseKey(key);
  const le = getLeftEnd(), re = getRightEnd();
  if (le === -1 && re === -1) {
    executePlay(key, 'remaining', 'first', who);
    return;
  }
  const canLeft = a === le || b === le;
  const canRight = a === re || b === re;
  if (!canLeft && !canRight) {
    alert(`Kartu [${a}|${b}] tidak bisa disambung ke ujung ${le}|${re} — periksa lagi kartu yang dimainkan lawan.`);
    return;
  }
  // lawan boleh memilih sisi — tanyakan bila keduanya cocok (bug auto-pilih diperbaiki)
  if (canLeft && canRight) showEndChoice(key, 'remaining', a, b, who);
  else if (canLeft) executePlay(key, 'remaining', 'left', who);
  else executePlay(key, 'remaining', 'right', who);
}

/* ---- modal atribusi: siapa yang main kartu lawan? (v3) ---- */
function openAttribModal(key) {
  state.pendingAttrib = { key };
  const [a, b] = parseKey(key);
  $('attribTile').innerHTML =
    `<div class="preview-tile">${renderPipsHTML(a, 'p')}<div class="p-div"></div>${renderPipsHTML(b, 'p')}</div>`;

  const numOpp = parseInt($('playerCount').value, 10) - 1;
  let h = '';
  for (let i = 0; i < numOpp; i++) {
    h += `<button class="attrib-btn" data-who="opp${i + 1}">👤 Lawan ${i + 1}</button>`;
  }
  $('attribButtons').innerHTML = h;
  $('attribButtons').querySelectorAll('.attrib-btn').forEach((btn) => {
    btn.addEventListener('click', () => resolveAttribution(btn.dataset.who));
  });
  $('attribModal').classList.add('active');
}

function resolveAttribution(who) {
  if (!state.pendingAttrib) return;
  const { key } = state.pendingAttrib;
  state.pendingAttrib = null;
  $('attribModal').classList.remove('active');
  executePlay(key, 'remaining', 'auto', who);
}

/* ---- alur main kartu ---- */
function handleCardPlay(key, source) {
  const [a, b] = parseKey(key);
  const le = getLeftEnd(), re = getRightEnd();

  if (le === -1 && re === -1) {
    executePlay(key, source, 'first');
    return;
  }
  const canLeft = a === le || b === le;
  const canRight = a === re || b === re;

  if (!canLeft && !canRight) {
    alert('Kartu ini tidak bisa dimainkan!');
    return;
  }
  if (canLeft && canRight) showEndChoice(key, source, a, b);
  else if (canLeft) executePlay(key, source, 'left');
  else executePlay(key, source, 'right');
}

function executePlay(key, source, side, attributedTo) {
  const [a, b] = parseKey(key);
  const le = getLeftEnd(), re = getRightEnd();

  if (source === 'hand') {
    const idx = state.myHand.indexOf(key);
    if (idx >= 0) state.myHand.splice(idx, 1);
  }

  pushSnapshot();

  const owner = source === 'hand' ? 'me' : 'opp';
  let oriented;
  if (side === 'first') {
    oriented = [a, b];
    state.boardTiles.push({ tile: oriented, origKey: key, owner, source });
  } else if (side === 'left') {
    oriented = a === le ? [b, a] : [a, b];
    state.boardTiles.unshift({ tile: oriented, origKey: key, owner, source });
  } else if (side === 'right') {
    oriented = a === re ? [a, b] : [b, a];
    state.boardTiles.push({ tile: oriented, origKey: key, owner, source });
  } else {
    // auto (kartu lawan): sambung ujung mana pun yang cocok, kiri dulu
    if (a === le || b === le) {
      oriented = a === le ? [b, a] : [a, b];
      state.boardTiles.unshift({ tile: oriented, origKey: key, owner, source });
    } else {
      oriented = a === re ? [a, b] : [b, a];
      state.boardTiles.push({ tile: oriented, origKey: key, owner, source });
    }
  }

  state.allPlayed.push(key);
  state.playedBy.push(source === 'hand' ? 'me' : (attributedTo || 'unknown'));
  updateAll();
  runAnalysis(); // analisis otomatis setelah setiap langkah
}

function resetGame() {
  if (state.isAnalyzing) return;
  pushSnapshot();
  // live mode tetap hidup: reset bukan alasan mematikan analisis otomatis
  state.myHand = [];
  state.boardTiles = [];
  state.allPlayed = [];
  state.playedBy = [];
  state.opponents.forEach((o) => { o.passes = []; o.eliminated = []; });
  state.lastAnalysis = null;
  updateAll();
  hideAnalysis();
  $('progressContainer').classList.remove('active');
}

function hideAnalysis() {
  $('analysisPanel').classList.remove('active');
}

/* ---- API ke engine C++ (via server Python) ---- */
async function apiPost(path, body, signal) {
  let res;
  try {
    res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    throw new Error('Tidak bisa menghubungi server — apakah `python start.py` masih berjalan?');
  }
  let json;
  try {
    json = await res.json();
  } catch (e) {
    throw new Error(`Respons server tidak valid (HTTP ${res.status})`);
  }
  if (!res.ok || json.ok === false) {
    throw new Error(json.error || `HTTP ${res.status}`);
  }
  return json;
}

function friendlyError(msg) {
  return String(msg)
    .replace(/invalid tile key: (\S+)/, (m, k) =>
      `Kartu "${k}" tidak dikenali — pilih kartu dari daftar, jangan ketik manual.`)
    .replace(/duplicate tile: (\S+)/, (m, k) =>
      `Kartu "${k}" muncul dua kali — periksa tangan & papan Anda.`)
    .replace(/atribusi kartu melebihi[^\n]*/, () =>
      `Data atribusi tidak konsisten — satu kartu tidak mungkin milik dua lawan sekaligus. Periksa kembali penandaan kartu lawan.`);
}

function buildAnalyzeRequest() {
  const numPlayers = parseInt($('playerCount').value, 10);
  const cardsPerPlayer = parseInt($('cardsPerPlayer').value, 10);
  return {
    cmd: 'analyze',
    numPlayers,
    cardsPerPlayer,
    numSims: parseInt($('simCount').value, 10),
    seed: SEED,
    leftEnd: getLeftEnd(),
    rightEnd: getRightEnd(),
    myHand: state.myHand.slice(),
    played: state.allPlayed.slice(),
    playedBy: state.playedBy.slice(),
    nextSeat: parseInt($('nextSeat').value, 10),
    deadlockRule: $('deadlockRule').value,
    tieRule: $('tieRule').value,
    cangkul: $('cangkulMode').value === 'ya',
    adversarial: $('adversarial').checked,
    opponents: state.opponents.map((o) => ({
      passes: o.passes.length,
      eliminated: o.eliminated.slice(),
    })),
  };
}

function setProgress(pct, text, detail) {
  const pc = $('progressContainer');
  pc.classList.add('active');
  $('progressFill').style.width = `${pct}%`;
  $('progressText').innerHTML = text;
  $('progressDetail').textContent = detail || '';
}

/* ---- analisis ---- */
async function runAnalysis() {
  if (state.isAnalyzing) { state.pendingRun = true; return; } // antre: jalankan ulang setelah ini selesai
  // Papan kosong + tangan terisi = MODE KARTU PERTAMA: analisis langsung jalan
  // sehingga pemain pertama tahu kartu buka terbaik sejak awal. Tangan kosong
  // boleh selama papan sudah bergerak — hasil berisi CTA PASS + profil lawan.
  if (state.myHand.length === 0 && state.boardTiles.length === 0) return;

  const cardsPerPlayer = parseInt($('cardsPerPlayer').value, 10);
  if (state.myHand.length > cardsPerPlayer) {
    alert('Kartu di tangan melebihi kartu per pemain!');
    return;
  }

  state.isAnalyzing = true;
  state.abortCtl = new AbortController();
  const btn = $('analyzeBtn');
  btn.textContent = state.liveMode ? '⏸ Jeda Live…' : '✕ Batal';

  const req = buildAnalyzeRequest();
  const isFirstMove = req.leftEnd === -1 && req.rightEnd === -1;
  const hasPassData = state.opponents.some((o) => o.passes.length > 0);
  const hasAttrib = state.playedBy.some((w) => w && w.startsWith('opp'));

  setProgress(
    30,
    '<span class="loading-icon">⏳</span> ' +
      (isFirstMove ? '🎯 Analisis Kartu Pertama' : '🎯 Menganalisis...'),
    `${req.myHand.length} kartu × ${req.numSims} sim (engine C++ v3)` +
      (hasPassData ? ' • data PASS' : '') +
      (hasAttrib ? ' • atribusi lawan' : '') +
      (req.adversarial ? ' • mode teliti' : '')
  );

  try {
    const data = await apiPost('/api/analyze', req, state.abortCtl.signal);
    if (!data.moves || data.moves.length === 0) {
      showNoMoves();
    } else {
      setProgress(100, '✅ Selesai!', '');
      displayResults(data, isFirstMove, hasPassData);
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      setProgress(100, state.liveMode ? '⏸ Live dijeda' : '🚫 Analisis dibatalkan', '');
    } else {
      const panel = $('analysisPanel');
      panel.classList.add('active');
      $('analysisResults').innerHTML =
        `<div class="empty-state"><div class="icon">⚠️</div>` +
        `<p><strong>Gagal menganalisis:</strong></p><p style="margin-top:5px;font-size:0.72rem;">${esc(friendlyError(err.message))}</p></div>`;
    }
  } finally {
    btn.disabled = false;
    btn.textContent = state.liveMode ? '⏸ Jeda Live' : '▶️ Analisis Live';
    state.isAnalyzing = false;
    state.abortCtl = null;
    if (state.liveMode && state.pendingRun) {
      state.pendingRun = false;
      setTimeout(() => runAnalysis(), 60); // jalankan antrean terbaru
    } else {
      setTimeout(() => $('progressContainer').classList.remove('active'), 900);
    }
  }
}

function cancelAnalysis() {
  if (state.abortCtl) state.abortCtl.abort();
}

function showNoMoves() {
  const panel = $('analysisPanel');
  panel.classList.add('active');
  setProgress(100, '⚠️ Tidak ada langkah valid', '');
  $('analysisResults').innerHTML =
    '<div class="pass-cta"><strong>😔 Tidak ada langkah valid — Anda harus PASS (lewat).</strong><br>' +
    'Jika yang lewat adalah <strong>lawan</strong>, tekan tombol ⏭ PASS di kartu lawan ' +
    'agar sistem mencatat eliminasi angka → analisis berikutnya jadi jauh lebih akurat.<br>' +
    'Jika giliran Anda kembali tanpa bisa main, catat PASS Anda dan lanjutkan permainan.</div>';
}

/* ---- render hasil analisis ---- */
function sortResults(moves, isFirstMove) {
  // engine sudah mengurutkan via rankScore; UI menambah bucket "aman" di atas
  const withMeta = moves.map((r) => ({
    r,
    safe: r.winRate >= 0.5,
    sc: r.rankScore !== undefined ? r.rankScore : 0,
  }));
  withMeta.sort((x, y) => {
    if (x.safe !== y.safe) return x.safe ? -1 : 1;
    return y.sc - x.sc;
  });
  return withMeta.map((s) => s.r);
}

function makeMoveTileHTML(a, b) {
  return `<div class="move-tile-v">${renderPipsHTML(a, 'm')}<div class="m-div"></div>${renderPipsHTML(b, 'm')}</div>`;
}

function displayResults(data, isFirstMove, hasPassData) {
  const panel = $('analysisPanel');
  const div = $('analysisResults');
  panel.classList.add('active');
  div.innerHTML = '';
  state.lastAnalysis = data;
  updateRemainingDisplay(); // refresh mode-C kandidat kartu mati dengan data terbaru

  const results = sortResults(data.moves, isFirstMove);
  const best = results[0];
  const numSims = data.numSims;

  // chips ringkasan mode
  const chips = [];
  if (hasPassData) chips.push('<span class="opp-held-chip">🔍 PASS</span>');
  if (data.hasAttribution) chips.push('<span class="opp-held-chip">🎯 Atribusi</span>');
  if (data.adversarial) chips.push('<span class="opp-held-chip">😈 Teliti</span>');
  if (data.boneyardCount > 0) chips.push(`<span class="opp-held-chip">📦 Cangkul ${data.boneyardCount}</span>`);
  $('analysisChips').innerHTML = chips.length ? ' ' + chips.join(' ') : '';

  if (isFirstMove) {
    div.innerHTML += '<div class="first-move-box"><h4>🎯 MODE: KARTU PERTAMA</h4>' +
      '<p>Pilih kartu pertama terbaik agar tidak diblokir di putaran ke-2.</p></div>';
  }

  if (hasPassData) {
    const totalElim = state.opponents.reduce((s, o) => s + o.eliminated.length, 0);
    if (totalElim > 0) {
      div.innerHTML += '<div class="first-move-box" style="background:rgba(248,81,73,0.06);border-color:rgba(248,81,73,0.3);">' +
        '<h4 style="color:#f85149;">🔍 Data PASS Lawan Aktif</h4>' +
        `<p style="color:#8b949e;">Simulasi menggunakan informasi eliminasi dari ${totalElim} angka yang tercatat — distribusi kartu lawan jauh lebih akurat!</p></div>`;
    }
  }

  // panel dominasi (dihitung ulang lokal dari tangan)
  const counts = [0, 0, 0, 0, 0, 0, 0];
  state.myHand.forEach((k) => { const [a, b] = parseKey(k); counts[a]++; counts[b]++; });
  const dominant = [];
  for (let n = 0; n <= 6; n++) if (counts[n] >= 3) dominant.push({ num: n, count: counts[n] });
  let domHTML = '<div class="dominance-panel"><div class="dominance-title">👑 Dominasi Angka</div><div class="dominance-numbers">';
  for (let n = 0; n <= 6; n++) {
    const cls = counts[n] >= 3 ? 'dominant' : counts[n] === 2 ? 'strong' : '';
    domHTML += `<div class="dom-num ${cls}"><div class="num-val">${n}</div><div class="num-count">${counts[n]}x</div></div>`;
  }
  domHTML += '</div>';
  if (dominant.length > 0) {
    domHTML += `<div style="font-size:0.6rem;color:#3fb950;margin-top:4px;">🏆 DOMINAN: ${dominant.map((d) => `${d.num}(${d.count})`).join(', ')}</div>`;
  }
  domHTML += '</div>';
  div.innerHTML += domHTML;

  results.forEach((r, idx) => {
    const a = r.a, b = r.b;
    const isD = a === b;
    const cc = idx === 0 ? 'best' : idx <= 2 ? 'good' : r.winRate < 0.3 ? 'danger' : '';
    const rc = idx === 0 ? 'rank-gold' : idx === 1 ? 'rank-silver' : idx === 2 ? 'rank-bronze' : 'rank-normal';
    let bc, bt;
    if (idx === 0 && r.winRate >= 0.5) { bc = 'badge-best'; bt = '🏆 TERBAIK'; }
    else if (r.winRate >= 0.5) { bc = 'badge-good'; bt = '✓ AMAN'; }
    else if (idx <= 2) { bc = 'badge-good'; bt = '⚠ HATI-HATI'; }
    else { bc = 'badge-risk'; bt = '⚠ RISIKO'; }

    const wp = (r.winRate * 100).toFixed(1);
    const ciHalf = ((r.winHi - r.winLo) / 2 * 100).toFixed(1);
    const ciText = `interval 95%: ${(r.winLo * 100).toFixed(1)}–${(r.winHi * 100).toFixed(1)}%`;
    const barC = r.winRate >= 0.5 ? 'green' : r.winRate >= 0.35 ? 'yellow' : 'red';

    let inner = '<div class="move-header">';
    inner += `<div class="move-rank ${rc}">#${idx + 1}</div>`;
    inner += makeMoveTileHTML(a, b);
    inner += `<div class="move-info"><div class="move-title">[${a}|${b}]${isD ? ' ⚡' : ''} → [${r.newLeft}|${r.newRight}]`;
    inner += ` <span class="badge ${bc}">${bt}</span>`;
    if (isFirstMove) inner += ' <span class="badge badge-first">🎯 PERTAMA</span>';
    if (isD) inner += ' <span class="badge badge-dom">BALAK</span>';
    if (r.trapScore >= 15) inner += ' <span class="badge badge-trap">🪤 JERAT</span>';
    if (r.blockScore >= 25) inner += ' <span class="badge badge-block">🔒 KUNCI</span>';
    if (r.guaranteedBlocks.length > 0) inner += ` <span class="badge badge-block">⛔ ${r.guaranteedBlocks.length} LAWAN MATI</span>`;
    inner += '</div>';
    inner += `<div class="move-desc">${numSims} sim: <strong style="color:#3fb950">${r.wins}M</strong> / <strong style="color:#f85149">${r.losses}K</strong>` +
      (r.deadlockWins > 0 ? ` (🎯 ${r.deadlockWins} menang adu)` : '') + '</div>';
    inner += '</div></div>';

    inner += '<div class="stats-grid">';
    inner += `<div class="stat-box"><div class="val ${r.winRate >= 0.5 ? 'val-green' : r.winRate >= 0.35 ? 'val-yellow' : 'val-red'}">${wp}%</div><div class="lbl">Win</div></div>`;
    inner += `<div class="stat-box"><div class="val val-pink">${r.trapScore}</div><div class="lbl">Jerat</div></div>`;
    inner += `<div class="stat-box"><div class="val val-red">${r.blockScore}</div><div class="lbl">Kunci</div></div>`;
    inner += `<div class="stat-box"><div class="val val-blue">${r.avgOppPasses.toFixed(1)}</div><div class="lbl">Lawan Pass</div></div>`;
    inner += `<div class="stat-box"><div class="val val-purple">${r.avgMyVal.toFixed(1)}</div><div class="lbl">Sisa Mata</div></div>`;
    inner += `<div class="stat-box"><div class="val ${r.riskScore < 20 ? 'val-green' : r.riskScore < 40 ? 'val-yellow' : 'val-red'}">${r.riskScore.toFixed(0)}</div><div class="lbl">Risk</div></div>`;
    inner += '</div>';

    inner += `<div class="comp-bar"><div class="bar-label"><span>🏆 Peluang Menang <span class="ci-note">(${ciText})</span></span><span><strong>${wp}% ±${ciHalf}</strong></span></div><div class="bar-track"><div class="bar-fill ${barC}" style="width:${wp}%"></div></div></div>`;

    if (r.deadlockWinRate > 0.01) {
      inner += `<div class="comp-bar"><div class="bar-label"><span>⚖️ Menang lewat ADU</span><span>${(r.deadlockWinRate * 100).toFixed(1)}%</span></div><div class="bar-track"><div class="bar-fill orange" style="width:${r.deadlockWinRate * 100}%"></div></div></div>`;
    }
    if (r.trapScore > 0) {
      inner += `<div class="comp-bar"><div class="bar-label"><span>🪤 Kekuatan Jerat</span><span>${r.trapScore} poin</span></div><div class="bar-track"><div class="bar-fill pink" style="width:${Math.min(100, r.trapScore * 2)}%"></div></div></div>`;
    }

    if (r.guaranteedBlocks.length > 0) {
      inner += '<div class="strategy-box" style="background:rgba(248,81,73,0.08);border-color:rgba(248,81,73,0.4);"><h4 style="color:#f85149;">⛔ BLOK TERJAMIN (dari data PASS)</h4>';
      r.guaranteedBlocks.forEach((gb) => {
        inner += `<p style="color:#f85149;font-weight:600;">${gb.reason}</p>`;
      });
      inner += '</div>';
    }

    if (r.trapReasons.length > 0 || r.blockReasons.length > 0) {
      inner += '<div class="strategy-box"><h4>🧠 Analisis Strategi</h4>';
      r.trapReasons.forEach((reason) => { inner += `<p>${reason}</p>`; });
      r.blockReasons.forEach((reason) => { inner += `<p>${reason}</p>`; });
      inner += '</div>';
    }

    if (isFirstMove && r.firstMoveSafety) {
      const f = r.firstMoveSafety;
      const sp = (f.safetyRatio * 100).toFixed(0);
      const sbc = f.safetyRatio >= 0.5 ? 'green' : f.safetyRatio >= 0.25 ? 'yellow' : 'red';
      inner += `<div class="comp-bar"><div class="bar-label"><span>🛡️ Keamanan Putaran 2</span><span>${f.canPlayNext}/${f.totalRemaining} (${sp}%)</span></div><div class="bar-track"><div class="bar-fill ${sbc}" style="width:${sp}%"></div></div></div>`;
      if (f.safetyRatio === 0) {
        inner += '<div style="background:rgba(248,81,73,0.1);border:1px solid #f85149;border-radius:5px;padding:5px;margin-top:3px;font-size:0.58rem;color:#f85149;font-weight:600;">⚠️ BAHAYA! Tidak ada kartu yang bisa dimainkan di putaran ke-2!</div>';
      } else if (f.safetyRatio >= 0.5) {
        inner += `<div style="background:rgba(63,185,80,0.1);border:1px solid #3fb950;border-radius:5px;padding:5px;margin-top:3px;font-size:0.58rem;color:#3fb950;font-weight:600;">✅ AMAN! ${f.canPlayNext} kartu bisa dimainkan.</div>`;
      }
      inner += '<div class="playable-section"><div class="playable-label">✅ Bisa dimainkan putaran 2:</div><div class="playable-tiles">';
      if (f.canPlayKeys.length > 0) {
        f.canPlayKeys.forEach((k) => {
          const [x, y] = parseKey(k);
          inner += `<span class="playable-tag">${x}|${y}</span>`;
        });
      } else {
        inner += '<span style="font-size:0.58rem;color:#f85149;">TIDAK ADA!</span>';
      }
      inner += '</div></div>';
    }

    if (r.domSupportReasons.length > 0) {
      inner += '<div class="dominance-box"><h4>👑 Analisis Dominasi</h4>';
      r.domSupportReasons.forEach((reason) => { inner += `<p>• ${reason}</p>`; });
      inner += '</div>';
    }

    if (r.topDanger.length > 0) {
      inner += '<div class="risk-box"><h4>⚠️ Kartu Berbahaya</h4><div class="danger-tiles">';
      r.topDanger.slice(0, 5).forEach((d) => {
        const [x, y] = parseKey(d.key);
        inner += `<div class="danger-tile">[${x}|${y}] ${(d.freq * 100).toFixed(0)}%</div>`;
      });
      inner += '</div></div>';
    }

    const card = document.createElement('div');
    card.className = `move-card ${cc}`;
    card.innerHTML = inner;
    div.appendChild(card);
  });

  // rekomendasi
  const tip = document.createElement('div');
  tip.className = 'info-text';
  let t = '<strong>💡 Rekomendasi Strategi:</strong><br>';
  t += `🎯 Mainkan <strong>[${best.a}|${best.b}]</strong> → ujung [${best.newLeft}|${best.newRight}] (Win ${(best.winRate * 100).toFixed(0)}%)<br>`;
  if (best.guaranteedBlocks.length > 0) t += `⛔ Langkah ini <strong>MATIKAN ${best.guaranteedBlocks.length} lawan</strong> berdasarkan data pass!<br>`;
  if (best.trapScore >= 15) t += '🪤 Jerat terpasang untuk lawan.<br>';
  if (best.blockScore >= 25) t += '🔒 Mengunci jalan lawan.<br>';
  if (best.deadlockWinRate > 0.05) t += `⚖️ ${(best.deadlockWinRate * 100).toFixed(0)}% menang lewat adu.<br>`;
  if (dominant.length > 0) {
    t += `<br>👑 Angka dominan: ${dominant.map((d) => d.num).join(', ')}. Pertahankan di ujung papan!`;
  }
  tip.innerHTML = t;
  div.appendChild(tip);
}

/* ---- export / import sesi ---- */
function exportSession() {
  const blob = new Blob([JSON.stringify(serializeState(), null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const aEl = document.createElement('a');
  aEl.href = url;
  aEl.download = `domino-analisis-${new Date().toISOString().slice(0, 10)}.json`;
  aEl.click();
  URL.revokeObjectURL(url);
}
function importSession(file) {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      if (restoreFrom(JSON.parse(reader.result))) {
        alert('Sesi berhasil dimuat!');
      } else {
        alert('File bukan sesi Domino Analyzer v3 yang valid.');
      }
    } catch (e) {
      alert('File tidak bisa dibaca sebagai JSON.');
    }
  };
  reader.readAsText(file);
}

/* ---- init & event listeners ---- */
$('playerCount').addEventListener('change', () => {
  updateCardsPerPlayerOptions();
  updateAll();
});
$('cardsPerPlayer').addEventListener('change', () => {
  updateSetupInfo();
  updateAll();
});
$('cangkulMode').addEventListener('change', () => {
  updateSetupInfo();
  updateAll();
});
$('pickHandBtn').addEventListener('click', () => { openHandModal(); $('qiLeft').focus(); });
initQuickInput();
$('closeModalBtn').addEventListener('click', closeHandModal);
$('handModal').addEventListener('click', (e) => {
  if (e.target === $('handModal')) closeHandModal();
});
$('choiceLeft').addEventListener('click', () => chooseEnd('left'));
$('choiceRight').addEventListener('click', () => chooseEnd('right'));
$('attribUnknown').addEventListener('click', () => resolveAttribution('unknown'));
$('analyzeBtn').addEventListener('click', () => setLiveMode(!state.liveMode));
$('undoBtn').addEventListener('click', undoLastAction);
$('exportBtn').addEventListener('click', exportSession);
$('importBtn').addEventListener('click', () => $('importFile').click());
$('importFile').addEventListener('change', (e) => {
  if (e.target.files && e.target.files[0]) importSession(e.target.files[0]);
  e.target.value = '';
});
$('resetBtn').addEventListener('click', resetGame);

updateCardsPerPlayerOptions();
initOpponents();
loadState();
updateAll();

/* ---- LIVE mode aktif otomatis sejak aplikasi dibuka (v3.2) ---- */
setLiveMode(true);

/* ---- PWA ---- */
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('sw.js').catch(() => { /* dev/offline file */ });
  });
}

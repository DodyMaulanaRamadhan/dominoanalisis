/* ============================================================================
   Domino Analyzer Pro — app.js
   Sections: state · utils · setup · render · modals · play flow ·
             undo/reset · API · results · init
   Semua perhitungan berat (Monte-Carlo, skoring) dilakukan engine C++
   lewat POST /api/analyze — file ini hanya UI + orkestrasi.
   ========================================================================== */
'use strict';

/* ---- state ---- */
const state = {
  myHand: [],        // ["3-5", ...]
  boardTiles: [],    // { tile:[a,b], origKey, owner:'me'|'opp'|'first', source }
  allPlayed: [],     // semua key yang ada di papan
  opponents: [],     // { passes:[{left,right,boardLen}], eliminated:[num] }
  pending: null,     // { key, source } menunggu pilihan ujung
  isAnalyzing: false,
};

const SEED = 20240922; // deterministik: input sama -> hasil sama
const $ = (id) => document.getElementById(id);

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
  const maxCards = getMaxCardsPerPlayer(parseInt($('playerCount').value, 10));
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

  updateSetupInfo();
  initOpponents();
}

function updateSetupInfo() {
  const numPlayers = parseInt($('playerCount').value, 10);
  const cardsPerPlayer = parseInt($('cardsPerPlayer').value, 10);
  const distributed = numPlayers * cardsPerPlayer;
  const boneyard = 28 - distributed;

  let info = `${numPlayers} pemain × ${cardsPerPlayer} kartu = ${distributed} dibagikan`;
  info += boneyard > 0 ? ` | Cangkul: ${boneyard}` : ' | Semua kartu terpakai';
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
    return;
  }

  const le = getLeftEnd(), re = getRightEnd();
  const isFirstMove = le === -1 && re === -1;

  container.innerHTML = state.myHand.map((key) => {
    const [a, b] = parseKey(key);
    const playable = isFirstMove || a === le || b === le || a === re || b === re;
    const cls = playable ? 'playable' : 'unplayable';
    return `<div class="hand-card ${cls}" data-key="${key}">` +
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
  const opp = state.opponents[oppIdx];
  opp.passes.push({ left: le, right: re, boardLen: state.boardTiles.length });
  if (le !== -1 && !opp.eliminated.includes(le)) opp.eliminated.push(le);
  if (re !== -1 && !opp.eliminated.includes(re)) opp.eliminated.push(re);
  updateOpponentsDisplay();
  hideAnalysis();
}

function undoOpponentPass(oppIdx) {
  const opp = state.opponents[oppIdx];
  if (opp.passes.length === 0) return;
  opp.passes.pop();
  const newElim = [];
  opp.passes.forEach((p) => {
    if (p.left !== -1 && !newElim.includes(p.left)) newElim.push(p.left);
    if (p.right !== -1 && !newElim.includes(p.right)) newElim.push(p.right);
  });
  opp.eliminated = newElim;
  updateOpponentsDisplay();
  hideAnalysis();
}

function updateOpponentsDisplay() {
  const container = $('opponentsContainer');
  const numPlayers = parseInt($('playerCount').value, 10);
  const cardsPerPlayer = parseInt($('cardsPerPlayer').value, 10);
  const numOpp = numPlayers - 1;
  const distributed = numPlayers * cardsPerPlayer;
  const totalOppCardsNow = Math.max(0, distributed - state.myHand.length - state.allPlayed.length);
  const perOpp = Math.floor(totalOppCardsNow / numOpp);

  const used = getAllUsedKeys();
  const unknownKeys = getAllTiles()
    .map(tileKey)
    .filter((k) => !used[k]);

  const le = getLeftEnd(), re = getRightEnd();
  const boardActive = !(le === -1 && re === -1);

  const html = [];
  for (let i = 0; i < numOpp; i++) {
    const opp = state.opponents[i];
    const hasPass = opp.passes.length > 0;
    const possible = getPossibleCardsForOpponent(i, unknownKeys);
    const cardCount = i === numOpp - 1
      ? totalOppCardsNow - perOpp * (numOpp - 1)
      : perOpp;

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
        h += `<span class="elim-chip">${n}</span>`;
      });
      h += '</div>';
      h += `<div class="opp-passlog">Riwayat pass: ${opp.passes.map((p) => `[${p.left}|${p.right}]`).join(' → ')}</div>`;
    }

    h += `<div class="opp-info">📊 Kemungkinan kartu: <strong>${possible.length}</strong> dari ${unknownKeys.length} kartu unknown`;
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
      else undoOpponentPass(idx);
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
  const remaining = getRemainingTiles();
  $('remainingCount').textContent = remaining.length;

  if (remaining.length === 0) {
    container.innerHTML = '<span class="placeholder" style="font-size:0.65rem;">Semua kartu sudah dipilih/dimainkan</span>';
    return;
  }

  const le = getLeftEnd(), re = getRightEnd();
  const isFirstMove = le === -1 && re === -1;

  container.innerHTML = remaining.map((tile) => {
    const [a, b] = tile;
    const playable = isFirstMove || a === le || b === le || a === re || b === re;
    const cls = playable ? 'playable' : 'unplayable';
    return `<div class="remaining-card ${cls}" data-key="${tileKey(tile)}">` +
      `${renderPipsHTML(a, 'r')}<div class="r-div"></div>${renderPipsHTML(b, 'r')}</div>`;
  }).join('');

  container.querySelectorAll('.remaining-card').forEach((el) => {
    el.addEventListener('click', () => {
      if (!state.isAnalyzing) handleCardPlay(el.dataset.key, 'remaining');
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
    return `<div class="modal-tile ${cls}" data-key="${key}">` +
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
    });
  });

  $('handModal').classList.add('active');
}

function closeHandModal() {
  $('handModal').classList.remove('active');
  updateAll();
}

/* ---- modal: pilih ujung ---- */
function showEndChoice(key, source, a, b) {
  state.pending = { key, source };
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
  const { key, source } = state.pending;
  state.pending = null;
  $('endChoiceModal').classList.remove('active');
  executePlay(key, source, side);
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

function executePlay(key, source, side) {
  const [a, b] = parseKey(key);
  const le = getLeftEnd(), re = getRightEnd();

  if (source === 'hand') {
    const idx = state.myHand.indexOf(key);
    if (idx >= 0) state.myHand.splice(idx, 1);
  }

  const owner = source === 'hand' ? 'me' : 'opp';
  let oriented;
  if (side === 'first') {
    oriented = [a, b];
    state.boardTiles.push({ tile: oriented, origKey: key, owner, source });
  } else if (side === 'left') {
    oriented = a === le ? [b, a] : [a, b];
    state.boardTiles.unshift({ tile: oriented, origKey: key, owner, source });
  } else {
    oriented = a === re ? [a, b] : [b, a];
    state.boardTiles.push({ tile: oriented, origKey: key, owner, source });
  }

  state.allPlayed.push(key);
  updateAll();
  runAnalysis(); // analisis otomatis setelah setiap langkah
}

function undoLastMove() {
  if (state.isAnalyzing || state.boardTiles.length === 0) return;

  const last = state.boardTiles.pop();
  const idx = state.allPlayed.indexOf(last.origKey);
  if (idx >= 0) state.allPlayed.splice(idx, 1);
  if (last.source === 'hand' && !state.myHand.includes(last.origKey)) {
    state.myHand.push(last.origKey);
  }

  updateAll();
  hideAnalysis();
}

function resetGame() {
  if (state.isAnalyzing) return;
  state.myHand = [];
  state.boardTiles = [];
  state.allPlayed = [];
  state.opponents.forEach((o) => { o.passes = []; o.eliminated = []; });
  updateAll();
  hideAnalysis();
  $('progressContainer').classList.remove('active');
}

function hideAnalysis() {
  $('analysisPanel').classList.remove('active');
}

/* ---- API ke engine C++ (via server Python) ---- */
async function apiPost(path, body) {
  let res;
  try {
    res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (e) {
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

function buildAnalyzeRequest() {
  const numPlayers = parseInt($('playerCount').value, 10);
  const cardsPerPlayer = parseInt($('cardsPerPlayer').value, 10);
  const totalOppCards = Math.max(
    0,
    numPlayers * cardsPerPlayer - state.myHand.length - state.allPlayed.length
  );
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
    totalOppCards,
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
  if (state.isAnalyzing || state.myHand.length === 0) return;

  const cardsPerPlayer = parseInt($('cardsPerPlayer').value, 10);
  if (state.myHand.length > cardsPerPlayer) {
    alert('Kartu di tangan melebihi kartu per pemain!');
    return;
  }

  state.isAnalyzing = true;
  const btn = $('analyzeBtn');
  btn.disabled = true;
  btn.textContent = '⏳ ...';

  const req = buildAnalyzeRequest();
  const isFirstMove = req.leftEnd === -1 && req.rightEnd === -1;
  const hasPassData = state.opponents.some((o) => o.passes.length > 0);

  setProgress(
    30,
    '<span class="loading-icon">⏳</span> ' +
      (isFirstMove ? '🎯 Analisis Kartu Pertama' : '🎯 Menganalisis...'),
    `${req.myHand.length} kartu × ${req.numSims} sim (engine C++)` +
      (hasPassData ? ' • dengan data PASS lawan' : '')
  );

  try {
    const data = await apiPost('/api/analyze', req);
    if (!data.moves || data.moves.length === 0) {
      showNoMoves();
    } else {
      setProgress(100, '✅ Selesai!', '');
      displayResults(data, isFirstMove, hasPassData);
    }
  } catch (err) {
    const panel = $('analysisPanel');
    panel.classList.add('active');
    $('analysisResults').innerHTML =
      `<div class="empty-state"><div class="icon">⚠️</div>` +
      `<p><strong>Gagal menganalisis:</strong></p><p style="margin-top:5px;font-size:0.72rem;">${err.message}</p></div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '🔬 Analisis';
    state.isAnalyzing = false;
    setTimeout(() => $('progressContainer').classList.remove('active'), 700);
  }
}

function showNoMoves() {
  const panel = $('analysisPanel');
  panel.classList.add('active');
  $('analysisResults').innerHTML =
    '<div class="empty-state"><div class="icon">😔</div>' +
    '<p><strong>Tidak ada langkah valid!</strong></p>' +
    '<p style="margin-top:5px;font-size:0.75rem;">Anda harus PASS (lewat).</p></div>';
}

/* ---- render hasil analisis ---- */
function scoreOf(r, isFirstMove) {
  let s =
    r.winRate * 100 +
    r.domSupportScore * 0.6 +
    r.trapScore * 0.8 +
    r.blockScore * 0.7 -
    r.selfTrapScore * 0.5 -
    r.riskScore * 0.5 +
    r.deadlockWinRate * 20 +
    r.guaranteedBlocks.length * 8 +
    r.avgOppPasses * 3;
  if (isFirstMove && r.firstMoveSafety) s += r.firstMoveSafety.safetyRatio * 30;
  return s;
}

function sortResults(moves, isFirstMove) {
  const scored = moves.map((r) => ({ r, sc: scoreOf(r, isFirstMove) }));
  scored.sort((x, y) => {
    if (x.r.winRate >= 0.5 && y.r.winRate < 0.5) return -1;
    if (x.r.winRate < 0.5 && y.r.winRate >= 0.5) return 1;
    if (Math.abs(x.sc - y.sc) > 3) return y.sc - x.sc;
    return x.r.riskScore - y.r.riskScore;
  });
  return scored.map((s) => s.r);
}

function makeMoveTileHTML(a, b) {
  return `<div class="move-tile-v">${renderPipsHTML(a, 'm')}<div class="m-div"></div>${renderPipsHTML(b, 'm')}</div>`;
}

function displayResults(data, isFirstMove, hasPassData) {
  const panel = $('analysisPanel');
  const div = $('analysisResults');
  panel.classList.add('active');
  div.innerHTML = '';

  const results = sortResults(data.moves, isFirstMove);
  const best = results[0];
  const numSims = data.numSims;

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

    inner += `<div class="comp-bar"><div class="bar-label"><span>🏆 Peluang Menang</span><span><strong>${wp}%</strong></span></div><div class="bar-track"><div class="bar-fill ${barC}" style="width:${wp}%"></div></div></div>`;

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

/* ---- init & event listeners ---- */
$('playerCount').addEventListener('change', () => {
  updateCardsPerPlayerOptions();
  updateAll();
});
$('cardsPerPlayer').addEventListener('change', () => {
  updateSetupInfo();
  updateAll();
});
$('pickHandBtn').addEventListener('click', openHandModal);
$('closeModalBtn').addEventListener('click', closeHandModal);
$('handModal').addEventListener('click', (e) => {
  if (e.target === $('handModal')) closeHandModal();
});
$('choiceLeft').addEventListener('click', () => chooseEnd('left'));
$('choiceRight').addEventListener('click', () => chooseEnd('right'));
$('analyzeBtn').addEventListener('click', runAnalysis);
$('undoBtn').addEventListener('click', undoLastMove);
$('resetBtn').addEventListener('click', resetGame);

updateCardsPerPlayerOptions();
initOpponents();
updateAll();

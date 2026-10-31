(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const state = { mode: 'paste', file: null, result: null, loading: false, toastTimer: null };
  const sourceInput = $('source-text');
  const inputView = $('input-view');
  const resultsView = $('results-view');

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function toast(message) {
    const box = $('toast'); box.textContent = message; box.classList.add('visible');
    clearTimeout(state.toastTimer); state.toastTimer = setTimeout(() => box.classList.remove('visible'), 2400);
  }
  function countText(text) {
    $('word-count').textContent = text.trim() ? text.trim().split(/\s+/).length.toLocaleString() : '0';
    $('char-count').textContent = text.length.toLocaleString();
  }
  function sourceText() { return state.mode === 'upload' ? $('extracted-text').value : sourceInput.value; }
  function updateCounts() { countText(sourceText()); }
  function setMode(mode) {
    state.mode = mode;
    document.querySelectorAll('.tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.tab === mode));
    $('paste-panel').classList.toggle('hidden', mode !== 'paste');
    $('upload-panel').classList.toggle('hidden', mode !== 'upload');
    $('clear-text').classList.toggle('hidden', mode === 'upload' && !state.file);
    updateCounts();
  }
  function clearInput() {
    sourceInput.value = ''; $('extracted-text').value = ''; state.file = null;
    $('file-input').value = ''; $('file-info').classList.add('hidden'); $('preview-box').classList.add('hidden');
    $('drop-zone').classList.remove('hidden'); $('extract-progress').classList.add('hidden'); $('clear-text').classList.remove('hidden');
    updateCounts();
  }
  async function api(path, options = {}) {
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 150000);
    try {
      const response = await fetch(path, { ...options, signal: controller.signal });
      let data; try { data = await response.json(); } catch { data = {}; }
      if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
      return data;
    } catch (err) {
      if (err.name === 'AbortError') throw new Error('This request took too long. Try a shorter source or retry.');
      throw err;
    } finally { clearTimeout(timer); }
  }
  async function health() {
    try {
      const data = await api('/api/health', { signal: AbortSignal.timeout(5000) });
      const pill = document.querySelector('.status-pill');
      if (data.ai_configured) { pill.classList.add('ready'); $('service-status').textContent = 'AI ready'; }
      else { pill.classList.add('offline'); $('service-status').textContent = 'Setup needed'; }
    } catch { document.querySelector('.status-pill').classList.add('offline'); $('service-status').textContent = 'Server unavailable'; }
  }
  function formatBytes(bytes) { return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`; }
  async function acceptFile(file) {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'txt'].includes(ext)) { toast('Choose a PDF, DOCX, or TXT file.'); return; }
    if (file.size > 12 * 1024 * 1024) { toast('This file is over the 12 MB limit.'); return; }
    state.file = file; $('drop-zone').classList.add('hidden'); $('preview-box').classList.add('hidden');
    $('file-info').classList.remove('hidden'); $('file-name').textContent = file.name; $('file-size').textContent = formatBytes(file.size);
    $('extract-progress').classList.remove('hidden'); $('clear-text').classList.add('hidden'); $('extracted-text').value = ''; updateCounts();
    const form = new FormData(); form.append('file', file);
    try {
      const data = await api('/api/extract', { method: 'POST', body: form });
      if (state.file !== file) return;
      $('extracted-text').value = data.text; $('extracted-preview').textContent = data.text.slice(0, 4500) + (data.text.length > 4500 ? '\n…' : '');
      $('preview-box').classList.remove('hidden'); $('editor-hint').textContent = `Extracted from ${data.filename}`; updateCounts();
    } catch (err) {
      if (state.file === file) { toast(err.message); state.file = null; $('file-info').classList.add('hidden'); $('drop-zone').classList.remove('hidden'); }
    } finally { if (state.file === file) $('extract-progress').classList.add('hidden'); }
  }
  function setLoading(on, button = $('generate-btn')) {
    state.loading = on; button.disabled = on;
    if (button === $('generate-btn')) button.innerHTML = on ? '<span class="spinner small"></span> Finding your memory hook…' : 'Make it memorable <span>↗</span>';
  }
  async function generateResult() {
    if (state.loading) return;
    const text = sourceText().trim();
    if (text.length < 20) { toast('Add at least 20 characters of notes first.'); return; }
    const button = $('generate-btn'); setLoading(true, button);
    try {
      state.result = await api('/api/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
      renderResult(state.result); inputView.classList.add('hidden'); resultsView.classList.remove('hidden'); window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) { toast(err.message); }
    finally { setLoading(false, button); }
  }
  function appendBreakdown(items) {
    const list = $('breakdown-list'); list.replaceChildren();
    items.forEach((item) => {
      const row = element('div', 'breakdown-item'); row.append(element('span', 'breakdown-key', item.component));
      const copy = element('div'); copy.append(element('strong', '', item.meaning), document.createTextNode(` — ${item.explanation}`)); row.append(copy); list.append(row);
    });
  }
  function renderFacts(facts) {
    const list = $('facts-list'); list.replaceChildren();
    facts.forEach((fact) => {
      const li = element('li'); const text = element('span');
      const keywords = new Set((fact.keywords || []).map((word) => word.toLowerCase()).filter(Boolean));
      const escaped = [...keywords].sort((a, b) => b.length - a.length).map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
      if (escaped) {
        const re = new RegExp(`(${escaped})`, 'ig'); let cursor = 0; let match;
        while ((match = re.exec(fact.fact)) !== null) { text.append(document.createTextNode(fact.fact.slice(cursor, match.index))); text.append(element('strong', '', match[0])); cursor = re.lastIndex; }
        text.append(document.createTextNode(fact.fact.slice(cursor)));
      } else text.textContent = fact.fact;
      li.append(text, document.createTextNode(` ${fact.explanation}`)); list.append(li);
    });
  }
  function renderQuiz(questions) {
    const host = $('quiz-questions'); host.replaceChildren(); $('quiz-count').textContent = `${questions.length} QUESTIONS`;
    questions.forEach((q, index) => {
      const card = element('div', 'quiz-question'); card.dataset.index = String(index);
      const typeLabel = q.type === 'mcq' ? 'MULTIPLE CHOICE' : q.type === 'fill_blank' ? 'FILL IN THE BLANK' : 'SHORT ANSWER';
      card.append(element('span', 'question-type', typeLabel)); card.append(element('h3', '', `${index + 1}. ${q.question}`));
      if (q.type === 'mcq') {
        const options = element('div', 'quiz-options');
        q.options.forEach((option, optionIndex) => {
          const label = element('label', 'quiz-option'); const input = document.createElement('input'); input.type = 'radio'; input.name = `q-${index}`; input.value = option; input.required = true;
          label.append(input, element('span', '', option)); options.append(label);
        }); card.append(options);
      } else {
        const input = document.createElement('input'); input.className = 'quiz-input'; input.name = `q-${index}`; input.type = 'text'; input.autocomplete = 'off'; input.required = true; input.placeholder = 'Your answer…'; card.append(input);
      }
      card.append(element('div', 'answer-feedback hidden')); host.append(card);
    });
    $('quiz-result').textContent = ''; $('retry-quiz').classList.add('hidden'); $('submit-quiz').classList.remove('hidden'); $('submit-quiz').disabled = false;
  }
  function renderResult(data) {
    $('result-topic').textContent = data.topic; $('result-overview').textContent = data.content_overview;
    $('mnemonic-title').textContent = data.mnemonic.title; $('mnemonic-text').textContent = data.mnemonic.text;
    $('technique-label').textContent = data.technique; $('technique-reason').textContent = data.technique_reason;
    appendBreakdown(data.mnemonic.breakdown); renderFacts(data.key_facts);
    const tips = $('tips-list'); tips.replaceChildren(); data.memory_tips.forEach((tip) => tips.append(element('li', '', tip)));
    const notes = $('accuracy-notes'); const notesList = $('accuracy-list'); notesList.replaceChildren();
    (data.accuracy_notes || []).forEach((note) => notesList.append(element('li', '', note)));
    notes.classList.toggle('hidden', !data.accuracy_notes || !data.accuracy_notes.length);
    renderQuiz(data.recall_test);
  }
  function normalize(text) { return text.normalize('NFKC').toLocaleLowerCase().replace(/[.,!?;:'"()[\]{}]/g, '').replace(/\s+/g, ' ').trim(); }
  function submitQuiz(event) {
    event.preventDefault(); if (!state.result) return;
    const cards = [...document.querySelectorAll('.quiz-question')]; let score = 0;
    cards.forEach((card, index) => {
      const q = state.result.recall_test[index]; let answer = '';
      if (q.type === 'mcq') answer = card.querySelector('input:checked')?.value || '';
      else answer = card.querySelector('.quiz-input').value.trim();
      const validAnswers = [q.correct_answer, ...(q.acceptable_answers || [])].map(normalize);
      const correct = validAnswers.includes(normalize(answer)); if (correct) score++;
      const feedback = card.querySelector('.answer-feedback'); feedback.className = `answer-feedback ${correct ? 'correct' : 'incorrect'}`;
      const explanation = document.createTextNode(`${correct ? 'Correct.' : `Not quite. Answer: ${q.correct_answer}.`} ${q.explanation}`); feedback.replaceChildren(explanation);
      card.classList.toggle('is-correct', correct); card.classList.toggle('is-wrong', !correct);
      card.querySelectorAll('input').forEach((input) => { input.disabled = true; });
    });
    $('quiz-result').textContent = `${score} / ${cards.length} correct`;
    $('submit-quiz').classList.add('hidden'); $('retry-quiz').classList.remove('hidden');
  }
  function copy(text, message) { navigator.clipboard.writeText(text).then(() => toast(message)).catch(() => toast('Clipboard access was blocked by your browser.')); }
  function allResultsText() {
    const data = state.result; if (!data) return '';
    return `${data.topic}\n\n${data.content_overview}\n\n${data.mnemonic.title}\n${data.mnemonic.text}\nTechnique: ${data.technique} — ${data.technique_reason}\n\nBreakdown\n${data.mnemonic.breakdown.map((x) => `• ${x.component}: ${x.meaning}. ${x.explanation}`).join('\n')}\n\nKey facts\n${data.key_facts.map((x, i) => `${i + 1}. ${x.fact} — ${x.explanation}`).join('\n')}\n\nMemory tips\n${data.memory_tips.map((x) => `• ${x}`).join('\n')}`;
  }
  function explanationText() {
    const data = state.result; return data ? `${data.mnemonic.title}\n${data.mnemonic.text}\n\n${data.technique}: ${data.technique_reason}\n\n${data.mnemonic.breakdown.map((x) => `${x.component} → ${x.meaning}: ${x.explanation}`).join('\n')}` : '';
  }
  document.querySelectorAll('.tab').forEach((tab) => tab.addEventListener('click', () => setMode(tab.dataset.tab)));
  sourceInput.addEventListener('input', updateCounts);
  $('clear-text').addEventListener('click', clearInput);
  $('browse-file').addEventListener('click', () => $('file-input').click());
  $('drop-zone').addEventListener('click', (event) => { if (!event.target.closest('button')) $('file-input').click(); });
  $('drop-zone').addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); $('file-input').click(); } });
  $('file-input').addEventListener('change', (event) => acceptFile(event.target.files[0]));
  $('remove-file').addEventListener('click', clearInput);
  $('drop-zone').addEventListener('dragover', (event) => { event.preventDefault(); $('drop-zone').classList.add('dragover'); });
  $('drop-zone').addEventListener('dragleave', () => $('drop-zone').classList.remove('dragover'));
  $('drop-zone').addEventListener('drop', (event) => { event.preventDefault(); $('drop-zone').classList.remove('dragover'); acceptFile(event.dataTransfer.files[0]); });
  $('edit-extracted').addEventListener('click', () => { setMode('paste'); sourceInput.value = $('extracted-text').value; updateCounts(); sourceInput.focus(); });
  $('generate-btn').addEventListener('click', generateResult);
  $('sample-btn').addEventListener('click', () => { setMode('paste'); sourceInput.value = 'The planets in order from the Sun are Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, and Neptune.'; updateCounts(); sourceInput.focus(); });
  $('back-btn').addEventListener('click', () => { resultsView.classList.add('hidden'); inputView.classList.remove('hidden'); window.scrollTo({ top: 0, behavior: 'smooth' }); });
  $('regenerate-btn').addEventListener('click', async () => { resultsView.classList.add('hidden'); inputView.classList.remove('hidden'); await generateResult(); });
  $('copy-mnemonic-btn').addEventListener('click', () => copy(`${state.result.mnemonic.title}\n${state.result.mnemonic.text}`, 'Mnemonic copied.'));
  $('copy-all-btn').addEventListener('click', () => copy(allResultsText(), 'Learning guide copied.'));
  $('copy-explanation-btn').addEventListener('click', () => copy(explanationText(), 'Explanation copied.'));
  $('quiz-form').addEventListener('submit', submitQuiz);
  $('retry-quiz').addEventListener('click', () => renderQuiz(state.result.recall_test));
  $('theme-toggle').addEventListener('click', () => { document.body.classList.toggle('dark'); localStorage.setItem('memomind-theme', document.body.classList.contains('dark') ? 'dark' : 'light'); });
  if (localStorage.getItem('memomind-theme') === 'dark') document.body.classList.add('dark');
  health(); updateCounts();
})();

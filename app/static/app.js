'use strict';

(() => {
  const $ = (selector, parent = document) => parent.querySelector(selector);
  const $$ = (selector, parent = document) => Array.from(parent.querySelectorAll(selector));
  const state = {
    view: 'dashboard', config: null, materials: [], questions: [], wrongbook: [], history: [], stats: null,
    selected: new Set(), generated: [], quiz: null, answers: {}, result: null, wrongFilter: 'unmastered',
    seedBusy: false, quizStarting: false, submitting: false, refreshing: false
  };
  const titles = {
    dashboard: ['学习概览', '把学习资料变成练习，把每一次错误变成进步。'],
    materials: ['学习资料', '收好每一份资料，给知识一个清晰的起点。'],
    generate: ['智能出题', '从资料出发，让练习更贴近你正在学习的内容。'],
    bank: ['我的题库', '让零散的知识点，成为可以反复练习的题目。'],
    quiz: ['在线练习', '给自己一点专注时间，用主动回忆加深理解。'],
    wrongbook: ['错题复习', '每一道错题，都是下一次进步的线索。'],
    history: ['练习记录', '看见走过的每一步，也找到下一步的方向。']
  };
  const difficultyNames = { easy: '基础', medium: '进阶', hard: '挑战' };
  let toastTimer;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }
  function append(parent, ...children) {
    children.forEach(child => { if (child) parent.append(child); });
    return parent;
  }
  function text(selector, value) { $(selector).textContent = String(value ?? ''); }
  function button(label, className, action) {
    const node = el('button', className, label);
    node.type = 'button';
    if (action) node.addEventListener('click', action);
    return node;
  }
  function formatDate(value, withTime = true) {
    if (!value) return '暂无记录';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat('zh-CN', withTime
      ? { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }
      : { year: 'numeric', month: '2-digit', day: '2-digit' }).format(date);
  }
  function numeric(value, fallback = 0) { const n = Number(value); return Number.isFinite(n) ? n : fallback; }
  function percentage(value) { return Math.max(0, Math.min(100, numeric(value))); }
  function pct(value) { const n = percentage(value); return Number.isInteger(n) ? String(n) : n.toFixed(1); }
  function materialName(id) { return state.materials.find(m => String(m.id) === String(id))?.title || '未关联资料'; }
  function errorMessage(error) { return error instanceof Error ? error.message : '请求失败，请稍后重试。'; }
  function showError(error) {
    const message = errorMessage(error);
    text('#global-error', message);
    $('#global-error').hidden = false;
    toast(message, true);
  }
  function clearError() { $('#global-error').hidden = true; text('#global-error', ''); }
  function toast(message, isError = false) {
    clearTimeout(toastTimer);
    $('#toast-region').replaceChildren(el('div', `toast${isError ? ' error' : ''}`, message));
    toastTimer = setTimeout(() => $('#toast-region').replaceChildren(), isError ? 8500 : 4500);
  }
  async function api(path, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const headers = { Accept: 'application/json', ...options.headers };
    if (method !== 'GET' && method !== 'HEAD') headers['X-Requested-With'] = 'quiz-app';
    let body = options.body;
    if (body !== undefined && !(body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }
    let response;
    try { response = await fetch(path, { ...options, method, body, headers, credentials: 'same-origin' }); }
    catch (_) { throw new Error('无法连接本地服务。请确认服务仍在运行，然后重试。'); }
    let data;
    try { data = await response.json(); }
    catch (_) { throw new Error(`服务返回了无法读取的响应（HTTP ${response.status}）。请检查服务日志。`); }
    if (!response.ok) {
      let detail = data?.detail;
      if (Array.isArray(detail)) detail = detail.map(item => typeof item === 'string' ? item : item.msg || '字段校验失败').join('；');
      if (typeof detail !== 'string') detail = data?.message || `请求失败（HTTP ${response.status}），请重试。`;
      throw new Error(detail);
    }
    return data;
  }
  async function run(control, busyText, task) {
    if (control?.dataset.busy === 'true') return;
    clearError();
    const previous = control?.textContent;
    const wasDisabled = control?.disabled;
    if (control) {
      control.dataset.busy = 'true'; control.disabled = true; control.setAttribute('aria-busy', 'true');
      if (busyText) control.textContent = busyText;
    }
    try { return await task(); }
    catch (error) { showError(error); return undefined; }
    finally {
      if (control) {
        control.dataset.busy = 'false'; control.disabled = wasDisabled; control.removeAttribute('aria-busy');
        if (busyText) control.textContent = previous;
      }
      updateSelection();
      updateWrongPracticeButton();
    }
  }
  function emptyState(title, description, icon = '▤', action) {
    const node = el('div', 'empty-state');
    const symbol = el('span', 'empty-icon', icon); symbol.setAttribute('aria-hidden', 'true');
    append(node, symbol, el('h3', '', title), el('p', '', description));
    if (action) node.append(button(action.label, 'button button-secondary button-sm', action.run));
    return node;
  }

  function navigate(view, { allowQuizLeave = false, focus = true } = {}) {
    if (!titles[view]) view = 'dashboard';
    if (view === state.view) return true;
    if (state.submitting && view !== 'quiz') {
      toast('答案正在提交，请等待结果后再切换页面。'); return false;
    }
    if (state.quiz && state.view === 'quiz' && view !== 'quiz' && !allowQuizLeave) {
      if (!window.confirm('本次练习尚未提交。离开后，当前作答不会保存，需要重新开始。确定离开吗？')) return false;
      state.quiz = null; state.answers = {}; renderQuiz();
    }
    state.view = view;
    $$('.view').forEach(node => { node.hidden = node.id !== `view-${view}`; });
    $$('.nav-item').forEach(node => {
      const active = node.dataset.view === view;
      node.classList.toggle('active', active);
      if (active) node.setAttribute('aria-current', 'page'); else node.removeAttribute('aria-current');
    });
    text('#page-title', titles[view][0]); text('#page-subtitle', titles[view][1]);
    document.title = `${titles[view][0]} · 知题`;
    history.replaceState(null, '', `#${view}`);
    clearError();
    if (focus) { $('#main-content').focus({ preventScroll: true }); window.scrollTo({ top: 0, behavior: 'instant' }); }
    return true;
  }

  async function refreshAll() {
    const [config, stats, materials, questions, wrongbook, historyItems] = await Promise.all([
      api('/api/config'), api('/api/stats'), api('/api/materials'), api('/api/questions'), api('/api/wrongbook'), api('/api/history')
    ]);
    Object.assign(state, { config, stats, materials, questions, wrongbook, history: historyItems });
    const ids = new Set(questions.map(q => String(q.id)));
    state.selected.forEach(id => { if (!ids.has(String(id))) state.selected.delete(id); });
    renderConfig(); renderDashboard(); renderMaterials(); renderMaterialOptions(); renderBank(); renderWrongbook(); renderHistory();
  }
  function renderConfig() {
    const ready = Boolean(state.config?.remote_ready);
    text('#sidebar-mode', ready ? '本地运行 · API 已配置' : '本地运行 · 演示可用');
    text('#sidebar-model', ready ? `模型：${state.config.model || '使用后端配置'}` : '无需密钥即可体验示例');
    $('#remote-mode-radio').disabled = !ready;
    text('#remote-model-help', ready ? `模型：${state.config.model || '使用后端配置'} · 内容将发送至服务商` : '请在 .env 配置服务商、模型和 API Key 后重启服务');
    if (!ready) $('input[name="generate-mode"][value="demo"]').checked = true;
    text('#upload-help', `支持 TXT、Markdown、含文本层的 PDF（最多 40 页），最大 ${state.config?.upload_limit_mb || 5} MB；提取后最多 30,000 字符。`);
    updateModeNote();
  }
  function renderDashboard() {
    const s = state.stats || {};
    text('#stat-materials', numeric(s.materials)); text('#stat-questions', numeric(s.questions)); text('#stat-quizzes', numeric(s.quiz_count));
    text('#stat-accuracy', numeric(s.total_answered) ? `${pct(s.accuracy)}%` : '—');
    text('#stat-answered', `已累计作答 ${numeric(s.total_answered)} 道题`);
    text('#stat-wrong', `${numeric(s.wrong_count)} 道错题，值得再次回顾`);
    text('#nav-material-count', numeric(s.materials)); text('#nav-question-count', numeric(s.questions)); text('#nav-wrong-count', numeric(s.wrong_count));
    const knowledge = $('#knowledge-list'); knowledge.replaceChildren();
    const points = Array.isArray(s.knowledge_points) ? s.knowledge_points : [];
    if (!points.length) knowledge.append(emptyState('理解的足迹，从一次练习开始', '完成一组练习后，这里会展示各知识点的作答情况。', '↗'));
    points.slice(0, 6).forEach(point => {
      const row = el('div', 'knowledge-row');
      const label = el('div', 'knowledge-label');
      append(label, el('span', '', point.knowledge_point || '综合知识'), el('span', '', `${numeric(point.correct)}/${numeric(point.total)} · ${pct(point.accuracy)}%`));
      const track = el('div', 'progress-track');
      track.setAttribute('role', 'meter'); track.setAttribute('aria-label', `${point.knowledge_point || '综合知识'}正确率`);
      track.setAttribute('aria-valuemin', '0'); track.setAttribute('aria-valuemax', '100'); track.setAttribute('aria-valuenow', String(percentage(point.accuracy)));
      const fill = el('div', `progress-fill${percentage(point.accuracy) < 60 ? ' low' : ''}`);
      fill.style.width = `${percentage(point.accuracy)}%`; track.append(fill);
      append(row, label, track); knowledge.append(row);
    });
    const recent = $('#recent-list'); recent.replaceChildren();
    const scores = Array.isArray(s.recent_scores) ? s.recent_scores : [];
    if (!scores.length) recent.append(emptyState('你的学习记录，等你来写', '做完的每一组题，都会在这里留下记录。', '◷', { label: '开始一次练习', run: () => navigate('quiz') }));
    scores.slice(0, 4).forEach((item, index) => {
      const row = button('', 'recent-row', () => openHistory(item.id, row));
      const info = el('span', 'recent-info');
      append(info, el('strong', '', `练习记录 · #${item.id}`), el('small', '', formatDate(item.created_at)));
      const score = el('span', 'score', pct(item.score)); score.append(el('small', '', '分'));
      append(row, el('span', 'recent-icon', '▤'), info, score); recent.append(row);
    });
  }
  function renderMaterials() {
    text('#materials-summary', `共 ${state.materials.length} 份资料 · 保存在本地`);
    const list = $('#materials-list'); list.replaceChildren();
    if (!state.materials.length) {
      list.append(emptyState('给学习添一份资料', '可以粘贴文本、上传文件，也可以先体验内置 Python 示例。', '▤', { label: '加载 Python 示例', run: event => seedDemo(event.currentTarget) })); return;
    }
    state.materials.forEach(material => {
      const card = el('article', 'material-card');
      const top = el('div', 'material-card-top'); const details = el('div', 'material-details');
      append(details, el('h3', '', material.title), el('div', 'material-meta', `${material.course || '未分类'} · ${String(material.text || '').length.toLocaleString('zh-CN')} 字符`));
      append(top, el('span', 'material-icon', '▤'), details);
      const footer = el('div', 'card-footer');
      const actions = el('div', 'button-row');
      append(actions, button('查看原文', 'text-button', () => showMaterial(material)), button('用它出题 ↗', 'text-button', () => selectMaterialForGeneration(material.id)));
      append(footer, el('small', '', formatDate(material.created_at, false)), actions);
      append(card, top, el('p', 'material-excerpt', material.text || ''), footer); list.append(card);
    });
  }
  function renderMaterialOptions() {
    ['#generate-material', '#bank-material'].forEach(selector => {
      const select = $(selector); const previous = select.value;
      const placeholder = document.createElement('option'); placeholder.value = ''; placeholder.textContent = selector === '#generate-material' ? '请选择资料' : '全部资料';
      select.replaceChildren(placeholder);
      state.materials.forEach(material => { const option = el('option', '', material.title); option.value = String(material.id); select.append(option); });
      if (state.materials.some(m => String(m.id) === previous)) select.value = previous;
      else if (selector === '#generate-material' && state.materials.length === 1) select.value = String(state.materials[0].id);
    });
    renderMaterialPreview();
  }
  function renderMaterialPreview() {
    const material = state.materials.find(m => String(m.id) === $('#generate-material').value);
    const preview = $('#generation-material-preview');
    preview.classList.toggle('empty-source', !material);
    preview.textContent = material ? material.text || '这份资料尚无可用文本。' : '选择一份资料，查看原文内容。';
  }
  function selectMaterialForGeneration(id) {
    if (!navigate('generate')) return;
    $('#generate-material').value = String(id); renderMaterialPreview(); $('#generate-material').focus();
  }
  function showDialog(title, content) {
    text('#dialog-title', title); $('#dialog-content').replaceChildren(content);
    if (!$('#detail-dialog').open) $('#detail-dialog').showModal();
  }
  function showMaterial(material) {
    const body = el('div');
    append(body, el('p', 'dialog-meta', `${material.course || '未分类'} · ${material.filename || '粘贴文本'} · ${formatDate(material.created_at, false)}`), el('div', 'source-preview dialog-source', material.text || '暂无文本。'));
    showDialog(material.title, body);
  }
  function updateModeNote() {
    const remote = $('input[name="generate-mode"]:checked')?.value === 'openai';
    $('#generate-difficulty').disabled = !remote;
    if (!remote) $('#generate-difficulty').value = 'easy';
    text('#generation-mode-note', remote
      ? '真实 API 会把所选资料的完整文本发送给后端配置的服务商，并可能产生费用。开始前会再次确认；请勿上传不应外发的内容。'
      : '演示模式仅支持内置 Python 示例资料，使用固定基础难度示例题，不是实时 AI 生成；自定义资料需要配置真实 API。');
  }
  async function seedDemo(control) {
    if (state.seedBusy) return;
    state.seedBusy = true;
    const controls = [$('#seed-demo-button'), $('#generate-seed-button')];
    controls.forEach(node => { node.disabled = true; });
    await run(control, '加载示例中…', async () => {
      const result = await api('/api/demo/seed', { method: 'POST' });
      await refreshAll();
      if (result.material?.id !== undefined) { $('#generate-material').value = String(result.material.id); renderMaterialPreview(); }
      toast('Python 示例已就绪。可以直接练习，也可以在智能出题页生成一组题目。');
    });
    state.seedBusy = false; controls.forEach(node => { node.disabled = false; });
  }
  async function saveMaterial(event) {
    event.preventDefault();
    const source = $('input[name="material-source"]:checked').value;
    const title = $('#material-title').value.trim(); const course = $('#material-course').value.trim() || '未分类';
    if (!title) { showError(new Error('请填写资料标题。')); $('#material-title').focus(); return; }
    await run($('#save-material-button'), '保存中…', async () => {
      let material;
      if (source === 'file') {
        const file = $('#material-file').files[0];
        if (!file) throw new Error('请选择要上传的资料文件。');
        if (file.size > numeric(state.config?.upload_limit_mb, 5) * 1024 * 1024) throw new Error(`资料文件不能超过 ${state.config?.upload_limit_mb || 5} MB。`);
        const form = new FormData(); form.append('file', file); form.append('title', title); form.append('course', course);
        material = await api('/api/materials/upload', { method: 'POST', body: form });
      } else {
        const value = $('#material-text').value.trim();
        if (value.length < 20 || value.length > 30000) throw new Error('资料正文需要 20–30,000 字符。');
        material = await api('/api/materials', { method: 'POST', body: { title, course, text: value } });
      }
      $('#material-form').reset(); updateMaterialSource();
      await refreshAll();
      if (material?.id !== undefined) { $('#generate-material').value = String(material.id); renderMaterialPreview(); }
      toast('资料已保存，可前往智能出题页配置练习。');
    });
  }
  function updateMaterialSource() {
    const useFile = $('input[name="material-source"]:checked').value === 'file';
    $('#material-text-field').hidden = useFile; $('#material-file-field').hidden = !useFile;
    $('#material-text').required = !useFile; $('#material-file').required = useFile;
  }
  async function generateQuestions(event) {
    event.preventDefault();
    const material = state.materials.find(m => String(m.id) === $('#generate-material').value);
    if (!material) { showError(new Error('请先选择一份学习资料。')); return; }
    const mode = $('input[name="generate-mode"]:checked').value;
    let confirmSend = false;
    if (mode === 'openai') {
      if (!state.config?.remote_ready) { showError(new Error('真实 API 尚未配置。请在 .env 中配置服务商、模型和 API Key，重启服务后再试。')); return; }
      const provider = state.config.provider || state.config.provider_host || state.config.base_url || '后端配置的 OpenAI 兼容服务商';
      confirmSend = window.confirm(`确认发送资料并调用真实 API？\n\n资料：${material.title}\n内容：当前预览的完整资料文本（${String(material.text || '').length.toLocaleString('zh-CN')} 字符）\n接收方：${provider}\n模型：${state.config.model || '使用后端配置'}\n\n所选资料的完整文本将离开本机并发送至该服务商，可能产生 API 费用。请确认你有权外发这些内容。生成结果需要人工核验。\n\n点击“确定”发送，点击“取消”保留在本地。`);
      if (!confirmSend) return;
    }
    const count = Number($('#generate-count').value);
    if (!Number.isInteger(count) || count < 1 || count > 10) { showError(new Error('每次生成数量需要是 1–10 之间的整数。')); return; }
    await run($('#generate-submit-button'), mode === 'openai' ? '模型正在生成，请稍候…' : '正在准备练习…', async () => {
      const result = await api('/api/generate', { method: 'POST', body: { material_id: material.id, count, difficulty: $('#generate-difficulty').value, mode, confirm_send: confirmSend } });
      state.generated = Array.isArray(result.questions) ? result.questions : [];
      const list = $('#generation-result-list'); list.replaceChildren();
      state.generated.forEach((question, index) => {
        const item = el('div', 'generated-item'); const copy = el('div');
        append(copy, el('strong', '', question.stem), el('small', '', `${question.knowledge_point || '综合知识'} · ${difficultyNames[question.difficulty] || question.difficulty || '未标注难度'}`));
        append(item, el('span', '', String(index + 1).padStart(2, '0')), copy); list.append(item);
      });
      text('#generation-result-note', result.note || `本次已准备 ${state.generated.length} 道题。题目已保存到题库。`);
      $('#generation-results').hidden = false;
      $('#practice-generated-button').disabled = state.generated.length === 0;
      await refreshAll();
      toast(`已准备 ${state.generated.length} 道练习题，请核验参考答案与原文出处。`);
      if (state.view === 'generate') $('#generation-results').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  }

  function filteredQuestions() {
    const query = $('#bank-search').value.trim().toLocaleLowerCase();
    const material = $('#bank-material').value; const difficulty = $('#bank-difficulty').value;
    return state.questions.filter(q => (!material || String(q.material_id) === material) && (!difficulty || q.difficulty === difficulty)
      && (!query || `${q.stem || ''} ${q.knowledge_point || ''} ${(q.options || []).join(' ')}`.toLocaleLowerCase().includes(query)));
  }
  function answerPanel(question) {
    const panel = el('div', 'answer-panel');
    const answer = Number(question.answer); const validAnswer = Number.isInteger(answer) && answer >= 0 && answer < 4;
    append(panel, el('p', 'answer-heading', validAnswer ? `参考答案：${String.fromCharCode(65 + answer)}. ${question.options?.[answer] || ''}` : '参考答案：未提供'), el('p', 'explanation-text', question.explanation || '暂无解析。'));
    const quote = el('div', 'source-quote');
    append(quote, el('span', 'source-quote-title', '原文出处 · 请对照资料核验'), el('span', '', question.source_quote || '未提供原文引文。'));
    append(panel, quote, el('p', 'review-note', '题目、参考答案与引文用于辅助学习，可能存在错误，请人工复核。'));
    return panel;
  }
  function questionCard(question, { index, selectable = false, result = null } = {}) {
    const card = el('article', 'question-card'); const head = el('div', 'question-head');
    if (selectable) {
      const label = el('label', 'checkbox-label'); const checkbox = el('input'); checkbox.type = 'checkbox';
      checkbox.checked = state.selected.has(String(question.id)); checkbox.dataset.questionId = String(question.id);
      checkbox.setAttribute('aria-label', `选择题目：${question.stem}`);
      checkbox.addEventListener('change', () => {
        if (checkbox.checked && state.selected.size >= 50) { checkbox.checked = false; toast('每次最多选择 50 道题，请先取消部分选择。', true); return; }
        if (checkbox.checked) state.selected.add(String(question.id)); else state.selected.delete(String(question.id)); updateSelection();
      });
      label.append(checkbox); head.append(label);
    }
    if (index !== undefined) head.append(el('span', 'question-index', `题目 ${String(index + 1).padStart(2, '0')}`));
    append(head, el('span', 'pill', question.knowledge_point || '综合知识'));
    if (question.difficulty) head.append(el('span', 'pill blue-pill', difficultyNames[question.difficulty] || question.difficulty));
    if (result) head.append(el('span', `result-status${result.is_correct ? '' : ' incorrect'}`, result.is_correct ? '✓ 回答正确' : '需再练习'));
    append(card, head, el('h3', 'question-stem', question.stem));
    const options = el('div', 'options-list');
    (question.options || []).forEach((option, optionIndex) => {
      let className = 'option-line';
      if (result && optionIndex === Number(result.answer)) className += ' correct-option';
      if (result && !result.is_correct && result.selected !== null && result.selected !== undefined && optionIndex === Number(result.selected)) className += ' wrong-option';
      const row = el('div', className);
      append(row, el('span', 'option-letter', String.fromCharCode(65 + optionIndex)), el('span', '', option));
      if (result && result.selected !== null && result.selected !== undefined && optionIndex === Number(result.selected)) row.append(el('span', 'option-status', '你的选择'));
      else if (result && optionIndex === Number(result.answer)) row.append(el('span', 'option-status', '参考答案'));
      options.append(row);
    });
    card.append(options);
    const details = el('details', 'question-details');
    details.open = Boolean(result);
    append(details, el('summary', '', '参考答案、解析与原文出处'), answerPanel(question)); card.append(details);
    if (question.material_id !== undefined) {
      const generator = String(question.generator || '').startsWith('demo') ? '本地固定示例题' : question.generator === 'imported' ? '备份导入' : question.generator ? `生成来源：${question.generator}` : '已保存题目';
      card.append(el('p', 'question-footnote', `${materialName(question.material_id)} · ${generator}`));
    }
    return card;
  }
  function renderBank() {
    const list = $('#bank-list'); list.replaceChildren();
    const questions = filteredQuestions(); text('#bank-summary', `我的题目 · ${state.questions.length} 道`);
    if (!questions.length) list.append(emptyState(state.questions.length ? '没有匹配的题目' : '题库还空着，先生成一组吧', state.questions.length ? '试试其他关键词，或调整资料与难度筛选。' : '从你的资料出发，逐步积累专属练习。', '▦', state.questions.length ? undefined : { label: '前往智能出题', run: () => navigate('generate') }));
    questions.forEach((question, index) => list.append(questionCard(question, { index, selectable: true })));
    updateSelection();
  }
  function updateSelection() {
    text('#bank-selected-count', `已选 ${state.selected.size} / 50 道题`);
    const control = $('#practice-selected-button');
    if (control.dataset.busy !== 'true') control.disabled = state.selected.size === 0 || state.quizStarting;
    const questions = filteredQuestions(); const selected = questions.filter(q => state.selected.has(String(q.id))).length;
    $('#bank-select-all').checked = questions.length > 0 && selected === questions.length;
    $('#bank-select-all').indeterminate = selected > 0 && selected < questions.length;
    $('#bank-select-all').disabled = questions.length === 0;
  }
  async function exportBank(event) {
    event.preventDefault();
    await run($('#export-button'), '导出中…', async () => {
      let response;
      try { response = await fetch('/api/export', { credentials: 'same-origin', headers: { Accept: 'application/json' } }); }
      catch (_) { throw new Error('无法连接本地服务，请确认服务仍在运行后重试。'); }
      if (!response.ok) {
        let detail;
        try { detail = (await response.json()).detail; } catch (_) { /* Show the status fallback below. */ }
        throw new Error(typeof detail === 'string' ? detail : `导出失败（HTTP ${response.status}）。`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = `zhiti-question-bank-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      toast('已开始下载资料与题目备份，不包含练习记录。');
    });
  }
  async function importBank(file) {
    if (!file) return;
    await run($('#import-button'), '导入中…', async () => {
      const form = new FormData(); form.append('file', file);
      const result = await api('/api/import', { method: 'POST', body: form });
      await refreshAll();
      const materials = Array.isArray(result.materials) ? result.materials.length : numeric(result.materials);
      const questions = Array.isArray(result.questions) ? result.questions.length : numeric(result.questions);
      toast(`备份已导入：${materials} 份资料，${questions} 道题目。`);
    });
    $('#import-file').value = '';
  }

  async function startQuiz(ids, mode = 'normal', control = null) {
    if (state.quizStarting) return;
    if (!ids.length) { toast('暂无可练习题目。请先生成题目。'); return; }
    if (ids.length > 50) { showError(new Error('每次练习最多 50 道题，请减少选择后再试。')); return; }
    if (state.quiz && !window.confirm('当前练习尚未提交。重新组卷将放弃当前作答，确定继续吗？')) return;
    state.quizStarting = true;
    await run(control, '正在组卷…', async () => {
      const quiz = await api('/api/quizzes', { method: 'POST', body: { question_ids: ids, mode } });
      if (!quiz.questions?.length) throw new Error('本次组卷未返回题目，请重新选择。');
      state.quiz = { ...quiz, mode }; state.answers = {}; state.result = null;
      renderQuiz(); navigate('quiz', { allowQuizLeave: true });
    });
    state.quizStarting = false; updateSelection(); updateWrongPracticeButton();
  }
  function renderQuiz() {
    $('#quiz-empty').hidden = Boolean(state.quiz || state.result);
    $('#quiz-active').hidden = !state.quiz;
    $('#quiz-result').hidden = !state.result;
    if (state.result) $('#quiz-result').replaceChildren(resultView(state.result));
    if (!state.quiz) return;
    text('#quiz-mode-label', state.quiz.mode === 'wrongbook' ? 'REVISIT & REMEMBER · 错题专项' : 'FOCUS TIME · 专注练习');
    const list = $('#quiz-questions'); list.replaceChildren();
    state.quiz.questions.forEach((question, index) => {
      const fieldset = el('fieldset', 'quiz-question'); const legend = el('legend');
      append(legend, el('span', 'question-index', `第 ${index + 1} 题 · ${question.knowledge_point || '综合知识'}`), el('span', 'question-stem', question.stem));
      const options = el('div', 'quiz-option-list');
      (question.options || []).forEach((option, optionIndex) => {
        const label = el('label', 'quiz-option'); const radio = el('input');
        radio.type = 'radio'; radio.name = `question-${question.id}`; radio.value = String(optionIndex);
        radio.checked = state.answers[String(question.id)] === optionIndex;
        radio.addEventListener('change', () => { state.answers[String(question.id)] = optionIndex; updateQuizProgress(); });
        append(label, radio, el('span', '', `${String.fromCharCode(65 + optionIndex)}. ${option}`)); options.append(label);
      });
      append(fieldset, legend, options); list.append(fieldset);
    });
    updateQuizProgress();
  }
  function updateQuizProgress() {
    if (!state.quiz) return;
    const count = state.quiz.questions.filter(q => state.answers[String(q.id)] !== undefined).length; const total = state.quiz.questions.length;
    text('#quiz-progress-label', `已作答 ${count} / ${total} 道`);
    text('#quiz-submit-hint', count === total ? '已完成全部作答，可以提交并查看解析。' : `还有 ${total - count} 道题未作答。`);
    $('#quiz-progress-bar').style.width = `${total ? count / total * 100 : 0}%`;
  }
  async function submitQuiz(event) {
    event.preventDefault();
    if (!state.quiz || state.submitting) return;
    const missing = state.quiz.questions.find(q => state.answers[String(q.id)] === undefined);
    if (missing) {
      toast('还有题目未作答，请完成全部题目后提交。', true);
      const control = $(`input[name="question-${CSS.escape(String(missing.id))}"]`);
      if (control) { control.focus(); control.closest('fieldset').scrollIntoView({ behavior: 'smooth', block: 'center' }); }
      return;
    }
    state.submitting = true;
    $('#quit-quiz-button').disabled = true;
    $$('#quiz-questions input').forEach(control => { control.disabled = true; });
    await run($('#submit-quiz-button'), '提交中…', async () => {
      const result = await api(`/api/quizzes/${encodeURIComponent(state.quiz.id)}/submit`, { method: 'POST', body: { answers: { ...state.answers } } });
      state.quiz = null; state.answers = {}; state.result = result; renderQuiz();
      toast(`练习已完成，答对 ${result.correct} / ${result.total} 道。`);
      window.scrollTo({ top: 0, behavior: 'smooth' });
      await refreshAll();
    });
    state.submitting = false; $('#quit-quiz-button').disabled = false;
    $$('#quiz-questions input').forEach(control => { control.disabled = false; });
  }
  function resultView(result, inDialog = false) {
    const container = el('div', inDialog ? 'result-panel-in-dialog' : '');
    const hero = el('div', 'panel result-hero'); const score = el('div', 'result-score', pct(result.score)); score.append(el('small', '', '分'));
    const copy = el('div', 'result-copy');
    append(copy, el('h2', '', '这次练习，已认真完成'), el('p', '', `共 ${numeric(result.total)} 道题，答对 ${numeric(result.correct)} 道 · ${formatDate(result.created_at || result.submitted_at)}`));
    if (!inDialog) {
      const actions = el('div', 'result-actions');
      append(actions, button('回顾错题', 'button button-primary button-sm', () => navigate('wrongbook')), button('继续选题', 'button button-secondary button-sm', () => navigate('bank')));
      copy.append(actions);
    }
    append(hero, score, copy); container.append(hero);
    container.append(el('div', 'notice notice-subtle', '以下展示参考答案与资料引文，请人工核验。错题已收录到错题本；本次已提交的作答结果不能修改。'));
    const list = el('div', 'stack');
    (result.results || []).forEach((item, index) => list.append(questionCard(item, { index, result: item })));
    container.append(list); return container;
  }
  function quitQuiz() {
    if (!state.quiz || state.submitting) return;
    if (!window.confirm('确定结束本次练习吗？未提交的作答不会保存。你可以随时重新选题开始。')) return;
    state.quiz = null; state.answers = {}; state.result = null; renderQuiz(); toast('已结束本次练习，可以重新选题。');
  }
  function renderWrongbook() {
    const list = $('#wrongbook-list'); list.replaceChildren();
    const unmastered = state.wrongbook.filter(entry => !entry.mastered);
    text('#wrongbook-summary', `待复习 ${unmastered.length} 道 · 已掌握 ${state.wrongbook.length - unmastered.length} 道`);
    const entries = state.wrongbook.filter(entry => state.wrongFilter === 'all' || (state.wrongFilter === 'mastered' ? entry.mastered : !entry.mastered));
    if (!entries.length) list.append(emptyState(state.wrongFilter === 'mastered' ? '这里记录你重新掌握的知识' : '当前没有待显示的错题', state.wrongbook.length ? '切换筛选，可以查看其他错题。' : '练习中答错的题目会自动收录，方便你有针对性地回顾。', '↺', { label: '开始练习', run: () => navigate('quiz') }));
    entries.forEach((entry, index) => {
      const question = entry.question; if (!question) return;
      const card = questionCard(question, { index });
      const meta = el('div', 'wrong-meta');
      append(meta, el('span', `pill ${entry.mastered ? 'mastered-pill' : 'unmastered-pill'}`, entry.mastered ? '已掌握' : '待复习'), el('span', '', `累计答错 ${numeric(entry.wrong_count)} 次`), el('span', '', `最近：${formatDate(entry.last_wrong_at)}`));
      card.prepend(meta);
      const actions = el('div', 'wrong-card-actions');
      const selected = Number(entry.last_selected);
      const selection = entry.last_selected !== null && entry.last_selected !== undefined && Number.isInteger(selected) && selected >= 0 && selected <= 3
        ? `上次选择：${String.fromCharCode(65 + selected)}` : '上次未作答';
      const buttons = el('div', 'button-row');
      const practice = button('单题重练', 'button button-secondary button-sm', () => startQuiz([question.id], 'wrongbook', practice));
      const toggle = button(entry.mastered ? '标为待复习' : '标记已掌握 ✓', 'button button-secondary button-sm', () => run(toggle, '保存中…', async () => {
        await api(`/api/wrongbook/${encodeURIComponent(question.id)}`, { method: 'PATCH', body: { mastered: !entry.mastered } });
        await refreshAll(); toast(entry.mastered ? '已移回待复习。' : '已标记为掌握，仍可在“已掌握”中查看。');
      }));
      append(buttons, practice, toggle); append(actions, el('span', 'field-hint', selection), buttons); card.append(actions); list.append(card);
    });
    updateWrongPracticeButton();
  }
  function updateWrongPracticeButton() {
    const control = $('#practice-wrong-button');
    if (control.dataset.busy !== 'true') {
      const count = state.wrongbook.filter(entry => !entry.mastered).length;
      control.disabled = count === 0 || state.quizStarting;
      control.textContent = count > 50 ? '练习前 50 道未掌握错题 ↗' : '练习未掌握错题 ↗';
    }
  }
  function renderHistory() {
    const list = $('#history-list'); list.replaceChildren();
    const completed = state.history.filter(item => item.submitted_at || item.score !== null && item.score !== undefined);
    if (!completed.length) { list.append(emptyState('每一份认真，都值得记录', '完成并提交练习后，你可以在这里重新查看作答与解析。', '◷', { label: '去选一组题', run: () => navigate('bank') })); return; }
    completed.forEach((item, index) => {
      const row = el('article', 'history-row'); const score = el('div', 'history-score', pct(item.score)); score.append(el('small', '', '分'));
      const description = el('div', 'history-description');
      append(description, el('h3', '', `${item.mode === 'wrongbook' ? '错题专项练习' : '自主练习'} · 第 ${completed.length - index} 次`), el('p', '', formatDate(item.submitted_at || item.created_at)));
      const view = button('查看解析 ↗', 'button button-secondary button-sm', () => openHistory(item.id, view));
      append(row, score, description, el('span', 'history-metrics', `${numeric(item.correct)} / ${numeric(item.total)} 道正确`), view); list.append(row);
    });
  }
  async function openHistory(id, control) {
    await run(control, null, async () => {
      const result = await api(`/api/history/${encodeURIComponent(id)}`);
      showDialog('练习记录与解析', resultView(result, true));
    });
  }

  function bindEvents() {
    $$('.nav-item').forEach(control => control.addEventListener('click', () => navigate(control.dataset.view)));
    $$('[data-navigate]').forEach(control => control.addEventListener('click', () => navigate(control.dataset.navigate)));
    $('.brand').addEventListener('click', event => { event.preventDefault(); navigate('dashboard'); });
    $('#seed-demo-button').addEventListener('click', event => seedDemo(event.currentTarget));
    $('#generate-seed-button').addEventListener('click', event => seedDemo(event.currentTarget));
    $('#refresh-button').addEventListener('click', async event => {
      if (state.refreshing) return; state.refreshing = true;
      await run(event.currentTarget, '刷新中…', async () => { await refreshAll(); toast('学习数据已更新。'); });
      state.refreshing = false;
    });
    $('#material-form').addEventListener('submit', saveMaterial);
    $$('input[name="material-source"]').forEach(control => control.addEventListener('change', updateMaterialSource));
    $('#generate-form').addEventListener('submit', generateQuestions);
    $('#generate-material').addEventListener('change', renderMaterialPreview);
    $$('input[name="generate-mode"]').forEach(control => control.addEventListener('change', updateModeNote));
    $('#practice-generated-button').addEventListener('click', event => startQuiz(state.generated.map(q => q.id), 'normal', event.currentTarget));
    $('#bank-search').addEventListener('input', renderBank);
    $('#bank-material').addEventListener('change', renderBank);
    $('#bank-difficulty').addEventListener('change', renderBank);
    $('#bank-select-all').addEventListener('change', event => {
      const questions = filteredQuestions();
      questions.forEach(q => { if (event.target.checked && state.selected.size < 50) state.selected.add(String(q.id)); else if (!event.target.checked) state.selected.delete(String(q.id)); });
      if (event.target.checked && questions.some(q => !state.selected.has(String(q.id)))) toast('每次最多选择 50 道题，已保留现有选择并按顺序补选。');
      $$('#bank-list input[data-question-id]').forEach(control => { control.checked = state.selected.has(control.dataset.questionId); }); updateSelection();
    });
    $('#bank-clear-selection').addEventListener('click', () => { state.selected.clear(); $$('#bank-list input[data-question-id]').forEach(control => { control.checked = false; }); updateSelection(); });
    $('#practice-selected-button').addEventListener('click', event => {
      const ids = state.questions.filter(q => state.selected.has(String(q.id))).map(q => q.id); startQuiz(ids, 'normal', event.currentTarget);
    });
    $('#export-button').addEventListener('click', exportBank);
    $('#import-button').addEventListener('click', () => $('#import-file').click());
    $('#import-file').addEventListener('change', event => importBank(event.target.files[0]));
    $('#quick-practice-button').addEventListener('click', event => startQuiz(state.questions.slice(0, 10).map(q => q.id), 'normal', event.currentTarget));
    $('#practice-wrong-button').addEventListener('click', event => startQuiz(state.wrongbook.filter(entry => !entry.mastered && entry.question).slice(0, 50).map(entry => entry.question.id), 'wrongbook', event.currentTarget));
    $('#quit-quiz-button').addEventListener('click', quitQuiz);
    $('#quiz-form').addEventListener('submit', submitQuiz);
    $$('[data-wrong-filter]').forEach(control => control.addEventListener('click', () => {
      state.wrongFilter = control.dataset.wrongFilter;
      $$('[data-wrong-filter]').forEach(item => { const selected = item === control; item.classList.toggle('selected', selected); item.setAttribute('aria-pressed', String(selected)); });
      renderWrongbook();
    }));
    $('#close-dialog-button').addEventListener('click', () => $('#detail-dialog').close());
    $('#detail-dialog').addEventListener('click', event => { if (event.target === $('#detail-dialog')) { const r = event.target.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) event.target.close(); } });
    window.addEventListener('beforeunload', event => { if (state.quiz) { event.preventDefault(); event.returnValue = ''; } });
    window.addEventListener('hashchange', () => { const target = location.hash.slice(1); if (!navigate(target)) history.replaceState(null, '', `#${state.view}`); });
  }
  async function init() {
    text('#today-label', new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' }).format(new Date()));
    bindEvents(); updateMaterialSource();
    const initialView = location.hash.slice(1);
    if (titles[initialView] && initialView !== 'dashboard') navigate(initialView, { focus: false });
    try { await refreshAll(); }
    catch (error) { showError(error); text('#sidebar-mode', '服务连接异常'); text('#sidebar-model', '检查服务后点击刷新数据'); }
  }
  init();
})();

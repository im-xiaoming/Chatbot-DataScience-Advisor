// Giao diện chat: đăng nhập/đăng ký, gọi POST /chat và đọc luồng SSE từng token
// (event: conversation | query | sources | token | done | error). Lịch sử hội thoại lưu ở máy chủ theo tài khoản.
/*
 * Sự kiện SSE của POST /chat (api/main.py), theo thứ tự:
 *   conversation {id, title}          chỉ khi đã đăng nhập: id cuộc trò chuyện (mới tạo hoặc đang tiếp tục)
 *   query        {query}              câu hỏi sau khi viết lại (chỉ có khi khác câu gốc, tức câu nối tiếp)
 *   sources      {intent, sources[]}  các nguồn [1..n]: title, url, category, section_path, score, snippet
 *   (mặc định)   {token}              từng mẩu câu trả lời (không có dòng "event:")
 *   clarify      {question, thread_id} câu hỏi chưa rõ, agent hỏi lại: gửi thread_id ở tin nhắn sau để agent chạy tiếp
 *   done         {cited, invalid_citations, course_check, first_token_ms, total_ms}
 *   error        {message}            lỗi phía máy chủ; luồng kết thúc
 *
 * Đăng nhập: POST /auth/register hoặc /auth/login trả {token, user}; token (JWT) lưu ở localStorage
 * "khdl-token" và gửi trong header Authorization qua hàm api(). Tải lại trang: boot() gọi /health
 * (biết máy chủ có bắt đăng nhập không), /auth/me (token còn hạn không), rồi /conversations và mở lại
 * cuộc trò chuyện cuối ("khdl-current"). Gặp 401 khi đang có token thì logout() và hiện form đăng nhập.
 * Khi đã đăng nhập, máy chủ tự lấy lịch sử theo conversation_id; chưa đăng nhập (AUTH_REQUIRED=0) thì
 * trình duyệt gửi kèm lịch sử trong trang.
 */
const $ = (id) => document.getElementById(id);
const thread = $('thread'), scroll = $('scroll'), input = $('input'), composer = $('composer');

const ICON = {
  chart: '<svg viewBox="0 0 24 24"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
  brain: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4M5 5l3 3M16 16l3 3M19 5l-3 3M8 16l-3 3"/></svg>',
  gear: '<svg viewBox="0 0 24 24"><path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z"/></svg>',
  db: '<svg viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg>',
  compass: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5z"/></svg>',
  brief: '<svg viewBox="0 0 24 24"><rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 13h18"/></svg>',
  chat: '<svg viewBox="0 0 24 24"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg>',
  calendar: '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18M8 14h3M8 17h6"/></svg>',
  award: '<svg viewBox="0 0 24 24"><circle cx="12" cy="9" r="6"/><path d="M8.5 14L7 22l5-3 5 3-1.5-8"/></svg>',
  trend: '<svg viewBox="0 0 24 24"><path d="M3 17l6-6 4 4 8-8M15 7h6v6"/></svg>',
  bot: '<svg viewBox="0 0 24 24"><rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 4v4M9 13h.01M15 13h.01M9 17h6"/></svg>',
  chevron: '<svg viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg>',
  copy: '<svg viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/></svg>',
  trash: '<svg viewBox="0 0 24 24"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>',
  eye: '<svg viewBox="0 0 24 24"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>',
  eyeOff: '<svg viewBox="0 0 24 24"><path d="M3 3l18 18M10.6 5.1A10.5 10.5 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.2M6.6 6.6A17 17 0 0 0 2 12s3.5 7 10 7a9.7 9.7 0 0 0 5.4-1.6M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>',
  retry: '<svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 0 1 15.5-6.3L21 8M21 3v5h-5M21 12a9 9 0 0 1-15.5 6.3L3 16M3 21v-5h5"/></svg>',
};

const GOALS = [
  { id: 'Data Analyst', icon: 'chart', desc: 'Phân tích, trực quan hoá, báo cáo' },
  { id: 'Data Scientist', icon: 'brain', desc: 'Thống kê và mô hình học máy' },
  { id: 'ML Engineer', icon: 'gear', desc: 'Đưa mô hình vào sản phẩm thật' },
  { id: 'Data Engineer', icon: 'db', desc: 'Xây pipeline và kho dữ liệu' },
  { id: '', icon: 'compass', desc: 'Chưa chọn, mình muốn tìm hiểu' },
];

// 5 chức năng chính trong đề bài
const FEATURES = [
  { icon: 'brief', title: 'Tìm hiểu vị trí công việc', desc: 'Mô tả, kỹ năng, công cụ, lộ trình thăng tiến, mức lương tham khảo.',
    q: (g) => `Giải thích chi tiết vị trí ${g || 'Data Scientist'}: mô tả công việc, kỹ năng cần có, công cụ phổ biến, lộ trình thăng tiến và mức lương tham khảo.`, cat: 'career_role' },
  { icon: 'chat', title: 'Hỏi đáp ngành học', desc: 'Ngành KHDL học gì, khác gì các ngành CNTT khác, ra trường làm gì.',
    q: () => 'Ngành Khoa học Dữ liệu học những gì và ra trường có thể làm những công việc nào?', cat: '' },
  { icon: 'calendar', title: 'Chọn môn theo học kỳ', desc: 'Gợi ý môn từng học kỳ theo niên giám, đúng tiên quyết, đủ tín chỉ.',
    q: (g) => `Gợi ý chọn môn cho từng học kỳ để theo hướng ${g || 'ngành dữ liệu'}, đảm bảo đúng môn tiên quyết và đủ tín chỉ.`, cat: 'curriculum' },
  { icon: 'award', title: 'Yêu cầu đầu ra', desc: 'Chứng chỉ, ngoại ngữ, dự án cá nhân, thực tập trước khi tốt nghiệp.',
    q: (g) => `Trước khi tốt nghiệp mình cần đạt chứng chỉ, chuẩn ngoại ngữ, dự án cá nhân và thực tập gì${g ? ` để làm ${g}` : ''}?`, cat: '' },
  { icon: 'trend', title: 'Thị trường tuyển dụng', desc: 'Xu hướng tuyển dụng, kỹ năng và công nghệ đang được săn đón.',
    q: (g) => `Xu hướng tuyển dụng hiện nay cho ${g || 'ngành dữ liệu'} thế nào, kỹ năng và công nghệ nào đang được săn đón?`, cat: 'market_trend' },
];

const CAT_LABEL = {
  career_role: 'Vị trí công việc', market_trend: 'Thị trường', curriculum: 'Chương trình đào tạo',
  regulation: 'Quy chế', scholarship_tuition: 'Học phí, học bổng', academic_notice: 'Thông báo',
  student_support: 'Hỗ trợ SV', admission: 'Tuyển sinh',
};

// ---------- lưu trữ (localStorage có thể bị chặn, nên bọc try/catch) ----------
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
let state = { goal: store.get('khdl-goal', 'Data Scientist') };
let controller = null;
const save = () => store.set('khdl-goal', state.goal);

// ---------- tài khoản và gọi API ----------
let token = store.get('khdl-token', null);
let me = null;                 // {id, username, display_name}
let authRequired = true;       // máy chủ báo qua /health (AUTH_REQUIRED=0 thì cho dùng không cần đăng nhập)
/**
 * fetch() kèm token đăng nhập và Content-Type JSON khi có body.
 * Gặp 401 trong lúc đang có token (token hết hạn hoặc bị đổi khoá) thì đăng xuất luôn.
 * @param {string} path đường dẫn API, ví dụ '/conversations'
 * @param {RequestInit} [opts] tuỳ chọn fetch; headers truyền vào được gộp sau header mặc định
 * @returns {Promise<Response>}
 * @throws {Error} 'unauthorized' khi phiên đăng nhập hết hạn
 */
async function api(path, opts = {}) {
  const headers = { ...(opts.body ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  const res = await fetch(path, { ...opts, headers: { ...headers, ...(opts.headers || {}) } });
  if (res.status === 401 && token) { logout('Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.'); throw new Error('unauthorized'); }
  return res;
}
async function errorText(res) {
  try {
    const d = await res.json();
    if (typeof d.detail === 'string') return d.detail;
    if (Array.isArray(d.detail)) return 'Thông tin chưa hợp lệ: ' + d.detail.map((e) => e.loc?.slice(-1)[0]).join(', ');
  } catch {}
  return `Máy chủ trả lỗi ${res.status}`;
}

// ---------- hội thoại (lưu ở máy chủ) ----------
let convs = [];                // danh sách {id, title, updated_at}, mới nhất trước
const chats = {};              // id -> {id, title, messages}
let current = null;            // id hội thoại đang mở
let draft = null;              // hội thoại mới, chưa có id (chưa gửi câu đầu tiên)
const currentChat = () => (current ? chats[current] : draft);
/** Tải danh sách cuộc trò chuyện của người dùng vào `convs` rồi vẽ lại thanh bên; chưa đăng nhập thì để rỗng. */
async function loadConvs() {
  if (!token) { convs = []; renderRecent(); return; }
  try { const r = await api('/conversations'); if (r.ok) convs = await r.json(); } catch {}
  renderRecent();
}
/**
 * Mở một cuộc trò chuyện: lấy tin nhắn từ máy chủ ở lần mở đầu (sau đó dùng bản trong `chats`),
 * nhớ id vào localStorage để tải lại trang thì mở lại đúng cuộc này.
 * @param {number} id id cuộc trò chuyện
 */
async function openConv(id) {
  if (!chats[id]) {
    try {
      const r = await api(`/conversations/${id}`);
      if (!r.ok) { toast('Không mở được cuộc trò chuyện'); return; }
      const c = await r.json();
      chats[id] = { id: c.id, title: c.title, messages: c.messages };
    } catch { return; }
  }
  current = id; draft = null; store.set('khdl-current', id); renderThread();
}

// ---------- tiện ích ----------
// Bỏ ký hiệu Markdown (#, |, ---, **) để đoạn trích dễ đọc
const plain = (s) => String(s).replace(/\|?\s*:?-{3,}:?\s*/g, ' ').replace(/[#*>|`_]+/g, ' ').replace(/\s+/g, ' ').trim();
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function renderMd(text) {
  let html = window.marked ? marked.parse(text, { breaks: true }) : `<p>${esc(text).replace(/\n/g, '<br>')}</p>`;
  if (window.DOMPurify) html = DOMPurify.sanitize(html);
  // [1] -> nút trích dẫn (bỏ qua trong thẻ code)
  return html.replace(/\[(\d{1,2})\](?![^<]*<\/code>)/g, '<button class="cite" data-n="$1" type="button">$1</button>');
}
function toast(msg) {
  const t = $('toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('show'), 2200);
}
const nearBottom = () => scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 120;
const toBottom = (force) => { if (force || nearBottom()) scroll.scrollTop = scroll.scrollHeight; };

// ---------- sidebar ----------
function renderGoals() {
  $('goals').innerHTML = GOALS.map((g) => `
    <button class="goal" type="button" data-goal="${g.id}" aria-pressed="${state.goal === g.id}">
      <span class="gi">${ICON[g.icon]}</span>
      <span><b>${g.id || 'Chưa xác định'}</b><small>${g.desc}</small></span>
    </button>`).join('');
  $('goalPill').innerHTML = state.goal ? `Đang tư vấn theo mục tiêu <b>${esc(state.goal)}</b>` : 'Chưa chọn mục tiêu nghề nghiệp';
}
$('goals').onclick = (e) => {
  const b = e.target.closest('.goal'); if (!b) return;
  state.goal = b.dataset.goal; save(); renderGoals(); closeMenu();
};
function renderRecent() {
  if (!token) { $('recent').innerHTML = '<li class="empty">Đăng nhập để lưu lịch sử trò chuyện</li>'; return; }
  $('recent').innerHTML = convs.length
    ? convs.map((c) => `<li><button type="button" data-id="${c.id}" class="${c.id === current ? 'active' : ''}" title="${esc(c.title)}">${esc(c.title)}</button>
        <button type="button" class="del" data-del="${c.id}" aria-label="Xoá cuộc trò chuyện" title="Xoá">${ICON.trash}</button></li>`).join('')
    : '<li class="empty">Chưa có cuộc trò chuyện nào</li>';
}
$('recent').onclick = async (e) => {
  if (controller) return;
  const del = e.target.closest('[data-del]');
  if (del) {
    const id = +del.dataset.del;
    if (!confirm('Xoá cuộc trò chuyện này? Không thể khôi phục.')) return;
    try {
      const r = await api(`/conversations/${id}`, { method: 'DELETE' });
      if (!r.ok) { toast(await errorText(r)); return; }
    } catch { return; }
    convs = convs.filter((c) => c.id !== id); delete chats[id];
    if (current === id) { current = null; draft = null; renderThread(); } else renderRecent();
    toast('Đã xoá cuộc trò chuyện');
    return;
  }
  const b = e.target.closest('button[data-id]'); if (!b) return;
  await openConv(+b.dataset.id); closeMenu();
};
const openMenu = () => { $('sidebar').classList.add('open'); $('scrim').classList.add('show'); };
const closeMenu = () => { $('sidebar').classList.remove('open'); $('scrim').classList.remove('show'); };
$('menuBtn').onclick = openMenu; $('scrim').onclick = closeMenu;

// ---------- màn chào ----------
function renderWelcome() {
  $('features').innerHTML = FEATURES.map((f, i) => `
    <button class="feature" type="button" data-i="${i}">
      <span class="fi">${ICON[f.icon]}</span><b>${f.title}</b><span>${f.desc}</span>
    </button>`).join('');
}
$('features').onclick = (e) => {
  const b = e.target.closest('.feature'); if (!b) return;
  const f = FEATURES[b.dataset.i];
  if (f.cat !== undefined) $('category').value = f.cat;
  send(f.q(state.goal));
};

// ---------- tin nhắn ----------
function userEl(text) {
  const el = document.createElement('div');
  el.className = 'msg user';
  el.innerHTML = `<div class="bubble">${esc(text)}</div>`;
  return el;
}
function botEl() {
  const el = document.createElement('div');
  el.className = 'msg bot';
  el.innerHTML = `<div class="avatar">${ICON.bot}</div>
    <div class="body"><div class="card"><div class="md"><span class="status">Đang tìm tài liệu liên quan…</span><div class="typing"><i></i><i></i><i></i></div></div></div>
    <div class="src-slot"></div><div class="actions" hidden></div></div>`;
  return el;
}
function sourcesHtml(sources, cited) {
  if (!sources?.length) return '';
  const used = new Set(cited || []);
  return `<details class="sources" open><summary>${ICON.chevron}${sources.length} tài liệu tham khảo</summary><div class="src-list">
    ${sources.map((s, i) => `<div class="src${cited && !used.has(i + 1) ? ' unused' : ''}" data-n="${i + 1}"><span class="n">${i + 1}</span><div>
      <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a>
      <div class="meta"><span class="tag">${esc(CAT_LABEL[s.category] || s.category)}</span>${used.has(i + 1) ? '<span class="tag used">Đã trích dẫn</span>' : ''}${s.section_path?.length ? `<span>${esc(s.section_path.slice(-2).join(' › '))}</span>` : ''}</div>
      <p>${esc(plain(s.snippet || ''))}</p></div></div>`).join('')}</div></details>`;
}
/**
 * Vẽ (lại) một câu trả lời: nội dung Markdown hoặc hộp lỗi, thẻ nguồn, cảnh báo môn học, thời gian, nút phản hồi.
 * Gọi nhiều lần trong lúc stream (qua requestAnimationFrame) và một lần cuối khi xong.
 * @param {HTMLElement} el phần tử do botEl() tạo
 * @param {{content: string, sources?: object[], cited?: number[], courseCheck?: object, timing?: object,
 *          error?: string, stopped?: boolean, query?: string, feedback?: number}} msg tin nhắn assistant
 * @param {boolean} streaming true khi còn đang nhận token: hiện con trỏ, chưa đánh dấu nguồn được trích
 */
function fillBot(el, msg, streaming) {
  const md = el.querySelector('.md');
  if (msg.error) md.innerHTML = `<div class="error-box">${esc(msg.error)}</div>`;
  else if (msg.content) { md.innerHTML = renderMd(msg.content); md.classList.toggle('cursor', !!streaming); }
  el.querySelector('.src-slot').innerHTML = sourcesHtml(msg.sources, streaming ? null : msg.cited);
  const cc = msg.courseCheck;
  if (!streaming && cc && (cc.unknown.length || cc.semester_mismatch.length || cc.name_mismatch?.length)) {
    const parts = [];
    if (cc.unknown.length) parts.push(`mã môn không có trong niên giám: <b>${cc.unknown.map(esc).join(', ')}</b>`);
    cc.semester_mismatch.forEach((m) => parts.push(`${esc(m.name)} (${m.code}) ghi học kỳ ${m.said}, niên giám là học kỳ ${m.actual}`));
    (cc.name_mismatch || []).forEach((m) => parts.push(`mã ${m.code} là môn ${esc(m.actual_name)}, không phải ${esc(m.said_name)}`));
    md.insertAdjacentHTML('beforeend', `<div class="warn-box">⚠ Cần kiểm tra lại: ${parts.join('; ')}.</div>`);
  }
  if (msg.query) md.insertAdjacentHTML('afterbegin', `<div class="rewritten">Đã hiểu câu hỏi là: “${esc(msg.query)}”</div>`);
  const act = el.querySelector('.actions');
  if (!streaming && !msg.error) {
    act.hidden = false;
    act.innerHTML = `<button type="button" data-act="copy">${ICON.copy}Sao chép</button>
      <button type="button" data-act="retry">${ICON.retry}Hỏi lại</button>
      ${msg.feedback ? `<span class="fb-done">${msg.feedback > 0 ? '👍 Cảm ơn bạn!' : '👎 Đã ghi nhận'}</span>`
        : `<button type="button" data-act="up" title="Câu trả lời hữu ích">👍</button><button type="button" data-act="down" title="Câu trả lời chưa tốt">👎</button>`}
      ${msg.timing ? `<span class="timing">Token đầu ${msg.timing.first_token_ms} ms · tổng ${(msg.timing.total_ms / 1000).toFixed(1)} s</span>` : ''}
      ${msg.stopped ? '<span class="timing">Đã dừng</span>' : ''}`;
  }
}
thread.onclick = (e) => {
  const cite = e.target.closest('.cite');
  if (cite) {
    const box = cite.closest('.body').querySelector(`.src[data-n="${cite.dataset.n}"]`);
    if (box) {
      box.closest('details').open = true;
      box.scrollIntoView({ behavior: 'smooth', block: 'center' });
      box.classList.add('flash'); setTimeout(() => box.classList.remove('flash'), 1400);
    }
    return;
  }
  const act = e.target.closest('[data-act]'); if (!act) return;
  const idx = [...thread.querySelectorAll('.msg')].indexOf(act.closest('.msg'));
  const chat = currentChat(); const m = chat?.messages[idx]; if (!m) return;
  if (act.dataset.act === 'up') sendFeedback(m, chat.messages[idx - 1]?.content, 1, null, act.closest('.msg'));
  if (act.dataset.act === 'down') askReason(m, chat.messages[idx - 1]?.content, act.closest('.msg'));
  if (act.dataset.act === 'copy') navigator.clipboard?.writeText(m.content).then(() => toast('Đã sao chép câu trả lời'));
  if (act.dataset.act === 'retry' && !controller) {  // hỏi lại = gửi lại câu hỏi đó thành một lượt mới
    const q = chat.messages[idx - 1]?.content; if (q) send(q);
  }
};

// ---------- phản hồi 👍/👎 (dùng khi thử nghiệm với sinh viên) ----------
const REASONS = ['Sai thông tin', 'Thiếu ý', 'Không đúng câu hỏi', 'Khó hiểu', 'Quá dài', 'Nguồn không liên quan'];
const testerId = (() => {  // mã người thử: ?tester=SV01; bỏ trống thì máy chủ ghi tên đăng nhập
  const t = new URLSearchParams(location.search).get('tester');
  if (t) store.set('khdl-tester', t);
  return t || store.get('khdl-tester', null);
})();
async function sendFeedback(m, question, rating, extra, el) {
  m.feedback = rating;
  try {
    await api('/feedback', { method: 'POST', body: JSON.stringify({
      rating, question: question || '', answer: m.content, reason: extra?.reason || null, comment: extra?.comment || null,
      goal: state.goal || null, category: $('category').value || null, tester: testerId,
      sources: (m.sources || []).map((s) => s.url), timing: m.timing || null }) });
    toast(rating > 0 ? 'Cảm ơn bạn đã đánh giá!' : 'Đã ghi nhận góp ý');
  } catch { toast('Không gửi được đánh giá'); }
  fillBot(el, m, false);
}
function askReason(m, question, el) {
  const act = el.querySelector('.actions');
  if (act.querySelector('.fb-form')) return;
  act.insertAdjacentHTML('afterend', `<div class="fb-form"><span>Chưa tốt ở điểm nào?</span>
    <div class="fb-reasons">${REASONS.map((r) => `<button type="button" data-r="${r}">${r}</button>`).join('')}</div>
    <input type="text" maxlength="500" placeholder="Góp ý thêm (không bắt buộc)"><button type="button" class="fb-send">Gửi</button></div>`);
  const form = el.querySelector('.fb-form');
  let reason = null;
  form.onclick = (e) => {
    const b = e.target.closest('[data-r]');
    if (b) { reason = b.dataset.r; form.querySelectorAll('[data-r]').forEach((x) => x.classList.toggle('on', x === b)); }
    if (e.target.closest('.fb-send')) { const comment = form.querySelector('input').value.trim(); form.remove(); sendFeedback(m, question, -1, { reason, comment }, el); }
  };
}

function renderThread() {
  const chat = currentChat();
  $('heroKicker').textContent = me ? `Xin chào ${me.display_name}!` : 'Xin chào tân sinh viên!';
  thread.querySelectorAll('.msg').forEach((n) => n.remove());
  $('welcome').hidden = !!chat?.messages.length;
  for (const m of chat?.messages || []) {
    if (m.role === 'user') thread.append(userEl(m.content));
    else { const el = botEl(); thread.append(el); fillBot(el, m, false); }
  }
  renderRecent();
  if (chat?.messages.length) toBottom(true); else scroll.scrollTop = 0;
}

// ---------- gửi câu hỏi và đọc stream ----------
/**
 * Gửi câu hỏi tới POST /chat và đọc luồng SSE (xem khối chú thích đầu file).
 * Bỏ qua nếu câu rỗng hoặc đang có câu trả lời chạy dở; chưa đăng nhập mà máy chủ bắt đăng nhập thì mở form.
 * Bấm nút gửi lần nữa trong lúc chạy sẽ huỷ qua `controller` (AbortController); phần đã nhận vẫn giữ.
 * @param {string} text câu hỏi người dùng gõ
 */
async function send(text) {
  text = text.trim(); if (!text || controller) return;
  if (!token && authRequired) { showAuth('login'); return; }
  let chat = currentChat();
  if (!chat) { chat = draft = { id: null, title: text.slice(0, 60), messages: [] }; current = null; }
  // đã đăng nhập: máy chủ tự lấy lịch sử theo conversation_id; chưa đăng nhập: gửi kèm lịch sử trong trang
  const history = token ? [] : chat.messages.filter((m) => m.content && !m.error).map(({ role, content }) => ({ role, content }));
  chat.messages.push({ role: 'user', content: text });
  const msg = { role: 'assistant', content: '', sources: [] };
  chat.messages.push(msg);
  $('welcome').hidden = true;
  thread.append(userEl(text));
  const el = botEl(); thread.append(el); toBottom(true);
  input.value = ''; autosize();

  controller = new AbortController(); composer.classList.add('busy');
  const threadId = chat.threadId; chat.threadId = null; // chỉ dùng cho đúng tin nhắn ngay sau câu hỏi lại
  let raf = 0;
  const paint = () => { raf = 0; fillBot(el, msg, true); toBottom(); };
  try {
    const res = await api('/chat', {
      method: 'POST', signal: controller.signal,
      body: JSON.stringify({ question: text, filters: $('category').value ? { category: $('category').value } : null, goal: state.goal || null,
                             history, conversation_id: chat.id, thread_id: threadId || null }),
    });
    if (!res.ok) { msg.error = await errorText(res); return; }
    const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
    let buf = '';
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += value;
      let i;
      while ((i = buf.indexOf('\n\n')) >= 0) {         // mỗi sự kiện SSE kết thúc bằng một dòng trống
        const raw = buf.slice(0, i); buf = buf.slice(i + 2);
        const event = (raw.match(/^event: (.*)$/m) || [])[1];
        const data = JSON.parse((raw.match(/^data: (.*)$/m) || [, '{}'])[1]);
        if (event === 'conversation') {
          if (!chat.id) { chat.id = data.id; chat.title = data.title; chats[data.id] = chat; draft = null; }
          current = chat.id; store.set('khdl-current', chat.id);
          convs = [{ id: chat.id, title: chat.title, updated_at: Date.now() / 1000 }, ...convs.filter((c) => c.id !== chat.id)];
          renderRecent();
        } else if (event === 'query') {
          msg.query = data.query;
          el.querySelector('.status').textContent = `Đang tìm: “${data.query}”`;
        } else if (event === 'sources') {
          msg.sources = data.sources;
          el.querySelector('.status').textContent = `Đã tìm thấy ${data.sources.length} tài liệu, đang soạn câu trả lời…`;
          el.querySelector('.src-slot').innerHTML = sourcesHtml(msg.sources);
        } else if (event === 'clarify') { chat.threadId = data.thread_id; // agent đang chờ câu trả lời cho câu hỏi lại
        } else if (event === 'done') { msg.timing = data; msg.cited = data.cited; msg.courseCheck = data.course_check; }
        else if (event === 'error') msg.error = `Có lỗi ở máy chủ: ${data.message}`;
        else if (data.token) { msg.content += data.token; if (!raf) raf = requestAnimationFrame(paint); }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') msg.stopped = true;
    else if (err.message === 'unauthorized') msg.error = 'Bạn cần đăng nhập lại.';
    else msg.error = 'Không kết nối được máy chủ. Kiểm tra uvicorn và Ollama đã chạy chưa.';
  } finally {
    cancelAnimationFrame(raf);
    if (!msg.content && !msg.error) msg.error = msg.stopped ? 'Đã dừng trước khi có câu trả lời.' : 'Không nhận được câu trả lời.';
    controller = null; composer.classList.remove('busy');
    fillBot(el, msg, false); toBottom();
  }
}

composer.onsubmit = (e) => { e.preventDefault(); controller ? controller.abort() : send(input.value); };
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); composer.requestSubmit(); }
});
function autosize() { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 180) + 'px'; }
input.addEventListener('input', autosize);
$('newChat').onclick = () => {
  if (controller) return;
  current = null; draft = null; store.set('khdl-current', null); renderThread(); input.focus(); closeMenu();
};

// ---------- màn đăng nhập / đăng ký ----------
const authBox = $('auth'), authForm = $('authForm');
let authTab = 'login';
function setAuthTab(tab) {
  authTab = tab;
  authBox.classList.toggle('register', tab === 'register');
  authBox.querySelectorAll('[role="tab"]').forEach((b) => b.setAttribute('aria-selected', b.dataset.tab === tab));
  $('authTitle').textContent = $('authSubmit').textContent = tab === 'login' ? 'Đăng nhập' : 'Tạo tài khoản';
  $('authSwitch').innerHTML = tab === 'login'
    ? 'Chưa có tài khoản? <button type="button" data-tab="register">Đăng ký ngay</button>'
    : 'Đã có tài khoản? <button type="button" data-tab="login">Đăng nhập</button>';
  authForm.password.autocomplete = tab === 'login' ? 'current-password' : 'new-password';
  $('authError').hidden = true;
}
function showAuth(tab = 'login', message) {
  setAuthTab(tab); authBox.hidden = false;
  if (message) { $('authError').textContent = message; $('authError').hidden = false; }
  setTimeout(() => (authForm.username.value ? authForm.password : authForm.username).focus(), 30);
}
authBox.addEventListener('click', (e) => { const t = e.target.closest('[data-tab]'); if (t) setAuthTab(t.dataset.tab); });
$('pwToggle').onclick = () => {
  const show = authForm.password.type === 'password';
  authForm.password.type = authForm.password2.type = show ? 'text' : 'password';
  $('pwToggle').setAttribute('aria-pressed', show); $('pwToggle').innerHTML = show ? ICON.eyeOff : ICON.eye;
};
function checkAuthForm(f) {
  if (!/^[A-Za-z0-9_.]{3,32}$/.test(f.username)) return 'Tên đăng nhập 3–32 ký tự, chỉ gồm chữ không dấu, số, dấu _ hoặc .';
  if (!f.password) return 'Vui lòng nhập mật khẩu.';
  if (authTab === 'login') return null;
  if (f.password !== f.password2) return 'Hai lần nhập mật khẩu chưa khớp.';
  return null;
}
authForm.onsubmit = async (e) => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(authForm));
  f.username = (f.username || '').trim();
  const bad = checkAuthForm(f);
  const err = $('authError');
  if (bad) { err.textContent = bad; err.hidden = false; return; }
  $('authSubmit').disabled = true; err.hidden = true;
  try {
    const body = authTab === 'login' ? { username: f.username, password: f.password }
      : { username: f.username, password: f.password, display_name: (f.display_name || '').trim() || null };
    const res = await fetch(`/auth/${authTab}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!res.ok) { err.textContent = await errorText(res); err.hidden = false; return; }
    const data = await res.json();
    token = data.token; me = data.user; store.set('khdl-token', token);
    authForm.reset(); authBox.hidden = true;
    renderUser(); await loadConvs(); renderThread();
    toast(authTab === 'login' ? `Chào mừng ${me.display_name} quay lại!` : 'Tạo tài khoản thành công!');
    input.focus();
  } catch { err.textContent = 'Không kết nối được máy chủ.'; err.hidden = false; }
  finally { $('authSubmit').disabled = false; }
};
function renderUser() {
  $('userMenu').hidden = !me && !(!authRequired);
  if (me) {
    $('userName').textContent = me.display_name; $('userInitial').textContent = me.display_name.trim()[0]?.toUpperCase() || '?';
    $('popName').textContent = me.display_name; $('popUser').textContent = '@' + me.username;
    $('logoutBtn').querySelector('span').textContent = 'Đăng xuất';
  } else {  // AUTH_REQUIRED=0: cho dùng thử, nút để đăng nhập
    $('userName').textContent = 'Đăng nhập'; $('userInitial').textContent = '?';
    $('popName').textContent = 'Chưa đăng nhập'; $('popUser').textContent = 'Lịch sử sẽ không được lưu';
    $('logoutBtn').querySelector('span').textContent = 'Đăng nhập';
  }
}
$('userChip').onclick = (e) => {
  e.stopPropagation();
  const pop = $('userPop'); pop.hidden = !pop.hidden; $('userChip').setAttribute('aria-expanded', !pop.hidden);
};
document.addEventListener('click', (e) => { if (!e.target.closest('#userMenu')) { $('userPop').hidden = true; $('userChip').setAttribute('aria-expanded', 'false'); } });
$('logoutBtn').onclick = () => { $('userPop').hidden = true; me ? logout() : showAuth('login'); };
/**
 * Đăng xuất: huỷ câu trả lời đang chạy, xoá token và mọi hội thoại đang giữ trong trang.
 * @param {string} [message] lý do hiện trên form đăng nhập (ví dụ phiên hết hạn)
 */
function logout(message) {
  controller?.abort();
  token = null; me = null; store.set('khdl-token', null); store.set('khdl-current', null);
  convs = []; for (const k in chats) delete chats[k]; current = null; draft = null;
  renderUser(); renderThread();
  if (authRequired || message) showAuth('login', message);
}

// ---------- khởi động ----------
/**
 * Khởi động trang: đọc /health (chế độ chạy, có bắt đăng nhập không), kiểm tra token bằng /auth/me,
 * rồi tải danh sách hội thoại và mở lại cuộc trò chuyện cuối; chưa đăng nhập thì hiện form đăng nhập.
 */
async function boot() {
  renderGoals(); renderWelcome();
  try {
    const h = await (await fetch('/health')).json();
    authRequired = h.auth !== false;
    const m = $('mode');
    m.textContent = `Tìm kiếm: ${h.retriever === 'qdrant' ? 'Qdrant' : 'dữ liệu mẫu'} · LLM: ${h.llm === 'ollama' ? 'Ollama' : 'giả lập'}${h.rerank ? ' · Rerank' : ''}`;
    m.classList.add('ok');
  } catch { $('mode').textContent = 'Mất kết nối máy chủ'; $('mode').classList.add('down'); }
  if (token) {
    try {
      const r = await api('/auth/me');
      if (r.ok) me = await r.json();
    } catch {}
  }
  renderUser();
  if (me) {
    await loadConvs();
    const last = store.get('khdl-current', null);
    if (last && convs.some((c) => c.id === last)) await openConv(last); else renderThread();
  } else {
    renderThread();
    if (authRequired) showAuth('login');
  }
}
boot();

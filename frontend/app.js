// Demo mode is the default. Add ?api=http://localhost:8000 to use a FastAPI SSE endpoint later.
const apiBase = new URLSearchParams(location.search).get('api');
const $ = (selector) => document.querySelector(selector);
const state = { controller: null, signup: false };

const authScreen = $('#auth-screen');
const authForm = $('#auth-form');
const authMessage = $('.auth-demo');
const nameField = $('#name-field');
const nameInput = $('#auth-name');
const emailInput = $('#auth-email');
const passwordInput = $('#auth-password');
const messages = $('#messages');
const question = $('#question');
const chatScroll = $('#chat-scroll');

function setAuthMode(signup) {
  state.signup = signup;
  authMessage.textContent = apiBase
    ? 'Đăng nhập thật qua FastAPI. Câu trả lời chat hiện vẫn là mô phỏng.'
    : 'Đây là bản thử giao diện. Tài khoản và mật khẩu chưa được xác thực.';
  nameField.hidden = !signup;
  nameInput.required = signup;
  passwordInput.autocomplete = signup ? 'new-password' : 'current-password';
  $('#auth-title').textContent = signup ? (apiBase ? 'Tạo tài khoản' : 'Tạo tài khoản bản thử') : 'Chào mừng trở lại';
  $('#auth-description').textContent = signup ? 'Bắt đầu hành trình khám phá dữ liệu.' : 'Đăng nhập để bắt đầu khám phá con đường của bạn.';
  $('#auth-submit').textContent = signup ? (apiBase ? 'Đăng ký' : 'Đăng ký bản thử') : (apiBase ? 'Đăng nhập' : 'Đăng nhập bản thử');
  $('#auth-switch-label').textContent = signup ? 'Đã có tài khoản?' : 'Chưa có tài khoản?';
  $('#auth-switch-button').textContent = signup ? 'Đăng nhập' : 'Đăng ký';
}

async function authRequest(path, options = {}) {
  const response = await fetch(`${apiBase.replace(/\/$/, '')}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
  return data;
}

function showUser(name) {
  $('#profile-name').textContent = name;
  $('#avatar').textContent = name.trim().charAt(0).toLocaleUpperCase('vi') || 'B';
  authScreen.hidden = true;
  question.focus();
}

$('#auth-switch-button').addEventListener('click', () => setAuthMode(!state.signup));
authForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!authForm.reportValidity()) return;
  const email = emailInput.value.trim();
  const password = passwordInput.value;
  const submit = $('#auth-submit');
  submit.disabled = true;
  try {
    if (apiBase) {
      if (state.signup) {
        await authRequest('/auth/register', {
          method: 'POST',
          body: JSON.stringify({ name: nameInput.value.trim(), email, password }),
        });
      }
      const user = await authRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      showUser(user.name);
    } else {
      // Demo mode keeps only a display name for this tab; it never stores the password.
      const name = (state.signup ? nameInput.value.trim() : '') || email.split('@')[0];
      sessionStorage.setItem('datapath-demo-name', name);
      showUser(name);
    }
    passwordInput.value = '';
  } catch (error) {
    authMessage.textContent = `Không thể đăng nhập/đăng ký: ${error.message}`;
  } finally {
    submit.disabled = false;
  }
});
$('#profile').addEventListener('click', async () => {
  stopStreaming();
  if (apiBase) {
    try {
      await authRequest('/auth/logout', { method: 'POST' });
    } catch (error) {
      authMessage.textContent = `Không thể đăng xuất: ${error.message}`;
      return;
    }
  }
  sessionStorage.removeItem('datapath-demo-name');
  authScreen.hidden = false;
  authForm.reset();
  setAuthMode(false);
});
const savedName = sessionStorage.getItem('datapath-demo-name');
if (apiBase) {
  $('.mode-badge').textContent = 'API · STREAMING DEMO';
  setAuthMode(false);
  authRequest('/auth/me').then((user) => showUser(user.name)).catch((error) => {
    if (error.message !== 'Please log in.') {
      authMessage.textContent = `Không thể kết nối API: ${error.message}`;
    }
  });
} else if (savedName) showUser(savedName);

function scrollToBottom() { chatScroll.scrollTop = chatScroll.scrollHeight; }

function addMessage(role, text = '') {
  $('#welcome').hidden = true;
  const item = document.createElement('article');
  item.className = `message ${role}`;
  const avatar = document.createElement('span');
  avatar.className = 'message-avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.textContent = role === 'user' ? $('#avatar').textContent : '✳';
  const content = document.createElement('div');
  content.className = 'message-content';
  const label = document.createElement('div');
  label.className = 'message-name';
  label.textContent = role === 'user' ? 'Bạn' : 'DataPath';
  const body = document.createElement('div');
  body.className = 'message-body';
  body.textContent = text;
  content.append(label, body);
  item.append(avatar, content);
  messages.append(item);
  scrollToBottom();
  return { item, content, body };
}

const sampleAnswers = [
  {
    match: /analyst|kỹ năng|ky nang/i,
    text: 'Để bắt đầu với Data Analyst, bạn có thể tập trung vào bốn nhóm kỹ năng: SQL để truy vấn dữ liệu, bảng tính để xử lý nhanh, Python để phân tích và trực quan hóa để trình bày kết quả.\n\nMột lộ trình thực hành là chọn một bộ dữ liệu nhỏ, đặt câu hỏi cụ thể, làm sạch dữ liệu, phân tích rồi viết báo cáo ngắn. Sau đó hãy xây dựng portfolio với 2–3 dự án có giải thích cách bạn đi từ dữ liệu tới kết luận.\n\nĐây là ví dụ mô phỏng. Khi nối hệ thống RAG, câu trả lời sẽ dựa trên tài liệu được truy xuất.',
  },
  {
    match: /nghề|nghe|việc làm|co hoi|cơ hội/i,
    text: 'Sinh viên Khoa học dữ liệu có thể tìm hiểu các vị trí như Data Analyst, Business Intelligence Analyst, Data Engineer hoặc Machine Learning Engineer. Mỗi vị trí có trọng tâm khác nhau: phân tích và báo cáo, xây dựng hệ thống dữ liệu, hoặc phát triển mô hình học máy.\n\nBạn nên chọn một hướng để thực hành sâu, đồng thời rèn kỹ năng giao tiếp và giải thích kết quả cho người không chuyên.\n\nĐây là câu trả lời mô phỏng; thông tin tuyển dụng thực tế cần đối chiếu với nguồn mới nhất.',
  },
  {
    match: /iuh|học|chuong trinh|chương trình|ngành/i,
    text: 'Ngành Khoa học dữ liệu thường kết hợp nền tảng toán, thống kê, lập trình và các môn xử lý dữ liệu, học máy. Để biết chính xác chương trình của IUH, cần đối chiếu đề cương và thông báo chính thức của trường.\n\nBạn có thể hỏi tiếp về một môn học, kỹ năng cần chuẩn bị hoặc lộ trình nghề nghiệp muốn theo đuổi.\n\nHiện đây là bản thử giao diện, chưa truy xuất tài liệu IUH.',
  },
];

function demoAnswer(prompt) {
  return sampleAnswers.find((answer) => answer.match.test(prompt))?.text || 'Mình có thể giúp bạn tìm hiểu về ngành Khoa học dữ liệu, kỹ năng phân tích dữ liệu và các hướng nghề nghiệp liên quan.\n\nBạn hãy đặt câu hỏi cụ thể hơn để nhận một câu trả lời hữu ích hơn. Đây là phản hồi mô phỏng; dữ liệu thật sẽ được kết nối sau.';
}

function pause(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(new DOMException('Stopped', 'AbortError'));
    const timer = setTimeout(() => { signal.removeEventListener('abort', onAbort); resolve(); }, ms);
    function onAbort() { clearTimeout(timer); reject(new DOMException('Stopped', 'AbortError')); }
    signal.addEventListener('abort', onAbort, { once: true });
  });
}

async function* demoStream(prompt, signal) {
  await pause(420, signal);
  const text = demoAnswer(prompt);
  // Simulate arbitrary text chunks; transport chunks are not guaranteed to equal model tokens.
  for (const chunk of text.match(/\S+\s*|\n/g) || []) {
    await pause(28 + Math.random() * 52, signal);
    yield { type: 'text', content: chunk };
  }
  yield { type: 'done' };
}

async function* apiStream(prompt, signal) {
  const response = await fetch(`${apiBase.replace(/\/$/, '')}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    credentials: 'include',
    body: JSON.stringify({ message: prompt }),
    signal,
  });
  if (response.status === 401) {
    authScreen.hidden = false;
    throw new Error('Phiên đăng nhập đã hết. Vui lòng đăng nhập lại.');
  }
  if (!response.ok) throw new Error(`API trả về HTTP ${response.status}`);
  if (!response.body) throw new Error('Trình duyệt không hỗ trợ đọc stream.');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done }).replace(/\r\n/g, '\n');
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = block.split('\n').filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trimStart()).join('\n');
        if (data) yield JSON.parse(data);
      }
      if (done) break;
    }
  } finally { reader.releaseLock(); }
}

function setStreaming(active) {
  $('#send-button').hidden = active;
  $('#stop-button').hidden = !active;
  question.disabled = active;
}

function stopStreaming() { state.controller?.abort(); }
$('#stop-button').addEventListener('click', stopStreaming);

async function submitQuestion(rawQuestion) {
  const prompt = rawQuestion.trim();
  if (!prompt || state.controller) return;
  question.value = '';
  question.style.height = '';
  addMessage('user', prompt);
  const answer = addMessage('assistant');
  answer.item.classList.add('streaming');
  const status = document.createElement('div');
  status.className = 'message-status';
  status.textContent = apiBase ? 'Đang kết nối...' : 'Đang tạo câu trả lời mô phỏng...';
  answer.content.append(status);
  const controller = new AbortController();
  state.controller = controller;
  setStreaming(true);
  try {
    for await (const event of apiBase ? apiStream(prompt, controller.signal) : demoStream(prompt, controller.signal)) {
      if (event.type === 'text') {
        answer.body.textContent += event.content || '';
        status.textContent = apiBase ? 'Đang trả lời...' : 'Đang hiển thị bản thử...';
      } else if (event.type === 'sources' && Array.isArray(event.sources)) {
        const list = document.createElement('div');
        list.className = 'source-list';
        for (const source of event.sources) {
          if (!/^https?:\/\//.test(source.url || '')) continue;
          const link = document.createElement('a');
          link.href = source.url;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          link.textContent = source.title || source.url;
          list.append(link);
        }
        answer.content.append(list);
      } else if (event.type === 'error') {
        throw new Error(event.message || 'Có lỗi khi tạo câu trả lời.');
      } else if (event.type === 'done') {
        status.textContent = apiBase ? 'Đã hoàn thành' : 'Đã hoàn thành · bản thử';
      }
      scrollToBottom();
    }
  } catch (error) {
    status.textContent = error.name === 'AbortError' ? 'Đã dừng' : `Lỗi: ${error.message}`;
  } finally {
    answer.item.classList.remove('streaming');
    state.controller = null;
    setStreaming(false);
    question.focus();
    scrollToBottom();
  }
}

$('#chat-form').addEventListener('submit', (event) => { event.preventDefault(); submitQuestion(question.value); });
question.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    submitQuestion(question.value);
  }
});
question.addEventListener('input', () => { question.style.height = 'auto'; question.style.height = `${Math.min(question.scrollHeight, 150)}px`; });
document.querySelectorAll('[data-prompt]').forEach((button) => button.addEventListener('click', () => {
  if (!authScreen.hidden) return;
  $('#sidebar').classList.remove('open');
  $('#menu-button').setAttribute('aria-expanded', 'false');
  submitQuestion(button.dataset.prompt);
}));
$('#new-chat').addEventListener('click', () => {
  stopStreaming();
  messages.replaceChildren();
  $('#welcome').hidden = false;
  $('#sidebar').classList.remove('open');
  $('#menu-button').setAttribute('aria-expanded', 'false');
  question.focus();
});
$('#menu-button').addEventListener('click', () => {
  const open = $('#sidebar').classList.toggle('open');
  $('#menu-button').setAttribute('aria-expanded', String(open));
});

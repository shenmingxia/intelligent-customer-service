const messages = document.querySelector('#messages');
const form = document.querySelector('#chatForm');
const input = document.querySelector('#messageInput');
const clearChat = document.querySelector('#clearChat');
const quickActions = document.querySelectorAll('[data-message]');
let sessionId = localStorage.getItem('support_session_id');

const welcomeText = '您好，我是智能客服助手。您可以问我退款、运费、发票、客服时间等问题。';

function appendMessage(role, text, meta = '') {
  const item = document.createElement('article');
  item.className = `message ${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  item.appendChild(bubble);

  if (meta) {
    const info = document.createElement('small');
    info.textContent = meta;
    item.appendChild(info);
  }

  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
  return item;
}

function appendTyping() {
  const item = document.createElement('article');
  item.className = 'message bot typing';
  item.innerHTML = '<div class="bubble"><span></span><span></span><span></span></div>';
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
  return item;
}

async function sendMessage(text) {
  const message = text.trim();
  if (!message) return;

  appendMessage('user', message);
  input.value = '';
  input.focus();

  const typing = appendTyping();
  form.querySelector('button').disabled = true;

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: 'web-user', message, session_id: sessionId }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    sessionId = data.session_id;
    localStorage.setItem('support_session_id', sessionId);
    typing.remove();
    const meta = `意图：${data.intent} · 置信度：${Math.round(data.confidence * 100)}%${data.need_human ? ' · 已转人工' : ''}`;
    appendMessage('bot', data.reply, meta);
  } catch (error) {
    typing.remove();
    appendMessage('bot', '连接客服服务失败，请确认后端服务正在运行。', error.message);
  } finally {
    form.querySelector('button').disabled = false;
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  sendMessage(input.value);
});

quickActions.forEach((button) => {
  button.addEventListener('click', () => sendMessage(button.dataset.message));
});

clearChat.addEventListener('click', () => {
  messages.innerHTML = '';
  sessionId = null;
  localStorage.removeItem('support_session_id');
  appendMessage('bot', welcomeText, '系统欢迎语');
});

appendMessage('bot', welcomeText, '系统欢迎语');

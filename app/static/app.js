const messages = document.querySelector('#messages');
const form = document.querySelector('#chatForm');
const input = document.querySelector('#messageInput');
const clearChat = document.querySelector('#clearChat');
const quickActions = document.querySelectorAll('[data-message]');
let sessionId = localStorage.getItem('support_session_id');

const welcomeText = '您好，我是智能客服助手。您可以问我退款、运费、发票、客服时间等问题。';
const feedbackReasons = ['答非所问', '没解决我的问题', '太啰嗦'];

function appendMessage(role, text, meta = '', feedbackData = null) {
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

  if (role === 'bot' && feedbackData) {
    item.appendChild(createFeedbackControls(feedbackData));
  }

  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
  return item;
}

function createFeedbackControls(feedbackData) {
  const panel = document.createElement('div');
  panel.className = 'feedback';

  const useful = document.createElement('button');
  useful.type = 'button';
  useful.textContent = '👍有用';

  const notUseful = document.createElement('button');
  notUseful.type = 'button';
  notUseful.textContent = '👎没用';

  const reasons = document.createElement('div');
  reasons.className = 'feedback-reasons';
  reasons.hidden = true;

  feedbackReasons.forEach((reason) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = reason;
    button.addEventListener('click', () => submitFeedback(panel, feedbackData, 'not_useful', reason));
    reasons.appendChild(button);
  });

  useful.addEventListener('click', () => submitFeedback(panel, feedbackData, 'useful'));
  notUseful.addEventListener('click', () => {
    reasons.hidden = !reasons.hidden;
  });

  panel.append(useful, notUseful, reasons);
  return panel;
}

async function submitFeedback(panel, feedbackData, rating, reason = null) {
  if (panel.dataset.submitted === 'true') return;

  const buttons = panel.querySelectorAll('button');
  buttons.forEach((button) => {
    button.disabled = true;
  });

  try {
    const response = await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: 'web-user',
        session_id: sessionId,
        user_message: feedbackData.userMessage,
        assistant_reply: feedbackData.assistantReply,
        intent: feedbackData.intent,
        rating,
        reason,
      }),
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    panel.dataset.submitted = 'true';
    panel.textContent = rating === 'useful' ? '感谢反馈：有用' : `感谢反馈：${reason}`;
  } catch (error) {
    buttons.forEach((button) => {
      button.disabled = false;
    });
    appendMessage('bot', '反馈提交失败，请稍后再试。', error.message);
  }
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
    appendMessage('bot', data.reply, meta, {
      userMessage: message,
      assistantReply: data.reply,
      intent: data.intent,
    });
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

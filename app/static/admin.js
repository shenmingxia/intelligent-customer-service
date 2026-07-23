const tokenInput = document.querySelector('#adminToken');
const reloadButton = document.querySelector('#reloadData');
const statusText = document.querySelector('#statusText');
const faqForm = document.querySelector('#faqForm');
const settingsForm = document.querySelector('#settingsForm');
const faqList = document.querySelector('#faqList');
const feedbackTopList = document.querySelector('#feedbackTopList');

const fields = {
  intent: document.querySelector('#faqIntent'),
  question: document.querySelector('#faqQuestion'),
  keywords: document.querySelector('#faqKeywords'),
  answer: document.querySelector('#faqAnswer'),
  humanKeywords: document.querySelector('#humanKeywords'),
  fallbackReply: document.querySelector('#fallbackReply'),
};

tokenInput.value = localStorage.getItem('admin_token') || '';

function headers() {
  const value = tokenInput.value.trim();
  if (value) localStorage.setItem('admin_token', value);
  return {
    'Content-Type': 'application/json',
    ...(value ? { 'x-admin-token': value } : {}),
  };
}

function setStatus(text) {
  statusText.textContent = text;
}

function splitKeywords(value) {
  return value
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...headers(), ...(options.headers || {}) },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error?.message || `HTTP ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

function renderFaq(items) {
  faqList.innerHTML = '';
  items.forEach((item) => {
    const row = document.createElement('article');
    row.className = 'faq-item';

    const content = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = `${item.intent} · ${item.question}`;
    const answer = document.createElement('p');
    answer.textContent = item.answer;
    const keywords = document.createElement('p');
    keywords.textContent = `关键词：${(item.keywords || []).join('，') || '无'}`;
    content.append(title, answer, keywords);

    const edit = document.createElement('button');
    edit.type = 'button';
    edit.className = 'secondary';
    edit.textContent = '编辑';
    edit.addEventListener('click', () => {
      fields.intent.value = item.intent;
      fields.question.value = item.question;
      fields.keywords.value = (item.keywords || []).join('，');
      fields.answer.value = item.answer;
      fields.intent.focus();
    });

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'danger';
    remove.textContent = '删除';
    remove.addEventListener('click', async () => {
      if (!confirm(`删除 FAQ：${item.intent}？`)) return;
      await api(`/api/admin/faq/${encodeURIComponent(item.intent)}`, { method: 'DELETE' });
      setStatus('FAQ 已删除');
      loadData();
    });

    row.append(content, edit, remove);
    faqList.appendChild(row);
  });
}

function renderFeedbackTop(items) {
  feedbackTopList.innerHTML = '';
  if (!items.length) {
    feedbackTopList.textContent = '暂无反馈数据。';
    return;
  }

  items.forEach((item, index) => {
    const row = document.createElement('article');
    row.className = 'feedback-top-item';

    const rate = Math.round(item.downvote_rate * 100);
    const reasons = Object.entries(item.reasons || {})
      .map(([reason, count]) => `${reason} ${count}`)
      .join(' / ') || '暂无点踩原因';

    const title = document.createElement('strong');
    title.textContent = `#${index + 1} ${item.question}`;
    const stats = document.createElement('p');
    stats.textContent = `点踩率：${rate}% · 点踩 ${item.downvotes} / 反馈 ${item.total_feedback} · 意图：${item.intent}`;
    const reasonLine = document.createElement('p');
    reasonLine.textContent = `原因：${reasons}`;
    const reply = document.createElement('p');
    reply.textContent = `最近回复：${item.latest_reply}`;

    row.append(title, stats, reasonLine, reply);
    feedbackTopList.appendChild(row);
  });
}

async function loadData() {
  setStatus('加载中...');
  const [faqItems, settings, feedbackTop] = await Promise.all([
    api('/api/admin/faq'),
    api('/api/admin/settings'),
    api('/api/admin/feedback/top'),
  ]);
  renderFaq(faqItems);
  renderFeedbackTop(feedbackTop);
  fields.humanKeywords.value = (settings.human_keywords || []).join('，');
  fields.fallbackReply.value = settings.fallback_reply || '';
  setStatus('已同步');
}

faqForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const intent = fields.intent.value.trim();
  const payload = {
    intent,
    question: fields.question.value.trim(),
    keywords: splitKeywords(fields.keywords.value),
    answer: fields.answer.value.trim(),
  };
  await api(`/api/admin/faq/${encodeURIComponent(intent)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
  faqForm.reset();
  setStatus('FAQ 已保存');
  loadData();
});

settingsForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  await api('/api/admin/settings', {
    method: 'PUT',
    body: JSON.stringify({
      human_keywords: splitKeywords(fields.humanKeywords.value),
      fallback_reply: fields.fallbackReply.value.trim(),
    }),
  });
  setStatus('规则已保存');
  loadData();
});

reloadButton.addEventListener('click', loadData);
loadData().catch((error) => setStatus(error.message));

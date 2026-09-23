const tabs = document.querySelectorAll('.tab');
const forms = document.querySelectorAll('.auth-form');
const authPanel = document.querySelector('.auth-panel');
const heroGrid = document.querySelector('.hero-grid');
const dashboardView = document.querySelector('#dashboard-view');
const headerLoginButton = document.querySelector('#header-login-button');
const likeButton = document.querySelector('#like-button');
const passButton = document.querySelector('#pass-button');
const matchStatus = document.querySelector('#match-status');
const chatPanel = document.querySelector('#chat-panel');
const messageForm = document.querySelector('#message-form');
const messageInput = document.querySelector('#message-input');
const messageList = document.querySelector('#message-list');
const chatTitle = document.querySelector('#chat-title');
const chatSubtitle = document.querySelector('#chat-subtitle');
const chatState = document.querySelector('#chat-state');
const sendButton = messageForm.querySelector('button');

function showLoginForm() {
  const loginTab = document.querySelector('[data-tab="login"]');
  loginTab.click();
  document.querySelector('.auth-panel').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function showDashboard() {
  heroGrid.classList.add('authenticated');
  authPanel.classList.add('authenticated');
  dashboardView.classList.add('visible');
  dashboardView.setAttribute('aria-hidden', 'false');
  chatPanel.classList.add('preview');
  chatPanel.setAttribute('aria-hidden', 'false');
  headerLoginButton.textContent = '서비스 이용 중';
  headerLoginButton.disabled = true;
}

tabs.forEach((tab) => {
  tab.addEventListener('click', () => {
    tabs.forEach((item) => item.classList.toggle('active', item === tab));
    forms.forEach((form) => {
      form.classList.toggle('active', form.id === `${tab.dataset.tab}-form`);
    });
  });
});

document.querySelector('#login-form').addEventListener('submit', (event) => {
  event.preventDefault();
  showDashboard();
});

document.querySelector('#signup-form').addEventListener('submit', (event) => {
  event.preventDefault();
  showLoginForm();
});

headerLoginButton.addEventListener('click', showLoginForm);

likeButton.addEventListener('click', async () => {
  likeButton.disabled = true;
  likeButton.textContent = '좋아요 보냄';
  matchStatus.textContent = '좋아요를 보냈어요. 상대방의 좋아요를 기다리는 중입니다.';

  const token = window.localStorage.getItem('hufs_match_access_token');
  if (!token) {
    return;
  }

  const response = await fetch('/api/v1/likes', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ to_user_id: 'candidate-demo-id' }),
  });
  const result = await response.json();
  if (result.matched) {
    openChat(result.chat_room_id || result.match_id);
  }
});

passButton.addEventListener('click', () => {
  passButton.disabled = true;
  likeButton.disabled = true;
  matchStatus.textContent = '이 후보를 건너뛰었습니다.';
});

function openChat(chatRoomId) {
  matchStatus.textContent = '서로 좋아요를 보내 매칭되었습니다. 이제 대화를 시작해보세요.';
  likeButton.textContent = '매칭 완료';
  chatPanel.classList.remove('preview');
  chatPanel.classList.add('visible');
  chatPanel.setAttribute('aria-hidden', 'false');
  chatPanel.dataset.chatRoomId = chatRoomId;
  chatTitle.textContent = '새로운 매칭';
  chatSubtitle.textContent = '커피한모금님과의 개인 채팅';
  chatState.textContent = '매칭 완료';
  chatState.classList.remove('neutral');
  chatState.classList.add('success');
  messageList.innerHTML = '<div class="message received">안녕하세요. 반가워요!</div>';
  messageInput.disabled = false;
  sendButton.disabled = false;
  messageInput.placeholder = '메시지를 입력하세요';
}

messageForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const body = messageInput.value.trim();
  if (!body || !chatPanel.classList.contains('visible')) {
    return;
  }

  const message = document.createElement('div');
  message.className = 'message sent';
  message.textContent = body;
  messageList.appendChild(message);
  messageInput.value = '';
});

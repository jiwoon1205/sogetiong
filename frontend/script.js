const tabs = document.querySelectorAll('.tab');
const forms = document.querySelectorAll('.auth-form');
const authPanel = document.querySelector('.auth-panel');
const heroGrid = document.querySelector('.hero-grid');
const dashboardView = document.querySelector('#dashboard-view');
const headerLoginButton = document.querySelector('#header-login-button');
const appNav = document.querySelector('#app-nav');
const appNavButtons = document.querySelectorAll('.app-nav-button');
const screenPanels = document.querySelectorAll('.screen-panel');
const likeButton = document.querySelector('#like-button');
const passButton = document.querySelector('#pass-button');
const matchStatus = document.querySelector('#match-status');
const chatPanel = document.querySelector('#chat-panel');
const chatDetailPanel = document.querySelector('#chat-detail-panel');
const chatBackButton = document.querySelector('#chat-back-button');
const messageForm = document.querySelector('#message-form');
const messageInput = document.querySelector('#message-input');
const messageList = document.querySelector('#message-list');
const chatTitle = document.querySelector('#chat-title');
const chatSubtitle = document.querySelector('#chat-subtitle');
const chatState = document.querySelector('#chat-state');
const sendButton = messageForm.querySelector('button');
const chatRooms = document.querySelector('#chat-rooms');
const chatEmpty = document.querySelector('#chat-empty');
const chatCount = document.querySelector('#chat-count');
const apiBaseUrl = window.HUFS_MATCH_API_URL || '/api/v1';
const signupForm = document.querySelector('#signup-form');
const signupEmail = document.querySelector('#signup-email');
const verificationCode = document.querySelector('#verification-code');
const sendVerificationButton = document.querySelector('#send-verification-button');
const verifyCodeButton = document.querySelector('#verify-code-button');
const verificationStatus = document.querySelector('#verification-status');
const signupSubmitButton = document.querySelector('#signup-submit-button');
let emailVerified = false;

async function requestJson(path, options) {
  const response = await fetch(`${apiBaseUrl}${path}`, options);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail || body.error?.message || '요청을 처리하지 못했습니다.');
  }
  return body;
}

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
  appNav.classList.add('visible');
  showScreen('discover');
  headerLoginButton.textContent = '서비스 이용 중';
  headerLoginButton.disabled = true;
}

function showScreen(screenName) {
  screenPanels.forEach((panel) => {
    panel.classList.toggle('active', panel.dataset.screen === screenName);
  });
  appNavButtons.forEach((button) => {
    button.classList.toggle('active', button.dataset.screenTarget === screenName);
  });
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

signupForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!emailVerified) {
    verificationStatus.textContent = '먼저 학교 이메일 인증을 완료해 주세요.';
    return;
  }

  try {
    const result = await requestJson('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: signupEmail.value,
        password: signupForm.querySelector('input[type="password"]').value,
        nickname: signupForm.querySelector('input[type="text"]').value,
        campus_id: signupForm.querySelector('select').value,
        gender: signupForm.querySelectorAll('select')[1].value,
        age: Number(signupForm.querySelector('input[type="number"]').value),
      }),
    });
    window.localStorage.setItem('hufs_match_access_token', result.access_token);
    showDashboard();
  } catch (error) {
    verificationStatus.textContent = error.message;
  }
});

headerLoginButton.addEventListener('click', showLoginForm);

sendVerificationButton.addEventListener('click', async () => {
  emailVerified = false;
  signupSubmitButton.disabled = true;
  verificationStatus.textContent = '인증 메일을 보내는 중입니다.';
  try {
    await requestJson('/auth/send-verification', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ school_id: 1, email: signupEmail.value }),
    });
    verificationStatus.textContent = '인증 메일을 확인하고 코드를 입력해 주세요.';
  } catch (error) {
    verificationStatus.textContent = error.message;
  }
});

verifyCodeButton.addEventListener('click', async () => {
  verificationStatus.textContent = '인증 코드를 확인하는 중입니다.';
  try {
    await requestJson('/auth/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: signupEmail.value, code: verificationCode.value }),
    });
    emailVerified = true;
    signupSubmitButton.disabled = false;
    verificationStatus.textContent = '학교 이메일 인증이 완료되었습니다.';
  } catch (error) {
    emailVerified = false;
    signupSubmitButton.disabled = true;
    verificationStatus.textContent = error.message;
  }
});

signupEmail.addEventListener('input', () => {
  emailVerified = false;
  signupSubmitButton.disabled = true;
});

appNavButtons.forEach((button) => {
  button.addEventListener('click', () => showScreen(button.dataset.screenTarget));
});

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
  chatDetailPanel.setAttribute('aria-hidden', 'false');
  chatPanel.dataset.chatRoomId = chatRoomId;
  chatEmpty.remove();
  const roomButton = document.createElement('button');
  roomButton.className = 'chat-room-item active';
  roomButton.type = 'button';
  roomButton.dataset.roomId = chatRoomId;
  roomButton.innerHTML = '<span class="chat-room-avatar">K</span><span class="chat-room-copy"><strong>커피한모금</strong><small>새로운 매칭</small></span>';
  roomButton.addEventListener('click', () => selectChatRoom(roomButton));
  chatRooms.appendChild(roomButton);
  chatCount.textContent = '1';
  selectChatRoom(roomButton);
}

function selectChatRoom(roomButton) {
  document.querySelectorAll('.chat-room-item').forEach((item) => item.classList.remove('active'));
  roomButton.classList.add('active');
  chatTitle.textContent = '커피한모금';
  chatSubtitle.textContent = '서로 좋아요로 연결된 1:1 개인 채팅';
  chatState.textContent = '매칭 완료';
  chatState.classList.remove('neutral');
  chatState.classList.add('success');
  messageList.innerHTML = '<div class="message received">안녕하세요. 반가워요!</div>';
  messageInput.disabled = false;
  sendButton.disabled = false;
  messageInput.placeholder = '메시지를 입력하세요';
  showScreen('chat-detail');
}

chatBackButton.addEventListener('click', () => showScreen('chat-list'));

messageForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const body = messageInput.value.trim();
  if (!body || !chatDetailPanel.classList.contains('active')) {
    return;
  }

  const message = document.createElement('div');
  message.className = 'message sent';
  message.textContent = body;
  messageList.appendChild(message);
  messageInput.value = '';
});

const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const welcomeMessage = document.getElementById('welcomeMessage');

let isStreaming = false;

// 세션 내 대화 히스토리 (LLM에 전달용)
const conversationHistory = [];

// 인증 확인 (auth.js)
document.addEventListener('DOMContentLoaded', async () => {
    await checkAuth();
});

function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

function sendSuggestion(btn) {
    chatInput.value = btn.textContent;
    sendMessage();
}

function appendMessage(role, content, sources = []) {
    // 환영 메시지 숨기기
    if (welcomeMessage) {
        welcomeMessage.style.display = 'none';
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? '나' : 'AI';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = formatMessage(content);

    // 출처 정보
    if (sources && sources.length > 0) {
        const sourcesHtml = createSourcesHtml(sources);
        contentDiv.innerHTML += sourcesHtml;
    }

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);

    scrollToBottom();
    return contentDiv;
}

function createSourcesHtml(sources) {
    let html = '<details class="message-sources"><summary>참고 출처</summary><ul>';
    for (const src of sources) {
        let text = src.document;
        if (src.article) text += ` - ${src.article}`;
        if (src.relevance_score > 0) text += ` (유사도: ${(src.relevance_score * 100).toFixed(0)}%)`;
        html += `<li>${text}</li>`;
    }
    html += '</ul></details>';
    return html;
}

function formatMessage(text) {
    // marked.js로 마크다운 렌더링
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true,
        });
        return marked.parse(text);
    }
    // marked 로드 실패 시 기본 변환
    return text
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`(.*?)`/g, '<code>$1</code>');
}

function showTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'chat-message bot';
    typingDiv.id = 'typingIndicator';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = 'AI';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';

    typingDiv.appendChild(avatar);
    typingDiv.appendChild(contentDiv);
    chatMessages.appendChild(typingDiv);

    scrollToBottom();
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) indicator.remove();
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendMessage() {
    const message = chatInput.value.trim();
    if (!message || isStreaming) return;

    // 사용자 메시지 표시
    appendMessage('user', message);
    chatInput.value = '';
    chatInput.style.height = 'auto';

    // 히스토리에 사용자 메시지 추가
    conversationHistory.push({ role: 'user', content: message });

    isStreaming = true;
    sendBtn.disabled = true;

    // 스트리밍 응답
    try {
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                history: conversationHistory.slice(0, -1),
            }),
        });

        if (!response.ok) {
            throw new Error(`서버 오류: ${response.status}`);
        }

        // 봇 메시지 컨테이너 생성
        const botContent = appendMessage('bot', '');
        let fullText = '';

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6).trim();
                    if (data === '[DONE]') continue;

                    try {
                        const parsed = JSON.parse(data);
                        if (parsed.token) {
                            fullText += parsed.token;
                            botContent.innerHTML = formatMessage(fullText);
                            scrollToBottom();
                        }
                        if (parsed.error) {
                            fullText += `\n\n오류: ${parsed.error}`;
                            botContent.innerHTML = formatMessage(fullText);
                        }
                    } catch (e) {
                        // JSON 파싱 실패 무시
                    }
                }
            }
        }

        // 스트리밍 성공 시 히스토리에 AI 응답 추가
        if (fullText) {
            conversationHistory.push({ role: 'assistant', content: fullText });
        } else {
            // 스트리밍 실패 시 일반 API로 폴백
            botContent.remove();
            await sendMessageFallback(message);
        }

    } catch (error) {
        removeTypingIndicator();
        // 폴백: 일반 API 사용
        await sendMessageFallback(message);
    } finally {
        isStreaming = false;
        sendBtn.disabled = false;
        chatInput.focus();
    }
}

async function sendMessageFallback(message) {
    showTypingIndicator();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                history: conversationHistory.slice(0, -1),
            }),
        });

        removeTypingIndicator();

        if (!response.ok) {
            throw new Error(`서버 오류: ${response.status}`);
        }

        const data = await response.json();
        appendMessage('bot', data.answer, data.sources);

        // 히스토리에 AI 응답 추가
        conversationHistory.push({ role: 'assistant', content: data.answer });

    } catch (error) {
        removeTypingIndicator();
        appendMessage('bot', `오류가 발생했습니다: ${error.message}\n\n서버가 실행 중인지 확인해 주세요.`);
    }
}

// 페이지 로드 시 입력란 포커스
chatInput.focus();

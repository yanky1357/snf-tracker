/* ReefPilot — Chat UI */

let chatLoaded = false;

function addChatWelcome() {
    const msgs = document.getElementById('chat-messages');
    msgs.innerHTML = `
        <div class="chat-welcome">
            <div class="chat-welcome-icon">
                <img src="/static/reef/icons/icon-192.png" alt="ReefPilot" width="48" height="48" style="border-radius:12px;">
            </div>
            <h3>ReefPilot AI</h3>
            <p>Tell me your water test results and I'll log them automatically. Ask me anything about reef keeping!</p>
            <div class="chat-suggestions">
                <button class="suggestion-chip" onclick="sendSuggestion('My KH is 8.2 and calcium is 430')">KH is 8.2, Ca is 430</button>
                <button class="suggestion-chip" onclick="sendSuggestion('What should my ideal parameters be?')">Ideal parameters?</button>
                <button class="suggestion-chip" onclick="sendSuggestion('How often should I test my water?')">Testing schedule?</button>
            </div>
        </div>
    `;
}

async function loadChatHistory() {
    if (chatLoaded) return;
    try {
        const data = await api('/chat/history');
        if (data.messages && data.messages.length > 0) {
            const msgs = document.getElementById('chat-messages');
            msgs.innerHTML = '';
            data.messages.forEach(m => {
                appendChatBubble(m.role, m.content);
            });
            scrollChat();
        }
        chatLoaded = true;
    } catch {
        // ignore
    }
}

function renderMarkdown(text) {
    // Sanitize HTML entities first
    let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // Headings: ### heading
    html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');

    // Bold: **text**
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Italic: *text*
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Unordered lists: - item or * item
    html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');

    // Numbered lists: 1. item
    html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
    // Wrap consecutive <li> not already in <ul> into <ol>
    html = html.replace(/<\/ul>\s*<ul>/g, ''); // merge adjacent <ul>
    html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, (match) => {
        if (match.includes('<ul>')) return match;
        return '<ul>' + match + '</ul>';
    });

    // Inline code: `code`
    html = html.replace(/`(.+?)`/g, '<code>$1</code>');

    // Paragraphs: split on double newlines
    html = html.split(/\n{2,}/).map(block => {
        block = block.trim();
        if (!block) return '';
        // Don't wrap blocks that are already block-level elements
        if (/^<(h[1-6]|ul|ol|li|blockquote)/.test(block)) return block;
        return '<p>' + block.replace(/\n/g, '<br>') + '</p>';
    }).join('');

    return html;
}

function appendChatBubble(role, content) {
    const msgs = document.getElementById('chat-messages');
    // Remove welcome message if present
    const welcome = msgs.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble ' + role;
    if (role === 'assistant') {
        bubble.innerHTML = renderMarkdown(content);
    } else {
        bubble.textContent = content;
    }
    msgs.appendChild(bubble);
}

function showTypingIndicator() {
    const msgs = document.getElementById('chat-messages');
    const typing = document.createElement('div');
    typing.className = 'chat-typing';
    typing.id = 'typing-indicator';
    typing.innerHTML = `
        <div class="typing-logo">
            <img src="/static/reef/icons/icon-192.png" alt="ReefPilot" width="32" height="32" style="border-radius:8px;">
        </div>
        <span class="typing-text">Analyzing...</span>
    `;
    msgs.appendChild(typing);
    scrollChat();
}

function removeTypingIndicator() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
}

function showParamToast(params) {
    if (!params || params.length === 0) return;
    const msgs = document.getElementById('chat-messages');
    const toast = document.createElement('div');
    toast.className = 'param-toast';
    const items = params.map(p => {
        const label = p.type.charAt(0).toUpperCase() + p.type.slice(1);
        return `${label}: ${p.value} ${p.unit}`;
    });
    toast.innerHTML = '&#10003; Auto-logged: ' + items.join(', ');
    msgs.appendChild(toast);
    scrollChat();
}

function scrollChat() {
    const msgs = document.getElementById('chat-messages');
    setTimeout(() => msgs.scrollTop = msgs.scrollHeight, 50);
}

async function handleChatSend(e) {
    e.preventDefault();
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return false;

    input.value = '';
    appendChatBubble('user', message);
    scrollChat();

    const sendBtn = document.getElementById('btn-send');
    sendBtn.disabled = true;
    showTypingIndicator();

    try {
        const data = await api('/chat', {
            method: 'POST',
            body: { message },
        });
        removeTypingIndicator();
        appendChatBubble('assistant', data.response);
        if (data.extracted_params && data.extracted_params.length > 0) {
            showParamToast(data.extracted_params);
        }
        scrollChat();
    } catch (err) {
        removeTypingIndicator();
        appendChatBubble('assistant', 'Sorry, something went wrong. Please try again.');
        showToast(err.message, 'error');
    } finally {
        sendBtn.disabled = false;
        input.focus();
    }
    return false;
}

function sendSuggestion(text) {
    document.getElementById('chat-input').value = text;
    document.getElementById('chat-form').dispatchEvent(new Event('submit'));
}

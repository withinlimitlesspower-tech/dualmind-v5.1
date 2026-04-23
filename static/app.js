let currentSessionId = null;
let isGenerating = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    createSession();
    loadSessions();
    
    // Enter key to send
    document.getElementById('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
});

async function createSession() {
    try {
        const response = await fetch('/api/sessions', {
            method: 'POST',
        });
        const data = await response.json();
        currentSessionId = data.id;
        
        // Clear messages
        document.getElementById('chat-messages').innerHTML = '';
        document.getElementById('chat-input').value = '';
        document.getElementById('chat-input').disabled = false;
        
        // Update header
        document.getElementById('session-title').textContent = 'New Chat';
        
        // Hide GitHub button
        document.getElementById('github-btn').classList.remove('visible');
        
        // Load sessions
        loadSessions();
    } catch (error) {
        console.error('Error creating session:', error);
    }
}

async function loadSessions() {
    try {
        const response = await fetch('/api/sessions');
        const sessions = await response.json();
        
        const sessionsList = document.getElementById('sessions-list');
        sessionsList.innerHTML = '';
        
        sessions.forEach(session => {
            const item = document.createElement('div');
            item.className = 'session-item' + (session.id === currentSessionId ? ' active' : '');
            item.textContent = session.name || 'New Chat';
            item.onclick = () => switchSession(session.id);
            sessionsList.appendChild(item);
        });
    } catch (error) {
        console.error('Error loading sessions:', error);
    }
}

async function switchSession(sessionId) {
    currentSessionId = sessionId;
    
    // Update active state
    document.querySelectorAll('.session-item').forEach(item => {
        item.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // Load messages
    await loadMessages(sessionId);
    
    // Enable input
    document.getElementById('chat-input').disabled = false;
    document.getElementById('chat-input').focus();
}

async function loadMessages(sessionId) {
    try {
        const response = await fetch(`/api/sessions/${sessionId}/messages`);
        const messages = await response.json();
        
        const messagesContainer = document.getElementById('chat-messages');
        messagesContainer.innerHTML = '';
        
        messages.forEach(msg => {
            displayMessage(msg.role, msg.content, msg.code);
        });
        
        // Update header
        if (messages.length > 0) {
            document.getElementById('session-title').textContent = messages[0].content.substring(0, 50);
        }
        
        // Check for code to show GitHub button
        const hasCode = messages.some(msg => msg.code);
        if (hasCode) {
            document.getElementById('github-btn').classList.add('visible');
        }
        
        // Scroll to bottom
        scrollToBottom();
    } catch (error) {
        console.error('Error loading messages:', error);
    }
}

async function sendMessage() {
    if (isGenerating) return;
    
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Clear input
    input.value = '';
    
    // Show user message
    displayMessage('user', message);
    
    // Show typing indicator
    showTypingIndicator();
    
    // Disable input
    input.disabled = true;
    isGenerating = true;
    
    try {
        const formData = new FormData();
        formData.append('session_id', currentSessionId);
        formData.append('message', message);
        
        const response = await fetch('/api/chat', {
            method: 'POST',
            body: formData,
        });
        
        const data = await response.json();
        
        // Hide typing indicator
        hideTypingIndicator();
        
        // Display AI response
        displayMessage('assistant', data.content, data.code);
        
        // Show GitHub button if code exists
        if (data.code) {
            document.getElementById('github-btn').classList.add('visible');
        }
        
        // Update session title
        document.getElementById('session-title').textContent = message.substring(0, 50);
        
        // Reload sessions
        loadSessions();
    } catch (error) {
        console.error('Error sending message:', error);
        hideTypingIndicator();
        displayMessage('assistant', 'Sorry, an error occurred. Please try again.');
    } finally {
        input.disabled = false;
        isGenerating = false;
        input.focus();
    }
}

function displayMessage(role, content, code = null) {
    const messagesContainer = document.getElementById('chat-messages');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;
    messageDiv.appendChild(contentDiv);
    
    // Add code block if exists
    if (code) {
        const codeWrapper = document.createElement('div');
        codeWrapper.className = 'code-block-wrapper';
        
        const codeHeader = document.createElement('div');
        codeHeader.className = 'code-block-header';
        codeHeader.innerHTML = '<span>Python</span>';
        
        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.textContent = 'Copy';
        copyBtn.onclick = () => copyCode(code, copyBtn);
        codeHeader.appendChild(copyBtn);
        
        const pre = document.createElement('pre');
        const codeElement = document.createElement('code');
        codeElement.textContent = code;
        pre.appendChild(codeElement);
        
        codeWrapper.appendChild(codeHeader);
        codeWrapper.appendChild(pre);
        messageDiv.appendChild(codeWrapper);
    }
    
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
}

function showTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    indicator.classList.add('visible');
    scrollToBottom();
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    indicator.classList.remove('visible');
}

function scrollToBottom() {
    const messagesContainer = document.getElementById('chat-messages');
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

async function pushToGitHub() {
    const repoName = prompt('Enter repository name:');
    if (!repoName) return;
    
    try {
        const formData = new FormData();
        formData.append('session_id', currentSessionId);
        formData.append('repo_name', repoName);
        
        const response = await fetch('/api/push-to-github', {
            method: 'POST',
            body: formData,
        });
        
        const data = await response.json();
        
        if (response.ok) {
            displayMessage('assistant', `✅ Code pushed to GitHub!\n\nRepository URL: ${data.repo_url}`);
        } else {
            displayMessage('assistant', `❌ Error: ${data.detail}`);
        }
    } catch (error) {
        console.error('Error pushing to GitHub:', error);
        displayMessage('assistant', '❌ Failed to push to GitHub. Please check your token and try again.');
    }
}

function copyCode(code, button) {
    navigator.clipboard.writeText(code).then(() => {
        button.textContent = 'Copied!';
        button.classList.add('copied');
        setTimeout(() => {
            button.textContent = 'Copy';
            button.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
    });
}

// Mobile sidebar toggle
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('open');
}

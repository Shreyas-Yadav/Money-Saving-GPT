const API_BASE_URL = 'http://127.0.0.1:8000';
const chatMessages = document.getElementById('chat-messages');

async function fetchChatHistory(sessionId) {
    try {
        const response = await fetch(`${API_BASE_URL}/get_chat_history/${sessionId}`);
        const data = await response.json();
        data.forEach(message => {
            const messageContainer = document.createElement('div');
            messageContainer.classList.add('message', message.role);
            
            const contentDiv = document.createElement('div');
            contentDiv.classList.add('message-content');
            contentDiv.textContent = message.content;
            
            messageContainer.appendChild(contentDiv);
            chatMessages.appendChild(messageContainer);
        });
    } catch (error) {
        console.error('Error fetching chat history:', error);
    }
}

// Extract session ID from URL
const sessionId = window.location.pathname.split('/').pop();
fetchChatHistory(sessionId);
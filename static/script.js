const API_BASE_URL = 'http://127.0.0.1:8000';
const WS_BASE_URL = 'ws://127.0.0.1:8000';
let sessionId = null;
let selectedModel = 'openai/gpt-3.5-turbo';
const chatMessages = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const connectionStatus = document.getElementById('connection-status');
const modelList = document.getElementById('model-list');
let socket = null;
let totalCost = 0;

function updateUIState(connected) {
    connectionStatus.innerHTML = `<i class="fas fa-circle ${connected ? 'text-success' : 'text-danger'}"></i> ${connected ? 'Connected' : 'Disconnected'}`;
    messageInput.disabled = !connected;
    sendBtn.disabled = !connected;
}

// Update connectWebSocket with better error handling
async function connectWebSocket() {
    totalCost = 0;  // Reset total when connecting
    document.getElementById('total-cost').textContent = '$0.0000';
    updateUIState(false);
    chatMessages.innerHTML = '';
    
    try {
        sessionId = sessionId || (await createSession());
        socket = new WebSocket(`${WS_BASE_URL}/chat/${sessionId}`);

        socket.onopen = () => updateUIState(true);
        socket.onmessage = (event) => {
            const response = JSON.parse(event.data);

            console.log(response);
            
            if(response.content === 'IRRELEVANT') {
                // Show modal for irrelevant content
                $('#irrelevantContentModal').modal('show');
                return;
            }
            
            if (response.action === 'new_session') {
                sessionId = response.session_id;
                if (socket) socket.close();
                connectWebSocket();
                return;
            }
            
            const sender = response.sender || 'ai';
            addMessage(sender, response.content);
            if (response.cost) {
                addCostBadge(response.cost);
                totalCost += response.cost;
                document.getElementById('total-cost').textContent = `$${totalCost.toFixed(4)}`;
            }
        };
        socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            updateUIState(false);
        };
        socket.onclose = (event) => {
            if (!event.wasClean) {
                console.error('Unexpected disconnect:', event.reason);
            }
            updateUIState(false);
        };
    } catch (error) {
        console.error('Connection failed:', error);
        updateUIState(false);
        throw error;
    }
}

function addCostBadge(cost) {
    const costBadge = document.createElement('div');
    costBadge.className = 'cost-badge';
    costBadge.innerHTML = `💰 Cost: $${cost.toFixed(4)}`;
    chatMessages.appendChild(costBadge);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function createSession() {
    const response = await fetch(`${API_BASE_URL}/create_session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: selectedModel })
    });
    const data = await response.json();
    return data.session_id;
}

function addMessage(sender, message) {
    const messageContainer = document.createElement('div');
    messageContainer.classList.add('message', sender);
    
    const contentDiv = document.createElement('div');
    contentDiv.classList.add('message-content');
    
    if (sender === 'ai') {
        contentDiv.innerHTML = DOMPurify.sanitize(marked.parse(message));
    } else {
        contentDiv.textContent = message;
    }

    messageContainer.appendChild(contentDiv);
    chatMessages.appendChild(messageContainer);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Add this function to select the first model
function initializeDefaultModel() {
    const firstModel = document.querySelector('#model-list .list-group-item');
    if (firstModel) {
        firstModel.classList.add('active');
        selectedModel = firstModel.getAttribute('data-model');
        // logger.info(`Default model set to: ${selectedModel}`);
    }
}

async function sendMessage() {
    const message = messageInput.value.trim();
    // console.log('Selected model:', selectedModel);
    if (message && socket && socket.readyState === WebSocket.OPEN) {
        const payload = JSON.stringify({
            content: message,
            model: selectedModel
        });
        socket.send(payload);
        addMessage('user', message);
        messageInput.value = '';
    }
}

modelList.addEventListener('click', (e) => {
    const clickedModel = e.target.closest('.list-group-item');
    if (clickedModel) {
        document.querySelectorAll('.list-group-item').forEach(item => item.classList.remove('active'));
        clickedModel.classList.add('active');
        selectedModel = clickedModel.getAttribute('data-model');
        // logger.info(`Model changed to: ${selectedModel}`);
    }
});

sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Function to fetch and display history
async function fetchHistory() {
    try {
        const response = await fetch(`${API_BASE_URL}/get_history`);
        const data = await response.json();
        const historyList = document.getElementById('history-list');
        
        historyList.innerHTML = ''; // Clear existing history
        data.forEach(session => {
            const sessionItem = document.createElement('a');
            sessionItem.href = `${API_BASE_URL}/history/${session.session_id}`;
            sessionItem.className = 'list-group-item';
            sessionItem.textContent = session.session_id;
            historyList.appendChild(sessionItem);
        });
    } catch (error) {
        console.error('Error fetching history:', error);
    }
}

// Event listener for the "Start New Session" button in the modal
document.getElementById('startNewSessionBtn').addEventListener('click', () => {
    // Close the modal
    $('#irrelevantContentModal').modal('hide');
    
    // Close existing socket if open
    if (socket) {
        socket.close();
    }
    
    // Reset session and reconnect
    sessionId = null;
    connectWebSocket();
});

window.addEventListener('load', ()=>{
    connectWebSocket();
    initializeDefaultModel();
    fetchHistory();
});

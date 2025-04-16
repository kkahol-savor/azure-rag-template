// DOM Elements
const queryInput = document.getElementById('query-input');
const submitBtn = document.getElementById('submit-btn');
const clearSessionBtn = document.getElementById('clear-session-btn');
const responseText = document.getElementById('response-text');
const citationPanel = document.getElementById('citation-panel');
const closeCitationBtn = document.getElementById('close-citation-btn');
const citationContent = document.getElementById('citation-content');
const historyPanel = document.querySelector('.history-panel');
const toggleHistoryBtn = document.getElementById('toggle-history-btn');
const historyList = document.getElementById('history-list');

// State
let currentSessionId = null;
let currentCitations = [];
let conversationHistory = [];

// Event Listeners
submitBtn.addEventListener('click', handleSubmit);
queryInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleSubmit();
    }
});
closeCitationBtn.addEventListener('click', closeCitationPanel);
clearSessionBtn.addEventListener('click', clearCurrentSession);
toggleHistoryBtn.addEventListener('click', toggleHistoryPanel);

// Functions
async function handleSubmit() {
    const query = queryInput.value.trim();
    if (!query) return;

    // Disable input and button during processing
    setLoadingState(true);

    try {
        const response = await fetch('/api/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                query,
                session_id: currentSessionId
            }),
        });

        if (!response.ok) {
            throw new Error('Network response was not ok');
        }

        const data = await response.json();
        
        // Update session ID if this is a new session
        if (!currentSessionId && data.session_id) {
            currentSessionId = data.session_id;
        }
        
        displayResponse(data);
        await loadConversationHistory();
    } catch (error) {
        console.error('Error:', error);
        displayError('An error occurred while processing your query. Please try again.');
    } finally {
        setLoadingState(false);
    }
}

function displayResponse(data) {
    // Store citations for later use
    currentCitations = data.citations || [];

    // Format response text with citation markers
    let formattedText = data.response;
    if (currentCitations.length > 0) {
        currentCitations.forEach((citation, index) => {
            const marker = `[${index + 1}]`;
            formattedText = formattedText.replace(
                new RegExp(`\\[${index + 1}\\]`, 'g'),
                `<span class="citation-marker" onclick="showCitation(${index})">${marker}</span>`
            );
        });
    }

    responseText.innerHTML = formattedText;
}

function showCitation(index) {
    const citation = currentCitations[index];
    if (!citation) return;

    citationContent.innerHTML = `
        <div class="citation-item">
            <h3>Source ${index + 1}</h3>
            <p><strong>Document:</strong> ${citation.document}</p>
            <p><strong>Content:</strong> ${citation.content}</p>
            <p><strong>Confidence Score:</strong> <span class="confidence-score">${(citation.score * 100).toFixed(2)}%</span></p>
        </div>
    `;

    citationPanel.classList.add('active');
}

function closeCitationPanel() {
    citationPanel.classList.remove('active');
}

function setLoadingState(isLoading) {
    queryInput.disabled = isLoading;
    submitBtn.disabled = isLoading;
    document.body.classList.toggle('loading', isLoading);
}

function displayError(message) {
    responseText.innerHTML = `<div class="error">${message}</div>`;
}

async function loadConversationHistory() {
    try {
        const response = await fetch('/api/conversations');
        if (!response.ok) {
            throw new Error('Failed to load conversation history');
        }
        
        const data = await response.json();
        conversationHistory = data;
        
        renderConversationHistory();
    } catch (error) {
        console.error('Error loading conversation history:', error);
    }
}

function renderConversationHistory() {
    historyList.innerHTML = '';
    
    conversationHistory.forEach(conversation => {
        const historyItem = document.createElement('div');
        historyItem.className = 'history-item';
        if (conversation.id === currentSessionId) {
            historyItem.classList.add('active');
        }
        
        const date = new Date(conversation.timestamp);
        const formattedDate = date.toLocaleString();
        
        historyItem.innerHTML = `
            <div class="query">${conversation.query}</div>
            <div class="timestamp">${formattedDate}</div>
        `;
        
        historyItem.addEventListener('click', () => loadConversation(conversation.id));
        historyList.appendChild(historyItem);
    });
}

async function loadConversation(sessionId) {
    try {
        const response = await fetch(`/api/conversations/${sessionId}`);
        if (!response.ok) {
            throw new Error('Failed to load conversation');
        }
        
        const conversation = await response.json();
        currentSessionId = sessionId;
        
        // Display the conversation
        queryInput.value = conversation.query;
        displayResponse({
            response: conversation.response,
            citations: conversation.search_results || []
        });
        
        // Update active state in history
        document.querySelectorAll('.history-item').forEach(item => {
            item.classList.remove('active');
            if (item.querySelector('.query').textContent === conversation.query) {
                item.classList.add('active');
            }
        });
    } catch (error) {
        console.error('Error loading conversation:', error);
        displayError('Failed to load conversation. Please try again.');
    }
}

function clearCurrentSession() {
    // Clear current session but keep history in DB
    currentSessionId = null;
    queryInput.value = '';
    responseText.innerHTML = '';
    currentCitations = [];
    
    // Update active state in history
    document.querySelectorAll('.history-item').forEach(item => {
        item.classList.remove('active');
    });
}

function toggleHistoryPanel() {
    historyPanel.classList.toggle('collapsed');
}

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    // Set initial state
    setLoadingState(false);
    
    // Load conversation history
    await loadConversationHistory();
}); 
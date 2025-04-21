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
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const closeSettingsBtn = document.getElementById('close-settings-btn');
const settingsForm = document.getElementById('settings-form');
const temperatureInput = document.getElementById('temperature');
const temperatureValue = document.getElementById('temperature-value');
const topPInput = document.getElementById('top-p');
const topPValue = document.getElementById('top-p-value');

// State
let currentSessionId = null;
let currentCitations = [];
let conversationHistory = [];

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    submitBtn.addEventListener('click', handleSubmit);
    queryInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleSubmit();
        }
    });
    closeCitationBtn.addEventListener('click', closeCitationPanel);
    clearSessionBtn.addEventListener('click', clearCurrentSession);
    toggleHistoryBtn.addEventListener('click', toggleHistoryPanel);
    settingsBtn.addEventListener('click', openSettingsModal);
    closeSettingsBtn.addEventListener('click', closeSettingsModal);
    settingsForm.addEventListener('submit', saveSettings);
    temperatureInput.addEventListener('input', () => updateRangeValue(temperatureInput, temperatureValue));
    topPInput.addEventListener('input', () => updateRangeValue(topPInput, topPValue));

    // Close modal when clicking outside
    settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            closeSettingsModal();
        }
    });
});

// Settings Functions
function openSettingsModal() {
    settingsModal.classList.add('active');
    loadSettings();
}

function closeSettingsModal() {
    settingsModal.classList.remove('active');
}

function loadSettings() {
    const settings = JSON.parse(localStorage.getItem('healrag_settings') || '{}');
    
    document.getElementById('plan-name-filter').value = settings.plan_name_filter || '';
    temperatureInput.value = settings.temperature || 0.7;
    temperatureValue.textContent = settings.temperature || 0.7;
    topPInput.value = settings.top_p || 0.9;
    topPValue.textContent = settings.top_p || 0.9;
}

function saveSettings(event) {
    event.preventDefault();
    
    const settings = {
        plan_name_filter: document.getElementById('plan-name-filter').value,
        temperature: parseFloat(temperatureInput.value),
        top_p: parseFloat(topPInput.value)
    };
    
    localStorage.setItem('healrag_settings', JSON.stringify(settings));
    closeSettingsModal();
    alert('Settings saved successfully!');
}

function updateRangeValue(input, valueElement) {
    valueElement.textContent = input.value;
}

// Functions
async function handleSubmit() {
    const query = queryInput.value.trim();
    if (!query) return;

    // Disable input and button during processing
    setLoadingState(true);

    try {
        // Get current settings
        const settings = JSON.parse(localStorage.getItem('healrag_settings') || '{}');
        
        // Generate session ID if not exists
        if (!currentSessionId) {
            currentSessionId = crypto.randomUUID();
        }

        const response = await fetch('/api/query/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                query,
                session_id: currentSessionId,
                plan_name_filter: settings.plan_name_filter,
                temperature: settings.temperature,
                top_p: settings.top_p
            }),
        });

        if (!response.ok) {
            throw new Error('Network response was not ok');
        }

        // Clear previous response
        responseText.innerHTML = '';
        
        // Handle streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            
            // Process complete JSON objects from the buffer
            let startIndex = 0;
            let endIndex;
            
            while ((endIndex = buffer.indexOf('\n', startIndex)) !== -1) {
                try {
                    const jsonStr = buffer.substring(startIndex, endIndex).trim();
                    if (jsonStr) {
                        const data = JSON.parse(jsonStr);
                        if (data.response) {
                            responseText.innerHTML += data.response;
                            // Scroll to bottom of response
                            responseText.scrollTop = responseText.scrollHeight;
                        }
                        if (data.citations) {
                            currentCitations = data.citations;
                        }
                    }
                    startIndex = endIndex + 1;
                } catch (e) {
                    console.error('Error parsing JSON:', e);
                    break;
                }
            }
            
            buffer = buffer.substring(startIndex);
        }
        
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
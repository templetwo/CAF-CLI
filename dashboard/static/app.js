/**
 * CAF Dashboard - Frontend JavaScript
 *
 * Connects to WebSocket for real-time updates,
 * manages UI state, and handles user interactions.
 */

class CAFDashboard {
    constructor() {
        this.ws = null;
        this.isRunning = false;

        // DOM elements
        this.goalForm = document.getElementById('goal-form');
        this.goalInput = document.getElementById('goal-input');
        this.runBtn = document.getElementById('run-btn');
        this.currentGoal = document.getElementById('current-goal');
        this.turnDisplay = document.getElementById('turn-display');
        this.statusDisplay = document.getElementById('status-display');
        this.actionStream = document.getElementById('action-stream');
        this.observationPanel = document.getElementById('observation-panel');
        this.memoryPanel = document.getElementById('memory-panel');
        this.errorPanel = document.getElementById('error-panel');

        this.init();
    }

    init() {
        // Connect WebSocket
        this.connectWebSocket();

        // Load initial data
        this.loadMemory();
        this.loadErrors();

        // Event listeners
        this.goalForm.addEventListener('submit', (e) => this.handleSubmit(e));

        // Focus input
        this.goalInput.focus();
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected, reconnecting...');
            setTimeout(() => this.connectWebSocket(), 2000);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    handleMessage(data) {
        switch (data.type) {
            case 'state':
                this.updateState(data.state);
                break;
            case 'turn':
                this.updateTurn(data.turn, data.max_turns);
                break;
            case 'action':
                this.addAction(data.event);
                break;
            case 'complete':
                this.handleComplete(data.turns);
                break;
            case 'error':
                this.handleError(data.message);
                break;
            case 'memory_consulted':
                if (data.has_context) {
                    this.addSystemMessage('Memory consulted');
                }
                break;
        }
    }

    updateState(state) {
        this.setStatus(state.status);
        this.turnDisplay.textContent = `Turn: ${state.turn}/${state.max_turns}`;

        if (state.goal) {
            this.currentGoal.textContent = `Goal: ${state.goal}`;
        }

        // Restore history
        this.actionStream.innerHTML = '';
        state.history.forEach(event => this.addAction(event, false));
    }

    updateTurn(turn, maxTurns) {
        this.turnDisplay.textContent = `Turn: ${turn}/${maxTurns}`;
    }

    setStatus(status) {
        this.statusDisplay.textContent = status;
        this.statusDisplay.className = `status ${status}`;
        this.isRunning = status === 'running';
        this.runBtn.disabled = this.isRunning;
    }

    addAction(event, scroll = true) {
        const div = document.createElement('div');
        div.className = `action-item ${event.success ? 'success' : 'failure'}`;

        const argDisplay = event.argument.length > 40
            ? event.argument.substring(0, 40) + '...'
            : event.argument;

        div.innerHTML = `
            <span class="action-turn">[${event.turn}]</span>
            <span class="action-status">${event.success ? '✓' : '✗'}</span>
            <span class="action-name">${event.action}:</span>
            <span class="action-arg">${this.escapeHtml(argDisplay)}</span>
        `;

        this.actionStream.appendChild(div);

        // Update observation panel
        this.observationPanel.innerHTML = `
            <div class="observation-content ${event.success ? '' : 'error'}">
                ${this.escapeHtml(event.observation)}
            </div>
        `;

        if (scroll) {
            this.actionStream.scrollTop = this.actionStream.scrollHeight;
        }
    }

    addSystemMessage(message) {
        const div = document.createElement('div');
        div.className = 'action-item';
        div.innerHTML = `<span class="muted">${this.escapeHtml(message)}</span>`;
        this.actionStream.appendChild(div);
    }

    handleComplete(turns) {
        this.setStatus('complete');
        this.addSystemMessage(`--- Complete (${turns} turns) ---`);
        this.loadMemory();
        this.loadErrors();
    }

    handleError(message) {
        this.setStatus('error');
        this.observationPanel.innerHTML = `
            <div class="observation-content error">Error: ${this.escapeHtml(message)}</div>
        `;
    }

    async handleSubmit(e) {
        e.preventDefault();

        const goal = this.goalInput.value.trim();
        if (!goal || this.isRunning) return;

        // Clear UI
        this.actionStream.innerHTML = '';
        this.observationPanel.innerHTML = '<p class="muted">Waiting...</p>';
        this.currentGoal.textContent = `Goal: ${goal}`;
        this.goalInput.value = '';

        // Start agent
        this.setStatus('running');

        try {
            const response = await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ goal, max_turns: 15 })
            });

            if (!response.ok) {
                const error = await response.json();
                this.handleError(error.detail || 'Failed to start agent');
            }
        } catch (error) {
            this.handleError(error.message);
        }
    }

    async loadMemory() {
        try {
            const response = await fetch('/api/memory?limit=5');
            const data = await response.json();

            if (data.insights && data.insights.length > 0) {
                this.memoryPanel.innerHTML = data.insights.map(ins => `
                    <div class="memory-item">
                        <div class="memory-domain">[${ins.domain || '?'}]</div>
                        <div class="memory-content">${this.escapeHtml((ins.content || '').substring(0, 80))}</div>
                    </div>
                `).join('');
            } else {
                this.memoryPanel.innerHTML = '<p class="muted">(no recent memories)</p>';
            }
        } catch (error) {
            this.memoryPanel.innerHTML = '<p class="muted">(failed to load)</p>';
        }
    }

    async loadErrors() {
        try {
            const response = await fetch('/api/errors?limit=5');
            const data = await response.json();

            if (data.errors && data.errors.length > 0) {
                this.errorPanel.innerHTML = data.errors.map(err => `
                    <div class="error-item">
                        <span class="error-status ${err.status === 'fixed' ? 'fixed' : 'open'}">
                            ${err.status === 'fixed' ? '✓' : '○'}
                        </span>
                        <div class="error-info">
                            <div class="error-cat">[${err.category || '?'}/${(err.fingerprint || '?').substring(0, 6)}]</div>
                        </div>
                    </div>
                `).join('');
            } else {
                this.errorPanel.innerHTML = '<p class="muted">(no errors tracked)</p>';
            }
        } catch (error) {
            this.errorPanel.innerHTML = '<p class="muted">(failed to load)</p>';
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new CAFDashboard();
});

/**
 * BhuRakshak — Hazard RAG Chatbot with Cinematic MapLibre Flythrough
 * ====================================================================
 * Conversational AI analyst grounded in atomic knowledge chunks.
 * Features:
 *   - Natural language input: "What's happening near Dharali?"
 *   - Grounded RAG retrieval of atomic knowledge chunks (Habitation, Disaster, Safe Zone, Lifeline)
 *   - Interactive Chunk Cards with FoS metrics, zone pills, and "Fly to Chunk" buttons
 *   - Cinematic camera flythrough sequences with MapLibre flyTo()
 *   - Quick-action prompt chips for high-frequency DM queries
 */

export class HazardChatPanel {
    constructor(map, apiBase = '') {
        this.map = map;
        this.apiBase = apiBase;
        this.isOpen = false;
        this.messages = [];
        this.isFlying = false;
        this.flightAbortController = null;
        this.activePopup = null;

        this._createPanel();
        this._bindEvents();
        this._fetchKnowledgeStatus();
    }

    // ================================================================
    // UI Construction
    // ================================================================

    _createPanel() {
        // Main container
        this.container = document.createElement('div');
        this.container.id = 'hazard-chat-panel';
        this.container.innerHTML = `
            <div class="hcp-header">
                <div class="hcp-title">
                    <span class="hcp-icon">🛰️</span>
                    <div>
                        <div class="hcp-main-title">BhuRakshak AI Analyst</div>
                        <div class="hcp-sub-title" id="hcp-kb-badge">89 Atomic Chunks Indexed (<1ms RAG)</div>
                    </div>
                </div>
                <div class="hcp-controls">
                    <button id="hcp-minimize" title="Minimize">─</button>
                    <button id="hcp-close" title="Close">✕</button>
                </div>
            </div>

            <div class="hcp-quick-prompts">
                <button class="hcp-quick-pill" data-query="Where does Uttarkashi locate?">📍 Where is Uttarkashi?</button>
                <button class="hcp-quick-pill" data-query="How is basically a red zone identified of a certain region or a green zone based on the hazard like landslide and floods and how can we calculate using GIS software and train an AI model so that it shows real time and how we can safely relocate from that zone to other zones?">🔬 Zonation & AI Model</button>
                <button class="hcp-quick-pill" data-query="Where are the critical Red Zones in Uttarkashi?">🔴 Red Zones (FoS &lt; 1.0)</button>
                <button class="hcp-quick-pill" data-query="How can we safely relocate from Dharali to safe zones?">🛡️ Dharali Relocation</button>
                <button class="hcp-quick-pill" data-query="Status and vulnerabilities of NH-108 lifeline corridor">🛣️ NH-108 Corridor</button>
                <button class="hcp-quick-pill" data-query="What happened during the 2012 Asi Ganga disaster benchmark?">📜 2012 Benchmark</button>
            </div>

            <div class="hcp-messages" id="hcp-messages">
                <div class="hcp-msg hcp-msg-system">
                    <div class="hcp-msg-avatar">🛡️</div>
                    <div class="hcp-msg-content">
                        <strong>BhuRakshak Conversational Intelligence</strong><br>
                        Ask me about any habitation, red zone, geotechnical slope stability, or evacuation corridor in Uttarkashi.
                        Every response is grounded in verified atomic knowledge chunks with physics calculations (FoS) and 3D camera navigation.<br><br>
                        <em>Click a quick prompt above or type your operational query below.</em>
                    </div>
                </div>
            </div>

            <div class="hcp-input-area">
                <input type="text" id="hcp-input" placeholder="Query habitations, safe sites, or corridor status..." autocomplete="off" />
                <button id="hcp-send" title="Send Query">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
                    </svg>
                </button>
            </div>
        `;

        // Inject styles
        if (!document.getElementById('hcp-styles')) {
            const style = document.createElement('style');
            style.id = 'hcp-styles';
            style.textContent = this._getStyles();
            document.head.appendChild(style);
        }

        document.body.appendChild(this.container);

        // Floating Toggle button
        this.toggleBtn = document.createElement('button');
        this.toggleBtn.id = 'hcp-toggle';
        this.toggleBtn.innerHTML = `
            <span class="hcp-toggle-icon">💬</span>
            <span class="hcp-toggle-text">AI Analyst Chat</span>
        `;
        this.toggleBtn.title = 'Open BhuRakshak AI Hazard Chatbot';
        document.body.appendChild(this.toggleBtn);
    }

    _bindEvents() {
        const input = document.getElementById('hcp-input');
        const sendBtn = document.getElementById('hcp-send');
        const closeBtn = document.getElementById('hcp-close');
        const minimizeBtn = document.getElementById('hcp-minimize');
        const messagesContainer = document.getElementById('hcp-messages');

        sendBtn.addEventListener('click', () => this._handleSend());
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this._handleSend();
            }
        });

        closeBtn.addEventListener('click', () => this.close());
        minimizeBtn.addEventListener('click', () => this.minimize());
        this.toggleBtn.addEventListener('click', () => this.toggle());

        // Quick prompt clicks
        this.container.querySelectorAll('.hcp-quick-pill').forEach(pill => {
            pill.addEventListener('click', (e) => {
                const query = e.currentTarget.getAttribute('data-query');
                if (query) {
                    input.value = query;
                    this._handleSend();
                }
            });
        });

        // Event delegation for "Fly to Chunk" buttons
        messagesContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.hcp-btn-fly-chunk');
            if (btn) {
                const lng = parseFloat(btn.getAttribute('data-lng'));
                const lat = parseFloat(btn.getAttribute('data-lat'));
                const title = btn.getAttribute('data-title') || 'Intelligence Chunk';
                const zone = btn.getAttribute('data-zone') || 'gray';
                const snippet = btn.getAttribute('data-snippet') || '';
                const chunkId = btn.getAttribute('data-chunk-id') || '';
                this._flyToCoordinates(lng, lat, title, zone, snippet, chunkId);
            }
        });
    }

    async _fetchKnowledgeStatus() {
        try {
            const res = await fetch(`${this.apiBase}/api/chat/knowledge-status`);
            if (res.ok) {
                const data = await res.json();
                const badge = document.getElementById('hcp-kb-badge');
                if (badge && data.chunks_indexed) {
                    badge.textContent = `📚 ${data.chunks_indexed} Chunks Indexed (<1ms BM25 + Spatial)`;
                }
            }
        } catch (e) {
            // Non-critical background telemetry
        }
    }

    // ================================================================
    // Chat Logic
    // ================================================================

    async _handleSend() {
        const input = document.getElementById('hcp-input');
        const query = input.value.trim();
        if (!query) return;

        input.value = '';
        this._addMessage('user', query);
        this._addMessage('system', '<div class="hcp-typing">🧠 Ollama LLM (llama3.1:8b) is analyzing on CPU • Unlimited generation time<span class="hcp-dots">...</span></div>');

        try {
            const res = await fetch(`${this.apiBase}/api/chat/query`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });

            // Remove typing indicator
            this._removeLastSystemMessage();

            if (!res.ok) {
                this._addMessage('system', '⚠️ Backend service unavailable. Please check that FastAPI is running on port 8000.');
                return;
            }

            const data = await res.json();
            this._renderResponse(data);

            // Launch cinematic flythrough if flight plan exists and has waypoints
            if (data.flight_plan && data.flight_plan.length > 0) {
                this._startCinematicFlight(data.flight_plan);
            }

        } catch (err) {
            this._removeLastSystemMessage();
            this._addMessage('system', `⚠️ Connection error: ${err.message}. Please verify the server connection.`);
        }
    }

    _renderResponse(data) {
        let html = '<div class="hcp-response">';

        // 1. Narrative Analysis Section
        if (data.narrative) {
            const formatted = this._formatMarkdown(data.narrative);
            html += `<div class="hcp-narrative">${formatted}</div>`;
        }

        // 2. Flight Plan Banner
        if (data.flight_plan && data.flight_plan.length > 1) {
            html += `<div class="hcp-flight-banner">
                <div class="hcp-flight-info">
                    🎬 <strong>Cinematic 3D Flythrough</strong>: Touring ${data.flight_plan.length} Strategic Waypoints
                </div>
                <button class="hcp-stop-flight" onclick="document.dispatchEvent(new Event('hcp-stop-flight'))">⏹ Stop Tour</button>
            </div>`;
        }

        // 3. Grounded Atomic Knowledge Chunks Section
        if (data.cited_chunks && data.cited_chunks.length > 0) {
            html += `
            <div class="hcp-chunks-wrapper">
                <div class="hcp-chunks-header">
                    <span class="hcp-chunk-sec-icon">📚</span>
                    <span class="hcp-chunk-sec-title">Grounded Atomic Knowledge Chunks (${data.cited_chunks.length} Cited)</span>
                </div>
                <div class="hcp-chunks-grid">`;

            for (const chunk of data.cited_chunks) {
                const zone = chunk.zone || 'gray';
                const catLabel = {
                    'habitation_risk': '🏔️ Habitation Risk',
                    'disaster_history': '📜 Disaster Benchmark',
                    'safe_resettlement': '🛡️ Safe Resettlement',
                    'corridor_lifeline': '🛣️ Lifeline Corridor'
                }[chunk.category] || `📍 ${chunk.category}`;

                const relevancePct = Math.round((chunk.relevance_score || 0.8) * 100);

                let metricsBadges = '';
                if (chunk.metrics) {
                    if (chunk.metrics.factor_of_safety !== undefined) {
                        const fos = Number(chunk.metrics.factor_of_safety);
                        const fosClass = fos < 1.0 ? 'fos-fail' : (fos < 1.5 ? 'fos-warn' : 'fos-safe');
                        const fosDesc = fos < 1.0 ? 'Failure Limit' : (fos < 1.5 ? 'Marginally Stable' : 'Stable');
                        metricsBadges += `<span class="hcp-metric-pill ${fosClass}">FoS: ${fos.toFixed(2)} (${fosDesc})</span>`;
                    }
                    if (chunk.metrics.slope_deg !== undefined) {
                        metricsBadges += `<span class="hcp-metric-pill">Slope: ${chunk.metrics.slope_deg}°</span>`;
                    }
                    if (chunk.metrics.population !== undefined) {
                        metricsBadges += `<span class="hcp-metric-pill">Pop: ${chunk.metrics.population.toLocaleString()}</span>`;
                    }
                    if (chunk.metrics.safe_site_destination) {
                        metricsBadges += `<span class="hcp-metric-pill hcp-dest-pill">🎯 Reloc Target: ${chunk.metrics.safe_site_destination}</span>`;
                    }
                    if (chunk.metrics.event_year) {
                        metricsBadges += `<span class="hcp-metric-pill">Year: ${chunk.metrics.event_year}</span>`;
                    }
                }

                const snippetEsc = this._escapeHtml(chunk.snippet || '');
                const titleEsc = this._escapeHtml(chunk.title || '');

                html += `
                    <div class="hcp-chunk-card border-${zone}">
                        <div class="hcp-card-top">
                            <span class="hcp-card-cat">${catLabel}</span>
                            <span class="hcp-card-id">${chunk.chunk_id}</span>
                            <span class="hcp-badge-zone badge-${zone}">${zone.toUpperCase()}</span>
                            <span class="hcp-card-rel">${relevancePct}% match</span>
                        </div>
                        <div class="hcp-card-title">${titleEsc}</div>
                        <div class="hcp-card-snippet">${snippetEsc}</div>
                        ${metricsBadges ? `<div class="hcp-card-metrics">${metricsBadges}</div>` : ''}
                        <div class="hcp-card-footer">
                            <span class="hcp-card-coord">📍 ${chunk.coordinates[1].toFixed(3)}°N, ${chunk.coordinates[0].toFixed(3)}°E</span>
                            <button class="hcp-btn-fly-chunk"
                                data-lng="${chunk.coordinates[0]}"
                                data-lat="${chunk.coordinates[1]}"
                                data-title="${titleEsc}"
                                data-zone="${zone}"
                                data-snippet="${snippetEsc}"
                                data-chunk-id="${chunk.chunk_id}">
                                🎯 Fly to Chunk
                            </button>
                        </div>
                    </div>
                `;
            }

            html += `</div></div>`;
        }

        html += '</div>';
        this._addMessage('system', html);
    }

    _flyToCoordinates(lng, lat, title, zone, snippet, chunkId) {
        if (!this.map) return;

        // Smooth camera fly-to with dramatic 3D Himalayan angle
        this.map.flyTo({
            center: [lng, lat],
            zoom: 14.8,
            pitch: 62,
            bearing: 25,
            duration: 2200,
            essential: true
        });

        // Show floating HUD banner
        if (this.activePopup) {
            this.activePopup.remove();
        }

        const popup = document.createElement('div');
        popup.className = 'hcp-flight-popup';
        popup.innerHTML = `
            <div class="hcp-fp-header">
                <span class="hcp-fp-badge badge-${zone}">${zone.toUpperCase()}</span>
                <span>${title}</span>
                <span class="hcp-fp-id">${chunkId}</span>
            </div>
            <div class="hcp-fp-body">${snippet}</div>
        `;
        document.body.appendChild(popup);
        this.activePopup = popup;

        setTimeout(() => {
            if (popup.parentNode) popup.remove();
            if (this.activePopup === popup) this.activePopup = null;
        }, 5000);
    }

    // ================================================================
    // Cinematic MapLibre Flythrough
    // ================================================================

    async _startCinematicFlight(flightPlan) {
        if (this.isFlying) {
            this._stopFlight();
        }

        this.isFlying = true;
        this.flightAbortController = new AbortController();
        const signal = this.flightAbortController.signal;

        const stopHandler = () => this._stopFlight();
        document.addEventListener('hcp-stop-flight', stopHandler, { once: true });

        try {
            for (let i = 0; i < flightPlan.length; i++) {
                if (signal.aborted) break;

                const wp = flightPlan[i];

                await new Promise((resolve) => {
                    if (signal.aborted) { resolve(); return; }

                    this.map.flyTo({
                        center: [wp.lng, wp.lat],
                        zoom: wp.zoom || 14,
                        pitch: wp.pitch || 60,
                        bearing: wp.bearing || 0,
                        duration: wp.duration_ms || 3000,
                        essential: true
                    });

                    const onEnd = () => resolve();
                    this.map.once('moveend', onEnd);

                    setTimeout(() => {
                        this.map.off('moveend', onEnd);
                        resolve();
                    }, (wp.duration_ms || 3000) + 800);
                });

                if (signal.aborted) break;

                this._showFlightPopup(wp, i + 1, flightPlan.length);
                await this._sleep(wp.pause_ms || 2500, signal);
            }
        } catch (e) {
            // Flythrough ended or was cancelled
        }

        this.isFlying = false;
        document.removeEventListener('hcp-stop-flight', stopHandler);
    }

    _stopFlight() {
        if (this.flightAbortController) {
            this.flightAbortController.abort();
        }
        this.isFlying = false;
        const existing = document.querySelector('.hcp-flight-popup');
        if (existing) existing.remove();
    }

    _showFlightPopup(wp, index, total) {
        const existing = document.querySelector('.hcp-flight-popup');
        if (existing) existing.remove();

        const popup = document.createElement('div');
        popup.className = 'hcp-flight-popup';
        popup.innerHTML = `
            <div class="hcp-fp-header">
                📍 <span>${wp.name}</span>
                <span class="hcp-fp-count">Waypoint ${index} of ${total}</span>
            </div>
            <div class="hcp-fp-body">${wp.summary || ''}</div>
        `;
        document.body.appendChild(popup);

        setTimeout(() => {
            if (popup.parentNode) popup.remove();
        }, (wp.pause_ms || 2500) + 500);
    }

    _sleep(ms, signal) {
        return new Promise((resolve, reject) => {
            const timer = setTimeout(resolve, ms);
            if (signal) {
                signal.addEventListener('abort', () => {
                    clearTimeout(timer);
                    reject(new Error('aborted'));
                }, { once: true });
            }
        });
    }

    // ================================================================
    // Message Management
    // ================================================================

    _addMessage(type, content) {
        const container = document.getElementById('hcp-messages');
        const msg = document.createElement('div');
        msg.className = `hcp-msg hcp-msg-${type}`;

        if (type === 'user') {
            msg.innerHTML = `
                <div class="hcp-msg-content hcp-msg-user-content">${this._escapeHtml(content)}</div>
                <div class="hcp-msg-avatar">👤</div>
            `;
        } else {
            msg.innerHTML = `
                <div class="hcp-msg-avatar">🛡️</div>
                <div class="hcp-msg-content">${content}</div>
            `;
        }

        container.appendChild(msg);
        container.scrollTop = container.scrollHeight;
        this.messages.push({ type, content });
    }

    _removeLastSystemMessage() {
        const container = document.getElementById('hcp-messages');
        const msgs = container.querySelectorAll('.hcp-msg-system');
        if (msgs.length > 0) {
            const last = msgs[msgs.length - 1];
            if (last.querySelector('.hcp-typing')) {
                last.remove();
            }
        }
    }

    _escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    _formatMarkdown(text) {
        if (!text) return '';
        let s = this._escapeHtml(text);
        // Headers
        s = s.replace(/^### (.*$)/gim, '<h4 class="hcp-narrative-h4">$1</h4>');
        s = s.replace(/^## (.*$)/gim, '<h3 class="hcp-narrative-h3">$1</h3>');
        s = s.replace(/^# (.*$)/gim, '<h2 class="hcp-narrative-h2">$1</h2>');
        // Bold & Italic
        s = s.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
        s = s.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        s = s.replace(/\*(.*?)\*/g, '<em>$1</em>');
        // Zone dots
        s = s.replace(/🔴/g, '<span class="hcp-zone-dot hcp-red">●</span>');
        s = s.replace(/🟠/g, '<span class="hcp-zone-dot hcp-orange">●</span>');
        s = s.replace(/🟡/g, '<span class="hcp-zone-dot hcp-yellow">●</span>');
        s = s.replace(/🟢/g, '<span class="hcp-zone-dot hcp-green">●</span>');
        // List items
        s = s.replace(/^\s*[\-\*]\s+(.*)$/gim, '<div class="hcp-bullet-item"><span class="hcp-bullet-dot">›</span><span>$1</span></div>');
        s = s.replace(/^\s*(\d+)\.\s+(.*)$/gim, '<div class="hcp-num-item"><span class="hcp-num-badge">$1</span><span>$2</span></div>');
        // Paragraph spacers
        s = s.replace(/\n\n/g, '<div class="hcp-para-spacer"></div>');
        s = s.replace(/\n/g, '<br>');
        return s;
    }

    // ================================================================
    // Panel Visibility
    // ================================================================

    toggle() {
        this.isOpen ? this.close() : this.open();
    }

    open() {
        this.container.classList.add('hcp-open');
        this.container.classList.remove('hcp-minimized');
        this.toggleBtn.classList.add('hcp-hidden');
        this.isOpen = true;
        const input = document.getElementById('hcp-input');
        if (input) input.focus();
    }

    close() {
        this.container.classList.remove('hcp-open');
        this.toggleBtn.classList.remove('hcp-hidden');
        this.isOpen = false;
        this._stopFlight();
    }

    minimize() {
        this.container.classList.toggle('hcp-minimized');
    }

    // ================================================================
    // CSS Styles
    // ================================================================

    _getStyles() {
        return `
            #hazard-chat-panel {
                position: fixed;
                bottom: 24px;
                right: 24px;
                width: 480px;
                max-width: calc(100vw - 48px);
                max-height: 84vh;
                display: none;
                flex-direction: column;
                z-index: 9999;
                background: rgba(13, 17, 26, 0.92);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 16px;
                box-shadow: 0 16px 48px rgba(0, 0, 0, 0.65), 0 0 0 1px rgba(99, 102, 241, 0.2);
                backdrop-filter: blur(24px);
                -webkit-backdrop-filter: blur(24px);
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                overflow: hidden;
                transition: transform 0.25s ease, opacity 0.25s ease;
            }
            #hazard-chat-panel.hcp-open { display: flex; }
            #hazard-chat-panel.hcp-minimized .hcp-messages,
            #hazard-chat-panel.hcp-minimized .hcp-quick-prompts,
            #hazard-chat-panel.hcp-minimized .hcp-input-area { display: none; }

            .hcp-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px 16px;
                background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95));
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            }
            .hcp-title {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .hcp-main-title {
                color: #f1f5f9;
                font-size: 13.5px;
                font-weight: 700;
                letter-spacing: 0.3px;
            }
            .hcp-sub-title {
                color: #94a3b8;
                font-size: 10.5px;
                font-weight: 500;
            }
            .hcp-icon { font-size: 18px; }
            .hcp-controls { display: flex; gap: 6px; }
            .hcp-controls button {
                background: rgba(255, 255, 255, 0.08);
                border: none;
                color: #94a3b8;
                width: 28px;
                height: 28px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 12px;
                transition: all 0.2s;
            }
            .hcp-controls button:hover { background: rgba(255, 255, 255, 0.2); color: #fff; }

            .hcp-quick-prompts {
                display: flex;
                gap: 6px;
                padding: 8px 12px;
                overflow-x: auto;
                background: rgba(0, 0, 0, 0.25);
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                white-space: nowrap;
            }
            .hcp-quick-prompts::-webkit-scrollbar { height: 3px; }
            .hcp-quick-prompts::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 2px; }
            .hcp-quick-pill {
                background: rgba(99, 102, 241, 0.12);
                border: 1px solid rgba(99, 102, 241, 0.3);
                border-radius: 12px;
                color: #c7d2fe;
                font-size: 11px;
                font-weight: 500;
                padding: 4px 10px;
                cursor: pointer;
                transition: all 0.2s;
                flex-shrink: 0;
            }
            .hcp-quick-pill:hover {
                background: rgba(99, 102, 241, 0.3);
                border-color: rgba(99, 102, 241, 0.6);
                color: #ffffff;
            }

            .hcp-messages {
                flex: 1;
                overflow-y: auto;
                padding: 14px;
                max-height: 460px;
                scroll-behavior: smooth;
            }
            .hcp-messages::-webkit-scrollbar { width: 5px; }
            .hcp-messages::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 3px; }

            .hcp-msg {
                display: flex;
                gap: 10px;
                margin-bottom: 14px;
                animation: hcp-fadeIn 0.25s ease;
            }
            .hcp-msg-user { flex-direction: row-reverse; }

            .hcp-msg-avatar {
                width: 32px;
                height: 32px;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.08);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 15px;
                flex-shrink: 0;
            }

            .hcp-msg-content {
                background: rgba(30, 41, 59, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
                padding: 12px 14px;
                color: #e2e8f0;
                font-size: 12.5px;
                line-height: 1.55;
                max-width: 400px;
                word-wrap: break-word;
            }
            .hcp-msg-user-content {
                background: rgba(99, 102, 241, 0.25);
                border-color: rgba(99, 102, 241, 0.4);
                color: #f8fafc;
            }

            .hcp-input-area {
                display: flex;
                gap: 8px;
                padding: 12px;
                border-top: 1px solid rgba(255, 255, 255, 0.08);
                background: rgba(15, 23, 42, 0.85);
            }
            #hcp-input {
                flex: 1;
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 10px;
                padding: 10px 14px;
                color: #f1f5f9;
                font-size: 12.5px;
                outline: none;
                transition: border-color 0.2s;
            }
            #hcp-input:focus { border-color: rgba(99, 102, 241, 0.6); background: rgba(255, 255, 255, 0.08); }
            #hcp-input::placeholder { color: #64748b; }

            #hcp-send {
                background: linear-gradient(135deg, #4f46e5, #7c3aed);
                border: none;
                border-radius: 10px;
                width: 40px;
                height: 40px;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                color: white;
                transition: transform 0.15s, opacity 0.15s;
            }
            #hcp-send:hover { transform: scale(1.04); opacity: 0.95; }

            .hcp-typing {
                color: #94a3b8;
                font-style: italic;
                font-size: 12px;
            }
            .hcp-dots { animation: hcp-blink 1.2s infinite; }

            .hcp-zone-dot { font-size: 11px; margin-right: 2px; }
            .hcp-zone-dot.hcp-red { color: #ef4444; }
            .hcp-zone-dot.hcp-orange { color: #f97316; }
            .hcp-zone-dot.hcp-yellow { color: #eab308; }
            .hcp-zone-dot.hcp-green { color: #10b981; }

            .hcp-narrative { 
                margin-bottom: 12px; 
                color: #f1f5f9; 
                font-size: 13px;
                line-height: 1.55;
            }
            .hcp-narrative-h2 {
                font-size: 14px;
                font-weight: 700;
                color: #38bdf8;
                margin: 10px 0 6px 0;
                letter-spacing: 0.3px;
                border-bottom: 1px solid rgba(56, 189, 248, 0.2);
                padding-bottom: 3px;
            }
            .hcp-narrative-h3 {
                font-size: 13px;
                font-weight: 700;
                color: #93c5fd;
                margin: 8px 0 4px 0;
                letter-spacing: 0.2px;
            }
            .hcp-narrative-h4 {
                font-size: 12.5px;
                font-weight: 600;
                color: #cbd5e1;
                margin: 6px 0 3px 0;
            }
            .hcp-bullet-item {
                display: flex;
                align-items: flex-start;
                gap: 6px;
                margin: 3px 0;
                color: #e2e8f0;
            }
            .hcp-bullet-dot {
                color: #38bdf8;
                font-weight: 700;
                line-height: 1.2;
            }
            .hcp-num-item {
                display: flex;
                align-items: flex-start;
                gap: 6px;
                margin: 3px 0;
                color: #e2e8f0;
            }
            .hcp-num-badge {
                display: inline-block;
                min-width: 16px;
                height: 16px;
                line-height: 16px;
                text-align: center;
                background: rgba(56, 189, 248, 0.2);
                color: #38bdf8;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                margin-top: 2px;
            }
            .hcp-para-spacer {
                height: 8px;
            }

            .hcp-flight-banner {
                background: rgba(99, 102, 241, 0.15);
                border: 1px solid rgba(99, 102, 241, 0.35);
                border-radius: 10px;
                padding: 10px 12px;
                margin: 10px 0;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 8px;
            }
            .hcp-flight-info {
                font-size: 12px;
                color: #c7d2fe;
            }
            .hcp-stop-flight {
                background: rgba(239, 68, 68, 0.2);
                border: 1px solid rgba(239, 68, 68, 0.4);
                color: #fca5a5;
                border-radius: 6px;
                padding: 4px 10px;
                cursor: pointer;
                font-size: 11px;
                font-weight: 600;
                transition: all 0.2s;
            }
            .hcp-stop-flight:hover { background: rgba(239, 68, 68, 0.4); }

            /* Chunks Layout */
            .hcp-chunks-wrapper {
                margin-top: 14px;
                border-top: 1px solid rgba(255, 255, 255, 0.08);
                padding-top: 12px;
            }
            .hcp-chunks-header {
                display: flex;
                align-items: center;
                gap: 6px;
                margin-bottom: 10px;
            }
            .hcp-chunk-sec-icon { font-size: 15px; }
            .hcp-chunk-sec-title {
                font-size: 12px;
                font-weight: 700;
                color: #e2e8f0;
                letter-spacing: 0.2px;
            }
            .hcp-chunks-grid {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }

            .hcp-chunk-card {
                background: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 10px 12px;
                transition: border-color 0.2s, transform 0.15s;
            }
            .hcp-chunk-card:hover {
                border-color: rgba(99, 102, 241, 0.5);
                transform: translateY(-1px);
            }
            .hcp-chunk-card.border-red { border-left: 3px solid #ef4444; }
            .hcp-chunk-card.border-orange { border-left: 3px solid #f97316; }
            .hcp-chunk-card.border-yellow { border-left: 3px solid #eab308; }
            .hcp-chunk-card.border-green { border-left: 3px solid #10b981; }

            .hcp-card-top {
                display: flex;
                align-items: center;
                gap: 6px;
                margin-bottom: 6px;
                flex-wrap: wrap;
            }
            .hcp-card-cat {
                font-size: 10.5px;
                font-weight: 600;
                color: #94a3b8;
            }
            .hcp-card-id {
                font-size: 10px;
                font-family: monospace;
                background: rgba(255, 255, 255, 0.08);
                padding: 2px 6px;
                border-radius: 4px;
                color: #cbd5e1;
            }
            .hcp-badge-zone {
                font-size: 9.5px;
                font-weight: 700;
                padding: 2px 6px;
                border-radius: 4px;
                letter-spacing: 0.3px;
            }
            .hcp-badge-zone.badge-red { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
            .hcp-badge-zone.badge-orange { background: rgba(249, 115, 22, 0.2); color: #fdba74; }
            .hcp-badge-zone.badge-yellow { background: rgba(234, 179, 8, 0.2); color: #fde047; }
            .hcp-badge-zone.badge-green { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; }

            .hcp-card-rel {
                margin-left: auto;
                font-size: 10px;
                color: #6366f1;
                font-weight: 600;
            }

            .hcp-card-title {
                font-size: 12.5px;
                font-weight: 700;
                color: #f8fafc;
                margin-bottom: 4px;
            }
            .hcp-card-snippet {
                font-size: 11.5px;
                color: #cbd5e1;
                line-height: 1.45;
                margin-bottom: 8px;
            }

            .hcp-card-metrics {
                display: flex;
                flex-wrap: wrap;
                gap: 5px;
                margin-bottom: 8px;
            }
            .hcp-metric-pill {
                font-size: 10px;
                padding: 2px 8px;
                border-radius: 6px;
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: #94a3b8;
            }
            .hcp-metric-pill.fos-fail { border-color: rgba(239, 68, 68, 0.5); color: #fca5a5; background: rgba(239, 68, 68, 0.12); }
            .hcp-metric-pill.fos-warn { border-color: rgba(249, 115, 22, 0.5); color: #fdba74; background: rgba(249, 115, 22, 0.12); }
            .hcp-metric-pill.fos-safe { border-color: rgba(16, 185, 129, 0.5); color: #6ee7b7; background: rgba(16, 185, 129, 0.12); }
            .hcp-metric-pill.hcp-dest-pill { border-color: rgba(16, 185, 129, 0.4); color: #34d399; }

            .hcp-card-footer {
                display: flex;
                align-items: center;
                justify-content: space-between;
                border-top: 1px solid rgba(255, 255, 255, 0.06);
                padding-top: 6px;
            }
            .hcp-card-coord {
                font-size: 10.5px;
                color: #64748b;
            }
            .hcp-btn-fly-chunk {
                background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(124, 58, 237, 0.25));
                border: 1px solid rgba(99, 102, 241, 0.4);
                color: #c7d2fe;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
            }
            .hcp-btn-fly-chunk:hover {
                background: linear-gradient(135deg, #4f46e5, #7c3aed);
                color: #ffffff;
                transform: scale(1.03);
            }

            /* Toggle Button */
            #hcp-toggle {
                position: fixed;
                bottom: 24px;
                right: 24px;
                z-index: 9998;
                background: linear-gradient(135deg, #4f46e5, #7c3aed);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 30px;
                padding: 10px 18px;
                cursor: pointer;
                color: white;
                box-shadow: 0 8px 24px rgba(79, 70, 229, 0.4);
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 13px;
                font-weight: 600;
                transition: all 0.25s ease;
            }
            #hcp-toggle:hover {
                transform: translateY(-2px);
                box-shadow: 0 12px 28px rgba(79, 70, 229, 0.6);
            }
            #hcp-toggle.hcp-hidden { display: none; }

            /* Flight Popup HUD */
            .hcp-flight-popup {
                position: fixed;
                top: 76px;
                left: 50%;
                transform: translateX(-50%);
                z-index: 10002;
                background: rgba(15, 23, 42, 0.95);
                border: 1px solid rgba(99, 102, 241, 0.4);
                border-radius: 12px;
                padding: 14px 20px;
                color: #f1f5f9;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                box-shadow: 0 12px 36px rgba(0, 0, 0, 0.6);
                backdrop-filter: blur(16px);
                max-width: 520px;
                width: calc(100vw - 40px);
                animation: hcp-slideDown 0.35s ease;
            }
            .hcp-fp-header {
                font-size: 14px;
                font-weight: 700;
                margin-bottom: 6px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .hcp-fp-id {
                margin-left: auto;
                font-size: 10px;
                font-family: monospace;
                color: #94a3b8;
            }
            .hcp-fp-count {
                margin-left: auto;
                font-size: 11px;
                color: #94a3b8;
                font-weight: 400;
            }
            .hcp-fp-body {
                font-size: 12px;
                color: #cbd5e1;
                line-height: 1.5;
            }
            .hcp-fp-badge {
                font-size: 9.5px;
                font-weight: 700;
                padding: 2px 6px;
                border-radius: 4px;
            }

            @keyframes hcp-fadeIn {
                from { opacity: 0; transform: translateY(6px); }
                to { opacity: 1; transform: translateY(0); }
            }
            @keyframes hcp-blink {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.3; }
            }
            @keyframes hcp-slideDown {
                from { opacity: 0; transform: translate(-50%, -16px); }
                to { opacity: 1; transform: translate(-50%, 0); }
            }

            @media (max-width: 560px) {
                #hazard-chat-panel { width: calc(100vw - 20px); right: 10px; bottom: 10px; }
            }
        `;
    }
}

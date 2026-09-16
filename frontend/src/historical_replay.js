/**
 * HazardShield — Historical Disaster Time-Machine & Ground-Truth Validation
 * Replays famous disaster events with before-and-after decision audits.
 */

export class HistoricalReplayManager {
    constructor(mapInstance, onTriggerSimulation) {
        this.map = mapInstance;
        this.onTriggerSimulation = onTriggerSimulation;
        this.modal = document.getElementById('history-replay-modal');
        this.currentScenario = null;
        this.currentStepIdx = 0;
        this.scenarios = [];
        this.init();
    }

    async init() {
        this.initListeners();
        try {
            const resp = await fetch('/api/disaster-simulations');
            const data = await resp.json();
            this.scenarios = data.scenarios || [];
            this.populateScenarioDropdown();
        } catch (err) {
            console.error('Failed to load historical simulations:', err);
        }
    }

    initListeners() {
        const btnOpen = document.getElementById('btn-history-replay');
        const btnClose = document.getElementById('btn-close-replay-modal');
        const selectScenario = document.getElementById('replay-scenario-select');
        const btnStepPrev = document.getElementById('replay-btn-prev');
        const btnStepNext = document.getElementById('replay-btn-next');
        const btnAutoPlay = document.getElementById('replay-btn-play');

        if (btnOpen) {
            btnOpen.addEventListener('click', () => this.open());
        }
        if (btnClose) {
            btnClose.addEventListener('click', () => this.close());
        }
        if (selectScenario) {
            selectScenario.addEventListener('change', (e) => this.selectScenario(e.target.value));
        }
        if (btnStepPrev) {
            btnStepPrev.addEventListener('click', () => this.prevStep());
        }
        if (btnStepNext) {
            btnStepNext.addEventListener('click', () => this.nextStep());
        }
        if (btnAutoPlay) {
            btnAutoPlay.addEventListener('click', () => this.toggleAutoPlay());
        }
    }

    populateScenarioDropdown() {
        const select = document.getElementById('replay-scenario-select');
        if (!select) return;

        select.innerHTML = this.scenarios.map((s, idx) => `
            <option value="${s.id}" ${idx === 0 ? 'selected' : ''}>${s.title} (${s.date})</option>
        `).join('');

        if (this.scenarios.length > 0) {
            this.selectScenario(this.scenarios[0].id);
        }
    }

    open() {
        if (!this.modal) return;
        this.modal.classList.remove('hidden');
        if (this.currentScenario) {
            this.applyScenario(this.currentScenario);
        }
    }

    close() {
        if (!this.modal) return;
        this.modal.classList.add('hidden');
        this.stopAutoPlay();
    }

    selectScenario(id) {
        const scenario = this.scenarios.find(s => s.id === id);
        if (!scenario) return;
        this.currentScenario = scenario;
        this.currentStepIdx = 0;
        this.applyScenario(scenario);
    }

    applyScenario(scenario) {
        // Fly map to the disaster epicenter
        if (this.map && scenario.center) {
            this.map.flyTo({
                center: scenario.center,
                zoom: scenario.zoom || 11.5,
                pitch: 58,
                bearing: -20,
                duration: 2500
            });
        }
        this.renderStep();
    }

    renderStep() {
        if (!this.currentScenario) return;
        const scenario = this.currentScenario;
        const timeline = scenario.timeline || [];
        const step = timeline[this.currentStepIdx] || {};

        // Update step UI
        const stepBadge = document.getElementById('replay-step-badge');
        const stepTitle = document.getElementById('replay-step-title');
        const stepDesc = document.getElementById('replay-step-desc');
        const progressBar = document.getElementById('replay-progress-fill');

        if (stepBadge) stepBadge.textContent = step.step || `Step ${this.currentStepIdx + 1}`;
        if (stepTitle) stepTitle.textContent = step.title || '';
        if (stepDesc) stepDesc.textContent = step.desc || '';
        if (progressBar) {
            const pct = ((this.currentStepIdx) / Math.max(1, timeline.length - 1)) * 100;
            progressBar.style.width = `${pct}%`;
        }

        // Apply physical simulation to map based on step
        if (this.onTriggerSimulation) {
            let rainVal = 20;
            if (this.currentStepIdx === 1) rainVal = scenario.rainfall_mm * 0.5;
            if (this.currentStepIdx >= 2) rainVal = scenario.rainfall_mm;
            this.onTriggerSimulation(rainVal);
        }

        // Render comparative audit card
        this.renderComparativeCard(scenario);
    }

    renderComparativeCard(scenario) {
        const container = document.getElementById('replay-comparison-container');
        if (!container) return;

        const hist = scenario.historical_reactive || {};
        const ai = scenario.hazardshield_proactive || {};

        container.innerHTML = `
            <div class="comparison-grid">
                <div class="comp-card reactive">
                    <div class="comp-badge">Historical Reality (Reactive Response)</div>
                    <h4>Without HazardShield</h4>
                    <div class="comp-metric-row">
                        <span class="m-label">Evacuation Timing:</span>
                        <span class="m-val text-danger">${hist.evacuation_timing}</span>
                    </div>
                    <div class="comp-metric-row">
                        <span class="m-label">Reported Casualties:</span>
                        <span class="m-val text-danger">${hist.casualties} fatalities</span>
                    </div>
                    <div class="comp-metric-row">
                        <span class="m-label">Trapped / Missing:</span>
                        <span class="m-val text-warning">${hist.injured_trapped} citizens</span>
                    </div>
                    <div class="comp-metric-row">
                        <span class="m-label">Emergency Relief Cost:</span>
                        <span class="m-val">₹${hist.infrastructure_loss_cr} Crores</span>
                    </div>
                </div>

                <div class="comp-card proactive">
                    <div class="comp-badge safe">HazardShield AI (Proactive Decision)</div>
                    <h4>With Intelligent Platform</h4>
                    <div class="comp-metric-row">
                        <span class="m-label">Advance Early Warning:</span>
                        <span class="m-val text-safe">${ai.alert_lead_time_hours} Hours Prior</span>
                    </div>
                    <div class="comp-metric-row">
                        <span class="m-label">Pre-Emptive Evacuation:</span>
                        <span class="m-val text-safe">${ai.pre_disaster_evacuated_pop.toLocaleString()} Citizens Relocated</span>
                    </div>
                    <div class="comp-metric-row">
                        <span class="m-label">Validated Safe Site:</span>
                        <span class="m-val text-safe">${ai.assigned_safe_site}</span>
                    </div>
                    <div class="comp-metric-row">
                        <span class="m-label">Lives Saved in Planned Zone:</span>
                        <span class="m-val text-safe highlight">100% of Zone (${ai.potential_lives_saved} Lives)</span>
                    </div>
                </div>
            </div>
        `;
    }

    nextStep() {
        if (!this.currentScenario) return;
        const len = (this.currentScenario.timeline || []).length;
        if (this.currentStepIdx < len - 1) {
            this.currentStepIdx++;
            this.renderStep();
        } else {
            this.stopAutoPlay();
        }
    }

    prevStep() {
        if (this.currentStepIdx > 0) {
            this.currentStepIdx--;
            this.renderStep();
        }
    }

    toggleAutoPlay() {
        const btn = document.getElementById('replay-btn-play');
        if (this.playInterval) {
            this.stopAutoPlay();
        } else {
            if (btn) btn.innerHTML = '<span>⏸ Pause Replay</span>';
            this.playInterval = setInterval(() => {
                const len = (this.currentScenario?.timeline || []).length;
                if (this.currentStepIdx < len - 1) {
                    this.nextStep();
                } else {
                    this.stopAutoPlay();
                }
            }, 3500);
        }
    }

    stopAutoPlay() {
        if (this.playInterval) {
            clearInterval(this.playInterval);
            this.playInterval = null;
            const btn = document.getElementById('replay-btn-play');
            if (btn) btn.innerHTML = '<span>▶ Auto Replay</span>';
        }
    }
}

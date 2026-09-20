/**
 * HazardShield — State DM Relocation Report & Official PDF Generator
 * Uttarakhand State Disaster Management Authority (USDMA) Decision Brief
 */

export class DMReportManager {
    constructor() {
        this.modal = document.getElementById('dm-report-modal');
        this.container = document.getElementById('dm-report-content');
        this.initListeners();
    }

    initListeners() {
        const btnOpen = document.getElementById('btn-dm-report');
        const btnClose = document.getElementById('btn-close-dm-modal');
        const btnPdf = document.getElementById('btn-export-dm-pdf');
        const btnPrint = document.getElementById('btn-print-dm');
        const btnCsv = document.getElementById('btn-export-dm-csv');

        if (btnOpen) {
            btnOpen.addEventListener('click', () => this.openReport());
        }
        if (btnClose) {
            btnClose.addEventListener('click', () => this.closeReport());
        }
        if (btnPdf) {
            btnPdf.addEventListener('click', () => this.exportPDF());
        }
        if (btnPrint) {
            btnPrint.addEventListener('click', () => window.print());
        }
        if (btnCsv) {
            btnCsv.addEventListener('click', () => this.exportCSV());
        }
    }

    openReport() {
        if (!this.modal) return;
        this.renderReport();
        this.modal.classList.remove('hidden');
    }

    closeReport() {
        if (!this.modal) return;
        this.modal.classList.add('hidden');
    }

    async renderReport() {
        if (!this.container) return;
        this.container.innerHTML = `<div class="report-loading"><div class="spinner"></div><p>Compiling Official Relocation Plan & Carrying Capacity Ledger...</p></div>`;

        try {
            const resp = await fetch('/api/dm-action-plan');
            const data = await resp.json();
            this.currentData = data;
            this.generateHTML(data);
        } catch (err) {
            console.error('Failed to load DM action plan:', err);
            this.container.innerHTML = `<div class="error-msg">Failed to load official report. Check backend server connection.</div>`;
        }
    }

    generateHTML(data) {
        const exec = data.executive_summary || {};
        const matrix = data.priorities_matrix || [];
        const actions = data.action_framework || [];

        const rows = matrix.map((p, idx) => `
            <tr class="priority-row ${p.timeline}">
                <td class="cell-rank">#${p.rank || idx + 1}</td>
                <td class="cell-name">
                    <strong>${p.village_name}</strong>
                    <span class="sub-text">${p.tehsil} Tehsil</span>
                </td>
                <td class="cell-zone">
                    <span class="badge badge-${p.current_zone}">${p.current_zone.toUpperCase()}</span>
                </td>
                <td class="cell-pop">${p.population ? p.population.toLocaleString() : '—'}</td>
                <td class="cell-score">
                    <div class="score-pill ${p.timeline}">VI: ${p.vulnerability_index}</div>
                </td>
                <td class="cell-timeline">
                    <span class="timeline-tag ${p.timeline}">${p.urgency_level || p.timeline.replace('_', ' ')}</span>
                </td>
                <td class="cell-safe">
                    ${p.suggested_safe_zone ? `
                        <strong>Safe Site Alpha-${p.suggested_safe_zone.site_id || '1'}</strong>
                        <span class="sub-text">${p.relocation_distance_km} km away • Buffer: +${(p.suggested_safe_zone.remaining_capacity_headroom || 0).toLocaleString()}</span>
                    ` : 'In Assessment'}
                </td>
                <td class="cell-rationale">
                    <p class="rationale-text">${p.defensible_rationale || 'Hazard assessment based on terrain slope and historical event proximity.'}</p>
                    <p class="action-text"><strong>DM Order:</strong> ${p.recommended_action || 'Execute planned evacuation and relocation.'}</p>
                </td>
            </tr>
        `).join('');

        const frameworkCards = actions.map(a => `
            <div class="framework-card">
                <div class="framework-header">
                    <h4>${a.phase}</h4>
                    <span class="statutory-badge">${a.statutory_mandate}</span>
                </div>
                <p class="framework-directive">${a.directive}</p>
            </div>
        `).join('');

        this.container.innerHTML = `
            <div class="official-report-document" id="printable-dm-document">
                <!-- Official Government Header -->
                <div class="gov-header">
                    <div class="gov-emblem">🏛️</div>
                    <div class="gov-titles">
                        <h2>GOVERNMENT OF INDIA • MINISTRY OF HOME AFFAIRS</h2>
                        <h3>DISASTER MANAGEMENT DIVISION & USDMA UTTARKASHI</h3>
                        <p class="gov-sub">National Relocation Priority Matrix & Carrying Capacity Allocation Order</p>
                        <div class="doc-meta">
                            <span><strong>ORDER NO:</strong> MHA-USDMA/UTK/RELOC-2026/09</span>
                            <span><strong>DATE:</strong> ${data.date_generated || 'September 2026'}</span>
                            <span><strong>STATUTE:</strong> SECTIONS 30 & 34, DM ACT 2005</span>
                            <span><strong>STATUS:</strong> EXECUTIVE STATUTORY DIRECTIVE</span>
                        </div>
                    </div>
                </div>

                <div class="doc-divider"></div>

                <!-- Executive Briefing Stats -->
                <div class="report-section">
                    <h3 class="section-title">1. Executive Overview, Carrying Capacity Balance & SDRF Rehabilitation Budget</h3>
                    <div class="report-stats-grid">
                        <div class="r-stat-box danger">
                            <span class="r-label">Habitations for Relocation</span>
                            <span class="r-value">${exec.villages_requiring_relocation || matrix.length}</span>
                            <span class="r-sub">Immediate: ${exec.timeline_breakdown?.immediate || 0} • Short-Term: ${exec.timeline_breakdown?.short_term || 0}</span>
                        </div>
                        <div class="r-stat-box warning">
                            <span class="r-label">Citizens at Critical Risk</span>
                            <span class="r-value">${(exec.population_at_critical_risk || 0).toLocaleString()}</span>
                            <span class="r-sub">${(exec.total_affected_households || 0).toLocaleString()} Affected Families</span>
                        </div>
                        <div class="r-stat-box safe">
                            <span class="r-label">Total Safe Sites Carrying Capacity</span>
                            <span class="r-value">${(exec.total_safe_carrying_capacity || 0).toLocaleString()}</span>
                            <span class="r-sub">Across ${exec.safe_sites_available || 0} Verified Terraces</span>
                        </div>
                        <div class="r-stat-box primary">
                            <span class="r-label">SDRF Financial Package</span>
                            <span class="r-value">₹${exec.estimated_sdrf_rehab_package_cr || '43.3'} Cr</span>
                            <span class="r-sub">₹7.0L / Household Norm</span>
                        </div>
                    </div>
                </div>

                <!-- Phased Implementation Framework -->
                <div class="report-section">
                    <h3 class="section-title">2. Statutory Framework & Phased Resettlement Protocol</h3>
                    <div class="framework-grid">
                        ${frameworkCards}
                    </div>
                </div>

                <!-- Village Relocation Priority Matrix -->
                <div class="report-section">
                    <div class="section-header-flex">
                        <h3 class="section-title">3. Prioritized Relocation Action Matrix & Defensible Rationales</h3>
                        <span class="doc-badge">Sorted by Multi-Hazard Vulnerability Index (VI)</span>
                    </div>
                    <div class="report-table-wrapper">
                        <table class="report-table">
                            <thead>
                                <tr>
                                    <th>Rank</th>
                                    <th>Habitation</th>
                                    <th>Zone</th>
                                    <th>Pop.</th>
                                    <th>Vulnerability</th>
                                    <th>Urgency Tier</th>
                                    <th>Destination Safe Site</th>
                                    <th>Defensible Rationale & DM Action Order</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${rows}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Official Signoff Footer -->
                <div class="doc-footer" style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-top: 30px; border-top: 1px solid rgba(255,255,255,0.15); padding-top: 20px;">
                    <div class="signoff-box">
                        <p class="signature-line">___________________________</p>
                        <p><strong>District Magistrate & Chairman, DDMA</strong></p>
                        <p>District Uttarkashi, Uttarakhand</p>
                    </div>
                    <div class="signoff-box">
                        <p class="signature-line">___________________________</p>
                        <p><strong>Chief Executive Officer</strong></p>
                        <p>Uttarakhand State Disaster Management Authority (USDMA)</p>
                    </div>
                    <div class="signoff-box">
                        <p class="signature-line">___________________________</p>
                        <p><strong>Joint Secretary (Disaster Management)</strong></p>
                        <p>Ministry of Home Affairs, Government of India</p>
                    </div>
                </div>
            </div>
        `;
    }

    exportPDF() {
        const element = document.getElementById('printable-dm-document');
        if (!element) return;

        const opt = {
            margin: [8, 8, 8, 8],
            filename: `Uttarkashi_DM_Relocation_Action_Plan_2026.pdf`,
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { scale: 2, useCORS: true },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'landscape' }
        };

        if (window.html2pdf) {
            window.html2pdf().set(opt).from(element).save();
        } else {
            window.print();
        }
    }

    exportCSV() {
        if (!this.currentData || !this.currentData.priorities_matrix) return;
        const matrix = this.currentData.priorities_matrix;
        
        let csv = 'Rank,Village,Tehsil,Zone,Population,VulnerabilityIndex,Timeline,SafeSiteID,DistanceKm,DefensibleRationale,RecommendedAction\n';
        
        matrix.forEach(p => {
            const safeId = p.suggested_safe_zone ? `Alpha-${p.suggested_safe_zone.site_id}` : 'None';
            const dist = p.relocation_distance_km || '';
            const rationale = `"${(p.defensible_rationale || '').replace(/"/g, '""')}"`;
            const action = `"${(p.recommended_action || '').replace(/"/g, '""')}"`;
            csv += `${p.rank},"${p.village_name}","${p.tehsil}",${p.current_zone},${p.population},${p.vulnerability_index},${p.timeline},${safeId},${dist},${rationale},${action}\n`;
        });

        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.setAttribute('download', 'Uttarkashi_Relocation_Priorities_Matrix.csv');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}

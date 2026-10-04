/**
 * Marcbantu Africa — Decisions page.
 * Wires the 8 calculators to the API.
 */
(function () {
    'use strict';
    if (!window.Auth?.requireLogin()) return;

    const { $, $$, Fmt, Toast, Modal } = window.UI;

    // ============================================================
    // GENERIC TOOL RUNNER
    // ============================================================
    async function runTool(toolName, apiCall, payload, resultContainerId) {
        const container = document.getElementById(resultContainerId);
        if (container) {
            container.style.display = 'block';
            container.innerHTML = '<div style="text-align:center; padding:20px;"><i class="fas fa-spinner fa-spin"></i> Calculating...</div>';
        }

        const result = await apiCall(payload);
        if (!result.ok) {
            if (container) container.innerHTML = `<div style="color:#c0392b; padding:16px;">${result.error}</div>`;
            Toast.error(result.error || 'Calculation failed');
            return null;
        }

        return result.data;
    }

    // ============================================================
    // BREAK-EVEN
    // ============================================================
    async function calcBreakeven() {
        const payload = {
            fixed_costs: parseFloat($('#be-fixed')?.value || 0),
            variable_cost_per_unit: parseFloat($('#be-var')?.value || 0),
            price_per_unit: parseFloat($('#be-price')?.value || 0),
            unit: $('#be-unit')?.value || 'units',
        };
        const d = await runTool('breakeven', Api.breakeven, payload, 'be-result');
        if (!d) return;

        $('#be-result').innerHTML = `
            <div style="background:#e8f0e1; border-left:5px solid #d4a017; border-radius:12px; padding:16px;">
                <h4 style="margin:0 0 12px; color:#1a3c2e;">Break-Even Result</h4>
                <div style="display:grid; gap:8px; font-size:.95rem;">
                    <div style="display:flex; justify-content:space-between; border-bottom:1px dashed #cbd5cd; padding-bottom:6px;">
                        <span style="color:#4a5a4a;">Contribution margin / unit</span>
                        <strong style="color:#1a3c2e;">${Fmt.currency(d.contribution_margin_per_unit)}</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between; border-bottom:1px dashed #cbd5cd; padding-bottom:6px;">
                        <span style="color:#4a5a4a;">Margin %</span>
                        <strong style="color:#1a3c2e;">${d.contribution_margin_percent}%</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between; border-bottom:1px dashed #cbd5cd; padding-bottom:6px;">
                        <span style="color:#4a5a4a;">Break-even units</span>
                        <strong style="color:#1a3c2e;">${Fmt.number(d.breakeven_units, 1)} ${d.unit}</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span style="color:#4a5a4a;">Break-even revenue</span>
                        <strong style="color:#2e7d32; font-size:1.1rem;">${Fmt.currency(d.breakeven_revenue)}</strong>
                    </div>
                </div>
                <p style="margin:12px 0 0; font-size:.9rem; color:#4a5a4a; font-style:italic;">${d.interpretation || ''}</p>
            </div>
            ${d.price_scenarios?.length ? `
                <div style="margin-top:16px;">
                    <h5 style="color:#1a3c2e; font-size:.9rem; margin:0 0 8px;">Price Sensitivity</h5>
                    <table style="width:100%; font-size:.85rem; border-collapse:collapse;">
                        <thead><tr style="background:#f5f8f2;"><th style="text-align:left; padding:6px;">Price Δ</th><th style="text-align:right; padding:6px;">New Price</th><th style="text-align:right; padding:6px;">New BE</th></tr></thead>
                        <tbody>
                            ${d.price_scenarios.map((s) => `
                                <tr><td style="padding:6px;">${s.price_change_percent > 0 ? '+' : ''}${s.price_change_percent}%</td>
                                <td style="padding:6px; text-align:right;">${Fmt.currency(s.new_price)}</td>
                                <td style="padding:6px; text-align:right;">${Fmt.number(s.new_breakeven_units, 1)}</td></tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>` : ''}
        `;
    }

    // ============================================================
    // GROSS MARGIN
    // ============================================================
    async function calcGrossMargin() {
        const payload = {
            revenue: parseFloat($('#gm-rev')?.value || 0),
            variable_costs: parseFloat($('#gm-cost')?.value || 0),
        };
        const d = await runTool('gross-margin', Api.grossMargin, payload, 'gm-result');
        if (!d) return;

        const color = d.gross_margin >= 0 ? '#2e7d32' : '#c0392b';
        $('#gm-result').innerHTML = `
            <div style="background:#e8f0e1; border-left:5px solid #d4a017; border-radius:12px; padding:16px;">
                <h4 style="margin:0 0 12px; color:#1a3c2e;">Gross Margin</h4>
                <div style="font-size:2rem; font-weight:800; color:${color};">${Fmt.currency(d.gross_margin)}</div>
                <div style="font-size:.9rem; color:#4a5a4a;">${d.gross_margin_percent}% margin · Rating: <strong>${d.rating}</strong></div>
            </div>
        `;
    }

    // ============================================================
    // MARGINAL
    // ============================================================
    async function calcMarginal() {
        const payload = {
            additional_revenue: parseFloat($('#ma-rev')?.value || 0),
            additional_cost: parseFloat($('#ma-cost')?.value || 0),
        };
        const d = await runTool('marginal', Api.marginalAnalysis, payload, 'ma-result');
        if (!d) return;

        const ok = d.marginal_profit > 0;
        $('#ma-result').innerHTML = `
            <div style="background:${ok ? '#e8f0e1' : '#fde8e8'}; border-left:5px solid ${ok ? '#2e7d32' : '#c0392b'}; border-radius:12px; padding:16px;">
                <h4 style="margin:0 0 8px; color:#1a3c2e;">${d.recommendation}</h4>
                <p style="margin:0 0 12px; color:#4a5a4a; font-size:.92rem;">${d.reason}</p>
                <div style="font-size:1.6rem; font-weight:800; color:${ok ? '#2e7d32' : '#c0392b'};">${Fmt.currency(d.marginal_profit)}</div>
                <div style="font-size:.85rem; color:#4a5a4a;">Marginal profit per additional unit</div>
            </div>
        `;
    }

    // ============================================================
    // LOAN
    // ============================================================
    async function calcLoan() {
        const payload = {
            loan_amount: parseFloat($('#la-amt')?.value || 0),
            annual_rate: parseFloat($('#la-rate')?.value || 0),
            term_months: parseInt($('#la-term')?.value || 12),
            monthly_profit: parseFloat($('#la-profit')?.value || 0),
        };
        const d = await runTool('loan', Api.loanAffordability, payload, 'la-result');
        if (!d) return;

        const color = d.verdict === 'Safe' ? '#2e7d32' : d.verdict === 'Manageable' ? '#b8860b' : '#c0392b';
        $('#la-result').innerHTML = `
            <div style="background:#fff; border:1px solid #e2e8dd; border-left:5px solid ${color}; border-radius:12px; padding:16px;">
                <h4 style="margin:0 0 4px; color:#1a3c2e;">${d.verdict}</h4>
                <p style="margin:0 0 12px; color:#4a5a4a; font-size:.9rem;">${d.verdict_detail}</p>
                <div style="display:grid; gap:6px; font-size:.9rem;">
                    <div style="display:flex; justify-content:space-between;"><span style="color:#4a5a4a;">Monthly payment</span><strong>${Fmt.currency(d.monthly_payment)}</strong></div>
                    <div style="display:flex; justify-content:space-between;"><span style="color:#4a5a4a;">Total interest</span><strong>${Fmt.currency(d.total_interest)}</strong></div>
                    <div style="display:flex; justify-content:space-between;"><span style="color:#4a5a4a;">% of profit</span><strong style="color:${color};">${d.percent_of_monthly_profit}%</strong></div>
                </div>
            </div>
        `;
    }

    // ============================================================
    // PAYBACK
    // ============================================================
    async function calcPayback() {
        const payload = {
            investment_cost: parseFloat($('#pb-cost')?.value || 0),
            additional_annual_income: parseFloat($('#pb-income')?.value || 0),
        };
        const d = await runTool('payback', Api.payback, payload, 'pb-result');
        if (!d) return;

        $('#pb-result').innerHTML = `
            <div style="background:#e8f0e1; border-left:5px solid #d4a017; border-radius:12px; padding:16px;">
                <div style="font-size:1.6rem; font-weight:800; color:#1a3c2e;">${d.payback_years} years</div>
                <div style="color:#4a5a4a; font-size:.9rem; margin-bottom:8px;">Payback period (${d.payback_months} months)</div>
                <div style="color:#2e7d32; font-weight:600;">ROI Year 1: ${d.roi_year1_percent}%</div>
            </div>
        `;
    }

    // ============================================================
    // WHAT-IF
    // ============================================================
    async function calcWhatIf() {
        const payload = {
            current_profit: parseFloat($('#wi-profit')?.value || 0),
            current_revenue: parseFloat($('#wi-revenue')?.value || 0),
            current_costs: parseFloat($('#wi-costs')?.value || 0),
            revenue_change_pct: parseFloat($('#wi-rev')?.value || 0),
            cost_change_pct: parseFloat($('#wi-cost')?.value || 0),
        };
        const d = await runTool('what-if', Api.whatIf, payload, 'wi-result');
        if (!d) return;

        const change = d.change.profit;
        const color = change >= 0 ? '#2e7d32' : '#c0392b';
        $('#wi-result').innerHTML = `
            <div style="background:#fff; border:1px solid #e2e8dd; border-left:5px solid ${color}; border-radius:12px; padding:16px;">
                <div style="font-size:.85rem; color:#4a5a4a;">Simulated Profit</div>
                <div style="font-size:1.8rem; font-weight:800; color:${color};">${Fmt.currency(d.simulated.profit)}</div>
                <div style="font-size:.9rem; color:${color}; margin-top:4px;">
                    <i class="fas fa-caret-${change >= 0 ? 'up' : 'down'}"></i>
                    ${change >= 0 ? '+' : ''}${Fmt.currency(change)} (${d.change.profit_percent}%)
                </div>
            </div>
        `;
    }

    // ============================================================
    // RISK
    // ============================================================
    async function calcRisk() {
        const payload = {
            scores: {
                drought: parseInt($('#r-drought')?.value || 1),
                pest: parseInt($('#r-pest')?.value || 1),
                price: parseInt($('#r-price')?.value || 1),
                market: parseInt($('#r-market')?.value || 1),
                finance: parseInt($('#r-finance')?.value || 1),
            }
        };
        const d = await runTool('risk', Api.riskAssessment, payload, 'r-result');
        if (!d) return;

        const color = d.level === 'Low' ? '#2e7d32' : d.level === 'Moderate' ? '#b8860b' : d.level === 'High' ? '#e67e22' : '#c0392b';
        $('#r-result').innerHTML = `
            <div style="background:#fff; border:1px solid #e2e8dd; border-left:5px solid ${color}; border-radius:12px; padding:16px;">
                <h4 style="margin:0 0 8px; color:${color};">${d.level} Risk (Score: ${d.average_score}/5)</h4>
                <div style="margin-bottom:10px;">
                    ${d.ranked_risks.map((r) => `
                        <div style="display:flex; justify-content:space-between; font-size:.85rem; padding:4px 0;">
                            <span style="color:#4a5a4a;">${Fmt.titleCase(r.risk)}</span>
                            <span style="color:#1a3c2e; font-weight:600;">${r.score}/5</span>
                        </div>
                    `).join('')}
                </div>
                ${d.recommendations?.length ? `
                    <div style="border-top:1px solid #eef1ea; padding-top:10px;">
                        <div style="font-size:.8rem; color:#4a5a4a; text-transform:uppercase; font-weight:600; margin-bottom:6px;">Top Mitigation</div>
                        <p style="margin:0; font-size:.85rem; color:#1a3c2e;"><strong>${Fmt.titleCase(d.recommendations[0].risk)}:</strong> ${d.recommendations[0].mitigation}</p>
                    </div>
                ` : ''}
            </div>
        `;
    }

    // ============================================================
    // COMPARE ENTERPRISES
    // ============================================================
    async function loadComparison() {
        const container = $('#compare-result');
        if (!container) return;
        container.innerHTML = '<div style="text-align:center; padding:20px;"><i class="fas fa-spinner fa-spin"></i></div>';

        const r = await Api.compareEnterprises({});
        if (!r.ok) { container.innerHTML = `<div style="color:#c0392b;">${r.error}</div>`; return; }

        const d = r.data;
        if (!d.enterprises?.length) {
            container.innerHTML = '<div style="text-align:center; padding:30px; color:#8a9c8c;">No enterprises to compare yet.</div>';
            return;
        }

        container.innerHTML = `
            <div style="overflow-x:auto;">
                <table style="width:100%; border-collapse:collapse; font-size:.9rem;">
                    <thead><tr style="background:#e8f0e1;">
                        <th style="text-align:left; padding:10px;">Enterprise</th>
                        <th style="text-align:right; padding:10px;">Income</th>
                        <th style="text-align:right; padding:10px;">Expenses</th>
                        <th style="text-align:right; padding:10px;">Profit</th>
                        <th style="text-align:right; padding:10px;">Margin</th>
                    </tr></thead>
                    <tbody>
                        ${d.enterprises.map((e) => `
                            <tr style="border-bottom:1px solid #eef1ea;">
                                <td style="padding:10px; color:#1a3c2e; font-weight:600;">${e.name}</td>
                                <td style="padding:10px; text-align:right; color:#2e7d32;">${Fmt.currency(e.income)}</td>
                                <td style="padding:10px; text-align:right; color:#c0392b;">${Fmt.currency(e.expenses)}</td>
                                <td style="padding:10px; text-align:right; font-weight:700; color:${e.profit >= 0 ? '#2e7d32' : '#c0392b'};">${Fmt.currency(e.profit)}</td>
                                <td style="padding:10px; text-align:right;">${e.margin_percent}%</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    // ============================================================
    // BOOT
    // ============================================================
    document.addEventListener('DOMContentLoaded', () => {
        // Wire calculator buttons
        const handlers = {
            'breakeven': calcBreakeven,
            'gross-margin': calcGrossMargin,
            'marginal': calcMarginal,
            'loan': calcLoan,
            'payback': calcPayback,
            'what-if': calcWhatIf,
            'risk': calcRisk,
        };

        Object.entries(handlers).forEach(([tool, fn]) => {
            $$(`[data-calc="${tool}"]`).forEach((el) =>
                el.addEventListener('click', fn));
        });

        // Auto-run comparison if on the compare tab
        if ($('#compare-result')) loadComparison();
    });
})();
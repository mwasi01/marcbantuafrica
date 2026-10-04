"""
Tests for routes/decisions.py — break-even, margin, loan, risk, etc.
"""
import pytest

from routes import decisions
from tests import make_request, make_env, make_auth_header, seed_farmer


# ============================================================
# HELPER
# ============================================================
async def _call(handler, payload: dict, env=None, user_id: int = 1):
    """Prepare env + request and call a decisions handler."""
    env = env or make_env()
    if not env.DB.tables["farmers"]:
        seed_farmer(env, farmer_id=user_id)
    request = make_request(
        method="POST",
        url="http://localhost/api/decisions",
        body=payload,
        headers=make_auth_header(user_id),
    )
    response = await handler(request, env)
    import json
    return response.status, json.loads(response.body)


# ============================================================
# BREAK-EVEN
# ============================================================
class TestBreakeven:
    @pytest.mark.asyncio
    async def test_basic(self):
        env = make_env()
        payload = {
            "fixed_costs": 20000,
            "variable_cost_per_unit": 15,
            "price_per_unit": 45,
        }
        status, body = await _call(decisions.breakeven, payload, env)
        assert status == 200
        assert body["success"] is True
        data = body["data"]
        # CM = 45 - 15 = 30; BE = 20000 / 30 = 666.67
        assert data["contribution_margin_per_unit"] == 30.0
        assert data["breakeven_units"] == 666.7
        assert data["breakeven_revenue"] == 30000.0

    @pytest.mark.asyncio
    async def test_price_equals_variable_cost(self):
        env = make_env()
        payload = {
            "fixed_costs": 20000,
            "variable_cost_per_unit": 45,
            "price_per_unit": 45,
        }
        status, body = await _call(decisions.breakeven, payload, env)
        assert status == 400

    @pytest.mark.asyncio
    async def test_missing_fields(self):
        env = make_env()
        status, body = await _call(decisions.breakeven, {"fixed_costs": 100}, env)
        assert status == 400


# ============================================================
# GROSS MARGIN
# ============================================================
class TestGrossMargin:
    @pytest.mark.asyncio
    async def test_basic(self):
        env = make_env()
        status, body = await _call(decisions.gross_margin, {
            "revenue": 202500,
            "variable_costs": 36400,
        }, env)
        assert status == 200
        data = body["data"]
        assert data["gross_margin"] == 166100.0
        assert data["gross_margin_percent"] == pytest.approx(82.0, abs=0.1)

    @pytest.mark.asyncio
    async def test_zero_revenue(self):
        env = make_env()
        status, body = await _call(decisions.gross_margin, {
            "revenue": 0,
            "variable_costs": 100,
        }, env)
        assert status == 200
        assert body["data"]["gross_margin_percent"] == 0


# ============================================================
# MARGINAL ANALYSIS
# ============================================================
class TestMarginal:
    @pytest.mark.asyncio
    async def test_positive(self):
        env = make_env()
        status, body = await _call(decisions.marginal_analysis, {
            "additional_revenue": 45000,
            "additional_cost": 28000,
        }, env)
        assert status == 200
        data = body["data"]
        assert data["marginal_profit"] == 17000.0
        assert data["recommendation"] == "Proceed"

    @pytest.mark.asyncio
    async def test_negative(self):
        env = make_env()
        status, body = await _call(decisions.marginal_analysis, {
            "additional_revenue": 20000,
            "additional_cost": 28000,
        }, env)
        assert status == 200
        assert body["data"]["recommendation"] == "Do not proceed"

    @pytest.mark.asyncio
    async def test_break_even(self):
        env = make_env()
        status, body = await _call(decisions.marginal_analysis, {
            "additional_revenue": 28000,
            "additional_cost": 28000,
        }, env)
        assert status == 200
        assert body["data"]["recommendation"] == "Break-even"


# ============================================================
# LOAN AFFORDABILITY
# ============================================================
class TestLoanAffordability:
    @pytest.mark.asyncio
    async def test_safe_loan(self):
        env = make_env()
        status, body = await _call(decisions.loan_affordability, {
            "loan_amount": 100000,
            "annual_rate": 14,
            "term_months": 12,
            "monthly_profit": 100000,
        }, env)
        assert status == 200
        data = body["data"]
        assert "monthly_payment" in data
        assert data["monthly_payment"] > 0
        # Payment should be ~8900 for 100k at 14% over 12 months
        assert 8000 < data["monthly_payment"] < 10000
        assert data["verdict"] in ("Safe", "Manageable", "Risky", "Not recommended")

    @pytest.mark.asyncio
    async def test_risky_loan(self):
        env = make_env()
        status, body = await _call(decisions.loan_affordability, {
            "loan_amount": 500000,
            "annual_rate": 14,
            "term_months": 12,
            "monthly_profit": 30000,
        }, env)
        assert status == 200
        # Payment ~44k vs 30k profit → >100% → Not recommended
        assert body["data"]["verdict"] == "Not recommended"

    @pytest.mark.asyncio
    async def test_invalid_term(self):
        env = make_env()
        status, body = await _call(decisions.loan_affordability, {
            "loan_amount": 100000,
            "annual_rate": 14,
            "term_months": 0,
            "monthly_profit": 30000,
        }, env)
        assert status == 400


# ============================================================
# PAYBACK PERIOD
# ============================================================
class TestPayback:
    @pytest.mark.asyncio
    async def test_basic(self):
        env = make_env()
        status, body = await _call(decisions.payback_period, {
            "investment_cost": 150000,
            "additional_annual_income": 60000,
        }, env)
        assert status == 200
        data = body["data"]
        assert data["payback_years"] == 2.5
        assert data["roi_year1_percent"] == 40.0

    @pytest.mark.asyncio
    async def test_zero_income(self):
        env = make_env()
        status, body = await _call(decisions.payback_period, {
            "investment_cost": 150000,
            "additional_annual_income": 0,
        }, env)
        assert status == 400


# ============================================================
# WHAT-IF
# ============================================================
class TestWhatIf:
    @pytest.mark.asyncio
    async def test_scenario(self):
        env = make_env()
        status, body = await _call(decisions.what_if, {
            "current_profit": 100000,
            "current_revenue": 200000,
            "current_costs": 100000,
            "revenue_change_pct": -10,
            "cost_change_pct": 20,
        }, env)
        assert status == 200
        data = body["data"]
        # New revenue = 180k, new costs = 120k, new profit = 60k
        assert data["new_revenue"] == 180000.0
        assert data["new_costs"] == 120000.0
        assert data["simulated"]["profit"] == 60000.0

    @pytest.mark.asyncio
    async def test_no_change(self):
        env = make_env()
        status, body = await _call(decisions.what_if, {
            "current_profit": 100000,
            "current_revenue": 200000,
            "current_costs": 100000,
        }, env)
        assert status == 200
        assert body["data"]["change"]["profit"] == 0


# ============================================================
# RISK ASSESSMENT
# ============================================================
class TestRisk:
    @pytest.mark.asyncio
    async def test_moderate(self):
        env = make_env()
        status, body = await _call(decisions.risk_assessment, {
            "scores": {"drought": 3, "pest": 4, "price": 3, "market": 2, "finance": 3},
        }, env)
        assert status == 200
        data = body["data"]
        assert data["total_score"] == 15
        assert data["average_score"] == 3.0
        assert data["level"] == "Moderate"
        assert data["top_risk"] == "pest"
        assert len(data["recommendations"]) <= 3

    @pytest.mark.asyncio
    async def test_low_risk(self):
        env = make_env()
        status, body = await _call(decisions.risk_assessment, {
            "scores": {"drought": 1, "pest": 1, "price": 1, "market": 1, "finance": 1},
        }, env)
        assert status == 200
        assert body["data"]["level"] == "Low"

    @pytest.mark.asyncio
    async def test_critical_risk(self):
        env = make_env()
        status, body = await _call(decisions.risk_assessment, {
            "scores": {"drought": 5, "pest": 5, "price": 5, "market": 5, "finance": 5},
        }, env)
        assert status == 200
        assert body["data"]["level"] == "Critical"

    @pytest.mark.asyncio
    async def test_missing_scores(self):
        env = make_env()
        status, body = await _call(decisions.risk_assessment, {}, env)
        assert status == 400


# ============================================================
# AUTH REQUIRED
# ============================================================
class TestAuthRequired:
    @pytest.mark.asyncio
    async def test_no_auth_header(self):
        env = make_env()
        seed_farmer(env)
        request = make_request(method="POST", body={
            "fixed_costs": 20000,
            "variable_cost_per_unit": 15,
            "price_per_unit": 45,
        })
        response = await decisions.breakeven(request, env)
        assert response.status == 401

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        env = make_env()
        seed_farmer(env)
        request = make_request(
            method="POST",
            body={"fixed_costs": 1, "variable_cost_per_unit": 1, "price_per_unit": 2},
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        response = await decisions.breakeven(request, env)
        assert response.status == 401
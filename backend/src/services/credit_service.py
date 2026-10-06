"""
Marcbantu Africa — Credit Service.
Compute a farm credit score (300-850) from records and financial performance.
"""
from datetime import datetime
from utils import now_iso, log_event


class CreditService:
    def __init__(self, env):
        self.env = env

    async def compute_score(self, farmer_id: int) -> dict:
        """Compute the credit score for a farmer."""
        from db import DB
        db = DB(self.env)

        farmer = await db.query_one("""
            SELECT id, created_at, verified, county
            FROM farmers WHERE id = ?
        """, [farmer_id])

        if not farmer:
            return None

        # Base score
        score = 300

        # 1. Account age (max 80 pts)
        try:
            created = datetime.fromisoformat(
                (farmer["created_at"] or now_iso()).replace("Z", "+00:00").split("+")[0]
            )
            days_old = max((datetime.now() - created).days, 0)
        except Exception:
            days_old = 0
        age_score = min(int(days_old / 3.65), 80)
        score += age_score

        # 2. Verification (50 pts)
        verification_score = 50 if farmer.get("verified") else 0
        score += verification_score

        # 3. Record volume (max 150 pts)
        record_count = (await db.query_one("""
            SELECT COUNT(*) as total FROM records r
            JOIN farms f ON r.farm_id = f.id WHERE f.farmer_id = ?
        """, [farmer_id]))["total"]
        record_score = min(record_count, 150)
        score += record_score

        # 4. Transaction history (max 150 pts)
        tx_count = (await db.query_one("""
            SELECT COUNT(*) as total FROM transactions t
            JOIN farms f ON t.farm_id = f.id WHERE f.farmer_id = ?
        """, [farmer_id]))["total"]
        tx_score = min(tx_count // 2, 150)
        score += tx_score

        # 5. Profitability (max 120 pts)
        profit_row = await db.query_one("""
            SELECT
                COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
                COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as expenses
            FROM transactions t
            JOIN farms f ON t.farm_id = f.id WHERE f.farmer_id = ?
        """, [farmer_id])

        income = profit_row["income"] if profit_row else 0
        expenses = profit_row["expenses"] if profit_row else 0
        if income > 0:
            margin = (income - expenses) / income
            profit_score = int(min(max(margin, 0), 1) * 120)
        else:
            profit_score = 0
        score += profit_score

        # Cap
        score = min(score, 850)

        # Rating
        if score >= 750:
            rating = "Excellent"
        elif score >= 650:
            rating = "Good"
        elif score >= 550:
            rating = "Fair"
        elif score >= 450:
            rating = "Poor"
        else:
            rating = "Very poor"

        # Recommended loan limit
        recent_income = await db.query_one("""
            SELECT COALESCE(SUM(t.amount), 0) as income
            FROM transactions t
            JOIN farms f ON t.farm_id = f.id
            WHERE f.farmer_id = ? AND t.type = 'income'
            AND t.transaction_date >= date('now', '-6 months')
        """, [farmer_id])
        monthly_avg = (recent_income["income"] / 6) if recent_income and recent_income["income"] else 0
        recommended_loan = min(monthly_avg * 6, 500000)

        log_event("credit_score_computed", {
            "farmer_id": farmer_id, "score": score, "rating": rating,
        })

        return {
            "score": score,
            "rating": rating,
            "range": {"min": 300, "max": 850},
            "components": {
                "account_age": age_score,
                "verification": verification_score,
                "record_volume": record_score,
                "transaction_history": tx_score,
                "profitability": profit_score,
            },
            "metrics": {
                "days_active": days_old,
                "record_count": record_count,
                "transaction_count": tx_count,
                "total_income": income,
                "total_expenses": expenses,
                "net_profit": income - expenses,
            },
            "recommended_loan_limit": round(recommended_loan),
            "computed_at": now_iso(),
            "note": "Credit score is an estimate based on farm records. Lenders may use their own criteria.",
        }

    async def is_loan_ready(self, farmer_id: int, amount: float) -> dict:
        """Check if farmer's score supports a loan of a given amount."""
        score_data = await self.compute_score(farmer_id)
        if not score_data:
            return {"eligible": False, "reason": "Score unavailable"}

        eligible = (
            score_data["score"] >= 550 and
            amount <= score_data["recommended_loan_limit"]
        )

        return {
            "eligible": eligible,
            "score": score_data["score"],
            "max_recommended": score_data["recommended_loan_limit"],
            "requested": amount,
            "reason": (
                "Score and limit meet requirements" if eligible
                else "Score too low" if score_data["score"] < 550
                else "Amount exceeds recommended limit"
            ),
        }
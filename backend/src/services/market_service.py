"""
Marcbantu Africa — Market Service.
Price aggregation, trend analysis, price alert matching.
"""
from utils import now_iso, log_event


class MarketService:
    def __init__(self, env):
        self.env = env

    async def latest_prices(self, crop: str = None, county: str = None) -> list:
        """Get latest prices, optionally filtered."""
        from db import DB
        db = DB(self.env)

        where = ["price_date = (SELECT MAX(price_date) FROM market_prices)"]
        params = []

        if crop:
            where.append("crop = ?")
            params.append(crop)
        if county:
            where.append("county = ?")
            params.append(county)

        return await db.query(
            f"SELECT * FROM market_prices WHERE {' AND '.join(where)} ORDER BY crop, market",
            params,
        )

    async def trend(self, crop: str, days: int = 30) -> dict:
        """Compute simple trend (up/down/stable) for a crop."""
        from db import DB
        db = DB(self.env)

        rows = await db.query("""
            SELECT price_date, AVG(price) as avg_price
            FROM market_prices
            WHERE crop = ? AND price_date >= date('now', '-' || ? || ' days')
            GROUP BY price_date
            ORDER BY price_date
        """, [crop, days])

        if len(rows) < 2:
            return {"crop": crop, "direction": "unknown", "change_percent": 0}

        first = rows[0]["avg_price"]
        last = rows[-1]["avg_price"]
        change_pct = ((last - first) / first * 100) if first > 0 else 0

        if change_pct > 3:
            direction = "up"
        elif change_pct < -3:
            direction = "down"
        else:
            direction = "stable"

        return {
            "crop": crop,
            "days": days,
            "first_price": round(first, 2),
            "last_price": round(last, 2),
            "change_percent": round(change_pct, 2),
            "direction": direction,
            "data_points": len(rows),
            "series": rows,
        }

    async def check_alerts(self, crop: str, new_price: float) -> list:
        """Check which price alerts are triggered by a new price."""
        from db import DB
        db = DB(self.env)

        alerts = await db.query("""
            SELECT pa.*, f.phone, f.full_name, f.id as farmer_id
            FROM price_alerts pa
            JOIN farmers f ON pa.farmer_id = f.id
            WHERE pa.crop = ? AND pa.active = 1
        """, [crop])

        triggered = []
        for alert in alerts:
            hit = False
            if alert["direction"] == "above" and new_price >= alert["target_price"]:
                hit = True
            elif alert["direction"] == "below" and new_price <= alert["target_price"]:
                hit = True

            if hit:
                triggered.append(alert)

                # Queue SMS
                try:
                    await self.env.JOBS.send({
                        "type": "send_sms",
                        "payload": {
                            "to": alert["phone"],
                            "farmer_id": alert["farmer_id"],
                            "template_code": "PRICE_TARGET",
                            "variables": {
                                "crop": crop,
                                "market": "local market",
                                "price": f"{new_price:,.2f}",
                                "target": f"{alert['target_price']:,.2f}",
                            },
                        },
                    })
                except Exception:
                    pass

                # Mark triggered
                await db.update("price_alerts", {
                    "triggered_at": now_iso(),
                    "active": 0,
                }, "id = ?", [alert["id"]])

        if triggered:
            log_event("price_alerts_triggered", {
                "crop": crop, "count": len(triggered), "price": new_price,
            })

        return triggered

    async def buyer_reliability(self, buyer_id: int) -> dict:
        """Compute a buyer's reliability from past sales."""
        from db import DB
        db = DB(self.env)

        stats = await db.query_one("""
            SELECT
                COUNT(*) as total_sales,
                COALESCE(SUM(total), 0) as total_value,
                COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as paid_count,
                COUNT(CASE WHEN payment_status = 'pending' THEN 1 END) as pending_count,
                AVG(JULIANDAY(payment_date) - JULIANDAY(sale_date)) as avg_days_to_pay
            FROM sales WHERE buyer_id = ?
        """, [buyer_id])

        total = stats["total_sales"] if stats else 0
        paid = stats["paid_count"] if stats else 0
        reliability = round((paid / total * 100), 1) if total > 0 else 0

        return {
            "buyer_id": buyer_id,
            "total_sales": total,
            "total_value": stats["total_value"] if stats else 0,
            "paid_sales": paid,
            "pending_sales": stats["pending_count"] if stats else 0,
            "reliability_percent": reliability,
            "avg_days_to_pay": round(stats["avg_days_to_pay"], 1) if stats and stats.get("avg_days_to_pay") else None,
        }
"""
Marcbantu Africa — AI Service.
Cloudflare Workers AI for pest diagnosis, chatbot, and content.
Falls back to rule-based logic when Workers AI is unavailable.
"""
import json
from utils import now_iso, log_event


class AIService:
    def __init__(self, env):
        self.env = env

    # ========================================================
    # PEST DIAGNOSIS
    # ========================================================
    async def diagnose_pest(self, image_url: str = None, crop: str = None,
                            symptoms: str = None) -> dict:
        """Diagnose a pest using Workers AI vision + knowledge base."""
        from db import DB
        db = DB(self.env)

        # Try Workers AI first
        if image_url and hasattr(self.env, "AI"):
            try:
                result = await self._vision_diagnose(image_url, crop)
                if result:
                    return result
            except Exception as e:
                log_event("ai_vision_failed", {"error": str(e)})

        # Fallback: knowledge base match on symptoms
        return await self._knowledge_base_match(db, crop, symptoms)

    async def _vision_diagnose(self, image_url: str, crop: str = None) -> dict | None:
        """Use Workers AI vision model. Returns structured diagnosis."""
        prompt = (
            f"You are an agricultural pest and disease expert for African farms. "
            f"{'The crop is ' + crop + '.' if crop else ''} "
            "Look at this image and identify any pests, diseases, or deficiencies. "
            "Respond with JSON only: "
            '{"pest_name": "...", "confidence": 0.0-1.0, "symptoms": "...", '
            '"treatment_organic": "...", "treatment_chemical": "..."}'
        )

        try:
            response = await self.env.AI.run(
                "@cf/meta/llama-3.2-11b-vision-instruct",
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": image_url}},
                            ],
                        }
                    ],
                    "max_tokens": 500,
                },
            )
            text = response.get("response", "") if isinstance(response, dict) else str(response)
            # Extract JSON
            import re
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return None
            data = json.loads(match.group())
            data["source"] = "vision_ai"
            return data
        except Exception as e:
            log_event("vision_diagnose_error", {"error": str(e)})
            return None

    async def _knowledge_base_match(self, db, crop: str, symptoms: str) -> dict:
        """Match symptoms/crop against pest_library."""
        candidates = []
        if crop:
            candidates = await db.query(
                "SELECT * FROM pest_library WHERE affected_crops LIKE ? LIMIT 15",
                [f"%{crop}%"],
            )
        if not candidates:
            candidates = await db.query("SELECT * FROM pest_library LIMIT 20")

        symptom_words = [
            w.strip().lower() for w in (symptoms or "").split() if len(w) > 3
        ]

        scored = []
        for pest in candidates:
            pest_symptoms = (pest.get("symptoms") or "").lower()
            score = sum(1 for w in symptom_words if w in pest_symptoms)
            scored.append((score, pest))

        scored.sort(key=lambda x: -x[0])
        top = scored[:3]

        if not top or top[0][0] == 0:
            return {
                "diagnosis": None,
                "message": "No matching pests. Add more symptoms or a clearer photo.",
                "confidence": 0,
                "source": "kb",
            }

        matches = []
        for score, pest in top:
            matches.append({
                "pest_name": pest["name"],
                "scientific_name": pest.get("scientific_name"),
                "type": pest.get("type"),
                "symptoms": pest.get("symptoms"),
                "treatment_organic": pest.get("treatment_organic"),
                "treatment_chemical": pest.get("treatment_chemical"),
                "prevention": pest.get("prevention"),
                "confidence": min(50 + score * 12, 95),
            })

        return {
            "diagnosis": matches[0],
            "alternatives": matches[1:],
            "source": "kb",
            "disclaimer": "AI-assisted. Confirm with a local extension officer.",
        }

    # ========================================================
    # CHATBOT
    # ========================================================
    async def chat(self, message: str, farmer: dict, context: dict = None) -> str:
        """Generate a reply. Uses Workers AI if available; else rules."""
        # Try Workers AI for richer answers
        if hasattr(self.env, "AI"):
            try:
                reply = await self._llm_chat(message, farmer, context)
                if reply:
                    return reply
            except Exception as e:
                log_event("ai_chat_failed", {"error": str(e)})

        return await self._rule_chat(message, farmer)

    async def _llm_chat(self, message: str, farmer: dict, context: dict = None) -> str | None:
        """LLM-powered chat."""
        system = (
            "You are Marcbantu, a warm and practical farm management advisor for African farmers. "
            "Give short, clear, actionable answers. Mention specific tools in the Marcbantu app "
            "(Records, Finance, Decisions, Market, Weather, Pest). Keep replies under 120 words."
        )

        messages = [{"role": "system", "content": system}]
        if context:
            messages.append({
                "role": "system",
                "content": f"Farmer context: {json.dumps(context)}",
            })
        messages.append({"role": "user", "content": message})

        try:
            response = await self.env.AI.run(
                "@cf/meta/llama-3.1-8b-instruct",
                {"messages": messages, "max_tokens": 300},
            )
            return response.get("response") if isinstance(response, dict) else None
        except Exception as e:
            log_event("llm_chat_error", {"error": str(e)})
            return None

    async def _rule_chat(self, message: str, farmer: dict) -> str:
        """Rule-based chat fallback."""
        msg = (message or "").lower()
        first = (farmer.get("full_name") or "farmer").split()[0]

        if any(w in msg for w in ["pest", "disease", "insect", "worm", "blight", "rust"]):
            return (
                "For pest issues: scout early morning, identify the pest, "
                "and log it in the Pest & Disease tool. You can upload a photo "
                "for AI diagnosis. High-severity records auto-alert you by SMS."
            )

        if any(w in msg for w in ["break", "profit", "margin", "cost", "loan"]):
            return (
                "Go to Finance → Dashboard for profit & loss. Use Decisions for "
                "break-even, loan affordability, and what-if simulations. "
                "Every calculation is saved for later."
            )

        if any(w in msg for w in ["weather", "rain", "drought", "forecast"]):
            return (
                "Open Weather to see your 7-day forecast, rainfall history, and "
                "spray/harvest recommendations. You'll also get alerts for heavy rain, "
                "dry spells, and heat."
            )

        if any(w in msg for w in ["price", "market", "sell", "buyer"]):
            return (
                "Check Market & Sales for today's prices, buyer directory, and "
                "your sales history. Set a price alert and we'll SMS you when "
                "your target is hit."
            )

        if any(w in msg for w in ["record", "log", "track"]):
            return (
                "Use Farm Records to log crop activities, livestock, inputs, "
                "harvests, and sales. Works offline — syncs automatically when "
                "you're back online."
            )

        if any(w in msg for w in ["learn", "course", "video", "tutorial"]):
            return (
                "Head to Learning to browse courses on farm management, finance, "
                "and decisions. Most are free. You can track progress and get "
                "certificates."
            )

        if any(w in msg for w in ["hello", "hi", "hey", "habari", "jambo"]):
            return f"Hello {first}! I'm your Marcbantu farm advisor. Ask me about pests, weather, prices, records, or farm decisions."

        return (
            "I can help with:\n"
            "• Pest & disease issues\n"
            "• Farm records and profitability\n"
            "• Weather and rainfall\n"
            "• Market prices and buyers\n"
            "• Learning resources\n\n"
            "What would you like to explore?"
        )

    # ========================================================
    # CONTENT GENERATION (for admins)
    # ========================================================
    async def generate_content(self, prompt: str, tone: str = "friendly") -> str | None:
        """Generate marketing or educational content."""
        if not hasattr(self.env, "AI"):
            return None

        try:
            response = await self.env.AI.run(
                "@cf/meta/llama-3.1-8b-instruct",
                {
                    "messages": [
                        {"role": "system", "content": f"You write in a {tone} tone for African farmers. Keep it short, clear, and actionable."},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 500,
                },
            )
            return response.get("response") if isinstance(response, dict) else None
        except Exception as e:
            log_event("content_gen_failed", {"error": str(e)})
            return None
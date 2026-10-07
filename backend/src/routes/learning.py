"""
Marcbantu Africa — Learning routes.
Courses, lessons, enrollments, progress tracking, videos,
AI chatbot, forum discussions, expert consultations.
"""

import json
from utils import (
    success_response,
    error_response,
    parse_json,
    require_auth,
    now_iso,
    to_int,
    to_float,
    log_event,
    require_fields,
    paginated_response,
    generate_reference,
    get_int_query,
    _sp,
)
from constants import HTTP, ErrorCode
from db import DB


# ============================================================
# HELPERS
# ============================================================
def _progress_for_course(course_id: int, lesson_id: int, completed_ids: set) -> int:
    return 100 if lesson_id in completed_ids else 0


# ============================================================
# COURSES — LIST
# ============================================================
async def list_courses(request, env):
    """GET /api/learning/courses
    Query: category?, level?, language?, free?, q?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["published = 1"]
    params = []

    category = url.search_params.get("category")
    if category:
        where.append("category = ?")
        params.append(category)

    level = url.search_params.get("level")
    if level:
        where.append("level = ?")
        params.append(level)

    language = url.search_params.get("language")
    if language:
        where.append("language = ?")
        params.append(language)

    if url.search_params.get("free") == "true":
        where.append("is_free = 1")

    search = url.search_params.get("q")
    if search:
        where.append("(title LIKE ? OR description LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])

    courses = await db.query(
        f"""
        SELECT * FROM courses
        WHERE {" AND ".join(where)}
        ORDER BY level, title
    """,
        params,
    )

    # Enrich with enrollment status for this user
    enrolled = await db.query(
        "SELECT course_id, progress, completed FROM enrollments WHERE farmer_id = ?",
        [user["id"]],
    )
    enrollment_map = {e["course_id"]: e for e in enrolled}

    for c in courses:
        e = enrollment_map.get(c["id"])
        c["enrolled"] = e is not None
        c["progress"] = e["progress"] if e else 0
        c["completed"] = bool(e["completed"]) if e else False

    return success_response(courses)


# ============================================================
# COURSES — GET
# ============================================================
async def get_course(request, env, course_id: int):
    """GET /api/learning/courses/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    course = await db.query_one("SELECT * FROM courses WHERE id = ?", [course_id])
    if not course:
        return error_response(
            "Course not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND
        )

    # Lessons
    course["lessons"] = await db.query(
        """
        SELECT id, title, content, video_url, order_num, duration_minutes
        FROM lessons WHERE course_id = ?
        ORDER BY order_num
    """,
        [course_id],
    )

    # Enrollment status
    enrollment = await db.query_one(
        """
        SELECT id, progress, current_lesson_id, completed, completed_at
        FROM enrollments WHERE farmer_id = ? AND course_id = ?
    """,
        [user["id"], course_id],
    )

    course["enrollment"] = enrollment
    course["enrolled"] = enrollment is not None

    return success_response(course)


# ============================================================
# LESSONS — LIST
# ============================================================
async def list_lessons(request, env, course_id: int):
    """GET /api/learning/courses/:id/lessons"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    course = await db.query_one("SELECT id FROM courses WHERE id = ?", [course_id])
    if not course:
        return error_response(
            "Course not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND
        )

    lessons = await db.query(
        """
        SELECT id, title, content, video_url, pdf_url, order_num, duration_minutes
        FROM lessons WHERE course_id = ?
        ORDER BY order_num
    """,
        [course_id],
    )

    # Mark completed lessons
    enrollment = await db.query_one(
        "SELECT id FROM enrollments WHERE farmer_id = ? AND course_id = ?",
        [user["id"], course_id],
    )

    completed_lesson_ids = set()
    if enrollment:
        progress = await db.query(
            "SELECT lesson_id FROM lesson_progress WHERE enrollment_id = ? AND completed = 1",
            [enrollment["id"]],
        )
        completed_lesson_ids = {p["lesson_id"] for p in progress}

    for l in lessons:
        l["completed"] = l["id"] in completed_lesson_ids

    return success_response(lessons)


# ============================================================
# ENROLL
# ============================================================
async def enroll(request, env):
    """POST /api/learning/enroll
    Body: {course_id}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ["course_id"])
    if err_msg:
        return error_response(
            err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD
        )

    course_id = to_int(data["course_id"])
    db = DB(env)

    course = await db.query_one(
        "SELECT id, is_free, price FROM courses WHERE id = ? AND published = 1",
        [course_id],
    )
    if not course:
        return error_response(
            "Course not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND
        )

    # Already enrolled?
    existing = await db.query_one(
        "SELECT id FROM enrollments WHERE farmer_id = ? AND course_id = ?",
        [user["id"], course_id],
    )
    if existing:
        return error_response(
            "Already enrolled in this course",
            status=HTTP.CONFLICT,
            code=ErrorCode.ALREADY_EXISTS,
        )

    # If paid course, verify tier (Pro+ can access)
    if not course["is_free"]:
        farmer = await db.query_one(
            "SELECT subscription_tier FROM farmers WHERE id = ?", [user["id"]]
        )
        if farmer["subscription_tier"] == "starter":
            return error_response(
                "This course requires Pro or Business subscription",
                status=HTTP.FORBIDDEN,
                code=ErrorCode.TIER_LIMIT_EXCEEDED,
            )

    enrollment_id = await db.insert(
        "enrollments",
        {
            "farmer_id": user["id"],
            "course_id": course_id,
            "progress": 0,
            "completed": 0,
        },
    )

    # Notify
    await db.insert(
        "notifications",
        {
            "farmer_id": user["id"],
            "type": "learning",
            "title": "Enrolled in course",
            "message": f"You are now enrolled. Start learning!",
            "action_url": f"/learning.html?course={course_id}",
        },
    )

    log_event("enrolled", {"farmer_id": user["id"], "course_id": course_id})

    enrollment = await db.query_one(
        "SELECT * FROM enrollments WHERE id = ?", [enrollment_id]
    )
    return success_response(
        enrollment, message="Enrolled successfully", status=HTTP.CREATED
    )


# ============================================================
# MY COURSES
# ============================================================
async def my_courses(request, env):
    """GET /api/learning/my-courses"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    courses = await db.query(
        """
        SELECT c.*,
               e.id as enrollment_id,
               e.progress,
               e.completed,
               e.enrolled_at,
               e.completed_at,
               e.current_lesson_id
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.farmer_id = ?
        ORDER BY e.completed ASC, e.enrolled_at DESC
    """,
        [user["id"]],
    )

    return success_response(courses)


# ============================================================
# UPDATE PROGRESS
# ============================================================
async def update_progress(request, env):
    """POST /api/learning/progress
    Body: {course_id, lesson_id, completed: true/false, time_spent_seconds?}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ["course_id", "lesson_id"])
    if err_msg:
        return error_response(
            err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD
        )

    course_id = to_int(data["course_id"])
    lesson_id = to_int(data["lesson_id"])
    completed = bool(data.get("completed", True))
    time_spent = to_int(data.get("time_spent_seconds", 0))

    db = DB(env)
    enrollment = await db.query_one(
        "SELECT id FROM enrollments WHERE farmer_id = ? AND course_id = ?",
        [user["id"], course_id],
    )
    if not enrollment:
        return error_response(
            "Not enrolled in this course",
            status=HTTP.BAD_REQUEST,
            code=ErrorCode.VALIDATION_ERROR,
        )

    # Upsert lesson progress
    existing = await db.query_one(
        "SELECT id FROM lesson_progress WHERE enrollment_id = ? AND lesson_id = ?",
        [enrollment["id"], lesson_id],
    )

    if existing:
        await db.update(
            "lesson_progress",
            {
                "completed": 1 if completed else 0,
                "completed_at": now_iso() if completed else None,
                "time_spent_seconds": time_spent or None,
            },
            "id = ?",
            [existing["id"]],
        )
    else:
        await db.insert(
            "lesson_progress",
            {
                "enrollment_id": enrollment["id"],
                "lesson_id": lesson_id,
                "completed": 1 if completed else 0,
                "completed_at": now_iso() if completed else None,
                "time_spent_seconds": time_spent or None,
            },
        )

    # Recalculate overall progress
    total_lessons = await db.count("lessons", "course_id = ?", [course_id])
    _cl = await db.query_one(
        """
        SELECT COUNT(*) as total FROM lesson_progress
        WHERE enrollment_id = ? AND completed = 1
    """,
        [enrollment["id"]],
    )
    completed_lessons = _cl["total"] if _cl else 0

    new_progress = (
        int((completed_lessons / total_lessons) * 100) if total_lessons > 0 else 0
    )
    is_complete = 1 if new_progress >= 100 else 0

    await db.update(
        "enrollments",
        {
            "progress": new_progress,
            "current_lesson_id": lesson_id,
            "completed": is_complete,
            "completed_at": now_iso() if is_complete else None,
            "last_activity_at": now_iso(),
        },
        "id = ?",
        [enrollment["id"]],
    )

    # Completion notification
    if is_complete:
        course = await db.query_one(
            "SELECT title FROM courses WHERE id = ?", [course_id]
        )
        await db.insert(
            "notifications",
            {
                "farmer_id": user["id"],
                "type": "learning",
                "title": "Course completed! 🎉",
                "message": f"You've completed {course['title'] if course else 'the course'}. Certificate available.",
            },
        )

    return success_response(
        {
            "progress": new_progress,
            "completed": bool(is_complete),
            "completed_lessons": completed_lessons,
            "total_lessons": total_lessons,
        },
        message="Progress updated",
    )


# ============================================================
# VIDEOS
# ============================================================
async def list_videos(request, env):
    """GET /api/learning/videos
    Query: category?, q?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["published = 1"]
    params = []

    category = url.search_params.get("category")
    if category:
        where.append("category = ?")
        params.append(category)

    search = url.search_params.get("q")
    if search:
        where.append("(title LIKE ? OR description LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])

    videos = await db.query(
        f"""
        SELECT * FROM videos
        WHERE {" AND ".join(where)}
        ORDER BY created_at DESC
        LIMIT 100
    """,
        params,
    )

    return success_response(videos)


# ============================================================
# AI CHATBOT
# ============================================================
async def chat(request, env):
    """POST /api/learning/chat
    Body: {message, session_id?}
    AI-powered (Cloudflare Workers AI) with farm context + persistent history.
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ["message"])
    if err_msg:
        return error_response(
            err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD
        )

    message = str(data["message"]).strip()
    session_id = data.get("session_id") or generate_reference("CHAT")

    db = DB(env)

    # Get or create conversation (scoped to farmer for security)
    convo = await db.query_one(
        "SELECT id FROM chatbot_conversations WHERE session_id = ? AND farmer_id = ?",
        [session_id, user["id"]],
    )
    if not convo:
        convo_id = await db.insert(
            "chatbot_conversations",
            {
                "farmer_id": user["id"],
                "session_id": session_id,
                "title": message[:80],
            },
        )
    else:
        convo_id = convo["id"]

    # Save user message
    await db.insert(
        "chatbot_messages",
        {
            "conversation_id": convo_id,
            "role": "user",
            "message": message,
        },
    )

    # Generate response (AI or fallback)
    reply = await _generate_reply(message, user, db, env)

    # Save assistant message
    await db.insert(
        "chatbot_messages",
        {
            "conversation_id": convo_id,
            "role": "assistant",
            "message": reply,
        },
    )

    return success_response(
        {
            "session_id": session_id,
            "reply": reply,
            "timestamp": now_iso(),
        }
    )


async def _generate_reply(message: str, user: dict, db: DB, env) -> str:
    """
    AI-powered reply using Cloudflare Workers AI.
    Falls back to rule-based replies if AI fails or returns empty.
    All chats persisted in D1 by the caller (chat handler).
    """
    # Try Workers AI first
    try:
        # Build farm context (farmer + farms + enterprises + recent activity)
        context = await _build_farm_context(db, user["id"])

        # Fetch last 20 messages for this farmer (memory)
        history = await db.query(
            """
            SELECT m.role, m.message
            FROM chatbot_messages m
            JOIN chatbot_conversations c ON m.conversation_id = c.id
            WHERE c.farmer_id = ?
            ORDER BY m.id DESC
            LIMIT 20
        """,
            [user["id"]],
        )
        history.reverse()  # oldest first

        # Build the messages array for the LLM
        system_prompt = (
            "You are Marcbantu AI, a practical farming advisor for African farmers. "
            "Be concise, specific, and Africa-focused. Prices in KES. Reference local Kenyan markets "
            "(Wakulima, Marikiti, Gikomba) and products available in East Africa.\n\n"
            "FARMER CONTEXT:\n" + (context or "No farm data yet.") + "\n\n"
            "RULES:\n"
            "- Keep replies under 150 words unless the user asks for detail\n"
            "- Recommend specific products available in Kenya (e.g. Ampligo 150ZC, Mavrik, DAP, CAN)\n"
            "- For medical/animal-health advice, defer to a licensed vet or doctor\n"
            "- Never invent data that is not in the FARMER CONTEXT\n"
            "- If unsure, ask a clarifying question instead of guessing\n"
            "- Use simple English that a smallholder farmer can understand\n"
            "- Swahili is fine if the farmer writes in Swahili"
        )

        messages = [{"role": "system", "content": system_prompt}]
        for h in history[:-1]:  # exclude the just-saved user message
            messages.append({"role": h["role"], "content": h["message"]})
        messages.append({"role": "user", "content": message})

        # Call Workers AI (Llama 3.1 8B)
        response = await env.AI.run(
            "@cf/meta/llama-3.1-8b-instruct",
            {
                "messages": messages,
                "max_tokens": 500,
                "temperature": 0.7,
            },
        )

        # Extract text from response (multiple formats possible)
        reply = None
        if isinstance(response, dict):
            reply = response.get("response") or response.get("result")
        elif hasattr(response, "response"):
            reply = response.response
        elif isinstance(response, str):
            reply = response

        if reply and len(str(reply).strip()) >= 10:
            return str(reply).strip()

    except Exception as e:
        # Log and fall through to rule-based
        try:
            log_event("ai_chat_failed", {"error": str(e), "farmer_id": user["id"]})
        except Exception:
            pass

    # Fallback: rule-based reply (guaranteed to return something)
    return _rule_based_reply(message, user)


async def _build_farm_context(db: DB, farmer_id: int) -> str:
    """Build a compact farm context block for the AI system prompt."""
    parts = []

    # Farmer profile
    farmer = await db.query_one(
        "SELECT full_name, county, location, language FROM farmers WHERE id = ?",
        [farmer_id],
    )
    if farmer:
        parts.append("Farmer: " + (farmer.get("full_name") or "Unknown"))
        if farmer.get("county"):
            parts.append("County: " + str(farmer["county"]))
        if farmer.get("location"):
            parts.append("Location: " + str(farmer["location"]))

    # Farms
    farms = await db.query(
        "SELECT id, name, size_acres, county FROM farms WHERE farmer_id = ?",
        [farmer_id],
    )
    if farms:
        farm_labels = []
        for f in farms[:5]:
            label = f["name"] or "Farm"
            if f.get("size_acres"):
                label = label + " (" + str(f["size_acres"]) + " acres)"
            farm_labels.append(label)
        parts.append("Farms: " + "; ".join(farm_labels))

    # Enterprises
    if farms:
        farm_ids = [f["id"] for f in farms]
        placeholders = ",".join(["?"] * len(farm_ids))
        ents = await db.query(
            "SELECT name, type, quantity, unit FROM enterprises "
            "WHERE farm_id IN (" + placeholders + ") LIMIT 10",
            farm_ids,
        )
        if ents:
            ent_labels = []
            for e in ents:
                label = e.get("name") or e.get("type") or "enterprise"
                if e.get("quantity"):
                    unit = e.get("unit") or ""
                    label = label + " (" + str(e["quantity"]) + " " + unit + ")"
                ent_labels.append(label.strip())
            parts.append("Enterprises: " + "; ".join(ent_labels))

    # Recent activity count
    if farms:
        farm_ids = [f["id"] for f in farms]
        placeholders = ",".join(["?"] * len(farm_ids))
        recent = await db.query_one(
            "SELECT COUNT(*) as n FROM records "
            "WHERE farm_id IN (" + placeholders + ") "
            "AND record_date >= date('now', '-30 days')",
            farm_ids,
        )
        if recent and recent.get("n"):
            parts.append("Records in last 30 days: " + str(recent["n"]))

    if not parts:
        return "New farmer - no farm data yet."
    return "\n".join(parts)


def _rule_based_reply(message: str, user: dict) -> str:
    """Fallback reply when AI is unavailable."""
    msg = message.lower()
    first_name = (user.get("full_name") or "farmer").split()[0]

    if any(
        w in msg
        for w in ["pest", "disease", "insect", "worm", "blight", "rust", "armyworm"]
    ):
        return (
            "For pest issues: scout twice weekly in the early morning, identify the pest, "
            "and use the Pest & Disease tool to log it. For fall armyworm, apply Ampligo 150ZC "
            "at dusk and rotate with Match 050EC. Upload a photo for AI diagnosis."
        )

    if any(
        w in msg for w in ["break", "profit", "margin", "cost", "loan", "breakeven"]
    ):
        return (
            "Break-even = Fixed costs / (Price per unit - Variable cost per unit). "
            "Use Finance then Dashboard for your P&L, or Decisions then Break-Even."
        )

    if any(w in msg for w in ["weather", "rain", "drought", "forecast", "spray"]):
        return (
            "Open the Weather section for your 7-day forecast, rainfall history, and "
            "spray/harvest advice based on current conditions."
        )

    if any(w in msg for w in ["price", "market", "sell", "buyer"]):
        return (
            "Check Market & Sales for today's prices near your farm, buyer directory, "
            "and sales history. Set a price alert and we'll SMS you when your target is hit."
        )

    if any(w in msg for w in ["record", "log", "track", "logbook"]):
        return (
            "Use Farm Records to log crop activities, livestock, inputs, harvests, and sales. "
            "Records work offline and sync when you're back online."
        )

    if any(w in msg for w in ["learn", "course", "video", "tutorial"]):
        return (
            "Head to Learning to browse courses on farm management, finance, and decisions. "
            "Most are free and you can track your progress."
        )

    if any(w in msg for w in ["hello", "hi ", "hey", "habari", "jambo", "niaje"]):
        return (
            "Hello "
            + first_name
            + "! I am your Marcbantu farm advisor. Ask me about pests, weather, prices, records, or farm decisions."
        )

    return (
        "I can help with: pest & disease, records, profit, weather, market prices, and learning. "
        "What would you like to explore?"
    )


# ============================================================
# CHAT HISTORY
# ============================================================
async def chat_history(request, env):
    """GET /api/learning/chat/history?session_id=xxx"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)
    session_id = url.search_params.get("session_id")

    if session_id:
        convo = await db.query_one(
            """
            SELECT id FROM chatbot_conversations
            WHERE session_id = ? AND farmer_id = ?
        """,
            [session_id, user["id"]],
        )
        if not convo:
            return error_response(
                "Conversation not found",
                status=HTTP.NOT_FOUND,
                code=ErrorCode.NOT_FOUND,
            )
        messages = await db.query(
            """
            SELECT role, message, created_at FROM chatbot_messages
            WHERE conversation_id = ?
            ORDER BY id
        """,
            [convo["id"]],
        )
        return success_response({"session_id": session_id, "messages": messages})

    # Return recent conversations
    convos = await db.query(
        """
        SELECT id, session_id, title, started_at, ended_at
        FROM chatbot_conversations
        WHERE farmer_id = ?
        ORDER BY started_at DESC
        LIMIT 20
    """,
        [user["id"]],
    )

    return success_response(convos)


# ============================================================
# FORUM — LIST TOPICS
# ============================================================
async def list_forum_topics(request, env):
    """GET /api/learning/forum/topics
    Query: category?, q?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["1=1"]
    params = []

    category = url.search_params.get("category")
    if category:
        where.append("t.category = ?")
        params.append(category)

    search = url.search_params.get("q")
    if search:
        where.append("(t.title LIKE ? OR t.body LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])

    topics = await db.query(
        f"""
        SELECT t.*, f.full_name as author_name
        FROM forum_topics t
        JOIN farmers f ON t.farmer_id = f.id
        WHERE {" AND ".join(where)}
        ORDER BY t.pinned DESC, t.updated_at DESC
        LIMIT 100
    """,
        params,
    )

    return success_response(topics)


# ============================================================
# FORUM — CREATE TOPIC
# ============================================================
async def create_forum_topic(request, env):
    """POST /api/learning/forum/topics
    Body: {title, body, category?}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ["title", "body"])
    if err_msg:
        return error_response(
            err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD
        )

    if len(data["title"].strip()) < 5:
        return error_response(
            "Title is too short",
            status=HTTP.BAD_REQUEST,
            code=ErrorCode.VALIDATION_ERROR,
        )

    db = DB(env)
    topic_id = await db.insert(
        "forum_topics",
        {
            "farmer_id": user["id"],
            "title": str(data["title"]).strip(),
            "body": str(data["body"]).strip(),
            "category": data.get("category"),
        },
    )

    topic = await db.query_one(
        """
        SELECT t.*, f.full_name as author_name
        FROM forum_topics t
        JOIN farmers f ON t.farmer_id = f.id
        WHERE t.id = ?
    """,
        [topic_id],
    )

    return success_response(topic, message="Topic created", status=HTTP.CREATED)


# ============================================================
# FORUM — GET TOPIC WITH REPLIES
# ============================================================
async def get_forum_topic(request, env, topic_id: int):
    """GET /api/learning/forum/topics/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    topic = await db.query_one(
        """
        SELECT t.*, f.full_name as author_name
        FROM forum_topics t
        JOIN farmers f ON t.farmer_id = f.id
        WHERE t.id = ?
    """,
        [topic_id],
    )

    if not topic:
        return error_response(
            "Topic not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND
        )

    # Increment view
    await db.execute(
        "UPDATE forum_topics SET view_count = view_count + 1 WHERE id = ?", [topic_id]
    )

    topic["replies"] = await db.query(
        """
        SELECT r.*, f.full_name as author_name
        FROM forum_replies r
        JOIN farmers f ON r.farmer_id = f.id
        WHERE r.topic_id = ?
        ORDER BY r.created_at
    """,
        [topic_id],
    )

    return success_response(topic)


# ============================================================
# FORUM — CREATE REPLY
# ============================================================
async def create_reply(request, env, topic_id: int):
    """POST /api/learning/forum/topics/:id/replies
    Body: {body}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ["body"])
    if err_msg:
        return error_response(
            err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD
        )

    db = DB(env)
    topic = await db.query_one(
        "SELECT id, farmer_id, title FROM forum_topics WHERE id = ?", [topic_id]
    )
    if not topic:
        return error_response(
            "Topic not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND
        )

    reply_id = await db.insert(
        "forum_replies",
        {
            "topic_id": topic_id,
            "farmer_id": user["id"],
            "body": str(data["body"]).strip(),
        },
    )

    # Update topic reply count + timestamp
    await db.execute(
        """
        UPDATE forum_topics
        SET reply_count = reply_count + 1, updated_at = datetime('now')
        WHERE id = ?
    """,
        [topic_id],
    )

    # Notify topic author
    if topic["farmer_id"] != user["id"]:
        author = await db.query_one(
            "SELECT full_name FROM farmers WHERE id = ?", [user["id"]]
        )
        await db.insert(
            "notifications",
            {
                "farmer_id": topic["farmer_id"],
                "type": "learning",
                "title": f"New reply to: {topic['title'][:50]}",
                "message": f"{author['full_name'] if author else 'Someone'} replied to your topic.",
                "action_url": f"/learning.html?topic={topic_id}",
            },
        )

    reply = await db.query_one(
        """
        SELECT r.*, f.full_name as author_name
        FROM forum_replies r
        JOIN farmers f ON r.farmer_id = f.id
        WHERE r.id = ?
    """,
        [reply_id],
    )

    return success_response(reply, message="Reply posted", status=HTTP.CREATED)


# ============================================================
# EXPERTS
# ============================================================
async def list_experts(request, env):
    """GET /api/learning/experts
    Query: specialty?
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)

    where = ["available = 1"]
    params = []

    specialty = url.search_params.get("specialty")
    if specialty:
        where.append("specialty LIKE ?")
        params.append(f"%{specialty}%")

    experts = await db.query(
        f"""
        SELECT id, name, specialty, bio, photo_url, hourly_rate, currency, languages
        FROM experts
        WHERE {" AND ".join(where)}
        ORDER BY name
    """,
        params,
    )

    return success_response(experts)


# ============================================================
# CONSULTATION BOOKING
# ============================================================
async def book_consultation(request, env):
    """POST /api/learning/consultations
    Body: {expert_id, scheduled_at, duration_minutes?, topic?}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ["expert_id", "scheduled_at"])
    if err_msg:
        return error_response(
            err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD
        )

    db = DB(env)
    expert = await db.query_one(
        "SELECT id, name, hourly_rate FROM experts WHERE id = ? AND available = 1",
        [to_int(data["expert_id"])],
    )
    if not expert:
        return error_response(
            "Expert not available", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND
        )

    duration = to_int(data.get("duration_minutes", 60))
    hourly_rate = to_float(expert.get("hourly_rate")) or 0
    cost = hourly_rate * (duration / 60)

    consultation_id = await db.insert(
        "consultations",
        {
            "farmer_id": user["id"],
            "expert_id": expert["id"],
            "scheduled_at": data["scheduled_at"],
            "duration_minutes": duration,
            "topic": data.get("topic"),
            "status": "scheduled",
            "cost": cost,
            "payment_status": "pending",
        },
    )

    # Notify farmer
    await db.insert(
        "notifications",
        {
            "farmer_id": user["id"],
            "type": "learning",
            "title": "Consultation booked",
            "message": f"Consultation with {expert['name']} scheduled. Cost: KES {cost:,.0f}.",
            "priority": "high",
        },
    )

    consultation = await db.query_one(
        """
        SELECT c.*, e.name as expert_name, e.specialty
        FROM consultations c
        JOIN experts e ON c.expert_id = e.id
        WHERE c.id = ?
    """,
        [consultation_id],
    )

    return success_response(
        consultation, message="Consultation booked", status=HTTP.CREATED
    )


# ============================================================
# MY CONSULTATIONS
# ============================================================
async def my_consultations(request, env):
    """GET /api/learning/consultations"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    consultations = await db.query(
        """
        SELECT c.*, e.name as expert_name, e.specialty, e.phone as expert_phone
        FROM consultations c
        JOIN experts e ON c.expert_id = e.id
        WHERE c.farmer_id = ?
        ORDER BY c.scheduled_at DESC
    """,
        [user["id"]],
    )

    return success_response(consultations)


# ============================================================
# LEARNING DASHBOARD
# ============================================================
async def learning_dashboard(request, env):
    """GET /api/learning/dashboard"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)

    # My enrolled courses
    my_courses = await db.query(
        """
        SELECT c.id, c.title, c.category, c.level, e.progress, e.completed
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.farmer_id = ?
        ORDER BY e.last_activity_at DESC
        LIMIT 5
    """,
        [user["id"]],
    )

    # Recommended (not enrolled)
    enrolled_ids = [c["id"] for c in my_courses]
    placeholders = ",".join(["?"] * len(enrolled_ids)) if enrolled_ids else "0"
    recommended = await db.query(
        f"""
        SELECT id, title, category, level, duration_minutes
        FROM courses
        WHERE published = 1 AND id NOT IN ({placeholders})
        ORDER BY id
        LIMIT 3
    """,
        enrolled_ids,
    )

    # Stats
    stats = await db.query_one(
        """
        SELECT
            COUNT(*) as enrolled_count,
            COUNT(CASE WHEN completed = 1 THEN 1 END) as completed_count,
            COALESCE(AVG(progress), 0) as avg_progress
        FROM enrollments WHERE farmer_id = ?
    """,
        [user["id"]],
    )

    # Recent videos
    videos = await db.query("""
        SELECT id, title, thumbnail_url, duration_seconds, category
        FROM videos WHERE published = 1        ORDER BY created_at DESC LIMIT 4
    """)

    # Upcoming consultations
    consultations = await db.query(
        """
        SELECT c.id, c.scheduled_at, c.topic, e.name as expert_name
        FROM consultations c
        JOIN experts e ON c.expert_id = e.id
        WHERE c.farmer_id = ? AND c.status = 'scheduled'
        AND c.scheduled_at >= datetime('now')
        ORDER BY c.scheduled_at ASC
        LIMIT 3
    """,
        [user["id"]],
    )

    return success_response(
        {
            "my_courses": my_courses,
            "recommended": recommended,
            "stats": {
                "enrolled": stats["enrolled_count"] if stats else 0,
                "completed": stats["completed_count"] if stats else 0,
                "avg_progress": round(stats["avg_progress"], 1)
                if stats and stats["avg_progress"]
                else 0,
            },
            "recent_videos": videos,
            "upcoming_consultations": consultations,
        }
    )

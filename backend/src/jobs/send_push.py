"""
Job: send_push
Payload: {token, platform, title, body, url?}
Sends web push (VAPID) or FCM depending on platform.
"""
import json
from utils import log_event, log_error


async def run(payload: dict, env):
    """Send a push notification to a single device token."""
    token = payload.get("token")
    platform = payload.get("platform", "web")
    title = payload.get("title", "Marcbantu")
    body = payload.get("body", "")
    url = payload.get("url")

    if not token:
        log_error("send_push: missing 'token'")
        return

    if platform == "web":
        await _send_web_push(env, token, title, body, url)
    elif platform in ("android", "ios"):
        await _send_fcm(env, token, title, body, url)
    else:
        log_error(f"send_push: unknown platform '{platform}'")


async def _send_web_push(env, token: str, title: str, body: str, url: str = None):
    """Web Push via VAPID. In production, use a library or an external service."""
    # Simplified: log the intent. Full Web Push requires signing with VAPID keys.
    # For production, integrate with a push service like OneSignal or Web-Push lib.
    log_event("web_push_queued", {"token": token[:20], "title": title})


async def _send_fcm(env, token: str, title: str, body: str, url: str = None):
    """Firebase Cloud Messaging."""
    fcm_key = getattr(env, "FCM_SERVER_KEY", "")
    if not fcm_key:
        log_error("send_push: FCM not configured")
        return

    data = {
        "to": token,
        "notification": {"title": title, "body": body},
    }
    if url:
        data["data"] = {"url": url}

    try:
        response = await fetch(
            "https://fcm.googleapis.com/fcm/send",
            method="POST",
            headers={
                "Authorization": f"key={fcm_key}",
                "Content-Type": "application/json",
            },
            body=json.dumps(data),
        )
        result = await response.json()
        log_event("fcm_sent", {"success": result.get("success", 0)})
    except Exception as e:
        log_error(f"FCM send failed: {str(e)}")
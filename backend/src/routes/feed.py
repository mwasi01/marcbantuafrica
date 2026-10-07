"""
Marcbantu Africa — Farmer Feed routes.
Social layer: posts, likes, comments, follows.

Feeds are scoped by visibility:
- public      → visible to everyone
- followers   → visible to followers only
- private     → only visible to author
"""
from utils import (
    success_response, error_response, parse_json, require_auth,
    now_iso, to_int, log_event, require_fields,
    paginated_response, _sp,
)
from constants import HTTP, ErrorCode
from db import DB


# ============================================================
# HELPERS
# ============================================================
async def _hydrate_posts(db, posts, viewer_id):
    """Add author info, viewer's like status, and top comments."""
    if not posts:
        return []

    post_ids = [p['id'] for p in posts]
    author_ids = list({p['farmer_id'] for p in posts})
    placeholders_p = ','.join(['?'] * len(post_ids))
    placeholders_a = ','.join(['?'] * len(author_ids))

    # Authors
    authors = await db.query(
        f"SELECT id, full_name, county, location FROM farmers WHERE id IN ({placeholders_a})",
        author_ids
    )
    authors_map = {a['id']: a for a in authors}

    # Viewer's likes
    liked = await db.query(
        f"SELECT post_id FROM post_likes WHERE post_id IN ({placeholders_p}) AND farmer_id = ?",
        post_ids + [viewer_id]
    )
    liked_set = {l['post_id'] for l in liked}

    # Top 3 comments per post
    comments = await db.query(f"""
        SELECT c.id, c.post_id, c.body, c.created_at, c.farmer_id, f.full_name as author_name
        FROM post_comments c
        JOIN farmers f ON c.farmer_id = f.id
        WHERE c.post_id IN ({placeholders_p})
        ORDER BY c.created_at ASC
    """, post_ids)
    comments_by_post = {}
    for c in comments:
        comments_by_post.setdefault(c['post_id'], []).append(c)

    # Viewer's follows
    followed = await db.query(
        f"SELECT following_id FROM follows WHERE follower_id = ? AND following_id IN ({placeholders_a})",
        [viewer_id] + author_ids
    )
    followed_set = {f['following_id'] for f in followed}

    result = []
    for p in posts:
        author = authors_map.get(p['farmer_id'], {})
        p['author'] = {
            'id': author.get('id'),
            'full_name': author.get('full_name', 'Farmer'),
            'county': author.get('county'),
            'location': author.get('location'),
        }
        p['liked_by_me'] = p['id'] in liked_set
        p['following_author'] = p['farmer_id'] in followed_set
        p['is_mine'] = (p['farmer_id'] == viewer_id)
        p['comments'] = comments_by_post.get(p['id'], [])[:3]
        p['comments_preview_count'] = len(comments_by_post.get(p['id'], []))
        result.append(p)

    return result


# ============================================================
# LIST FEED
# ============================================================
async def list_feed(request, env):
    """GET /api/feed
    Query: tab=all|following|mine, page, page_size
    """
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)
    tab = url.search_params.get('tab', 'all')
    page = to_int(url.search_params.get('page', 1), 1)
    page_size = min(to_int(url.search_params.get('page_size', 20), 20), 50)

    params = []
    if tab == 'mine':
        where = "p.farmer_id = ?"
        params.append(user['id'])
    elif tab == 'following':
        # Posts by farmers this user follows
        where = "p.farmer_id IN (SELECT following_id FROM follows WHERE follower_id = ?) AND p.visibility != 'private'"
        params.append(user['id'])
    else:
        # Public + own followers-only
        where = """(
            p.visibility = 'public'
            OR (p.visibility = 'followers' AND p.farmer_id IN (
                SELECT following_id FROM follows WHERE follower_id = ?
            ))
            OR p.farmer_id = ?
        )"""
        params.extend([user['id'], user['id']])

    sql = f"""
        SELECT p.*
        FROM posts p
        WHERE {where}
        ORDER BY p.pinned DESC, p.created_at DESC
    """

    result = await db.paginate(sql, params, page=page, page_size=page_size)
    result['items'] = await _hydrate_posts(db, result.get('items', []), user['id'])
    return paginated_response(result, message="Feed retrieved")


# ============================================================
# CREATE POST
# ============================================================
async def create_post(request, env):
    """POST /api/feed/posts
    Body: {content, media_url?, media_type?, visibility?}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ['content'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    content = str(data['content']).strip()
    if len(content) < 1:
        return error_response("Post cannot be empty",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)
    if len(content) > 5000:
        return error_response("Post too long (max 5000 chars)",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    visibility = data.get('visibility', 'public')
    if visibility not in ('public', 'followers', 'private'):
        visibility = 'public'

    db = DB(env)
    post_id = await db.insert('posts', {
        'farmer_id': user['id'],
        'content': content,
        'media_url': data.get('media_url'),
        'media_type': data.get('media_type', 'none'),
        'visibility': visibility,
    })

    post = await db.query_one("SELECT * FROM posts WHERE id = ?", [post_id])
    hydrated = (await _hydrate_posts(db, [post], user['id']))[0]

    log_event("post_created", {"post_id": post_id, "farmer_id": user['id']})
    return success_response(hydrated, message="Post created", status=HTTP.CREATED)


# ============================================================
# GET SINGLE POST
# ============================================================
async def get_post(request, env, post_id: int):
    """GET /api/feed/posts/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    post = await db.query_one("SELECT * FROM posts WHERE id = ?", [post_id])
    if not post:
        return error_response("Post not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    # Visibility check
    if post['visibility'] == 'private' and post['farmer_id'] != user['id']:
        return error_response("Post not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)
    if post['visibility'] == 'followers' and post['farmer_id'] != user['id']:
        following = await db.query_one(
            "SELECT id FROM follows WHERE follower_id = ? AND following_id = ?",
            [user['id'], post['farmer_id']]
        )
        if not following:
            return error_response("Post not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    hydrated = (await _hydrate_posts(db, [post], user['id']))[0]

    # Full comment list
    hydrated['comments'] = await db.query("""
        SELECT c.id, c.body, c.created_at, c.farmer_id, f.full_name as author_name
        FROM post_comments c
        JOIN farmers f ON c.farmer_id = f.id
        WHERE c.post_id = ?
        ORDER BY c.created_at ASC
    """, [post_id])

    return success_response(hydrated)


# ============================================================
# DELETE POST
# ============================================================
async def delete_post(request, env, post_id: int):
    """DELETE /api/feed/posts/:id — only own posts"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    post = await db.query_one("SELECT farmer_id FROM posts WHERE id = ?", [post_id])
    if not post:
        return error_response("Post not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)
    if post['farmer_id'] != user['id']:
        return error_response("Not authorized", status=HTTP.FORBIDDEN, code=ErrorCode.FORBIDDEN)

    await db.delete('posts', 'id = ?', [post_id])
    return success_response(None, message="Post deleted")


# ============================================================
# LIKE / UNLIKE
# ============================================================
async def like_post(request, env, post_id: int):
    """POST /api/feed/posts/:id/like"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    post = await db.query_one("SELECT id FROM posts WHERE id = ?", [post_id])
    if not post:
        return error_response("Post not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    existing = await db.query_one(
        "SELECT id FROM post_likes WHERE post_id = ? AND farmer_id = ?",
        [post_id, user['id']]
    )
    if existing:
        return success_response({"liked": True, "changed": False})

    await db.insert('post_likes', {'post_id': post_id, 'farmer_id': user['id']})
    await db.execute("UPDATE posts SET like_count = like_count + 1 WHERE id = ?", [post_id])

    return success_response({"liked": True, "changed": True})


async def unlike_post(request, env, post_id: int):
    """DELETE /api/feed/posts/:id/like"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    await db.delete('post_likes', 'post_id = ? AND farmer_id = ?', [post_id, user['id']])
    await db.execute(
        "UPDATE posts SET like_count = MAX(0, like_count - 1) WHERE id = ?",
        [post_id]
    )
    return success_response({"liked": False})


# ============================================================
# COMMENTS
# ============================================================
async def create_comment(request, env, post_id: int):
    """POST /api/feed/posts/:id/comments
    Body: {body}
    """
    user, err = require_auth(request, env)
    if err:
        return err

    data = await parse_json(request)
    err_msg = require_fields(data, ['body'])
    if err_msg:
        return error_response(err_msg, status=HTTP.BAD_REQUEST, code=ErrorCode.MISSING_FIELD)

    body = str(data['body']).strip()
    if len(body) < 1 or len(body) > 1000:
        return error_response("Comment must be 1-1000 chars",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)
    post = await db.query_one("SELECT id, farmer_id FROM posts WHERE id = ?", [post_id])
    if not post:
        return error_response("Post not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    comment_id = await db.insert('post_comments', {
        'post_id': post_id,
        'farmer_id': user['id'],
        'body': body,
    })
    await db.execute("UPDATE posts SET comment_count = comment_count + 1 WHERE id = ?", [post_id])

    # Notify post author (if not self)
    if post['farmer_id'] != user['id']:
        author = await db.query_one("SELECT full_name FROM farmers WHERE id = ?", [user['id']])
        await db.insert('notifications', {
            'farmer_id': post['farmer_id'],
            'type': 'social',
            'title': 'New comment on your post',
            'message': f"{author['full_name'] if author else 'Someone'}: {body[:80]}",
        })

    comment = await db.query_one("""
        SELECT c.id, c.body, c.created_at, c.farmer_id, f.full_name as author_name
        FROM post_comments c
        JOIN farmers f ON c.farmer_id = f.id
        WHERE c.id = ?
    """, [comment_id])

    return success_response(comment, message="Comment posted", status=HTTP.CREATED)


async def delete_comment(request, env, comment_id: int):
    """DELETE /api/feed/comments/:id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    comment = await db.query_one("SELECT id, post_id, farmer_id FROM post_comments WHERE id = ?", [comment_id])
    if not comment:
        return error_response("Comment not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)
    if comment['farmer_id'] != user['id']:
        return error_response("Not authorized", status=HTTP.FORBIDDEN, code=ErrorCode.FORBIDDEN)

    await db.delete('post_comments', 'id = ?', [comment_id])
    await db.execute("UPDATE posts SET comment_count = MAX(0, comment_count - 1) WHERE id = ?", [comment['post_id']])
    return success_response(None, message="Comment deleted")


# ============================================================
# FOLLOWS
# ============================================================
async def follow_farmer(request, env, farmer_id: int):
    """POST /api/feed/follow/:farmer_id"""
    user, err = require_auth(request, env)
    if err:
        return err

    if farmer_id == user['id']:
        return error_response("Cannot follow yourself",
                             status=HTTP.BAD_REQUEST, code=ErrorCode.VALIDATION_ERROR)

    db = DB(env)
    target = await db.query_one("SELECT id FROM farmers WHERE id = ?", [farmer_id])
    if not target:
        return error_response("Farmer not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    existing = await db.query_one(
        "SELECT id FROM follows WHERE follower_id = ? AND following_id = ?",
        [user['id'], farmer_id]
    )
    if existing:
        return success_response({"following": True, "changed": False})

    await db.insert('follows', {'follower_id': user['id'], 'following_id': farmer_id})

    # Notify
    me = await db.query_one("SELECT full_name FROM farmers WHERE id = ?", [user['id']])
    await db.insert('notifications', {
        'farmer_id': farmer_id,
        'type': 'social',
        'title': 'New follower',
        'message': f"{me['full_name'] if me else 'Someone'} started following you.",
    })

    return success_response({"following": True, "changed": True}, message="Following")


async def unfollow_farmer(request, env, farmer_id: int):
    """DELETE /api/feed/follow/:farmer_id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    await db.delete('follows', 'follower_id = ? AND following_id = ?', [user['id'], farmer_id])
    return success_response({"following": False}, message="Unfollowed")


async def list_followers(request, env, farmer_id: int):
    """GET /api/feed/followers/:farmer_id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    followers = await db.query("""
        SELECT f.id, f.full_name, f.county, f.location, fo.created_at as followed_at
        FROM follows fo
        JOIN farmers f ON fo.follower_id = f.id
        WHERE fo.following_id = ?
        ORDER BY fo.created_at DESC
        LIMIT 200
    """, [farmer_id])
    return success_response(followers)


async def list_following(request, env, farmer_id: int):
    """GET /api/feed/following/:farmer_id"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    following = await db.query("""
        SELECT f.id, f.full_name, f.county, f.location, fo.created_at as followed_at
        FROM follows fo
        JOIN farmers f ON fo.following_id = f.id
        WHERE fo.follower_id = ?
        ORDER BY fo.created_at DESC
        LIMIT 200
    """, [farmer_id])
    return success_response(following)


# ============================================================
# SUGGESTED FARMERS
# ============================================================
async def suggested_farmers(request, env):
    """GET /api/feed/suggested — farmers in same county or with same crops"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)

    me = await db.query_one("SELECT county FROM farmers WHERE id = ?", [user['id']])
    my_county = me['county'] if me else None

    # Farmers I'm not already following
    sql = """
        SELECT f.id, f.full_name, f.county, f.location,
               (SELECT COUNT(*) FROM follows WHERE following_id = f.id) as followers_count,
               (SELECT COUNT(*) FROM posts WHERE farmer_id = f.id) as posts_count
        FROM farmers f
        WHERE f.id != ?
          AND f.id NOT IN (SELECT following_id FROM follows WHERE follower_id = ?)
    """
    params = [user['id'], user['id']]

    if my_county:
        sql += " ORDER BY CASE WHEN f.county = ? THEN 0 ELSE 1 END, followers_count DESC LIMIT 10"
        params.append(my_county)
    else:
        sql += " ORDER BY followers_count DESC LIMIT 10"

    farmers = await db.query(sql, params)
    return success_response(farmers)


# ============================================================
# FARMER PUBLIC PROFILE (for feed)
# ============================================================
async def farmer_profile(request, env, farmer_id: int):
    """GET /api/feed/farmer/:id — public profile"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)

    farmer = await db.query_one("""
        SELECT id, full_name, county, location, created_at
        FROM farmers WHERE id = ?
    """, [farmer_id])
    if not farmer:
        return error_response("Farmer not found", status=HTTP.NOT_FOUND, code=ErrorCode.NOT_FOUND)

    followers = await db.query_one(
        "SELECT COUNT(*) as n FROM follows WHERE following_id = ?", [farmer_id]
    )
    following = await db.query_one(
        "SELECT COUNT(*) as n FROM follows WHERE follower_id = ?", [farmer_id]
    )
    posts_count = await db.query_one(
        "SELECT COUNT(*) as n FROM posts WHERE farmer_id = ?", [farmer_id]
    )
    is_following = await db.query_one(
        "SELECT id FROM follows WHERE follower_id = ? AND following_id = ?",
        [user['id'], farmer_id]
    )

    farmer['followers_count'] = followers['n'] if followers else 0
    farmer['following_count'] = following['n'] if following else 0
    farmer['posts_count'] = posts_count['n'] if posts_count else 0
    farmer['is_following'] = bool(is_following)
    farmer['is_me'] = (farmer['id'] == user['id'])

    return success_response(farmer)


# ============================================================
# FARMER'S POSTS (for profile view)
# ============================================================
async def farmer_posts(request, env, farmer_id: int):
    """GET /api/feed/farmer/:id/posts"""
    user, err = require_auth(request, env)
    if err:
        return err

    db = DB(env)
    url = _sp(request)
    page = to_int(url.search_params.get('page', 1), 1)
    page_size = min(to_int(url.search_params.get('page_size', 20), 20), 50)

    # Visibility
    if farmer_id == user['id']:
        where = "p.farmer_id = ?"
        params = [farmer_id]
    else:
        following = await db.query_one(
            "SELECT id FROM follows WHERE follower_id = ? AND following_id = ?",
            [user['id'], farmer_id]
        )
        if following:
            where = "p.farmer_id = ? AND p.visibility IN ('public', 'followers')"
        else:
            where = "p.farmer_id = ? AND p.visibility = 'public'"
        params = [farmer_id]

    sql = f"SELECT p.* FROM posts p WHERE {where} ORDER BY p.created_at DESC"
    result = await db.paginate(sql, params, page=page, page_size=page_size)
    result['items'] = await _hydrate_posts(db, result.get('items', []), user['id'])
    return paginated_response(result, message="Posts retrieved")

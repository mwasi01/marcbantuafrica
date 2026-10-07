/**
 * Marcbantu Africa — Farmer Feed.
 * Posts, likes, comments, follows.
 */
(function () {
    'use strict';
    if (!window.Auth?.requireLogin()) return;

    if (!window.UI) {
        console.error('[feed.js] window.UI missing — app.js failed to load.');
        return;
    }

    const { $, $$, Fmt, Toast, Modal } = window.UI;

    let state = {
        tab: 'all',
        page: 1,
        pageSize: 20,
        hasMore: true,
        loading: false,
        me: null,
    };

    // ============================================================
    // INIT
    // ============================================================
    async function loadMe() {
        const r = await Api.profile();
        if (!r.ok) return;
        state.me = r.data;
        const avatar = $('#my-avatar');
        const name = $('#my-name');
        const loc = $('#my-location');
        if (avatar) avatar.textContent = Fmt.initials(state.me.full_name);
        if (name) name.textContent = state.me.full_name;
        if (loc) loc.textContent = [state.me.county, state.me.location].filter(Boolean).join(', ') || 'Kenya';

        // Fetch follower/following/post counts
        const profile = await Api.feedFarmerProfile(state.me.id);
        if (profile.ok) {
            const p = profile.data;
            $('#stat-posts').textContent = p.posts_count || 0;
            $('#stat-followers').textContent = p.followers_count || 0;
            $('#stat-following').textContent = p.following_count || 0;
        }
    }

    // ============================================================
    // FEED
    // ============================================================
    async function loadFeed(reset = true) {
        if (state.loading) return;
        state.loading = true;
        if (reset) {
            state.page = 1;
            state.hasMore = true;
            $('#feed-stream').innerHTML = '<div style="text-align:center;padding:40px;color:#8a9c8c"><i class="fas fa-spinner fa-spin" style="font-size:24px"></i></div>';
        }

        const r = await Api.feedList({ tab: state.tab, page: state.page, page_size: state.pageSize });
        state.loading = false;

        if (!r.ok) {
            $('#feed-stream').innerHTML = '<div style="padding:30px;text-align:center;color:#c0392b;">Failed to load feed</div>';
            return;
        }

        const posts = r.data || [];
        const stream = $('#feed-stream');
        if (reset) stream.innerHTML = '';

        if (!posts.length && state.page === 1) {
            stream.innerHTML = emptyStateFor(state.tab);
            $('#load-more').style.display = 'none';
            return;
        }

        posts.forEach((p) => stream.insertAdjacentHTML('beforeend', renderPost(p)));

        state.hasMore = posts.length >= state.pageSize;
        $('#load-more').style.display = state.hasMore ? 'block' : 'none';

        bindPostActions();
    }

    function emptyStateFor(tab) {
        const messages = {
            all: { icon: 'fa-users', title: 'No posts yet', sub: 'Be the first to share an update with the community.' },
            following: { icon: 'fa-user-check', title: 'You are not following anyone yet', sub: 'Check "Suggested Farmers" on the right to start following.' },
            mine: { icon: 'fa-user', title: 'You have not posted yet', sub: 'Share what is happening on your farm.' },
        };
        const m = messages[tab] || messages.all;
        return `
            <div class="panel" style="text-align:center;padding:60px 20px">
                <i class="fas ${m.icon}" style="font-size:3rem;color:#d4a017;opacity:.5"></i>
                <h3 style="margin:1rem 0 .3rem;color:#1a3c2e">${m.title}</h3>
                <p style="color:#4a5a4a;font-size:.9rem;margin:0">${m.sub}</p>
            </div>`;
    }

    function renderPost(p) {
        const author = p.author || {};
        const initials = Fmt.initials(author.full_name || 'Farmer');
        const location = [author.county, author.location].filter(Boolean).join(', ');
        const isMine = p.is_mine;

        return `
            <div class="panel feed-post" data-post-id="${p.id}" style="margin-bottom:1rem">
                <!-- Post header -->
                <div style="display:flex;gap:12px;align-items:flex-start">
                    <div style="width:44px;height:44px;border-radius:50%;background:#1a3c2e;color:#e6b422;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.95rem;flex-shrink:0">${initials}</div>
                    <div style="flex:1;min-width:0">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">
                            <div style="min-width:0">
                                <a href="#" class="post-author-link" data-farmer-id="${author.id}" style="color:#1a3c2e;font-weight:700;font-size:.95rem;text-decoration:none">${author.full_name || 'Farmer'}</a>
                                ${location ? `<span style="color:#8a9c8c;font-size:.82rem"> · ${location}</span>` : ''}
                            </div>
                            <div style="display:flex;gap:6px;align-items:center;flex-shrink:0">
                                ${!isMine ? `<button class="btn-icon follow-btn" data-farmer-id="${author.id}" data-following="${p.following_author ? '1' : '0'}" title="${p.following_author ? 'Unfollow' : 'Follow'}"><i class="fas fa-${p.following_author ? 'user-check' : 'user-plus'}" style="color:${p.following_author ? '#2e7d32' : '#1a3c2e'}"></i></button>` : ''}
                                ${isMine ? `<button class="btn-icon delete-post-btn" data-post-id="${p.id}" title="Delete"><i class="fas fa-trash" style="color:#c0392b"></i></button>` : ''}
                            </div>
                        </div>
                        <div style="font-size:.78rem;color:#8a9c8c;margin-top:2px">${Fmt.dateRelative(p.created_at)}</div>
                    </div>
                </div>

                <!-- Post body -->
                <div style="margin-top:12px;color:#1a3c2e;font-size:.95rem;line-height:1.6;white-space:pre-wrap;word-wrap:break-word">${escapeHtml(p.content)}</div>

                ${p.media_url && p.media_type === 'image' ? `
                    <div style="margin-top:12px;border-radius:12px;overflow:hidden;max-height:500px;background:#fbfcf9">
                        <img src="${p.media_url}" alt="" style="width:100%;height:auto;display:block" onerror="this.parentElement.style.display='none'">
                    </div>` : ''}

                <!-- Actions -->
                <div style="display:flex;gap:1rem;margin-top:14px;padding-top:12px;border-top:1px solid #eef1ea">
                    <button class="feed-action like-btn" data-post-id="${p.id}" data-liked="${p.liked_by_me ? '1' : '0'}" style="background:none;border:none;cursor:pointer;font-family:inherit;color:${p.liked_by_me ? '#c0392b' : '#4a5a4a'};font-size:.88rem;display:flex;align-items:center;gap:6px">
                        <i class="fas fa-${p.liked_by_me ? 'heart' : 'heart'}"></i> <span class="like-count">${p.like_count || 0}</span>
                    </button>
                    <button class="feed-action comment-toggle" data-post-id="${p.id}" style="background:none;border:none;cursor:pointer;font-family:inherit;color:#4a5a4a;font-size:.88rem;display:flex;align-items:center;gap:6px">
                        <i class="fas fa-comment"></i> <span>${p.comment_count || 0}</span>
                    </button>
                    <button class="feed-action share-btn" data-post-id="${p.id}" style="background:none;border:none;cursor:pointer;font-family:inherit;color:#4a5a4a;font-size:.88rem;display:flex;align-items:center;gap:6px;margin-left:auto">
                        <i class="fas fa-share"></i> Share
                    </button>
                </div>

                <!-- Comments preview -->
                <div class="comments-preview" data-post-id="${p.id}" style="margin-top:12px;padding-top:12px;border-top:1px dashed #eef1ea;display:${(p.comments || []).length ? 'block' : 'none'}">
                    ${(p.comments || []).map((c) => `
                        <div style="display:flex;gap:8px;margin-bottom:8px;font-size:.88rem">
                            <strong style="color:#1a3c2e;flex-shrink:0">${escapeHtml(c.author_name || 'Farmer')}:</strong>
                            <span style="color:#4a5a4a;word-wrap:break-word">${escapeHtml(c.body)}</span>
                        </div>
                    `).join('')}
                </div>

                <!-- Comment form (hidden by default) -->
                <div class="comment-form" data-post-id="${p.id}" style="display:none;margin-top:10px;gap:8px;align-items:center">
                    <input type="text" class="comment-input" placeholder="Write a comment..." style="flex:1;padding:10px;border-radius:20px;border:1.5px solid #e2e8dd;font-family:inherit;font-size:.9rem">
                    <button class="btn-primary comment-submit" data-post-id="${p.id}" style="padding:8px 16px;border-radius:20px;font-size:.85rem">Post</button>
                </div>
            </div>`;
    }

    // ============================================================
    // POST ACTIONS
    // ============================================================
    function bindPostActions() {
        // Like
        $$('.like-btn').forEach((el) => {
            el.addEventListener('click', async () => {
                const postId = el.dataset.postId;
                const liked = el.dataset.liked === '1';
                const countSpan = el.querySelector('.like-count');
                let count = parseInt(countSpan.textContent) || 0;

                // Optimistic
                el.dataset.liked = liked ? '0' : '1';
                el.style.color = liked ? '#4a5a4a' : '#c0392b';
                countSpan.textContent = liked ? Math.max(0, count - 1) : count + 1;

                const r = liked
                    ? await Api.feedUnlike(postId)
                    : await Api.feedLike(postId);

                if (!r.ok) {
                    // Revert
                    el.dataset.liked = liked ? '1' : '0';
                    el.style.color = liked ? '#c0392b' : '#4a5a4a';
                    countSpan.textContent = count;
                    Toast.error('Failed to like');
                }
            });
        });

        // Delete post
        $$('.delete-post-btn').forEach((el) => {
            el.addEventListener('click', async () => {
                const ok = await Modal.confirm('Delete this post?', 'Confirm');
                if (!ok) return;
                const r = await Api.feedDeletePost(el.dataset.postId);
                if (!r.ok) { Toast.error(r.error); return; }
                Toast.success('Post deleted');
                loadFeed(true);
            });
        });

        // Follow
        $$('.follow-btn').forEach((el) => {
            el.addEventListener('click', async () => {
                const farmerId = el.dataset.farmerId;
                const following = el.dataset.following === '1';
                const r = following
                    ? await Api.feedUnfollow(farmerId)
                    : await Api.feedFollow(farmerId);
                if (!r.ok) { Toast.error(r.error); return; }
                Toast.success(following ? 'Unfollowed' : 'Now following');
                el.dataset.following = following ? '0' : '1';
                el.querySelector('i').className = following ? 'fas fa-user-plus' : 'fas fa-user-check';
                el.querySelector('i').style.color = following ? '#1a3c2e' : '#2e7d32';
                loadFeed(true);
            });
        });

        // Toggle comment form
        $$('.comment-toggle').forEach((el) => {
            el.addEventListener('click', () => {
                const form = document.querySelector(`.comment-form[data-post-id="${el.dataset.postId}"]`);
                if (form) {
                    form.style.display = form.style.display === 'flex' ? 'none' : 'flex';
                    form.querySelector('.comment-input')?.focus();
                }
            });
        });

        // Submit comment
        $$('.comment-submit').forEach((el) => {
            el.addEventListener('click', async () => {
                const postId = el.dataset.postId;
                const input = document.querySelector(`.comment-form[data-post-id="${postId}"] .comment-input`);
                const body = input?.value.trim();
                if (!body) return;

                el.disabled = true;
                el.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                const r = await Api.feedComment(postId, { body });
                el.disabled = false;
                el.textContent = 'Post';

                if (!r.ok) { Toast.error(r.error); return; }
                input.value = '';
                Toast.success('Comment posted');
                loadFeed(true);
            });
        });

        // Enter key in comment input
        $$('.comment-input').forEach((input) => {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    const postId = input.closest('.comment-form').dataset.postId;
                    document.querySelector(`.comment-submit[data-post-id="${postId}"]`)?.click();
                }
            });
        });

        // Author link → profile
        $$('.post-author-link').forEach((el) => {
            el.addEventListener('click', (e) => {
                e.preventDefault();
                openFarmerProfile(el.dataset.farmerId);
            });
        });

        // Share (copy link)
        $$('.share-btn').forEach((el) => {
            el.addEventListener('click', () => {
                const url = `${window.location.origin}/feed.html?post=${el.dataset.postId}`;
                navigator.clipboard.writeText(url).then(() => {
                    Toast.success('Link copied');
                }).catch(() => {
                    Toast.info('Post link: ' + url);
                });
            });
        });
    }

    // ============================================================
    // COMPOSE MODAL
    // ============================================================
    function openComposeModal() {
        const modal = Modal.open(`
            <div style="padding:28px;max-width:600px">
                <h2 style="margin:0 0 16px;color:#1a3c2e"><i class="fas fa-pen" style="color:#d4a017"></i> Share an Update</h2>
                <form id="composeForm" style="display:flex;flex-direction:column;gap:14px">
                    <textarea name="content" required maxlength="5000" rows="5" placeholder="What's happening on your farm? Share a tip, a win, a question..." style="padding:14px;border-radius:12px;border:1.5px solid #e2e8dd;font-family:inherit;font-size:.95rem;resize:vertical"></textarea>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                        <label style="display:flex;flex-direction:column;gap:6px">
                            <span style="font-size:13px;font-weight:600;color:#1a3c2e">Visibility</span>
                            <select name="visibility" style="padding:10px;border-radius:10px;border:1.5px solid #e2e8dd">
                                <option value="public">Public — everyone</option>
                                <option value="followers">Followers only</option>
                                <option value="private">Only me</option>
                            </select>
                        </label>
                        <label style="display:flex;flex-direction:column;gap:6px">
                            <span style="font-size:13px;font-weight:600;color:#1a3c2e">Photo (optional)</span>
                            <input type="file" id="mediaFile" accept="image/*" style="padding:6px;font-size:.85rem">
                        </label>
                    </div>
                    <div style="display:flex;gap:12px;justify-content:flex-end">
                        <button type="button" class="btn-outline" data-action="cancel">Cancel</button>
                        <button type="submit" class="btn-primary"><i class="fas fa-paper-plane"></i> Post</button>
                    </div>
                </form>
            </div>
        `);

        modal.querySelector('[data-action="cancel"]').addEventListener('click', () => Modal.close(modal));

        const form = modal.querySelector('#composeForm');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = form.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Posting...';

            let mediaUrl = null;
            let mediaType = 'none';

            // Upload image if provided
            const fileInput = form.querySelector('#mediaFile');
            if (fileInput?.files?.length) {
                const upload = await Api.uploadFile(fileInput.files[0], { context: 'post' });
                if (!upload.ok) {
                    Toast.error('Image upload failed: ' + (upload.error || 'unknown'));
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Post';
                    return;
                }
                mediaUrl = upload.data?.url || upload.data?.file_url || null;
                mediaType = 'image';
            }

            const payload = {
                content: form.querySelector('[name="content"]').value,
                visibility: form.querySelector('[name="visibility"]').value,
                media_url: mediaUrl,
                media_type: mediaType,
            };

            const r = await Api.feedCreatePost(payload);
            if (!r.ok) {
                Toast.error(r.error || 'Failed to post');
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Post';
                return;
            }
            Toast.success('Posted!');
            Modal.close(modal);
            state.tab = 'all';
            updateTabUI();
            loadFeed(true);
            loadMe();
        });
    }

    // ============================================================
    // FARMER PROFILE MODAL
    // ============================================================
    async function openFarmerProfile(farmerId) {
        if (!farmerId) return;
        const [profR, postsR] = await Promise.all([
            Api.feedFarmerProfile(farmerId),
            Api.feedFarmerPosts(farmerId, { page: 1, page_size: 10 }),
        ]);

        if (!profR.ok) { Toast.error('Could not load profile'); return; }
        const p = profR.data;
        const posts = postsR.ok ? (postsR.data || []) : [];

        const initials = Fmt.initials(p.full_name);
        const location = [p.county, p.location].filter(Boolean).join(', ') || 'Kenya';

        Modal.open(`
            <div style="padding:28px;max-width:640px;max-height:80vh;overflow-y:auto">
                <div style="display:flex;gap:16px;align-items:center;margin-bottom:1.5rem">
                    <div style="width:64px;height:64px;border-radius:50%;background:#1a3c2e;color:#e6b422;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.4rem;flex-shrink:0">${initials}</div>
                    <div style="flex:1">
                        <h2 style="margin:0;color:#1a3c2e;font-size:1.3rem">${escapeHtml(p.full_name)}</h2>
                        <div style="color:#8a9c8c;font-size:.9rem">${escapeHtml(location)}</div>
                    </div>
                    ${!p.is_me ? `
                        <button id="profile-follow-btn" class="btn-primary" data-farmer-id="${p.id}" data-following="${p.is_following ? '1' : '0'}" style="padding:8px 16px;border-radius:20px">
                            <i class="fas fa-${p.is_following ? 'user-check' : 'user-plus'}"></i> ${p.is_following ? 'Following' : 'Follow'}
                        </button>` : ''}
                </div>
                <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;text-align:center;padding:1rem;background:#fbfcf9;border-radius:12px;margin-bottom:1.5rem">
                    <div><strong style="display:block;font-size:1.3rem;color:#1a3c2e">${p.posts_count || 0}</strong><span style="font-size:.82rem;color:#8a9c8c">Posts</span></div>
                    <div><strong style="display:block;font-size:1.3rem;color:#1a3c2e">${p.followers_count || 0}</strong><span style="font-size:.82rem;color:#8a9c8c">Followers</span></div>
                    <div><strong style="display:block;font-size:1.3rem;color:#1a3c2e">${p.following_count || 0}</strong><span style="font-size:.82rem;color:#8a9c8c">Following</span></div>
                </div>
                <h3 style="margin:0 0 12px;color:#1a3c2e;font-size:1rem">Recent Posts</h3>
                ${posts.length ? posts.slice(0, 5).map((post) => `
                    <div style="padding:12px;border:1px solid #eef1ea;border-radius:10px;margin-bottom:10px">
                        <div style="font-size:.78rem;color:#8a9c8c">${Fmt.dateRelative(post.created_at)}</div>
                        <div style="color:#1a3c2e;font-size:.9rem;margin-top:4px;line-height:1.5">${escapeHtml(Fmt.truncate(post.content, 200))}</div>
                        <div style="display:flex;gap:1rem;margin-top:8px;font-size:.78rem;color:#8a9c8c">
                            <span><i class="fas fa-heart"></i> ${post.like_count || 0}</span>
                            <span><i class="fas fa-comment"></i> ${post.comment_count || 0}</span>
                        </div>
                    </div>`).join('') : '<p style="color:#8a9c8c;text-align:center;padding:20px">No posts yet</p>'}
                <div style="text-align:right;margin-top:1rem">
                    <button class="btn-outline" onclick="document.querySelector('.modal-overlay.open')?.remove()">Close</button>
                </div>
            </div>
        `);

        const followBtn = document.querySelector('#profile-follow-btn');
        if (followBtn) {
            followBtn.addEventListener('click', async () => {
                const following = followBtn.dataset.following === '1';
                const r = following
                    ? await Api.feedUnfollow(followBtn.dataset.farmerId)
                    : await Api.feedFollow(followBtn.dataset.farmerId);
                if (!r.ok) { Toast.error(r.error); return; }
                followBtn.dataset.following = following ? '0' : '1';
                followBtn.innerHTML = `<i class="fas fa-${following ? 'user-plus' : 'user-check'}"></i> ${following ? 'Follow' : 'Following'}`;
                Toast.success(following ? 'Unfollowed' : 'Following');
            });
        }
    }

    // ============================================================
    // SUGGESTED FARMERS
    // ============================================================
    async function loadSuggested() {
        const r = await Api.feedSuggested();
        const list = $('#suggested-list');
        if (!list) return;
        if (!r.ok || !r.data?.length) {
            list.innerHTML = '<div style="text-align:center;padding:16px;color:#8a9c8c;font-size:.85rem">No suggestions yet</div>';
            return;
        }
        list.innerHTML = r.data.slice(0, 6).map((f) => {
            const initials = Fmt.initials(f.full_name);
            return `
                <div style="display:flex;gap:10px;align-items:center">
                    <div style="width:36px;height:36px;border-radius:50%;background:#1a3c2e;color:#e6b422;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.8rem;flex-shrink:0">${initials}</div>
                    <div style="flex:1;min-width:0">
                        <div style="font-weight:600;color:#1a3c2e;font-size:.88rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(f.full_name)}</div>
                        <div style="font-size:.75rem;color:#8a9c8c">${f.county || 'Kenya'} · ${f.posts_count || 0} posts</div>
                    </div>
                    <button class="btn-icon follow-suggested" data-farmer-id="${f.id}" title="Follow"><i class="fas fa-user-plus" style="color:#1a3c2e"></i></button>
                </div>`;
        }).join('');

        $$('.follow-suggested').forEach((el) => {
            el.addEventListener('click', async () => {
                const r = await Api.feedFollow(el.dataset.farmerId);
                if (!r.ok) { Toast.error(r.error); return; }
                Toast.success('Following');
                loadSuggested();
                loadFeed(true);
            });
        });
    }

    // ============================================================
    // TABS
    // ============================================================
    function updateTabUI() {
        $$('.feed-tab').forEach((el) => {
            const active = el.dataset.tab === state.tab;
            el.classList.toggle('active', active);
            el.style.color = active ? '#1a3c2e' : '#8a9c8c';
            el.style.borderBottomColor = active ? '#d4a017' : 'transparent';
        });
    }

    function initTabs() {
        $$('.feed-tab').forEach((el) => {
            el.addEventListener('click', () => {
                state.tab = el.dataset.tab;
                updateTabUI();
                loadFeed(true);
            });
        });
        updateTabUI();
    }

    // ============================================================
    // HELPERS
    // ============================================================
    function escapeHtml(s) {
        if (!s) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // ============================================================
    // BOOT
    // ============================================================
    document.addEventListener('DOMContentLoaded', () => {
        loadMe();
        initTabs();
        loadFeed(true);
        loadSuggested();

        const compose = $('#compose-btn');
        if (compose) compose.addEventListener('click', openComposeModal);

        const loadMore = $('#load-more-btn');
        if (loadMore) loadMore.addEventListener('click', () => {
            if (!state.hasMore || state.loading) return;
            state.page += 1;
            loadFeed(false);
        });
    });
})();

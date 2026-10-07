/**
 * Marcbantu Africa — Direct Messages.
 */
(function () {
    'use strict';
    if (!window.Auth?.requireLogin()) return;

    if (!window.UI) {
        console.error('[messages.js] window.UI missing — app.js failed to load.');
        return;
    }

    const { $, $$, Fmt, Toast, Modal } = window.UI;

    let state = {
        conversations: [],
        currentConvo: null,
        messages: [],
        pollTimer: null,
        me: null,
    };

    // ============================================================
    // INIT
    // ============================================================
    async function loadMe() {
        const r = await Api.profile();
        if (r.ok) state.me = r.data;
    }

    // ============================================================
    // CONVERSATIONS
    // ============================================================
    async function loadConversations() {
        const r = await Api.dmConversations();
        if (!r.ok) {
            $('#conv-items').innerHTML = '<div style="padding:30px;text-align:center;color:#c0392b;font-size:.85rem">Failed to load</div>';
            return;
        }
        state.conversations = r.data || [];
        renderConversations();
        updateBadge();
    }

    function renderConversations() {
        const container = $('#conv-items');
        if (!container) return;
        if (!state.conversations.length) {
            container.innerHTML = '<div style="padding:40px 20px;text-align:center;color:#8a9c8c;font-size:.85rem"><i class="fas fa-comment-dots" style="font-size:2rem;opacity:.4;margin-bottom:.5rem;display:block"></i>No conversations yet.<br>Start one with "New Message".</div>';
            return;
        }

        const search = ($('#conv-search')?.value || '').toLowerCase();
        const filtered = search
            ? state.conversations.filter((c) =>
                (c.other_user?.full_name || '').toLowerCase().includes(search))
            : state.conversations;

        container.innerHTML = filtered.map((c) => {
            const u = c.other_user || {};
            const initials = Fmt.initials(u.full_name || 'F');
            const last = c.last_message || {};
            const preview = last.body || 'No messages yet';
            const isActive = state.currentConvo && state.currentConvo.id === c.id;

            return '<div class="conv-item ' + (isActive ? 'active' : '') + '" data-convo-id="' + c.id + '">' +
                '<div class="conv-avatar">' + initials + '</div>' +
                '<div class="conv-body">' +
                    '<div class="conv-name">' +
                        '<span>' + escapeHtml(u.full_name || 'Farmer') + '</span>' +
                        '<span class="conv-time">' + (c.last_message_at ? Fmt.dateRelative(c.last_message_at) : '') + '</span>' +
                    '</div>' +
                    '<div class="conv-preview">' +
                        (last.sender_id === state.me?.id ? '<strong>You:</strong> ' : '') +
                        escapeHtml(Fmt.truncate(preview, 45)) +
                        (c.unread_count > 0 ? '<span class="conv-badge">' + c.unread_count + '</span>' : '') +
                    '</div>' +
                '</div>' +
            '</div>';
        }).join('');

        $$('.conv-item').forEach((el) => {
            el.addEventListener('click', () => openConversation(parseInt(el.dataset.convoId)));
        });
    }

    // ============================================================
    // OPEN CONVERSATION
    // ============================================================
    async function openConversation(convoId) {
        if (state.currentConvo && state.currentConvo.id === convoId) return;

        let convo = state.conversations.find((c) => c.id === convoId);
        if (!convo) {
            const r = await Api.dmGetConversation(convoId);
            if (!r.ok) { Toast.error('Conversation not found'); return; }
            convo = r.data;
        }

        state.currentConvo = convo;
        renderConversations();
        renderChatHeader();
        await loadMessages();
        $('#messages-layout').classList.add('showing-chat');
        restartPolling();
    }

    function renderChatHeader() {
        const c = state.currentConvo;
        if (!c) return;
        const u = c.other_user || {};
        const initials = Fmt.initials(u.full_name || 'F');

        $('#chat-area').innerHTML =
            '<div class="chat-header">' +
                '<button class="chat-back" id="chat-back-btn"><i class="fas fa-arrow-left"></i></button>' +
                '<div class="chat-header-avatar">' + initials + '</div>' +
                '<div style="flex:1;min-width:0">' +
                    '<div class="chat-header-name">' + escapeHtml(u.full_name || 'Farmer') + '</div>' +
                    '<div class="chat-header-loc">' + escapeHtml([u.county, u.location].filter(Boolean).join(', ') || 'Kenya') + '</div>' +
                '</div>' +
            '</div>' +
            '<div class="chat-messages" id="chat-messages"></div>' +
            '<div class="chat-compose">' +
                '<textarea id="msg-input" rows="1" placeholder="Type a message..."></textarea>' +
                '<button id="send-btn" disabled><i class="fas fa-paper-plane"></i></button>' +
            '</div>';

        const input = $('#msg-input');
        const sendBtn = $('#send-btn');

        input.addEventListener('input', () => {
            sendBtn.disabled = !input.value.trim();
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 120) + 'px';
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        sendBtn.addEventListener('click', sendMessage);

        $('#chat-back-btn')?.addEventListener('click', () => {
            $('#messages-layout').classList.remove('showing-chat');
            state.currentConvo = null;
            renderConversations();
            renderEmptyChat();
        });
    }

    function renderEmptyChat() {
        $('#chat-area').innerHTML =
            '<div class="empty-chat">' +
                '<i class="fas fa-comments"></i>' +
                '<h3 style="color:#1a3c2e;margin:0 0 .3rem">No conversation selected</h3>' +
                '<p style="margin:0">Pick a conversation or start a new one.</p>' +
            '</div>';
    }

    // ============================================================
    // LOAD MESSAGES
    // ============================================================
    async function loadMessages(preserveScroll) {
        if (!state.currentConvo) return;
        const container = $('#chat-messages');
        if (!container) return;

        if (!preserveScroll) {
            container.innerHTML = '<div style="text-align:center;padding:20px;color:#8a9c8c;font-size:.85rem"><i class="fas fa-spinner fa-spin"></i></div>';
        }

        const r = await Api.dmMessages(state.currentConvo.id, { page: 1, page_size: 100 });
        if (!r.ok) {
            if (!preserveScroll) container.innerHTML = '<div style="text-align:center;padding:20px;color:#c0392b">Failed to load messages</div>';
            return;
        }

        state.messages = r.data || [];
        renderMessages(preserveScroll);

        if (state.currentConvo.unread_count > 0) {
            await Api.dmMarkRead(state.currentConvo.id);
            state.currentConvo.unread_count = 0;
            loadConversations();
        }
    }

    function renderMessages(preserveScroll) {
        const container = $('#chat-messages');
        if (!container) return;

        const prevScrollHeight = container.scrollHeight;
        const wasAtBottom = container.scrollTop + container.clientHeight >= prevScrollHeight - 50;

        if (!state.messages.length) {
            container.innerHTML = '<div style="text-align:center;padding:40px;color:#8a9c8c;font-size:.85rem">No messages yet. Say hi! 👋</div>';
            return;
        }

        container.innerHTML = state.messages.map((m) => {
            const mine = m.sender_id === state.me?.id;
            const readMark = mine
                ? (m.read_at ? '<span class="read">✓✓</span>' : '<span>✓</span>')
                : '';
            return '<div class="msg ' + (mine ? 'mine' : 'theirs') + '">' +
                '<div class="msg-bubble">' + escapeHtml(m.body) + '</div>' +
                '<div class="msg-meta">' + Fmt.time(m.created_at) + ' ' + readMark + '</div>' +
            '</div>';
        }).join('');

        if (!preserveScroll || wasAtBottom) {
            container.scrollTop = container.scrollHeight;
        }
    }

    // ============================================================
    // SEND MESSAGE
    // ============================================================
    async function sendMessage() {
        if (!state.currentConvo) return;
        const input = $('#msg-input');
        const body = input.value.trim();
        if (!body) return;

        input.value = '';
        input.style.height = 'auto';
        $('#send-btn').disabled = true;

        const r = await Api.dmSend(state.currentConvo.id, { body });
        if (!r.ok) {
            Toast.error(r.error || 'Failed to send');
            input.value = body;
            $('#send-btn').disabled = false;
            return;
        }

        state.messages.push(r.data);
        renderMessages();
        loadConversations();
    }

    // ============================================================
    // POLLING
    // ============================================================
    function restartPolling() {
        if (state.pollTimer) clearInterval(state.pollTimer);
        state.pollTimer = setInterval(async () => {
            if (document.hidden) return;
            if (state.currentConvo) {
                await loadMessages(true);
            }
            const r = await Api.dmConversations();
            if (r.ok) {
                state.conversations = r.data || [];
                renderConversations();
                updateBadge();
            }
        }, 5000);
    }

    async function updateBadge() {
        const r = await Api.dmUnreadCount();
        if (!r.ok) return;
        const count = r.data?.unread_count || 0;
        const badge = $('#msg-badge');
        if (badge) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.style.display = count > 0 ? 'inline-block' : 'none';
        }
    }

    // ============================================================
    // NEW MESSAGE MODAL
    // ============================================================
    async function openNewChatModal() {
        const r = await Api.dmSearchFarmers({});
        const farmers = r.ok ? r.data : [];

        const modal = Modal.open(
            '<div style="padding:28px;max-width:480px">' +
                '<h2 style="margin:0 0 6px;color:#1a3c2e"><i class="fas fa-comment-dots" style="color:#d4a017"></i> New Message</h2>' +
                '<p style="margin:0 0 16px;color:#4a5a4a;font-size:.9rem">Choose a farmer to message.</p>' +
                '<input type="text" id="farmer-search" placeholder="Search farmers by name..." style="width:100%;padding:12px 16px;border-radius:12px;border:1.5px solid #e2e8dd;font-family:inherit;font-size:.95rem;margin-bottom:14px">' +
                '<div id="farmer-list" style="max-height:320px;overflow-y:auto;display:flex;flex-direction:column;gap:4px">' +
                    renderFarmerOptions(farmers) +
                '</div>' +
                '<div style="display:flex;gap:12px;justify-content:flex-end;margin-top:16px">' +
                    '<button type="button" class="btn-outline" data-action="cancel">Cancel</button>' +
                '</div>' +
            '</div>'
        );

        const searchInput = modal.querySelector('#farmer-search');
        const listEl = modal.querySelector('#farmer-list');

        searchInput.addEventListener('input', async () => {
            const q = searchInput.value.trim();
            const resp = await Api.dmSearchFarmers({ q });
            listEl.innerHTML = renderFarmerOptions(resp.ok ? resp.data : []);
            bindFarmerOptions();
        });

        function bindFarmerOptions() {
            listEl.querySelectorAll('[data-pick-farmer]').forEach((el) => {
                el.addEventListener('click', async () => {
                    const fid = parseInt(el.dataset.pickFarmer);
                    const start = await Api.dmStartConversation(fid);
                    Modal.close(modal);
                    if (!start.ok) { Toast.error(start.error); return; }
                    await loadConversations();
                    const convo = state.conversations.find((c) => c.id === start.data.id);
                    if (convo) {
                        openConversation(start.data.id);
                    } else {
                        state.currentConvo = start.data;
                        renderChatHeader();
                        await loadMessages();
                        $('#messages-layout').classList.add('showing-chat');
                    }
                });
            });
        }

        bindFarmerOptions();
        modal.querySelector('[data-action="cancel"]').addEventListener('click', () => Modal.close(modal));
    }

    function renderFarmerOptions(farmers) {
        if (!farmers.length) {
            return '<div style="text-align:center;padding:30px;color:#8a9c8c;font-size:.85rem">No farmers found</div>';
        }
        return farmers.map((f) => {
            const initials = Fmt.initials(f.full_name);
            return '<div data-pick-farmer="' + f.id + '" style="padding:12px;border-radius:10px;cursor:pointer;display:flex;gap:12px;align-items:center">' +
                '<div style="width:40px;height:40px;border-radius:50%;background:#1a3c2e;color:#e6b422;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.85rem;flex-shrink:0">' + initials + '</div>' +
                '<div style="flex:1;min-width:0">' +
                    '<div style="font-weight:600;color:#1a3c2e;font-size:.92rem">' + escapeHtml(f.full_name) + '</div>' +
                    '<div style="font-size:.78rem;color:#8a9c8c">' + escapeHtml([f.county, f.location].filter(Boolean).join(', ') || 'Kenya') + '</div>' +
                '</div>' +
            '</div>';
        }).join('');
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
    document.addEventListener('DOMContentLoaded', async () => {
        await loadMe();
        await loadConversations();
        await updateBadge();
        restartPolling();

        $('#conv-search')?.addEventListener('input', renderConversations);
        $('#new-chat-btn')?.addEventListener('click', openNewChatModal);

        const urlParams = new URLSearchParams(window.location.search);
        const cid = urlParams.get('c');
        if (cid) {
            openConversation(parseInt(cid));
        }
    });
})();

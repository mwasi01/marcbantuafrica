/**
 * Marcbantu Africa — Learning page.
 */
(function () {
    'use strict';
    if (!window.Auth?.requireLogin()) return;


    // === Marcbantu UI guard ===
    if (!window.UI) {
        console.error('[learning.js] window.UI missing — app.js failed to load.');
        return;
    }
    // === end guard ===
    const { $, $$, Fmt, Toast, Modal } = window.UI;

    let state = {
        courses: [],
        myCourses: [],
        videos: [],
        chatSessionId: localStorage.getItem('marcbantu_chat_session') || null,
    };

    async function loadAll() {
        await Promise.all([
            loadDashboard(),
            loadCourses(),
            loadVideos(),
        ]);
    }

    async function loadDashboard() {
        const r = await Api.learningDashboard();
        if (!r.ok) return;
        const d = r.data;

        const container = $('#learning-kpis');
        if (container) {
            container.innerHTML = `
                <div class="kpi"><div class="kpi-label">Enrolled</div><div class="kpi-value">${d.stats?.enrolled || 0}</div></div>
                <div class="kpi"><div class="kpi-label">Completed</div><div class="kpi-value" style="color:#2e7d32;">${d.stats?.completed || 0}</div></div>
                <div class="kpi"><div class="kpi-label">Avg Progress</div><div class="kpi-value">${d.stats?.avg_progress || 0}%</div></div>
            `;
        }

        // My courses
        const mc = $('#my-courses');
        if (mc) {
            if (!d.my_courses?.length) {
                mc.innerHTML = '<div style="text-align:center; padding:20px; color:#8a9c8c;">No courses yet. Browse below to enroll.</div>';
            } else {
                mc.innerHTML = d.my_courses.map((c) => `
                    <div style="background:#fff; border:1px solid #e2e8dd; border-radius:14px; padding:1.2rem; margin-bottom:1rem; border-left:5px solid #d4a017; cursor:pointer;" data-course-id="${c.id}">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:1rem;">
                            <div style="flex:1;">
                                <h4 style="color:#1a3c2e; margin:0 0 .3rem; font-size:1rem;">${c.title}</h4>
                                <div style="font-size:.82rem; color:#4a5a4a;">${Fmt.titleCase(c.category)} · ${Fmt.titleCase(c.level)}</div>
                            </div>
                            <span style="font-size:11px; padding:3px 10px; border-radius:20px; font-weight:700; background:${c.completed ? '#e8f0e1' : '#fef3d0'}; color:${c.completed ? '#2e7d32' : '#b8860b'};">
                                ${c.completed ? 'Completed' : c.progress + '%'}
                            </span>
                        </div>
                        <div style="margin-top:.6rem; height:6px; background:#eef1ea; border-radius:20px; overflow:hidden;">
                            <div style="width:${c.progress}%; height:100%; background:linear-gradient(90deg,#2f5d3a,#d4a017);"></div>
                        </div>
                    </div>
                `).join('');

                $$('[data-course-id]').forEach((el) =>
                    el.addEventListener('click', () => openCourseDetail(el.dataset.courseId)));
            }
        }
    }

    async function loadCourses() {
        const r = await Api.listCourses({});
        if (!r.ok) return;
        state.courses = r.data || [];
        renderCourses();
    }

    function renderCourses() {
        const container = $('#all-courses');
        if (!container) return;
        container.innerHTML = state.courses.map((c) => `
            <div style="background:linear-gradient(135deg,#fff,#fbfcf9); border:1px solid #e2e8dd; border-radius:16px; padding:1.5rem; border-left:5px solid #d4a017; display:flex; flex-direction:column; gap:.6rem;">
                <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <h4 style="color:#1a3c2e; margin:0; font-size:1rem;">${c.title}</h4>
                    ${c.is_free ? '<span style="font-size:10px; background:#e8f0e1; color:#2e7d32; padding:2px 8px; border-radius:20px; font-weight:700;">FREE</span>' : '<span style="font-size:10px; background:#fef3d0; color:#b8860b; padding:2px 8px; border-radius:20px; font-weight:700;">PRO</span>'}
                </div>
                <p style="margin:0; color:#4a5a4a; font-size:.88rem; line-height:1.5;">${Fmt.truncate(c.description || '', 100)}</p>
                <div style="display:flex; gap:1rem; font-size:.78rem; color:#4a5a4a;">
                    <span><i class="fas fa-video"></i> ${c.lesson_count} lessons</span>
                    <span><i class="fas fa-clock"></i> ${c.duration_minutes || 0} min</span>
                    <span><i class="fas fa-signal"></i> ${Fmt.titleCase(c.level)}</span>
                </div>
                <div style="margin-top:auto; padding-top:.6rem;">
                    ${c.enrolled
                ? `<button class="btn-outline" style="width:100%; padding:.6rem;" data-course-id="${c.id}" data-action="view-course">Continue (${c.progress}%)</button>`
                : `<button class="btn-primary" style="width:100%; padding:.6rem; justify-content:center;" data-course-id="${c.id}" data-action="enroll">Enroll Now</button>`}
                </div>
            </div>
        `).join('');

        $$('[data-action="enroll"]').forEach((el) =>
            el.addEventListener('click', () => enrollInCourse(el.dataset.courseId)));
        $$('[data-action="view-course"]').forEach((el) =>
            el.addEventListener('click', () => openCourseDetail(el.dataset.courseId)));
    }

    async function enrollInCourse(courseId) {
        const r = await Api.enroll(parseInt(courseId));
        if (!r.ok) { Toast.error(r.error); return; }
        Toast.success('Enrolled! Start learning now.');
        loadAll();
    }

    async function openCourseDetail(courseId) {
        const r = await Api.getCourse(courseId);
        if (!r.ok) { Toast.error(r.error); return; }
        const c = r.data;

        const modal = Modal.open(`
            <div style="padding:28px; max-width:600px; max-height:80vh; overflow-y:auto;">
                <h2 style="margin:0 0 6px; color:#1a3c2e;">${c.title}</h2>
                <div style="font-size:.85rem; color:#4a5a4a; margin-bottom:16px;">${Fmt.titleCase(c.category)} · ${c.duration_minutes || 0} min · ${c.lessons?.length || 0} lessons</div>
                <p style="color:#4a5a4a; line-height:1.6; margin-bottom:20px;">${c.long_description || c.description || ''}</p>
                <h3 style="color:#1a3c2e; font-size:1rem; margin-bottom:10px;">Lessons</h3>
                <div style="display:flex; flex-direction:column; gap:8px;">
                    ${(c.lessons || []).map((l, i) => `
                        <div style="display:flex; align-items:center; gap:12px; padding:10px; background:#fbfcf9; border-radius:10px; border:1px solid #eef1ea;">
                            <div style="width:32px; height:32px; border-radius:50%; background:${l.completed ? '#2f5d3a' : '#e8f0e1'}; color:${l.completed ? '#fff' : '#1a3c2e'}; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:.9rem; flex-shrink:0;">
                                ${l.completed ? '<i class="fas fa-check"></i>' : i + 1}
                            </div>
                            <div style="flex:1;">
                                <div style="font-weight:600; color:#1a3c2e; font-size:.9rem;">${l.title}</div>
                                <div style="font-size:.78rem; color:#8a9c8c;">${l.duration_minutes || 0} min</div>
                            </div>
                            <button class="btn-icon" data-action="toggle-lesson" data-lesson-id="${l.id}" data-course-id="${c.id}" data-completed="${l.completed ? 1 : 0}" title="${l.completed ? 'Mark incomplete' : 'Mark complete'}">
                                <i class="fas fa-${l.completed ? 'undo' : 'check'}"></i>
                            </button>
                        </div>
                    `).join('')}
                </div>
                <div style="display:flex; gap:12px; justify-content:flex-end; margin-top:20px;">
                    <button class="btn-outline" data-action="close">Close</button>
                </div>
            </div>
        `);

        modal.querySelector('[data-action="close"]').addEventListener('click', () => Modal.close(modal));

        modal.querySelectorAll('[data-action="toggle-lesson"]').forEach((el) =>
            el.addEventListener('click', async () => {
                const isCompleted = el.dataset.completed === '1';
                const r = await Api.updateProgress({
                    course_id: parseInt(el.dataset.courseId),
                    lesson_id: parseInt(el.dataset.lessonId),
                    completed: !isCompleted,
                });
                if (!r.ok) { Toast.error(r.error); return; }
                Toast.success(isCompleted ? 'Marked incomplete' : 'Lesson completed!');
                Modal.close(modal);
                loadAll();
            }));
    }

    async function loadVideos() {
        const r = await Api.listVideos({});
        if (!r.ok) return;
        state.videos = r.data || [];
        renderVideos();
    }

    function renderVideos() {
        const container = $('#video-list');
        if (!container) return;
        container.innerHTML = state.videos.map((v) => `
            <div style="background:linear-gradient(135deg,#2f5d3a,#1a3c2e); border-radius:14px; overflow:hidden; cursor:pointer;" data-video-url="${v.video_url || ''}">
                <div style="height:130px; display:flex; align-items:center; justify-content:center; position:relative;">
                    <i class="fas fa-play-circle" style="font-size:3rem; color:#e6b422;"></i>
                    <span style="position:absolute; bottom:8px; right:8px; background:rgba(0,0,0,.7); color:#fff; padding:2px 8px; border-radius:4px; font-size:.75rem;">
                        ${Math.floor((v.duration_seconds || 0) / 60)}:${String((v.duration_seconds || 0) % 60).padStart(2, '0')}
                    </span>
                </div>
                <div style="padding:.9rem; background:#fff;">
                    <h4 style="color:#1a3c2e; font-size:.9rem; margin:0 0 .2rem;">${Fmt.truncate(v.title, 50)}</h4>
                    <div style="font-size:.78rem; color:#4a5a4a;">${v.category || 'Learning'}</div>
                </div>
            </div>
        `).join('');
    }

    // ============================================================
    // CHATBOT
    // ============================================================
    function initChatbot() {
        const input = $('#chat-input');
        const sendBtn = $('#chat-send');
        const box = $('#chat-box');
        if (!input || !sendBtn || !box) return;

        // Load previous session if exists
        if (state.chatSessionId) {
            loadChatHistory();
        } else {
            appendChat('assistant', "Hello! I'm your Marcbantu farm advisor. Ask me about pests, weather, prices, records, or farm decisions.");
        }

        // Wire the "New Chat" button
        const newChatBtn = $('#new-chat-btn');
        if (newChatBtn) {
            newChatBtn.addEventListener('click', () => {
                state.chatSessionId = null;
                localStorage.removeItem('marcbantu_chat_session');
                box.innerHTML = '';
                appendChat('assistant', "New conversation started. What would you like to know?");
                input.focus();
            });
        }

        const send = async () => {
            const message = input.value.trim();
            if (!message) return;
            appendChat('user', renderMarkdown(message));
            input.value = '';
            input.focus();

            const typingId = appendChat('assistant', '<i class="fas fa-spinner fa-spin"></i> Thinking...');

            const r = await Api.chat(message, state.chatSessionId);
            document.getElementById(typingId)?.remove();

            if (!r.ok) {
                appendChat('assistant', 'Sorry, I had trouble responding. Please try again.');
                return;
            }

            if (r.data.session_id) {
                state.chatSessionId = r.data.session_id;
                localStorage.setItem('marcbantu_chat_session', r.data.session_id);
            }

            appendChat('assistant', renderMarkdown(r.data.reply || ''));
        };

        sendBtn.addEventListener('click', send);
        input.addEventListener('keypress', (e) => { if (e.key === 'Enter') send(); });
    }

    async function loadChatHistory() {
        const box = $('#chat-box');
        if (!box || !state.chatSessionId) return;
        box.innerHTML = '<div style="text-align:center; padding:12px; color:#8a9c8c; font-size:12px;"><i class="fas fa-spinner fa-spin"></i> Loading history...</div>';

        const r = await Api.chatHistory(state.chatSessionId);
        if (!r.ok || !r.data?.messages) {
            box.innerHTML = '';
            appendChat('assistant', "Hello! I'm your Marcbantu farm advisor. Ask me about pests, weather, prices, records, or farm decisions.");
            return;
        }

        box.innerHTML = '';
        r.data.messages.forEach((m) => {
            appendChat(m.role === 'user' ? 'user' : 'assistant', renderMarkdown(m.message));
        });
    }

    function renderMarkdown(text) {
        if (!text) return '';
        let html = String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        html = html.replace(/`([^`]+)`/g, '<code style="background:#eef1ea; padding:2px 5px; border-radius:4px; font-size:.88em;">$1</code>');
        html = html.replace(/^\s*(\d+)\.\s+(.+)$/gm, '<div style="padding-left:16px;">$1. $2</div>');
        html = html.replace(/^\s*[-•]\s+(.+)$/gm, '<div style="padding-left:16px;">• $1</div>');
        html = html.replace(/\n/g, '<br>');

        return html;
    }

    function appendChat(role, text) {
        const box = $('#chat-box');
        if (!box) return '';
        const id = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
        const isUser = role === 'user';
        const div = document.createElement('div');
        div.id = id;
        div.style.cssText = `display:flex; gap:10px; margin-bottom:10px; ${isUser ? 'flex-direction:row-reverse;' : ''}`;
        div.innerHTML = `
            <div style="width:34px; height:34px; border-radius:50%; background:${isUser ? '#e8f0e1' : '#1a3c2e'}; color:${isUser ? '#1a3c2e' : '#e6b422'}; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:.75rem; flex-shrink:0;">
                ${isUser ? 'You' : 'AI'}
            </div>
            <div style="background:${isUser ? '#e8f0e1' : '#fff'}; padding:10px 14px; border-radius:12px; font-size:.9rem; max-width:75%; color:${isUser ? '#1a3c2e' : '#4a5a4a'}; border:1px solid #eef1ea;">
                ${text}
            </div>
        `;
        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
        return id;
    }

    document.addEventListener('DOMContentLoaded', () => {
        loadAll();
        initChatbot();
    });
})();
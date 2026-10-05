/**
 * Marcbantu Africa — API Client.
 * Central fetch wrapper with JWT, error handling, and retries.
 *
 * All API calls go through `api.call()` or the convenience methods
 * (api.get, api.post, api.put, api.del).
 */

const API_BASE = (() => {
    // Auto-detect environment
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return 'http://localhost:8787';
    }
    return 'https://marcbantu-api.josuit-mwasi.workers.dev';
})();

const TOKEN_KEY = 'marcbantu_token';
const USER_KEY = 'marcbantu_user';
const REFRESH_BUFFER_MS = 5 * 60 * 1000; // Refresh 5 min before expiry


// ============================================================
// TOKEN STORAGE
// ============================================================
const Auth = {
    getToken() {
        try {
            return localStorage.getItem(TOKEN_KEY);
        } catch {
            return null;
        }
    },

    setToken(token) {
        try {
            localStorage.setItem(TOKEN_KEY, token);
        } catch (e) {
            console.warn('Failed to store token:', e);
        }
    },

    clearToken() {
        try {
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(USER_KEY);
        } catch { }
    },

    getUser() {
        try {
            const raw = localStorage.getItem(USER_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch {
            return null;
        }
    },

    setUser(user) {
        try {
            localStorage.setItem(USER_KEY, JSON.stringify(user));
        } catch { }
    },

    isLoggedIn() {
        return !!this.getToken();
    },

    /**
     * Decode JWT payload (no signature verification — for UX only).
     */
    decodeToken(token) {
        if (!token) return null;
        try {
            const parts = token.split('.');
            if (parts.length !== 3) return null;
            const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
            const padded = payload + '='.repeat((4 - payload.length % 4) % 4);
            return JSON.parse(atob(padded));
        } catch {
            return null;
        }
    },

    /**
     * True if token expires within the refresh buffer.
     */
    isExpiringSoon() {
        const token = this.getToken();
        if (!token) return false;
        const payload = this.decodeToken(token);
        if (!payload?.exp) return false;
        const expiresAt = payload.exp * 1000;
        return Date.now() > expiresAt - REFRESH_BUFFER_MS;
    },

    isExpired() {
        const token = this.getToken();
        if (!token) return true;
        const payload = this.decodeToken(token);
        if (!payload?.exp) return true;
        return Date.now() > payload.exp * 1000;
    },

    requireLogin(redirect = '/login.html') {
        if (!this.isLoggedIn() || this.isExpired()) {
            this.clearToken();
            window.location.href = redirect;
            return false;
        }
        return true;
    },

    logout(redirect = '/login.html') {
        this.clearToken();
        if (redirect) window.location.href = redirect;
    },
};


// ============================================================
// API CLIENT
// ============================================================
const api = {
    /**
     * Core request method.
     * @param {string} path - e.g. '/api/farms'
     * @param {object} options - { method, body, headers, raw }
     * @returns {Promise<{ok: boolean, status: number, data?: any, error?: string, code?: string}>}
     */
    async call(path, options = {}) {
        const method = (options.method || 'GET').toUpperCase();
        const headers = {
            'Accept': 'application/json',
            ...(options.headers || {}),
        };

        // Attach token
        const token = Auth.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        // Body handling
        let body = options.body;
        if (body && typeof body === 'object' && !(body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
            body = JSON.stringify(body);
        }

        const url = path.startsWith('http') ? path : `${API_BASE}${path}`;

        try {
            const response = await fetch(url, { method, headers, body });

            // 401 — clear and redirect
            if (response.status === 401) {
                Auth.clearToken();
                if (!window.location.pathname.includes('login')) {
                    window.location.href = '/login.html?expired=1';
                }
                return { ok: false, status: 401, error: 'Session expired' };
            }

            // 204 No Content
            if (response.status === 204) {
                return { ok: true, status: 204, data: null };
            }

            // Parse JSON
            let data;
            const contentType = response.headers.get('Content-Type') || '';
            if (contentType.includes('application/json')) {
                data = await response.json();
            } else {
                data = await response.text();
            }

            if (!response.ok) {
                const errMsg = data?.error?.message || data?.message || `Request failed (${response.status})`;
                const errCode = data?.error?.code;
                return { ok: false, status: response.status, error: errMsg, code: errCode, data };
            }

            // Unwrap {success, data, meta}
            if (data && typeof data === 'object' && 'success' in data) {
                return {
                    ok: true,
                    status: response.status,
                    data: data.data !== undefined ? data.data : data,
                    meta: data.meta,
                    message: data.message,
                };
            }

            return { ok: true, status: response.status, data };
        } catch (err) {
            console.error('API error:', err);
            return {
                ok: false,
                status: 0,
                error: navigator.onLine ? 'Network error. Please try again.' : 'You are offline.',
                code: 'NETWORK_ERROR',
            };
        }
    },

    get(path, params) {
        if (params && Object.keys(params).length) {
            const qs = new URLSearchParams(
                Object.entries(params).filter(([_, v]) => v !== undefined && v !== null && v !== '')
            ).toString();
            if (qs) path += (path.includes('?') ? '&' : '?') + qs;
        }
        return this.call(path, { method: 'GET' });
    },

    post(path, body) {
        return this.call(path, { method: 'POST', body });
    },

    put(path, body) {
        return this.call(path, { method: 'PUT', body });
    },

    patch(path, body) {
        return this.call(path, { method: 'PATCH', body });
    },

    del(path) {
        return this.call(path, { method: 'DELETE' });
    },

    /**
     * Upload a file with form data.
     */
    async upload(path, file, extra = {}) {
        const form = new FormData();
        form.append('file', file);
        for (const [k, v] of Object.entries(extra)) {
            if (v !== undefined && v !== null) form.append(k, v);
        }
        return this.call(path, { method: 'POST', body: form });
    },

    /**
     * Retry wrapper — useful for queued/sync operations.
     */
    async callWithRetry(path, options = {}, maxRetries = 3) {
        let last;
        for (let i = 0; i < maxRetries; i++) {
            last = await this.call(path, options);
            if (last.ok) return last;
            if (last.status >= 400 && last.status < 500) return last; // don't retry client errors
            await new Promise(r => setTimeout(r, 500 * Math.pow(2, i))); // exponential backoff
        }
        return last;
    },
};


// ============================================================
// CONVENIENCE HELPERS
// ============================================================
const Api = {
    // Auth
    register: (data) => api.post('/api/auth/register', data),
    login: (data) => api.post('/api/auth/login', data),
    logout: () => api.post('/api/auth/logout'),
    me: () => api.get('/api/auth/me'),
    refresh: () => api.post('/api/auth/refresh'),
    changePassword: (data) => api.post('/api/auth/change-password', data),
    forgotPassword: (phone) => api.post('/api/auth/forgot-password', { phone }),
    resetPassword: (data) => api.post('/api/auth/reset-password', data),

    // Farmers
    profile: () => api.get('/api/farmers/me'),
    updateProfile: (data) => api.put('/api/farmers/me', data),
    stats: () => api.get('/api/farmers/stats'),
    dashboard: () => api.get('/api/farmers/dashboard'),
    subscription: () => api.get('/api/farmers/subscription'),

    // Farms
    listFarms: () => api.get('/api/farms'),
    createFarm: (data) => api.post('/api/farms', data),
    getFarm: (id) => api.get(`/api/farms/${id}`),
    updateFarm: (id, data) => api.put(`/api/farms/${id}`, data),
    deleteFarm: (id) => api.del(`/api/farms/${id}`),
    farmSummary: (id) => api.get(`/api/farms/${id}/summary`),

    // Plots
    listPlots: (farmId) => api.get(`/api/farms/${farmId}/plots`),
    createPlot: (farmId, data) => api.post(`/api/farms/${farmId}/plots`, data),
    updatePlot: (id, data) => api.put(`/api/plots/${id}`, data),
    deletePlot: (id) => api.del(`/api/plots/${id}`),

    // Enterprises
    listEnterprises: (farmId) => api.get(`/api/farms/${farmId}/enterprises`),
    createEnterprise: (farmId, data) => api.post(`/api/farms/${farmId}/enterprises`, data),
    getEnterprise: (id) => api.get(`/api/enterprises/${id}`),
    updateEnterprise: (id, data) => api.put(`/api/enterprises/${id}`, data),
    deleteEnterprise: (id) => api.del(`/api/enterprises/${id}`),
    enterprisePerformance: (id) => api.get(`/api/enterprises/${id}/performance`),

    // Records
    listRecords: (params) => api.get('/api/records', params),
    createRecord: (data) => api.post('/api/records', data),
    getRecord: (id) => api.get(`/api/records/${id}`),
    updateRecord: (id, data) => api.put(`/api/records/${id}`, data),
    deleteRecord: (id) => api.del(`/api/records/${id}`),
    recordsSummary: (params) => api.get('/api/records/summary', params),
    syncOffline: (records, source = 'pwa') => api.post('/api/records/sync', { records, source }),

    // Finance
    listTransactions: (params) => api.get('/api/finance/transactions', params),
    createTransaction: (data) => api.post('/api/finance/transactions', data),
    updateTransaction: (id, data) => api.put(`/api/finance/transactions/${id}`, data),
    deleteTransaction: (id) => api.del(`/api/finance/transactions/${id}`),
    profitLoss: (params) => api.get('/api/finance/profit-loss', params),
    financeDashboard: (params) => api.get('/api/finance/dashboard', params),
    cashFlow: (params) => api.get('/api/finance/cash-flow', params),
    expenseBreakdown: (params) => api.get('/api/finance/expense-breakdown', params),
    enterprisePerformanceFinance: () => api.get('/api/finance/enterprise-performance'),

    // Planning
    listBudgets: (params) => api.get('/api/planning/budgets', params),
    createBudget: (data) => api.post('/api/planning/budgets', data),
    getBudget: (id) => api.get(`/api/planning/budgets/${id}`),
    updateBudget: (id, data) => api.put(`/api/planning/budgets/${id}`, data),
    deleteBudget: (id) => api.del(`/api/planning/budgets/${id}`),
    addBudgetItem: (budgetId, data) => api.post(`/api/planning/budgets/${budgetId}/items`, data),
    updateBudgetItem: (budgetId, itemId, data) => api.put(`/api/planning/budgets/${budgetId}/items/${itemId}`, data),
    deleteBudgetItem: (budgetId, itemId) => api.del(`/api/planning/budgets/${budgetId}/items/${itemId}`),
    cashFlowForecast: (params) => api.get('/api/planning/cash-flow-forecast', params),
    seasonalPlan: (farmId) => api.get('/api/planning/seasonal-plan', { farm_id: farmId }),

    // Decisions
    breakeven: (data) => api.post('/api/decisions/breakeven', data),
    grossMargin: (data) => api.post('/api/decisions/gross-margin', data),
    marginalAnalysis: (data) => api.post('/api/decisions/marginal', data),
    loanAffordability: (data) => api.post('/api/decisions/loan', data),
    payback: (data) => api.post('/api/decisions/payback', data),
    whatIf: (data) => api.post('/api/decisions/what-if', data),
    riskAssessment: (data) => api.post('/api/decisions/risk', data),
    compareEnterprises: (params) => api.get('/api/decisions/compare', params),

    // Operations
    listTasks: (params) => api.get('/api/tasks', params),
    createTask: (data) => api.post('/api/tasks', data),
    updateTask: (id, data) => api.put(`/api/tasks/${id}`, data),
    deleteTask: (id) => api.del(`/api/tasks/${id}`),
    completeTask: (id) => api.post(`/api/tasks/${id}/complete`),
    listWorkers: (params) => api.get('/api/workers', params),
    createWorker: (data) => api.post('/api/workers', data),
    updateWorker: (id, data) => api.put(`/api/workers/${id}`, data),
    deleteWorker: (id) => api.del(`/api/workers/${id}`),
    recordAttendance: (data) => api.post('/api/attendance', data),
    listAttendance: (params) => api.get('/api/attendance', params),
    listEquipment: (params) => api.get('/api/equipment', params),
    createEquipment: (data) => api.post('/api/equipment', data),
    updateEquipment: (id, data) => api.put(`/api/equipment/${id}`, data),
    logMaintenance: (id, data) => api.post(`/api/equipment/${id}/maintenance`, data),
    operationsDashboard: (params) => api.get('/api/operations/dashboard', params),

    // Market
    marketPrices: (params) => api.get('/api/market/prices', params),
    priceHistory: (params) => api.get('/api/market/prices/history', params),
    listSales: (params) => api.get('/api/market/sales', params),
    createSale: (data) => api.post('/api/market/sales', data),
    updateSale: (id, data) => api.put(`/api/market/sales/${id}`, data),
    deleteSale: (id) => api.del(`/api/market/sales/${id}`),
    salesSummary: (params) => api.get('/api/market/sales/summary', params),
    listBuyers: (params) => api.get('/api/market/buyers', params),
    createBuyer: (data) => api.post('/api/market/buyers', data),
    listContracts: (params) => api.get('/api/market/contracts', params),
    createContract: (data) => api.post('/api/market/contracts', data),
    listAlerts: () => api.get('/api/market/alerts'),
    createAlert: (data) => api.post('/api/market/alerts', data),
    deleteAlert: (id) => api.del(`/api/market/alerts/${id}`),

    // Weather
    weather: (params) => api.get('/api/weather', params),
    rainfall: (params) => api.get('/api/weather/rainfall', params),
    weatherAlerts: (params) => api.get('/api/weather/alerts', params),
    historicalWeather: (params) => api.get('/api/weather/historical', params),

    // Pest
    listScouting: (params) => api.get('/api/pest/scouting', params),
    createScouting: (data) => api.post('/api/pest/scouting', data),
    updateScouting: (id, data) => api.put(`/api/pest/scouting/${id}`, data),
    deleteScouting: (id) => api.del(`/api/pest/scouting/${id}`),
    listTreatments: (params) => api.get('/api/pest/treatments', params),
    createTreatment: (data) => api.post('/api/pest/treatments', data),
    diagnosePest: (data) => api.post('/api/pest/diagnose', data),
    pestLibrary: (params) => api.get('/api/pest/library', params),
    pestAlerts: (farmId) => api.get('/api/pest/alerts', { farm_id: farmId }),
    pestDashboard: (params) => api.get('/api/pest/dashboard', params),

    // Learning
    listCourses: (params) => api.get('/api/learning/courses', params),
    getCourse: (id) => api.get(`/api/learning/courses/${id}`),
    listLessons: (courseId) => api.get(`/api/learning/courses/${courseId}/lessons`),
    enroll: (courseId) => api.post('/api/learning/enroll', { course_id: courseId }),
    myCourses: () => api.get('/api/learning/my-courses'),
    updateProgress: (data) => api.post('/api/learning/progress', data),
    listVideos: (params) => api.get('/api/learning/videos', params),
    chat: (message, sessionId) => api.post('/api/learning/chat', { message, session_id: sessionId }),
    chatHistory: (sessionId) => api.get('/api/learning/chat/history', { session_id: sessionId }),
    forumTopics: (params) => api.get('/api/learning/forum/topics', params),
    createForumTopic: (data) => api.post('/api/learning/forum/topics', data),
    forumTopic: (id) => api.get(`/api/learning/forum/topics/${id}`),
    replyToTopic: (topicId, body) => api.post(`/api/learning/forum/topics/${topicId}/replies`, { body }),
    listExperts: (params) => api.get('/api/learning/experts', params),
    bookConsultation: (data) => api.post('/api/learning/consultations', data),
    myConsultations: () => api.get('/api/learning/consultations'),
    learningDashboard: () => api.get('/api/learning/dashboard'),

    // Notifications
    listNotifications: (params) => api.get('/api/notifications', params),
    markRead: (id) => api.post(`/api/notifications/${id}/read`),
    markAllRead: () => api.post('/api/notifications/read-all'),
    deleteNotification: (id) => api.del(`/api/notifications/${id}`),
    unreadCount: () => api.get('/api/notifications/unread-count'),
    registerDevice: (token, platform = 'web') => api.post('/api/notifications/register-device', { token, platform }),

    // Uploads
    uploadFile: (file, extra) => api.upload('/api/uploads', file, extra),
    deleteUpload: (id) => api.del(`/api/uploads/${id}`),

    // Reports
    reportProfitLoss: (params) => api.get('/api/reports/profit-loss', params),
    reportEnterprisePerformance: (params) => api.get('/api/reports/enterprise-performance', params),
    reportCashFlow: (params) => api.get('/api/reports/cash-flow', params),
    reportCreditScore: () => api.get('/api/reports/credit-score'),
};


// ============================================================
// EXPORTS
// ============================================================
window.MarcbantuAPI = API_BASE;
window.Api = Api;
window.Auth = Auth;
window.api = api;
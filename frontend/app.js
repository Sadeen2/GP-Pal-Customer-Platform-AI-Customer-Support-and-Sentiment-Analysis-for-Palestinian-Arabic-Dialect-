document.addEventListener("DOMContentLoaded", async () => {

    // ═══════════════════════════════════════════════════
    // STATE
    // ═══════════════════════════════════════════════════
    const state = {
        isLoggedIn: false,
        currentUser: null,  // populated from /auth/me or login response
        messages: [],
        agents: [],         // loaded from /auth/users
        currentView: 'dashboard',
        selectedMessageId: null,
        currentLanguage: 'en',
        filters: {
            search: '',
            sentiment: 'All',
            urgency: 'All',
            routingStatus: 'All',
            routingUrgency: 'All',
            routingAssignment: 'All',
            channel: 'All'
        },
        faqs: [],
        users: [],          // loaded from /auth/users (admin only)
        conversationsById: {},  // conversation_id -> {assigned_agent, status, bot_enabled}
        realtimeConnected: false
    };

    // ═══════════════════════════════════════════════════
    // API BASE + HELPERS
    // ═══════════════════════════════════════════════════
    const API_BASE = window.API_BASE || window.location.origin;

    function getToken() {
        return localStorage.getItem('access_token') || '';
    }

    function authHeaders(extra = {}) {
        const token = getToken();
        return {
            ...extra,
            ...(token ? { Authorization: `Bearer ${token}` } : {})
        };
    }

    function decodeJwtPayload(token) {
        try {
            const part = String(token || '').split('.')[1];
            if (!part) return {};
            const normalized = part.replace(/-/g, '+').replace(/_/g, '/');
            const json = decodeURIComponent(atob(normalized).split('').map(c =>
                '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
            ).join(''));
            return JSON.parse(json);
        } catch (_) {
            return {};
        }
    }

    function normalizeUserObject(userLike = {}) {
        const tokenPayload = decodeJwtPayload(getToken());
        const stored = (() => {
            try { return JSON.parse(localStorage.getItem('current_user') || '{}'); }
            catch (_) { return {}; }
        })();

        const merged = { ...tokenPayload, ...stored, ...userLike };
        const role = String(
            merged.role ||
            merged.user_role ||
            merged.account_role ||
            merged.type ||
            'agent'
        ).toLowerCase();

        return {
            ...merged,
            id: merged.id || merged.user_id || merged.sub,
            name: merged.name || merged.full_name || merged.username || merged.email || 'User',
            email: merged.email || merged.sub || '',
            role
        };
    }

    async function apiRequest(path, options = {}) {
        const response = await fetch(`${API_BASE}${path}`, {
            ...options,
            headers: authHeaders(options.headers || {})
        });

        if (response.status === 401) {
            // Token expired — clear session and redirect to login
            clearSession();
            showToast('Session expired', 'Please sign in again.', 'warning');
            throw new Error('Unauthorized');
        }

        if (!response.ok) {
            let detail = '';
            try {
                const errorBody = await response.json();
                detail = errorBody.detail || JSON.stringify(errorBody);
            } catch (_) {
                detail = await response.text();
            }
            throw new Error(detail || `Request failed: ${response.status}`);
        }

        return response.json();
    }

    let dashboardSocket = null;
    let dashboardSocketReconnectTimer = null;
    let dashboardRefreshTimer = null;

    function clearSession() {
        stopDashboardWebSocket();
        state.isLoggedIn = false;
        state.currentUser = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('current_user');
        renderApp();
    }


    // ═══════════════════════════════════════════════════
    // REALTIME DASHBOARD WEBSOCKET
    // ═══════════════════════════════════════════════════
    function getDashboardWsUrl() {
        const base = new URL(API_BASE, window.location.origin);
        base.protocol = base.protocol === 'https:' ? 'wss:' : 'ws:';
        base.pathname = '/ws/dashboard';
        base.search = '';
        return base.toString();
    }

    function stopDashboardWebSocket() {
        if (dashboardSocketReconnectTimer) {
            clearTimeout(dashboardSocketReconnectTimer);
            dashboardSocketReconnectTimer = null;
        }
        if (dashboardRefreshTimer) {
            clearTimeout(dashboardRefreshTimer);
            dashboardRefreshTimer = null;
        }
        if (dashboardSocket) {
            try { dashboardSocket.close(); } catch (_) {}
            dashboardSocket = null;
        }
        state.realtimeConnected = false;
    }

    function startDashboardWebSocket() {
        // Start realtime even when the dashboard is served without a JWT token.
        // The WebSocket itself does not require auth in the backend; API requests still use token if available.
        if (dashboardSocket && [WebSocket.CONNECTING, WebSocket.OPEN].includes(dashboardSocket.readyState)) return;

        const wsUrl = getDashboardWsUrl();
        try {
            dashboardSocket = new WebSocket(wsUrl);
        window.dashboardSocket = dashboardSocket;
        } catch (err) {
            scheduleDashboardWebSocketReconnect();
            return;
        }

        dashboardSocket.onopen = () => {
            console.log('[realtime] dashboard WebSocket connected');
            state.realtimeConnected = true;
            // Keep local/proxy connections alive.
            if (dashboardSocket._pingTimer) clearInterval(dashboardSocket._pingTimer);
            dashboardSocket._pingTimer = setInterval(() => {
                try {
                    if (dashboardSocket && dashboardSocket.readyState === WebSocket.OPEN) {
                        dashboardSocket.send('ping');
                    }
                } catch (_) {}
            }, 25000);
        };

        dashboardSocket.onmessage = (event) => {
            console.log('[realtime] event received:', event.data);
            let data = {};
            try { data = JSON.parse(event.data || '{}'); } catch (_) { data = {}; }
            if (!data.type || data.type === 'connected') return;
            scheduleRealtimeRefresh(data);
        };

        dashboardSocket.onclose = () => {
            console.log('[realtime] dashboard WebSocket closed');
            state.realtimeConnected = false;
            if (dashboardSocket && dashboardSocket._pingTimer) clearInterval(dashboardSocket._pingTimer);
            dashboardSocket = null;
            scheduleDashboardWebSocketReconnect();
        };

        dashboardSocket.onerror = (err) => {
            console.warn('[realtime] dashboard WebSocket error', err);
            state.realtimeConnected = false;
            try { dashboardSocket.close(); } catch (_) {}
        };
    }

    function scheduleDashboardWebSocketReconnect() {
        if (dashboardSocketReconnectTimer) return;
        dashboardSocketReconnectTimer = setTimeout(() => {
            dashboardSocketReconnectTimer = null;
            startDashboardWebSocket();
        }, 3000);
    }

    function scheduleRealtimeRefresh(eventData = {}) {
        if (dashboardRefreshTimer) clearTimeout(dashboardRefreshTimer);
        dashboardRefreshTimer = setTimeout(async () => {
            try {
                console.log('[realtime] refreshing dashboard data...', eventData);
                await loadBackendMessages();
                if (isAdmin()) await loadAgents().catch(() => {});

                // Always re-render after a realtime event. This keeps Messages, Dashboard,
                // Routing, and Details live without pressing the Refresh button.
                renderApp();

                // Also click the visible refresh button as a fallback for older view handlers.
                const refreshButton = document.getElementById('refreshMsgsBtn')
                    || document.querySelector('button i.fa-rotate')?.closest('button')
                    || document.querySelector('button i.fa-refresh')?.closest('button')
                    || document.querySelector('button i.fa-rotate-right')?.closest('button');
                if (refreshButton && !refreshButton.disabled) {
                    // Avoid duplicate toast spam by not relying only on this path.
                    setTimeout(() => { try { refreshButton.click(); } catch (_) {} }, 50);
                }

                if (eventData.sender_type === 'customer' && eventData.channel) {
                    showToast('New message', `${channelLabel(eventData.channel)} message received`, 'info', 2500);
                }
            } catch (err) {
                console.warn('Realtime refresh failed:', err);
            }
        }, 150);
    }

    // ═══════════════════════════════════════════════════
    // TOAST NOTIFICATIONS
    // ═══════════════════════════════════════════════════
    const toastContainer = document.getElementById('toastContainer');

    const TOAST_ICONS = {
        success: 'fa-solid fa-circle-check',
        error:   'fa-solid fa-circle-xmark',
        warning: 'fa-solid fa-triangle-exclamation',
        info:    'fa-solid fa-circle-info'
    };

    function showToast(title, message = '', type = 'info', duration = 4000) {
        if (!toastContainer) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <i class="toast-icon ${TOAST_ICONS[type] || TOAST_ICONS.info}"></i>
            <div class="toast-body">
                <div class="toast-title">${title}</div>
                ${message ? `<div class="toast-msg">${message}</div>` : ''}
            </div>
            <button class="toast-close"><i class="fa-solid fa-xmark"></i></button>
        `;
        toastContainer.appendChild(toast);

        const close = () => {
            toast.classList.add('fade-out-toast');
            setTimeout(() => toast.remove(), 300);
        };

        toast.querySelector('.toast-close').addEventListener('click', close);
        setTimeout(close, duration);
    }

    // ═══════════════════════════════════════════════════
    // MODAL DIALOGS
    // ═══════════════════════════════════════════════════
    function showModal({ title, icon = 'fa-solid fa-circle-info', bodyHtml, footerHtml, onMount, size = '' }) {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal-box ${size}">
                <div class="modal-header">
                    <h3><i class="${icon}"></i> ${title}</h3>
                    <button class="modal-close"><i class="fa-solid fa-xmark"></i></button>
                </div>
                <div class="modal-body">${bodyHtml}</div>
                ${footerHtml ? `<div class="modal-footer">${footerHtml}</div>` : ''}
            </div>
        `;
        document.body.appendChild(overlay);

        const closeModal = () => overlay.remove();
        overlay.querySelector('.modal-close').addEventListener('click', closeModal);
        overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });

        if (onMount) onMount(overlay, closeModal);
        return { overlay, closeModal };
    }

    function showConfirmModal({ title, message, icon = 'fa-solid fa-triangle-exclamation', confirmLabel = 'Confirm', confirmClass = 'btn btn-primary', onConfirm }) {
        showModal({
            title,
            icon,
            size: 'modal-sm',
            bodyHtml: `<p>${message}</p>`,
            footerHtml: `
                <button class="btn btn-outline" id="confirmCancel">Cancel</button>
                <button class="${confirmClass}" id="confirmOk">${confirmLabel}</button>
            `,
            onMount: (overlay, closeModal) => {
                overlay.querySelector('#confirmCancel').addEventListener('click', closeModal);
                overlay.querySelector('#confirmOk').addEventListener('click', async () => {
                    closeModal();
                    await onConfirm();
                });
            }
        });
    }

    // ═══════════════════════════════════════════════════
    // BUTTON LOADING STATE
    // ═══════════════════════════════════════════════════
    function setButtonLoading(btn, loading, originalText = '') {
        if (loading) {
            btn._originalHtml = btn.innerHTML;
            btn.innerHTML = `<span class="spinner-inline"></span> Loading...`;
            btn.classList.add('btn-loading');
        } else {
            btn.innerHTML = btn._originalHtml || originalText;
            btn.classList.remove('btn-loading');
        }
    }

    // ═══════════════════════════════════════════════════
    // DATA MAPPING HELPERS
    // ═══════════════════════════════════════════════════
    function titleCaseLabel(value, fallback = 'Neutral') {
        if (!value) return fallback;
        const v = String(value).toLowerCase();
        return v.charAt(0).toUpperCase() + v.slice(1);
    }

    function mapUrgency(value, routingAction) {
        const u = String(value || 'normal').trim().toLowerCase();
        const action = String(routingAction || '').trim().toLowerCase();

        // UI buckets: normal/low => Low, urgent/medium => Medium, critical/high/escalation => High
        if (u === 'critical' || u === 'high' || action === 'escalation' || action === 'escalate') return 'High';
        if (u === 'urgent' || u === 'medium' || action === 'human_handoff') return 'Medium';
        if (u === 'normal' || u === 'low') return 'Low';

        return titleCaseLabel(u, 'Low');
    }

    function mapStatus(msg) {
        const action = String(msg.routing_action || '').toLowerCase();
        if (action === 'escalation' || action === 'human_handoff') return 'Escalated';
        if (action === 'bot_reply') return 'Responded';
        return 'Pending';
    }

    function extractIntent(routingReason, fallback) {
        const text = String(routingReason || '');
        const match = text.match(/intent=([^;]+)/);
        if (match && match[1] && match[1] !== 'None') return match[1];
        return fallback || 'other';
    }

    function getConfidencePercent(msg) {
        const values = [
            msg.sentiment_confidence,
            msg.category_confidence,
            msg.urgency_confidence
        ].filter(v => typeof v === 'number');
        if (!values.length) return 0;
        return Math.round(Math.max(...values) * 100);
    }

    function agentEmailFromRoutingReason(routingReason) {
        const match = String(routingReason || '').match(/manual_reply_by=([^;]+)/);
        return match ? match[1].trim() : null;
    }

    function channelLabel(channel) {
        const c = String(channel || 'web').toLowerCase();
        if (c === 'whatsapp') return 'WhatsApp';
        if (c === 'instagram') return 'Instagram';
        if (c === 'messenger') return 'Messenger';
        return 'Web Chat';
    }

    function channelIcon(channel) {
        const c = String(channel || 'web').toLowerCase();
        if (c === 'whatsapp') return 'fa-brands fa-whatsapp';
        if (c === 'instagram') return 'fa-brands fa-instagram';
        if (c === 'messenger') return 'fa-brands fa-facebook-messenger';
        return 'fa-solid fa-globe';
    }

    function channelBadgeHtml(msg) {
        const safeChannel = escapeHtml(String(msg.channel || 'web').toLowerCase());
        return `<span class="channel-badge channel-${safeChannel}"><i class="${channelIcon(msg.channel)}"></i> ${escapeHtml(msg.channelLabel || channelLabel(msg.channel))}</span>`;
    }

    function mapChatHistory(group) {
        return [...group]
            .sort((a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0))
            .map(item => {
                const isBot = item.sender_type === 'bot' || item.routing_action === 'bot_reply';
                const isAgent = item.sender_type === 'agent' || item.routing_action === 'agent_reply';

                let sender = item.customer_id || 'Customer';
                let kind = 'customer';

                if (isBot) {
                    sender = 'AI Bot';
                    kind = 'bot';
                } else if (isAgent) {
                    const agentEmail = agentEmailFromRoutingReason(item.routing_reason);
                    sender = agentEmail ? getAgentDisplayName(agentEmail) : 'Agent';
                    kind = 'agent';
                }

                return {
                    sender,
                    kind,
                    text: item.text || '',
                    time: item.created_at ? new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
                };
            });
    }

    function mapBackendMessage(msg, group, conversationInfo) {
        const conversationHistory = mapChatHistory(group || [msg]);
        const afterThisBot = [...(group || [])]
            .filter(item => (item.sender_type === 'bot' || item.routing_action === 'bot_reply') && item.id > msg.id)
            .sort((a, b) => a.id - b.id)[0];

        const info = conversationInfo || {};
        const channel = msg.channel || info.channel || 'web';
        const customerDbId = msg.customer_db_id || info.customer_db_id || null;
        const externalCustomerId = msg.customer_id || info.customer_id || 'Customer';

        const assignedAgent = (
            info.assigned_agent ||
            info.assignedAgent ||
            msg.assigned_agent ||
            msg.assignedAgent ||
            null
        );

        return {
            id: String(msg.id),
            backendId: msg.id,
            conversationId: msg.conversation_id || info.id || info.conversation_id,
            customerName: customerDbId ? `Customer #${customerDbId}` : externalCustomerId,
            customerDbId,
            externalCustomerId,
            email: `${channelLabel(channel)} • ${externalCustomerId}`,
            channel,
            channelLabel: channelLabel(channel),
            messagePreview: msg.text || '',
            fullMessage: msg.text || '',
            sentiment: titleCaseLabel(msg.sentiment, 'Neutral'),
            intent: extractIntent(msg.routing_reason, msg.category || msg.routing_action || 'other'),
            urgency: mapUrgency(msg.urgency, msg.routing_action),
            timestamp: msg.created_at || new Date().toISOString(),
            status: titleCaseLabel(info.status, mapStatus(msg)).replace('Pending_human', 'Pending Human'),
            conversationStatus: info.status || 'active',
            assignedAgent: assignedAgent || 'Unassigned',
            botEnabled: info.bot_enabled !== undefined ? info.bot_enabled : true,
            confidence: getConfidencePercent(msg),
            suggestedReply: afterThisBot ? afterThisBot.text : 'No bot reply saved for this message yet.',
            conversationHistory
        };
    }

    async function loadBackendMessages() {
        const [rawMessages, rawConversations] = await Promise.all([
            apiRequest('/messages'),
            apiRequest('/conversations').catch(() => [])
        ]);

        // Conversations API stores assignment on the conversation row.
        // Some backend versions return `id`, others return `conversation_id`.
        // Index by both so messages.conversation_id always finds the correct row.
        state.conversationsById = {};
        (rawConversations || []).forEach(conv => {
            const keys = [
                conv.conversation_id,
                conv.id,
                conv.customer_id
            ].filter(v => v !== undefined && v !== null && v !== '');

            keys.forEach(k => {
                state.conversationsById[String(k)] = conv;
                state.conversationsById[k] = conv;
            });
        });

        const groups = {};
        rawMessages.forEach(msg => {
            const key = msg.conversation_id || `msg-${msg.id}`;
            groups[key] = groups[key] || [];
            groups[key].push(msg);
        });
        state.messages = rawMessages
            .filter(msg => msg.sender_type === 'customer')
            .map(msg => mapBackendMessage(
                msg,
                groups[msg.conversation_id || `msg-${msg.id}`],
                state.conversationsById[String(msg.conversation_id)] || state.conversationsById[msg.conversation_id] || state.conversationsById[String(msg.customer_id)]
            ))
            .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    }

    function normalizeFaq(raw) {
        return {
            id: raw.id || raw.faq_id || raw.slug || raw.key,
            question: raw.question || raw.q || '',
            answer: raw.answer || raw.a || '',
            intent: raw.intent || '',
            category: raw.category || '',
            action: raw.action || 'auto_reply',
            needs_human: raw.needs_human || false,
            examples: Array.isArray(raw.examples) ? raw.examples : [],
            keywords: typeof raw.keywords === "string" ? raw.keywords : "",
            priority: raw.priority || 50,
            is_active: raw.is_active !== false,
            enabled: raw.enabled !== false && raw.disabled !== true && raw.is_active !== false
        };
    }

    async function loadBackendFaqs() {
        const rawFaqs = await apiRequest('/api/faqs/');
        const list = Array.isArray(rawFaqs) ? rawFaqs : (rawFaqs.faqs || rawFaqs.items || []);
        state.faqs = list.map(normalizeFaq);
    }

    async function loadAgents() {
        try {
            const data = await apiRequest('/auth/users');
            const users = data.users || [];
            state.users = users;
            // Only real support agents should appear in Routing assignment.
            // Admin / super_admin are NOT counted or shown as assignable agents.
            state.agents = users.filter(u =>
                String(u.role || '').toLowerCase() === 'agent' &&
                u.is_active !== false
            );
        } catch (_) {
            state.agents = [];
        }
    }

    function getActiveAgents() {
        return state.agents.filter(a =>
            String(a.role || '').toLowerCase() === 'agent' &&
            a.is_active !== false &&
            a.is_available === true
        );
    }

    function isAssigned(value) {
        return !!value && value !== 'Unassigned' && value !== 'null' && value !== 'undefined';
    }

    // assigned_agent is stored/matched by email on the backend, but we want
    // to show a human-friendly name in the UI.
    function getAgentDisplayName(emailOrUnassigned) {
        if (!isAssigned(emailOrUnassigned)) return 'Unassigned';
        const allUsers = [state.currentUser, ...state.agents, ...(state.users || [])].filter(Boolean);
        const key = String(emailOrUnassigned || '').toLowerCase();
        const match = allUsers.find(a =>
            String(a.email || '').toLowerCase() === key ||
            String(a.name || '').toLowerCase() === key
        );
        return match ? (match.name || match.email) : emailOrUnassigned;
    }

    function assignedToCurrentAgent(msg) {
        if (!msg || !isAssigned(msg.assignedAgent)) return false;

        const assignedRaw = String(msg.assignedAgent || '').toLowerCase().trim();
        const displayRaw = String(getAgentDisplayName(msg.assignedAgent) || '').toLowerCase().trim();
        const currentEmail = String(state.currentUser?.email || '').toLowerCase().trim();
        const currentName = String(state.currentUser?.name || '').toLowerCase().trim();

        return (
            (!!currentEmail && assignedRaw === currentEmail) ||
            (!!currentName && assignedRaw === currentName) ||
            (!!currentName && displayRaw === currentName) ||
            (!!currentEmail && displayRaw === currentEmail)
        );
    }

    function uniqueLatestByConversation(messages) {
        const sorted = [...(messages || [])]
            .sort((a, b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0));

        const seen = new Set();
        const rows = [];

        sorted.forEach(msg => {
            const key = String(msg.conversationId || msg.customerName || msg.id);
            if (seen.has(key)) return;
            seen.add(key);
            rows.push(msg);
        });

        return rows;
    }

    function getAgentConversationRows() {
        // Agent inbox should show active conversations assigned to this agent only,
        // one row per conversation. Full message history is still available
        // after opening the conversation details.
        return uniqueLatestByConversation(
            state.messages.filter(msg => {
                if (!assignedToCurrentAgent(msg)) return false;
                const status = String(msg.status || msg.conversationStatus || '').toLowerCase();
                return !['responded', 'resolved', 'closed'].includes(status);
            })
        );
    }

    function getRoutingConversationRows() {
        // Admin routing page should also show one row per conversation,
        // not every single message in the same conversation.
        return uniqueLatestByConversation(state.messages);
    }

    function getCurrentMessageList() {
        return isAgent() ? getAgentConversationRows() : state.messages;
    }

    async function createBackendFaq(question, answer) {
        const safeId = `custom_${Date.now()}`;
        return apiRequest('/api/faqs/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: safeId, category: "general", intent: "custom_faq",
                question, examples: [question], answer,
                keywords: "", action: "auto_reply", needs_human: false, priority: 50, is_active: true
            })
        });
    }

    async function updateBackendFaq(id, question, answer, existing = {}) {
        return apiRequest(`/api/faqs/${encodeURIComponent(id)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id, category: existing.category || "general", intent: existing.intent || "custom_faq",
                question, examples: Array.isArray(existing.examples) ? existing.examples : [question],
                answer, keywords: typeof existing.keywords === "string" ? existing.keywords : "",
                action: existing.action || "auto_reply", needs_human: existing.needs_human || false,
                priority: existing.priority || 50, is_active: existing.is_active !== false
            })
        });
    }

    async function deleteBackendFaq(id) {
        return apiRequest(`/api/faqs/${encodeURIComponent(id)}`, { method: 'DELETE' });
    }

    async function setBackendFaqEnabled(id, enabled) {
        return apiRequest(`/api/faqs/${encodeURIComponent(id)}/${enabled ? 'enable' : 'disable'}`, { method: 'PATCH' });
    }

    // ═══════════════════════════════════════════════════
    // ROLE HELPERS
    // ═══════════════════════════════════════════════════
    function getUserRole() {
        const normalized = normalizeUserObject(state.currentUser || {});
        const role = String(normalized.role || 'agent').toLowerCase();
        return role;
    }

    function isAdmin() {
        const role = getUserRole();
        return ['super_admin', 'admin', 'manager'].includes(role);
    }

    function isSuperAdmin() {
        return getUserRole() === 'super_admin';
    }

    function isAgent() {
        return !isAdmin();
    }

    function roleDisplayName(role = getUserRole()) {
        const labels = {
            super_admin: 'Super Admin',
            admin: 'Admin',
            manager: 'Manager',
            agent: 'Agent',
            user: 'Agent'
        };
        return labels[role] || titleCaseLabel(role, 'Agent');
    }

    function canAccessView(view) {
        const adminOnlyViews = ['analytics', 'routing', 'users'];
        return isAdmin() || !adminOnlyViews.includes(view);
    }

    function updateRoleChrome() {
        const role = getUserRole();
        const isAr = state.currentLanguage === 'ar';

        document.body.classList.toggle('role-admin', isAdmin());
        document.body.classList.toggle('role-agent', isAgent());
        if (dashboardApp) dashboardApp.setAttribute('data-role', isAdmin() ? 'admin' : 'agent');

        const brandSubtitle = document.querySelector('.brand-subtitle');
        if (brandSubtitle) {
            if (isAdmin()) {
                brandSubtitle.textContent = isAr ? 'لوحة إدارة النظام' : 'Admin Control Center';
            } else {
                brandSubtitle.textContent = isAr ? 'مساحة عمل الموظف' : 'Agent Workspace';
            }
        }

        let chip = document.querySelector('.sidebar-role-chip');
        const nav = document.querySelector('.sidebar-nav');
        if (nav && !chip) {
            chip = document.createElement('div');
            chip.className = 'sidebar-role-chip';
            nav.parentNode.insertBefore(chip, nav);
        }
        if (chip) {
            chip.className = `sidebar-role-chip ${isAdmin() ? 'admin-chip' : 'agent-chip'}`;
            chip.innerHTML = `
                <i class="fa-solid ${isAdmin() ? 'fa-user-shield' : 'fa-headset'}"></i>
                <span>${roleDisplayName(role)}</span>
            `;
        }
    }

    function applyRoleBasedNav() {
        const adminOnlyItems = [navRouting, navAnalytics, navUsers, ...document.querySelectorAll('.admin-only')]
            .filter(Boolean);

        adminOnlyItems.forEach(el => {
            el.style.display = isAdmin() ? 'flex' : 'none';
            el.setAttribute('aria-hidden', isAdmin() ? 'false' : 'true');
        });

        updateRoleChrome();
    }

    // Redirect non-admin users away from restricted views
    function checkViewAccess(view) {
        if (!canAccessView(view)) {
            showToast('Access Restricted', 'This page is available for admins only.', 'warning');
            if (state.currentView !== 'messages') {
                state.currentView = 'messages';
                renderApp();
            }
            return false;
        }
        return true;
    }

    // ═══════════════════════════════════════════════════
    // TRANSLATIONS
    // ═══════════════════════════════════════════════════
    const T = {
        en: {
            loginTitle: "Pal CustomerAI",
            loginSubtitle: "Sign in to access the customer support dashboard",
            loginTagline: "AI-powered Arabic Customer Support",
            loginHeroKicker: "Sentiment-aware support platform",
            loginHeroTitle: "Understand customers faster.",
            loginHeroSubtitle: "Pal CustomerAI reads Arabic customer messages, detects sentiment and urgency, matches FAQs, and routes complex cases to the right agent.",
            typingLabel: "Live AI focus",
            heroFeatureSentiment: "Sentiment analysis",
            heroFeatureUrgency: "Urgency routing",
            heroFeatureChannels: "WhatsApp & Messenger",
            emailLabel: "Email",
            emailPlaceholder: "Enter your email",
            passwordLabel: "Password",
            passwordPlaceholder: "Enter your password",
            rememberMe: "Remember me",
            signIn: "Sign In",
            loginFooter: "© 2026 Pal CustomerAI. All rights reserved.",
            navDashboard: "Dashboard",
            navMessages: "Messages",
            navRouting: "Routing",
            navFaq: "FAQ",
            navAnalytics: "Analytics",
            navUsers: "Users",
            titleDashboard: "Dashboard Overview",
            titleMessages: "Incoming Messages",
            titleDetails: "Message Details",
            titleRouting: "Routing & Assignment",
            titleFaq: "FAQ Management",
            titleAnalytics: "Analytics & Reports",
            titleUsers: "User Management",
            total: "Total",
            negative: "Negative",
            urgent: "Urgent",
            resolved: "Resolved",
            quickNav: "Quick Navigation",
            inbox: "Inbox",
            viewMessages: "View Messages",
            routing: "Routing",
            manageAgents: "Manage Agents",
            reports: "Reports",
            viewAnalytics: "View Analytics",
            faq: "FAQ",
            manageKnowledge: "Manage Knowledge",
            recentMessages: "Recent Messages",
            sentimentOverview: "Sentiment Overview",
            positive: "Positive",
            neutral: "Neutral",
            totalMessages: "Total Messages",
            urgentCases: "Urgent Cases",
            pendingCases: "Pending Cases",
            searchPlaceholder: "Search customer, intent...",
            allSentiments: "All Sentiments",
            allUrgencies: "All Urgencies",
            clear: "Clear",
            noMessagesFound: "No messages found",
            adjustFilters: "Try adjusting your filters or search terms.",
            autoBot: "AI Bot",
            humanRequired: "Human Agent Required",
            highUrgencyReason: "This case is marked High urgency — routing to a human agent.",
            lowConfidenceReason: "AI confidence is below 70% — a human agent should review.",
            sendManualReply: "Send Reply",
            autoReplySentAuto: "Auto-reply sent successfully by AI.",
            assigned: "Assigned",
            unassigned: "Unassigned",
            escalated: "Escalated",
            activeAgents: "Active Agents",
            allAssignments: "All Assignments",
            allStatuses: "All Statuses",
            allUrgenciesOpt: "All Urgencies",
            pending: "Pending",
            responded: "Responded",
            high: "High",
            medium: "Medium",
            low: "Low",
            customer: "Customer",
            intent: "Intent",
            sentiment: "Sentiment",
            urgency: "Urgency",
            status: "Status",
            assignedAgent: "Assigned Agent",
            quickAction: "Quick Action",
            escalate: "Escalate",
            noRoutingMatch: "No messages match your routing filters.",
            backToList: "Back to list",
            assignedTo: "Assigned to:",
            aiAnalysis: "AI Analysis",
            confidence: "Confidence",
            suggestedReply: "Suggested AI Response",
            sendAutoReply: "Send Auto Reply",
            markResolved: "Mark Resolved",
            conversationHistory: "Conversation History",
            autoReplySent: "Auto reply sent!",
            actionRecorded: "Action recorded.",
            replyPlaceholder: "Type a reply to the customer...",
            sendReply: "Send",
            botStatus: "Bot",
            botOn: "Active",
            botOff: "Paused",
            botOnHint: "The bot is replying automatically.",
            botOffHint: "Paused — you're handling this conversation.",
            noConversationLinked: "This test message isn't linked to a real conversation, so replying and bot controls aren't available.",
            replySentToast: "Reply sent to the customer.",
            replyFailedToast: "Couldn't send the reply",
            botToggleFailedToast: "Couldn't update the bot status",
            addNewFaq: "Add New FAQ",
            enterQuestion: "Enter Question",
            enterAnswer: "Enter Answer",
            addFaq: "Add FAQ",
            existingFaqs: "Existing FAQs",
            saveChanges: "Save Changes",
            cancel: "Cancel",
            noFaqs: "No FAQs added yet",
            noFaqsDesc: "Use the form above to add a new FAQ.",
            smartInsights: "Smart Insights",
            insightTitle1: "Sentiment Analysis Active",
            insightDesc1: "The AI is actively analyzing customer messages for sentiment, category, and urgency.",
            insightTitle2: "Auto-Reply Performance",
            insightDesc2: "Bot replies are intercepting basic inquiries, reducing manual workload for agents.",
            messagesOverTime: "Messages Over Time",
            topIntents: "Top Intents",
            urgencyBreakdown: "Urgency Breakdown",
            noData: "No Data",
            searchGlobal: "Search...",
            langBtn: "AR",
            // Users page
            addUser: "Add User",
            name: "Name",
            email: "Email",
            role: "Role",
            activeStatus: "Status",
            actions: "Actions",
            changePassword: "Change Password",
            newPassword: "New Password",
            generatePassword: "Generate",
            noUsers: "No users found",
            userCreated: "User created successfully",
            userUpdated: "User updated successfully",
            passwordChanged: "Password changed successfully",
            userDeleted: "User deleted successfully",
            confirmDelete: "Are you sure you want to delete this user? This action cannot be undone.",
            totalUsers: "Total Users",
            admins: "Admins",
            activeUsers: "Active Users"
        },
        ar: {
            loginTitle: "بال كستمر AI",
            loginSubtitle: "سجّل دخولك للوصول إلى لوحة دعم العملاء",
            loginTagline: "دعم عملاء عربي مدعوم بالذكاء الاصطناعي",
            loginHeroKicker: "منصة دعم تفهم شعور العميل",
            loginHeroTitle: "افهم رسائل العملاء أسرع.",
            loginHeroSubtitle: "Pal CustomerAI يحلل رسائل العملاء بالعربي، يحدد الشعور والاستعجال، يطابق الأسئلة الشائعة، ويوجه الحالات المهمة للموظف المناسب.",
            typingLabel: "تركيز الذكاء الاصطناعي",
            heroFeatureSentiment: "تحليل المشاعر",
            heroFeatureUrgency: "توجيه الحالات العاجلة",
            heroFeatureChannels: "واتساب وماسنجر",
            emailLabel: "البريد الإلكتروني",
            emailPlaceholder: "أدخل بريدك الإلكتروني",
            passwordLabel: "كلمة المرور",
            passwordPlaceholder: "أدخل كلمة المرور",
            rememberMe: "تذكرني",
            signIn: "تسجيل الدخول",
            loginFooter: "© 2026 بال كستمر AI. جميع الحقوق محفوظة.",
            navDashboard: "لوحة التحكم",
            navMessages: "الرسائل",
            navRouting: "التوجيه",
            navFaq: "الأسئلة الشائعة",
            navAnalytics: "التحليلات",
            navUsers: "المستخدمون",
            titleDashboard: "نظرة عامة",
            titleMessages: "الرسائل الواردة",
            titleDetails: "تفاصيل الرسالة",
            titleRouting: "التوجيه والتعيين",
            titleFaq: "إدارة الأسئلة الشائعة",
            titleAnalytics: "التقارير والتحليلات",
            titleUsers: "إدارة المستخدمين",
            total: "الإجمالي",
            negative: "سلبية",
            urgent: "عاجلة",
            resolved: "محلولة",
            quickNav: "روابط سريعة",
            inbox: "صندوق الوارد",
            viewMessages: "عرض الرسائل",
            routing: "التوجيه",
            manageAgents: "إدارة الموظفين",
            reports: "التقارير",
            viewAnalytics: "عرض التحليلات",
            faq: "الأسئلة الشائعة",
            manageKnowledge: "إدارة المعرفة",
            recentMessages: "أحدث الرسائل",
            sentimentOverview: "نظرة على المشاعر",
            positive: "إيجابية",
            neutral: "محايدة",
            totalMessages: "إجمالي الرسائل",
            urgentCases: "الحالات العاجلة",
            pendingCases: "الحالات المعلقة",
            searchPlaceholder: "ابحث باسم العميل أو النية...",
            allSentiments: "كل المشاعر",
            allUrgencies: "كل الأولويات",
            clear: "مسح",
            noMessagesFound: "لا توجد رسائل",
            adjustFilters: "جرّب تغيير الفلاتر أو كلمة البحث.",
            autoBot: "بوت الذكاء الاصطناعي",
            humanRequired: "يتطلب موظف بشري",
            highUrgencyReason: "هذه الحالة ذات أولوية عالية — تم تحويلها لموظف.",
            lowConfidenceReason: "ثقة الذكاء الاصطناعي أقل من 70% — يجب مراجعة موظف.",
            sendManualReply: "إرسال الرد",
            autoReplySentAuto: "تم إرسال الرد التلقائي بنجاح من قبل الذكاء الاصطناعي.",
            assigned: "مُعيَّن",
            unassigned: "غير مُعيَّن",
            escalated: "مُصعَّد",
            activeAgents: "الموظفون النشطون",
            allAssignments: "كل التعيينات",
            allStatuses: "كل الحالات",
            allUrgenciesOpt: "كل الأولويات",
            pending: "معلق",
            responded: "تم الرد",
            high: "عالية",
            medium: "متوسطة",
            low: "منخفضة",
            customer: "العميل",
            intent: "النية",
            sentiment: "المشاعر",
            urgency: "الأولوية",
            status: "الحالة",
            assignedAgent: "الموظف المعيَّن",
            quickAction: "إجراء سريع",
            escalate: "تصعيد",
            noRoutingMatch: "لا توجد رسائل تطابق فلاتر التوجيه.",
            backToList: "العودة للقائمة",
            assignedTo: ":مُعيَّن إلى",
            aiAnalysis: "تحليل الذكاء الاصطناعي",
            confidence: "الثقة",
            suggestedReply: "الرد المقترح بالذكاء الاصطناعي",
            sendAutoReply: "إرسال رد تلقائي",
            markResolved: "تعليم كمحلول",
            conversationHistory: "سجل المحادثة",
            autoReplySent: "تم إرسال الرد التلقائي!",
            actionRecorded: "تم تسجيل الإجراء.",
            replyPlaceholder: "اكتب ردًا للعميل...",
            sendReply: "إرسال",
            botStatus: "البوت",
            botOn: "شغّال",
            botOff: "متوقف",
            botOnHint: "البوت بيرد تلقائيًا على العميل.",
            botOffHint: "متوقف — أنت اللي بترد على هاد العميل.",
            noConversationLinked: "هاي رسالة تجريبية مش مرتبطة بمحادثة حقيقية، فميزة الرد والتحكم بالبوت غير متاحة.",
            replySentToast: "تم إرسال الرد للعميل.",
            replyFailedToast: "تعذر إرسال الرد",
            botToggleFailedToast: "تعذر تحديث حالة البوت",
            addNewFaq: "إضافة سؤال جديد",
            enterQuestion: "أدخل السؤال",
            enterAnswer: "أدخل الإجابة",
            addFaq: "إضافة",
            existingFaqs: "الأسئلة الحالية",
            saveChanges: "حفظ التغييرات",
            cancel: "إلغاء",
            noFaqs: "لا توجد أسئلة بعد",
            noFaqsDesc: "استخدم النموذج أعلاه لإضافة سؤال جديد.",
            smartInsights: "رؤى ذكية",
            insightTitle1: "تحليل المشاعر نشط",
            insightDesc1: "يقوم الذكاء الاصطناعي بتحليل رسائل العملاء للمشاعر والفئات والأولويات.",
            insightTitle2: "أداء الرد التلقائي",
            insightDesc2: "تعترض ردود البوت الاستفسارات الأساسية، مما يقلل العبء اليدوي على الموظفين.",
            messagesOverTime: "الرسائل عبر الوقت",
            topIntents: "أبرز النوايا",
            urgencyBreakdown: "توزيع الأولويات",
            noData: "لا توجد بيانات",
            searchGlobal: "بحث...",
            langBtn: "EN",
            addUser: "إضافة مستخدم",
            name: "الاسم",
            email: "البريد الإلكتروني",
            role: "الدور",
            activeStatus: "الحالة",
            actions: "الإجراءات",
            changePassword: "تغيير كلمة المرور",
            newPassword: "كلمة المرور الجديدة",
            generatePassword: "توليد",
            noUsers: "لا يوجد مستخدمون",
            userCreated: "تم إنشاء المستخدم بنجاح",
            userUpdated: "تم تحديث المستخدم بنجاح",
            passwordChanged: "تم تغيير كلمة المرور بنجاح",
            userDeleted: "تم حذف المستخدم بنجاح",
            confirmDelete: "هل أنت متأكد من حذف هذا المستخدم؟ لا يمكن التراجع عن هذا الإجراء.",
            totalUsers: "إجمالي المستخدمين",
            admins: "المديرون",
            activeUsers: "المستخدمون النشطون"
        }
    };

    function t(key) {
        return (T[state.currentLanguage] && T[state.currentLanguage][key]) || key;
    }

    let loginTypewriterTimer = null;

    function getLoginPhrases() {
        if (state.currentLanguage === 'ar') {
            return [
                'تحليل مشاعر العملاء باللهجة الفلسطينية',
                'اكتشاف الرسائل العاجلة قبل ما تتأخر',
                'ردود FAQ تلقائية للحالات البسيطة',
                'تحويل الحالات الصعبة للموظف المناسب'
            ];
        }

        return [
            'Palestinian Arabic sentiment analysis',
            'Urgent messages routed instantly',
            'FAQ answers for simple customer questions',
            'Human handoff for complex conversations'
        ];
    }

    function startLoginTypewriter() {
        const target = document.getElementById('typingText');
        if (!target) return;

        if (loginTypewriterTimer) {
            clearTimeout(loginTypewriterTimer);
            loginTypewriterTimer = null;
        }

        const phrases = getLoginPhrases();
        let phraseIndex = 0;
        let charIndex = 0;
        let deleting = false;

        function step() {
            const phrase = phrases[phraseIndex % phrases.length];

            if (deleting) {
                charIndex = Math.max(0, charIndex - 1);
            } else {
                charIndex = Math.min(phrase.length, charIndex + 1);
            }

            target.textContent = phrase.slice(0, charIndex);

            let delay = deleting ? 30 : 55;

            if (!deleting && charIndex === phrase.length) {
                deleting = true;
                delay = 1450;
            } else if (deleting && charIndex === 0) {
                deleting = false;
                phraseIndex = (phraseIndex + 1) % phrases.length;
                delay = 420;
            }

            loginTypewriterTimer = setTimeout(step, delay);
        }

        step();
    }

    // ═══════════════════════════════════════════════════
    // DOM ELEMENTS
    // ═══════════════════════════════════════════════════
    const loginApp       = document.getElementById('loginApp');
    const dashboardApp   = document.getElementById('dashboardApp');
    const loginForm      = document.getElementById('loginForm');
    const appContent     = document.getElementById('appContent');
    const pageTitle      = document.getElementById('pageTitle');
    const globalSearch   = document.getElementById('globalSearch');
    const sidebar        = document.getElementById('sidebar');
    const toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
    const closeSidebarBtn  = document.getElementById('closeSidebarBtn');
    const sidebarOverlay   = document.getElementById('sidebarOverlay');
    const navDashboard   = document.getElementById('navDashboard');
    const navMessages    = document.getElementById('navMessages');
    const navRouting     = document.getElementById('navRouting');
    const navFaq         = document.getElementById('navFaq');
    const navAnalytics   = document.getElementById('navAnalytics');
    const navUsers       = document.getElementById('navUsers');
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    const themeIcon      = document.getElementById('themeIcon');
    const authSplash     = document.getElementById('authSplash');

    // ═══════════════════════════════════════════════════
    // INITIALIZATION — check stored session on load
    // ═══════════════════════════════════════════════════
    initTheme();
    injectLangSwitch();
    applyLanguage(state.currentLanguage);

    await initSession();   // <-- this is the fix for page-refresh logout

    setupEventListeners();
    renderApp();
    // Extra safety: open the live dashboard socket after the UI is rendered.
    // This covers cases where the page is already authenticated or served directly.
    setTimeout(startDashboardWebSocket, 500);

    // ─────────────────────────────────────────
    // SESSION INIT: verify token on every page load
    // ─────────────────────────────────────────
    async function initSession() {
        const token = getToken();

        if (!token) {
            hideSplash();
            return;
        }

        try {
            // Token exists — verify it with the backend
            const user = await apiRequest('/auth/me');
            state.currentUser = normalizeUserObject(user);
            localStorage.setItem('current_user', JSON.stringify(state.currentUser));
            state.isLoggedIn = true;

            // Load data in parallel for faster startup
            await Promise.all([
                loadBackendMessages().catch(() => {}),
                isAdmin() ? loadAgents().catch(() => {}) : Promise.resolve()
            ]);
            startDashboardWebSocket();

        } catch (err) {
            // Token invalid/expired
            clearSession();
        } finally {
            hideSplash();
        }
    }

    function hideSplash() {
        if (!authSplash) return;
        authSplash.classList.add('fade-out');
        setTimeout(() => authSplash.remove(), 450);
    }

    // ═══════════════════════════════════════════════════
    // LANG SWITCH INJECTION
    // ═══════════════════════════════════════════════════
    function injectLangSwitch() {
        const navRight = document.querySelector('.nav-right');
        if (!navRight) return;

        const langSwitch = document.createElement('div');
        langSwitch.className = 'lang-switch';
        langSwitch.id = 'langSwitch';
        langSwitch.innerHTML = `
            <button class="lang-opt ${state.currentLanguage === 'en' ? 'active' : ''}" data-lang="en">EN</button>
            <span class="lang-sep">|</span>
            <button class="lang-opt ${state.currentLanguage === 'ar' ? 'active' : ''}" data-lang="ar">AR</button>
        `;

        const themeBtn = navRight.querySelector('.theme-toggle');
        if (themeBtn) navRight.insertBefore(langSwitch, themeBtn);
        else navRight.appendChild(langSwitch);

        langSwitch.addEventListener('click', (e) => {
            const btn = e.target.closest('.lang-opt');
            if (!btn) return;
            const lang = btn.getAttribute('data-lang');
            if (lang === state.currentLanguage) return;
            state.currentLanguage = lang;
            applyLanguage(lang);
            updateLangButtons();
            renderApp();
        });
    }

    function updateLangButtons() {
        document.querySelectorAll('.lang-opt').forEach(btn => {
            btn.classList.toggle('active', btn.getAttribute('data-lang') === state.currentLanguage);
        });
    }

    // ═══════════════════════════════════════════════════
    // APPLY LANGUAGE
    // ═══════════════════════════════════════════════════
    function applyLanguage(lang) {
        const isAr = lang === 'ar';
        document.documentElement.lang = lang;
        document.documentElement.dir = isAr ? 'rtl' : 'ltr';
        document.body.classList.toggle('rtl-mode', isAr);

        const el = id => document.getElementById(id);
        if (el('systemName'))    el('systemName').textContent    = t('loginTitle');
        if (el('loginTagline'))  el('loginTagline').textContent  = t('loginTagline');
        if (el('loginSubtitle')) el('loginSubtitle').textContent = t('loginSubtitle');
        if (el('loginHeroKicker')) el('loginHeroKicker').textContent = t('loginHeroKicker');
        if (el('loginHeroTitle')) el('loginHeroTitle').textContent = t('loginHeroTitle');
        if (el('loginHeroSubtitle')) el('loginHeroSubtitle').textContent = t('loginHeroSubtitle');
        if (el('typingLabel')) el('typingLabel').textContent = t('typingLabel');
        if (el('heroFeatureSentiment')) el('heroFeatureSentiment').textContent = t('heroFeatureSentiment');
        if (el('heroFeatureUrgency')) el('heroFeatureUrgency').textContent = t('heroFeatureUrgency');
        if (el('heroFeatureChannels')) el('heroFeatureChannels').textContent = t('heroFeatureChannels');
        if (el('emailLabel'))    el('emailLabel').textContent    = t('emailLabel');
        if (el('emailInput'))    el('emailInput').placeholder    = t('emailPlaceholder');
        if (el('passwordLabel')) el('passwordLabel').textContent = t('passwordLabel');
        if (el('passwordInput')) el('passwordInput').placeholder = t('passwordPlaceholder');
        const rememberSpan = document.querySelector('#rememberLabel span');
        if (rememberSpan)        rememberSpan.textContent        = t('rememberMe');
        if (el('signInBtn'))     el('signInBtn').textContent     = t('signIn');
        if (el('footerText'))    el('footerText').textContent    = t('loginFooter');
        if (el('langToggleBtn')) el('langToggleBtn').textContent = isAr ? 'English' : 'العربية';

        startLoginTypewriter();

        const navLabels = {
            navDashboard: 'navDashboard',
            navMessages:  'navMessages',
            navRouting:   'navRouting',
            navFaq:       'navFaq',
            navAnalytics: 'navAnalytics',
            navUsers:     'navUsers'
        };
        Object.entries(navLabels).forEach(([id, key]) => {
            const el2 = document.getElementById(id);
            if (el2) { const span = el2.querySelector('span'); if (span) span.textContent = t(key); }
        });

        if (globalSearch) globalSearch.placeholder = t('searchGlobal');
        if (state.isLoggedIn) {
            updateRoleChrome();
            updatePageTitle();
        }
    }

    function updatePageTitle() {
        const titleMap = {
            dashboard: 'titleDashboard',
            messages:  'titleMessages',
            details:   'titleDetails',
            routing:   'titleRouting',
            faq:       'titleFaq',
            analytics: 'titleAnalytics',
            users:     'titleUsers'
        };
        if (pageTitle && titleMap[state.currentView]) {
            if (state.currentView === 'dashboard' && isAgent()) {
                pageTitle.innerText = state.currentLanguage === 'ar' ? 'مساحة عمل الموظف' : 'Agent Workspace';
            } else {
                pageTitle.innerText = t(titleMap[state.currentView]);
            }
        }
    }

    // ═══════════════════════════════════════════════════
    // UPDATE PROFILE HEADER
    // ═══════════════════════════════════════════════════
    function updateProfileHeader() {
        const profileName  = document.querySelector('.profile-name');
        const profileEmail = document.querySelector('.profile-email');
        const profileRole  = document.querySelector('.profile-role');

        if (!state.currentUser) return;

        if (profileName)  profileName.textContent  = state.currentUser.name || 'User';
        if (profileEmail) profileEmail.textContent = state.currentUser.email || '';
        if (profileRole) {
            profileRole.textContent = roleDisplayName();
        }
    }

    // ═══════════════════════════════════════════════════
    // EVENT LISTENERS
    // ═══════════════════════════════════════════════════
    function setupEventListeners() {
        // Login form
        if (loginForm) {
            loginForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const email    = document.getElementById('emailInput').value.trim();
                const password = document.getElementById('passwordInput').value;
                const signBtn  = document.getElementById('signInBtn');

                try {
                    setButtonLoading(signBtn, true);
                    const loginResponse = await fetch(`${API_BASE}/auth/login`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, password })
                    });

                    if (!loginResponse.ok) {
                        const err = await loginResponse.json().catch(() => ({}));
                        throw new Error(err.detail || 'Invalid email or password');
                    }

                    const loginData = await loginResponse.json();
                    localStorage.setItem('access_token', loginData.access_token);

                    // Always fetch /auth/me after login so the UI gets the real role.
                    // This is what makes Agent and Admin dashboards render differently.
                    try {
                        const me = await apiRequest('/auth/me');
                        state.currentUser = normalizeUserObject(me);
                    } catch (_) {
                        state.currentUser = normalizeUserObject(loginData.user || loginData || {});
                    }
                    localStorage.setItem('current_user', JSON.stringify(state.currentUser));

                    await Promise.all([
                        loadBackendMessages().catch(() => {}),
                        isAdmin() ? loadAgents().catch(() => {}) : Promise.resolve()
                    ]);

                    state.isLoggedIn = true;
                    startDashboardWebSocket();
                    showToast('Welcome back!', `Signed in as ${state.currentUser.name}`, 'success');
                    navigateTo('dashboard');

                } catch (err) {
                    showToast('Login Failed', err.message, 'error');
                } finally {
                    setButtonLoading(signBtn, false);
                }
            });
        }

        // Global search
        if (globalSearch) {
            globalSearch.addEventListener('input', (e) => {
                state.filters.search = e.target.value.toLowerCase();
                if (state.currentView === 'messages') renderApp();
            });
        }

        // Nav links
        if (navDashboard) navDashboard.addEventListener('click', (e) => { e.preventDefault(); navigateTo('dashboard'); closeSidebar(); });
        if (navMessages)  navMessages.addEventListener('click',  (e) => { e.preventDefault(); navigateTo('messages');  closeSidebar(); });
        if (navRouting)   navRouting.addEventListener('click',   (e) => { e.preventDefault(); navigateTo('routing');   closeSidebar(); });
        if (navFaq)       navFaq.addEventListener('click',       (e) => { e.preventDefault(); navigateTo('faq');       closeSidebar(); });
        if (navAnalytics) navAnalytics.addEventListener('click', (e) => { e.preventDefault(); navigateTo('analytics'); closeSidebar(); });
        if (navUsers)     navUsers.addEventListener('click',     (e) => { e.preventDefault(); navigateTo('users');     closeSidebar(); });

        // Sidebar
        if (toggleSidebarBtn) toggleSidebarBtn.addEventListener('click', openSidebar);
        if (closeSidebarBtn)  closeSidebarBtn.addEventListener('click',  closeSidebar);
        if (sidebarOverlay)   sidebarOverlay.addEventListener('click',   closeSidebar);
        if (themeToggleBtn)   themeToggleBtn.addEventListener('click',   toggleTheme);

        // Login page lang toggle
        const loginLangBtn = document.getElementById('langToggleBtn');
        if (loginLangBtn) {
            loginLangBtn.addEventListener('click', () => {
                state.currentLanguage = state.currentLanguage === 'en' ? 'ar' : 'en';
                applyLanguage(state.currentLanguage);
                updateLangButtons();
            });
        }

        // Profile dropdown
        const userProfile     = document.getElementById('userProfile');
        const profileDropdown = document.getElementById('profileDropdown');
        const logoutBtn       = document.getElementById('logoutBtn');

        if (userProfile) {
            userProfile.addEventListener('click', (e) => {
                e.stopPropagation();
                profileDropdown.classList.toggle('open');
            });
        }
        document.addEventListener('click', () => {
            if (profileDropdown) profileDropdown.classList.remove('open');
        });

        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                profileDropdown.classList.remove('open');
                showConfirmModal({
                    title: 'Sign Out',
                    message: 'Are you sure you want to sign out?',
                    icon: 'fa-solid fa-right-from-bracket',
                    confirmLabel: 'Sign Out',
                    confirmClass: 'btn btn-primary',
                    onConfirm: async () => {
                        clearSession();
                        showToast('Signed out', 'You have been signed out successfully.', 'info');
                    }
                });
            });
        }
    }

    function openSidebar()  { sidebar.classList.add('open');    sidebarOverlay.classList.add('open'); }
    function closeSidebar() { sidebar.classList.remove('open'); sidebarOverlay.classList.remove('open'); }

    function initTheme() {
        const saved = localStorage.getItem('theme');
        if (saved === 'dark') {
            document.body.classList.add('dark');
            if (themeIcon) themeIcon.className = 'fa-solid fa-sun';
        } else {
            if (themeIcon) themeIcon.className = 'fa-regular fa-moon';
        }
    }

    function toggleTheme() {
        document.body.classList.toggle('dark');
        const isDark = document.body.classList.contains('dark');
        if (themeIcon) themeIcon.className = isDark ? 'fa-solid fa-sun' : 'fa-regular fa-moon';
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
    }

    // ═══════════════════════════════════════════════════
    // NAVIGATE
    // ═══════════════════════════════════════════════════
    async function navigateTo(view, messageId = null) {
        if (!checkViewAccess(view)) return;

        state.currentView       = view;
        state.selectedMessageId = messageId;
        if (view === 'messages' && globalSearch) globalSearch.value = state.filters.search;

        if (view === 'faq') {
            try { await loadBackendFaqs(); } catch (err) { showToast('Error', `Failed to load FAQs: ${err.message}`, 'error'); }
        }
        if (view === 'users' && isAdmin()) {
            try {
                const data = await apiRequest('/auth/users');
                state.users = data.users || [];
            } catch (err) { showToast('Error', `Failed to load users: ${err.message}`, 'error'); }
        }
        if (view === 'routing' && isAdmin()) {
            // Refresh both messages and conversations so assigned_agent from DB appears immediately.
            await Promise.all([
                loadBackendMessages().catch(() => {}),
                loadAgents().catch(() => {})
            ]);
        }

        renderApp();
    }

    // ═══════════════════════════════════════════════════
    // RENDER APP
    // ═══════════════════════════════════════════════════
    function renderApp() {
        if (!state.isLoggedIn) {
            if (loginApp)     loginApp.style.display     = 'flex';
            if (dashboardApp) dashboardApp.style.display = 'none';
            return;
        }

        if (loginApp)     loginApp.style.display     = 'none';
        if (dashboardApp) dashboardApp.style.display = 'flex';

        if (!canAccessView(state.currentView)) {
            state.currentView = 'messages';
            state.selectedMessageId = null;
        }

        appContent.innerHTML = '';

        // Update nav active states
        [navDashboard, navMessages, navRouting, navFaq, navAnalytics, navUsers].forEach(el => {
            if (el) el.classList.remove('active');
        });

        // Role-based nav visibility
        applyRoleBasedNav();

        // Update profile header with real user info
        updateProfileHeader();
        addRoleBadgeToProfile();

        updatePageTitle();

        const viewMap = {
            dashboard: () => { if (navDashboard) navDashboard.classList.add('active'); renderDashboardPage(appContent); },
            messages:  () => { if (navMessages)  navMessages.classList.add('active');  renderMessagesPage(appContent); },
            details:   () => { if (navMessages)  navMessages.classList.add('active');  renderMessageDetailsPage(appContent); },
            routing:   () => { if (navRouting)   navRouting.classList.add('active');   renderRoutingPage(appContent); },
            faq:       () => { if (navFaq)       navFaq.classList.add('active');       renderFaqPage(appContent); },
            analytics: () => { if (navAnalytics) navAnalytics.classList.add('active'); renderAnalyticsPage(appContent); },
            users:     () => { if (navUsers)     navUsers.classList.add('active');     renderUsersPage(appContent); }
        };

        if (viewMap[state.currentView]) viewMap[state.currentView]();
    }

    function addRoleBadgeToProfile() {
        if (!state.currentUser) return;
        const profileInfo = document.querySelector('.profile-info');
        if (!profileInfo) return;

        // Add role badge if not already present
        let badge = profileInfo.querySelector('.profile-role');
        if (!badge) {
            const nameEl = profileInfo.querySelector('.profile-name');
            if (nameEl) {
                const roleDiv = document.createElement('span');
                roleDiv.className = 'profile-role';
                roleDiv.textContent = roleDisplayName();
                nameEl.parentNode.insertBefore(roleDiv, nameEl.nextSibling);
            }
        }
    }

    // ═══════════════════════════════════════════════════
    // VIEW: AGENT WORKSPACE — clearly different from admin
    // ═══════════════════════════════════════════════════
    function renderAgentDashboardPage(container) {
        const isAr = state.currentLanguage === 'ar';
        if (pageTitle) pageTitle.innerText = isAr ? 'مساحة الموظف' : 'Agent Workspace';

        const agentRows = getAgentConversationRows();
        const total = agentRows.length;
        const waiting = agentRows.filter(m => m.status !== 'Responded').length;
        const resolved = agentRows.filter(m => m.status === 'Responded').length;
        const handoff = agentRows.filter(m => ['Escalated', 'Pending', 'Pending Human'].includes(m.status)).length;
        const recentMessages = agentRows.slice(0, 5);

        const firstName = escapeHtml(String(state.currentUser?.name || state.currentUser?.email || 'Agent').split(' ')[0]);

        let queueHtml = '';
        recentMessages.forEach((msg, idx) => {
            const statusClass = String(msg.status || '').toLowerCase().replace(/\s+/g, '-');
            queueHtml += `
                <button class="agent-ticket ${idx === 0 ? 'is-hot' : ''}" onclick="document.dispatchEvent(new CustomEvent('navToDetails',{detail:'${msg.id}'}))">
                    <span class="agent-ticket-avatar"><i class="fa-solid fa-user"></i></span>
                    <span class="agent-ticket-main">
                        <strong>${escapeHtml(msg.customerName || 'Customer')}</strong>
                        <small>${escapeHtml(msg.messagePreview || '')}</small>
                    </span>
                    <span class="agent-ticket-meta">
                        <em class="ticket-status ${statusClass}">${escapeHtml(msg.status || 'Pending')}</em>
                        <i class="fa-solid fa-chevron-right"></i>
                    </span>
                </button>`;
        });

        if (!queueHtml) {
            queueHtml = `<div class="agent-empty-queue">
                <i class="fa-solid fa-mug-hot"></i>
                <h3>${isAr ? 'لا توجد رسائل حالياً' : 'No active messages'}</h3>
                <p>${isAr ? 'عند وصول رسائل جديدة ستظهر في قائمة العمل هنا.' : 'New customer messages will appear in your queue here.'}</p>
            </div>`;
        }

        container.innerHTML = `
            <section class="agent-hero-v2">
                <div class="agent-hero-copy">
                    <span class="agent-eyebrow"><i class="fa-solid fa-headset"></i> ${isAr ? 'وضع الموظف' : 'Agent Mode'}</span>
                    <h1>${isAr ? `أهلًا ${firstName}، ركّز على محادثات العملاء` : `Hi ${firstName}, focus on customer conversations`}</h1>
                    <p>${isAr ? 'هاي واجهة تشغيل خفيفة للموظف: رسائل، ردود سريعة، و FAQ فقط. أدوات الإدارة والتحليلات مخفية.' : 'This is a lighter support workspace: messages, quick replies, and FAQ only. Admin tools and analytics are hidden.'}</p>
                    <div class="agent-hero-actions">
                        <button class="agent-primary-action" onclick="document.dispatchEvent(new CustomEvent('navToView',{detail:'messages'}))">
                            <i class="fa-solid fa-comments"></i> ${isAr ? 'افتح الرسائل' : 'Open Inbox'}
                        </button>
                        <button class="agent-secondary-action" onclick="document.dispatchEvent(new CustomEvent('navToView',{detail:'faq'}))">
                            <i class="fa-solid fa-circle-question"></i> FAQ
                        </button>
                    </div>
                </div>
                <div class="agent-live-card">
                    <div class="live-dot"></div>
                    <span>${isAr ? 'قيد العمل الآن' : 'Live support'}</span>
                    <strong>${waiting}</strong>
                    <small>${isAr ? 'رسائل بحاجة متابعة' : 'messages need attention'}</small>
                </div>
            </section>

            <section class="agent-metrics-strip">
                <div><span>${total}</span><small>${isAr ? 'كل الرسائل' : 'Total messages'}</small></div>
                <div><span>${waiting}</span><small>${isAr ? 'بانتظار الرد' : 'Waiting reply'}</small></div>
                <div><span>${handoff}</span><small>${isAr ? 'تحتاج متابعة' : 'Need follow-up'}</small></div>
                <div><span>${resolved}</span><small>${isAr ? 'تم الرد' : 'Responded'}</small></div>
            </section>

            <section class="agent-work-layout">
                <div class="agent-queue-panel">
                    <div class="agent-panel-head">
                        <div>
                            <h2>${isAr ? 'قائمة العمل' : 'Work Queue'}</h2>
                            <p>${isAr ? 'آخر محادثات العملاء للمتابعة السريعة' : 'Latest customer conversations for quick handling'}</p>
                        </div>
                        <button onclick="document.dispatchEvent(new CustomEvent('navToView',{detail:'messages'}))">${isAr ? 'عرض الكل' : 'View all'}</button>
                    </div>
                    <div class="agent-ticket-list">${queueHtml}</div>
                </div>

                <aside class="agent-side-panel">
                    <div class="agent-side-card">
                        <h3><i class="fa-solid fa-bolt"></i> ${isAr ? 'اختصارات الرد' : 'Quick tools'}</h3>
                        <button onclick="document.dispatchEvent(new CustomEvent('navToView',{detail:'messages'}))"><i class="fa-solid fa-reply"></i>${isAr ? 'رد على عميل' : 'Reply to customer'}</button>
                        <button onclick="document.dispatchEvent(new CustomEvent('navToView',{detail:'faq'}))"><i class="fa-solid fa-book-open"></i>${isAr ? 'افتح FAQ' : 'Open FAQ'}</button>
                    </div>
                    <div class="agent-side-card checklist">
                        <h3><i class="fa-solid fa-list-check"></i> ${isAr ? 'تذكير سريع' : 'Support checklist'}</h3>
                        <p><i class="fa-solid fa-check"></i>${isAr ? 'راجع الرسالة كاملة قبل الرد.' : 'Read the full message before replying.'}</p>
                        <p><i class="fa-solid fa-check"></i>${isAr ? 'حوّل للموظف المسؤول عند الشكاوى.' : 'Escalate complaints when needed.'}</p>
                        <p><i class="fa-solid fa-check"></i>${isAr ? 'استخدم FAQ للردود المتكررة.' : 'Use FAQ for repeated answers.'}</p>
                    </div>
                </aside>
            </section>
        `;

        document.addEventListener('navToDetails', (e) => { navigateTo('details', e.detail); }, { once: true });
        document.addEventListener('navToView',    (e) => { navigateTo(e.detail); },           { once: true });
    }

    // ═══════════════════════════════════════════════════
    // VIEW: DASHBOARD
    // ═══════════════════════════════════════════════════
    function renderDashboardPage(container) {
        if (isAgent()) {
            renderAgentDashboardPage(container);
            return;
        }

        const total    = state.messages.length;
        const negative = state.messages.filter(m => m.sentiment === 'Negative').length;
        const urgent   = state.messages.filter(m => m.urgency === 'High').length;
        const resolved = state.messages.filter(m => m.status === 'Responded').length;
        const positive = state.messages.filter(m => m.sentiment === 'Positive').length;
        const neutral  = state.messages.filter(m => m.sentiment === 'Neutral').length;

        const posPct = total ? Math.round((positive / total) * 100) : 0;
        const neuPct = total ? Math.round((neutral  / total) * 100) : 0;
        const negPct = total ? Math.round((negative / total) * 100) : 0;

        const recentMessages = state.messages.slice(0, 5);
        let recentHtml = '';
        recentMessages.forEach(msg => {
            recentHtml += `
            <div class="message-card" style="margin-bottom:12px;grid-template-columns:2fr 3fr;cursor:pointer;"
                 onclick="document.dispatchEvent(new CustomEvent('navToDetails',{detail:'${msg.id}'}))">
                <div class="msg-caller">
                    <h4>${msg.customerName}</h4>
                    <p style="font-size:0.8rem;color:var(--text-secondary);">${msg.intent}</p>
                </div>
                <div class="msg-preview">${msg.messagePreview}</div>
            </div>`;
        });

        if (!recentHtml) {
            recentHtml = `<div class="empty-state" style="padding:30px;">
                <i class="fa-solid fa-inbox"></i>
                <h3>No messages yet</h3>
                <p>Messages from customers will appear here.</p>
            </div>`;
        }

        const workspaceBanner = isAdmin() ? `
            <div class="workspace-banner admin-workspace">
                <div class="workspace-icon"><i class="fa-solid fa-user-shield"></i></div>
                <div>
                    <h2>Admin Control Center</h2>
                    <p>Full access to routing, analytics, FAQ, users, and customer conversations.</p>
                </div>
            </div>
        ` : `
            <div class="workspace-banner agent-workspace">
                <div class="workspace-icon"><i class="fa-solid fa-headset"></i></div>
                <div>
                    <h2>Agent Workspace</h2>
                    <p>Focused view for handling customer messages and FAQ replies. Routing and analytics are hidden for this role.</p>
                </div>
            </div>
        `;

        const adminCards = isAdmin() ? `
            <div class="summary-card" style="cursor:pointer;" onclick="document.dispatchEvent(new CustomEvent('navToView',{detail:'routing'}))">
                <div class="card-icon" style="color:var(--secondary);background:rgba(6,182,212,0.1);"><i class="fa-solid fa-users-gear"></i></div>
                <div class="card-info"><h3 style="font-size:1rem;color:var(--text-primary);font-weight:600;">${t('routing')}</h3><p style="font-size:0.8rem;color:var(--text-secondary);font-weight:400;">${t('manageAgents')}</p></div>
            </div>
            <div class="summary-card" style="cursor:pointer;" onclick="document.dispatchEvent(new CustomEvent('navToView',{detail:'analytics'}))">
                <div class="card-icon" style="color:var(--warning);background:rgba(245,158,11,0.1);"><i class="fa-solid fa-chart-pie"></i></div>
                <div class="card-info"><h3 style="font-size:1rem;color:var(--text-primary);font-weight:600;">${t('reports')}</h3><p style="font-size:0.8rem;color:var(--text-secondary);font-weight:400;">${t('viewAnalytics')}</p></div>
            </div>` : '';

        container.innerHTML = `
            ${workspaceBanner}
            <div class="summary-cards">
                <div class="summary-card">
                    <div class="card-icon icon-blue"><i class="fa-solid fa-envelope"></i></div>
                    <div class="card-info"><h3>${t('total')}</h3><p>${total}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-red"><i class="fa-solid fa-heart-crack"></i></div>
                    <div class="card-info"><h3>${t('negative')}</h3><p>${negative}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-yellow"><i class="fa-solid fa-bolt"></i></div>
                    <div class="card-info"><h3>${t('urgent')}</h3><p>${urgent}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-green"><i class="fa-solid fa-check-circle"></i></div>
                    <div class="card-info"><h3>${t('resolved')}</h3><p>${resolved}</p></div>
                </div>
            </div>

            <div class="page-section">
                <h2>${t('quickNav')}</h2>
                <div class="summary-cards" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr));">
                    <div class="summary-card" style="cursor:pointer;" onclick="document.dispatchEvent(new CustomEvent('navToView',{detail:'messages'}))">
                        <div class="card-icon" style="color:var(--primary);background:rgba(79,70,229,0.1);"><i class="fa-solid fa-inbox"></i></div>
                        <div class="card-info"><h3 style="font-size:1rem;color:var(--text-primary);font-weight:600;">${t('inbox')}</h3><p style="font-size:0.8rem;color:var(--text-secondary);font-weight:400;">${t('viewMessages')}</p></div>
                    </div>
                    ${adminCards}
                    <div class="summary-card" style="cursor:pointer;" onclick="document.dispatchEvent(new CustomEvent('navToView',{detail:'faq'}))">
                        <div class="card-icon" style="color:var(--success);background:rgba(34,197,94,0.1);"><i class="fa-solid fa-circle-question"></i></div>
                        <div class="card-info"><h3 style="font-size:1rem;color:var(--text-primary);font-weight:600;">${t('faq')}</h3><p style="font-size:0.8rem;color:var(--text-secondary);font-weight:400;">${t('manageKnowledge')}</p></div>
                    </div>
                </div>
            </div>

            <div class="dashboard-grid">
                <div class="page-section">
                    <h2>${t('recentMessages')}</h2>
                    <div class="messages-list" style="gap:8px;">${recentHtml}</div>
                </div>
                <div class="page-section">
                    <h2>${t('sentimentOverview')}</h2>
                    <div class="chart-card">
                        <div class="chart-row">
                            <span class="chart-label">${t('positive')}</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color:var(--success);width:0;" data-width="${posPct}%"></div></div>
                            <span class="chart-value">${posPct}%</span>
                        </div>
                        <div class="chart-row">
                            <span class="chart-label">${t('neutral')}</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color:var(--warning);width:0;" data-width="${neuPct}%"></div></div>
                            <span class="chart-value">${neuPct}%</span>
                        </div>
                        <div class="chart-row">
                            <span class="chart-label">${t('negative')}</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color:var(--danger);width:0;" data-width="${negPct}%"></div></div>
                            <span class="chart-value">${negPct}%</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.addEventListener('navToDetails', (e) => { navigateTo('details', e.detail); }, { once: true });
        document.addEventListener('navToView',    (e) => { navigateTo(e.detail); },           { once: true });
        setTimeout(() => { container.querySelectorAll('.chart-bar').forEach(b => { b.style.width = b.getAttribute('data-width'); }); }, 50);
    }

    // ═══════════════════════════════════════════════════
    // VIEW: ROUTING
    // ═══════════════════════════════════════════════════
    function renderRoutingPage(container) {
        const workspaceBanner = `
            <div class="workspace-banner admin-workspace routing-admin-banner">
                <div class="workspace-icon"><i class="fa-solid fa-route"></i></div>
                <div>
                    <h2>Routing & Assignment</h2>
                    <p>Track urgent conversations, see which support agent owns each case, and manually reassign when needed.</p>
                </div>
            </div>
        `;

        const routingRows = getRoutingConversationRows();
        const totalAssigned = routingRows.filter(m => isAssigned(m.assignedAgent)).length;
        const unassigned    = routingRows.filter(m => !isAssigned(m.assignedAgent)).length;
        const escalated     = routingRows.filter(m => String(m.status || '').toLowerCase().includes('escalated')).length;
        const activeAgents  = getActiveAgents();

        const searchVal = state.filters.search;
        const statFilt  = state.filters.routingStatus;
        const urgFilt   = state.filters.routingUrgency;
        const assFilt   = state.filters.routingAssignment;

        let filtered = routingRows.filter(m => {
            const matchSearch = m.customerName.toLowerCase().includes(searchVal) || m.intent.toLowerCase().includes(searchVal) || String(m.messagePreview || '').toLowerCase().includes(searchVal);
            const matchStat   = statFilt === 'All' || m.status === statFilt;
            const matchUrg    = urgFilt === 'All'  || m.urgency === urgFilt;
            let matchAss = true;
            if (assFilt === 'Assigned')   matchAss = isAssigned(m.assignedAgent);
            if (assFilt === 'Unassigned') matchAss = !isAssigned(m.assignedAgent);
            return matchSearch && matchStat && matchUrg && matchAss;
        });

        const buildAgentOptions = (selectedAgent) => state.agents
            .map(a => `<option value="${escapeHtml(a.email)}" ${selectedAgent === a.email ? 'selected' : ''}>${escapeHtml(a.name || a.email)}</option>`)
            .join('');

        let tableRows = filtered.map(msg => {
            const agentValue = isAssigned(msg.assignedAgent) ? msg.assignedAgent : 'Unassigned';
            const currentAgentMissing = isAssigned(agentValue) && !state.agents.some(a => a.email === agentValue);
            const currentAgentOption = currentAgentMissing
                ? `<option value="${escapeHtml(agentValue)}" selected>${escapeHtml(getAgentDisplayName(agentValue))}</option>`
                : '';
            const options = `<option value="Unassigned" ${agentValue === 'Unassigned' ? 'selected' : ''}>Unassigned</option>${currentAgentOption}${buildAgentOptions(agentValue)}`;

            return `
                <tr>
                    <td style="font-weight:500;">${msg.customerName}</td>
                    <td>${channelBadgeHtml(msg)}</td>
                    <td>${msg.intent}</td>
                    <td><span class="badge badge-${msg.sentiment.toLowerCase()}">${msg.sentiment}</span></td>
                    <td><span class="badge badge-${msg.urgency.toLowerCase()}">${msg.urgency}</span></td>
                    <td><span class="badge badge-${msg.status.toLowerCase()}">${msg.status}</span></td>
                    <td><select class="dropdown-agent" data-id="${msg.id}" data-conv="${msg.conversationId || ''}">${options}</select></td>
                    <td><button class="btn btn-outline escalate-btn" data-id="${msg.id}" data-conv="${msg.conversationId || ''}"
                        style="padding:6px 12px;font-size:0.8rem;color:var(--danger);border-color:var(--danger);">
                        <i class="fa-solid fa-triangle-exclamation"></i> ${t('escalate')}
                    </button></td>
                </tr>`;
        }).join('');

        if (filtered.length === 0) {
            tableRows = `<tr><td colspan="8" style="text-align:center;padding:40px;color:var(--text-secondary);">${t('noRoutingMatch')}</td></tr>`;
        }

        container.innerHTML = `
            ${workspaceBanner}
            <div class="summary-cards">
                <div class="summary-card"><div class="card-icon icon-blue"><i class="fa-solid fa-user-check"></i></div><div class="card-info"><h3>${t('assigned')}</h3><p>${totalAssigned}</p></div></div>
                <div class="summary-card"><div class="card-icon icon-yellow"><i class="fa-solid fa-user-clock"></i></div><div class="card-info"><h3>${t('unassigned')}</h3><p>${unassigned}</p></div></div>
                <div class="summary-card"><div class="card-icon icon-red"><i class="fa-solid fa-triangle-exclamation"></i></div><div class="card-info"><h3>${t('escalated')}</h3><p>${escalated}</p></div></div>
                <div class="summary-card"><div class="card-icon icon-green"><i class="fa-solid fa-users"></i></div><div class="card-info"><h3>${t('activeAgents')}</h3><p>${activeAgents.length}</p></div></div>
            </div>

            <div class="filter-bar">
                <input type="text" id="routeSearch" class="search-input" placeholder="${t('searchPlaceholder')}" value="${state.filters.search}" style="padding-left:16px;">
                <select id="routeAssignment" class="filter-select">
                    <option value="All" ${assFilt === 'All' ? 'selected' : ''}>${t('allAssignments')}</option>
                    <option value="Assigned" ${assFilt === 'Assigned' ? 'selected' : ''}>${t('assigned')}</option>
                    <option value="Unassigned" ${assFilt === 'Unassigned' ? 'selected' : ''}>${t('unassigned')}</option>
                </select>
                <select id="routeStatus" class="filter-select">
                    <option value="All" ${statFilt === 'All' ? 'selected' : ''}>${t('allStatuses')}</option>
                    <option value="Pending" ${statFilt === 'Pending' ? 'selected' : ''}>${t('pending')}</option>
                    <option value="Responded" ${statFilt === 'Responded' ? 'selected' : ''}>${t('responded')}</option>
                    <option value="Escalated" ${statFilt === 'Escalated' ? 'selected' : ''}>${t('escalated')}</option>
                </select>
                <select id="routeUrgency" class="filter-select">
                    <option value="All" ${urgFilt === 'All' ? 'selected' : ''}>${t('allUrgenciesOpt')}</option>
                    <option value="High" ${urgFilt === 'High' ? 'selected' : ''}>${t('high')}</option>
                    <option value="Medium" ${urgFilt === 'Medium' ? 'selected' : ''}>${t('medium')}</option>
                    <option value="Low" ${urgFilt === 'Low' ? 'selected' : ''}>${t('low')}</option>
                </select>
                <button id="clearRouteFilters" class="btn btn-outline"><i class="fa-solid fa-rotate-left"></i> ${t('clear')}</button>
            </div>

            <div class="routing-table-card">
                <table class="routing-table">
                    <thead>
                        <tr>
                            <th>${t('customer')}</th><th>Channel</th><th>${t('intent')}</th><th>${t('sentiment')}</th>
                            <th>${t('urgency')}</th><th>${t('status')}</th><th>${t('assignedAgent')}</th><th>${t('quickAction')}</th>
                        </tr>
                    </thead>
                    <tbody>${tableRows}</tbody>
                </table>
            </div>
        `;

        document.getElementById('routeSearch').addEventListener('input',    (e) => { state.filters.search = e.target.value.toLowerCase(); renderRoutingPage(container); });
        document.getElementById('routeAssignment').addEventListener('change',(e) => { state.filters.routingAssignment = e.target.value; renderRoutingPage(container); });
        document.getElementById('routeStatus').addEventListener('change',   (e) => { state.filters.routingStatus = e.target.value; renderRoutingPage(container); });
        document.getElementById('routeUrgency').addEventListener('change',  (e) => { state.filters.routingUrgency = e.target.value; renderRoutingPage(container); });
        document.getElementById('clearRouteFilters').addEventListener('click', () => {
            state.filters.search = ''; state.filters.routingAssignment = 'All';
            state.filters.routingStatus = 'All'; state.filters.routingUrgency = 'All';
            if (globalSearch) globalSearch.value = '';
            renderRoutingPage(container);
        });

        container.querySelectorAll('.dropdown-agent').forEach(select => {
            select.addEventListener('change', async (e) => {
                const msgId  = e.target.getAttribute('data-id');
                const convId = e.target.getAttribute('data-conv');
                const agent  = e.target.value;

                const normalizedAgent = agent === 'Unassigned' ? 'Unassigned' : agent;

                state.messages
                    .filter(m => m.id === msgId || (convId && String(m.conversationId) === String(convId)))
                    .forEach(m => {
                        m.assignedAgent = normalizedAgent;
                        m.botEnabled = normalizedAgent === 'Unassigned';
                    });

                if (convId) {
                    try {
                        const updated = await apiRequest(`/conversations/${convId}/assign`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ assigned_agent: agent === 'Unassigned' ? null : agent })
                        });

                        const conv = state.conversationsById[String(convId)] || state.conversationsById[convId] || {};
                        conv.assigned_agent = agent === 'Unassigned' ? null : agent;
                        conv.bot_enabled = agent === 'Unassigned';
                        state.conversationsById[String(convId)] = { ...conv, ...(updated || {}) };

                        showToast('Agent Assigned', `Assigned to ${agent === 'Unassigned' ? 'nobody' : getAgentDisplayName(agent)}`, 'success');
                    } catch (err) {
                        showToast('Error', `Failed to assign: ${err.message}`, 'error');
                    }
                }

                await loadBackendMessages().catch(() => {});
                renderRoutingPage(container);
            });
        });

        container.querySelectorAll('.escalate-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const msgId  = e.currentTarget.getAttribute('data-id');
                const convId = e.currentTarget.getAttribute('data-conv');
                const msg    = state.messages.find(m => m.id === msgId);

                if (msg) msg.status = 'Escalated';
                if (convId) {
                    try {
                        await apiRequest(`/conversations/${convId}/status`, {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ status: 'escalated' })
                        });
                        showToast('Escalated', 'Conversation has been escalated.', 'warning');
                    } catch (err) {
                        showToast('Error', `Failed to escalate: ${err.message}`, 'error');
                    }
                }
                await loadBackendMessages().catch(() => {});
                renderRoutingPage(container);
            });
        });
    }

    // ═══════════════════════════════════════════════════
    // VIEW: MESSAGES
    // ═══════════════════════════════════════════════════
    function renderMessagesPage(container) {
        const visibleRows = getCurrentMessageList();
        const total    = visibleRows.length;
        const negative = visibleRows.filter(m => m.sentiment === 'Negative').length;
        const urgent   = visibleRows.filter(m => m.urgency === 'High').length;
        const pending  = visibleRows.filter(m => ['Pending', 'Escalated', 'Pending Human'].includes(m.status)).length;

        container.insertAdjacentHTML('beforeend', `
            ${isAgent() ? `<div class="agent-inbox-notice"><i class="fa-solid fa-user-check"></i><div><strong>My assigned conversations</strong><span>Only conversations assigned to you appear here. Open a conversation to view its full history.</span></div></div>` : ''}
            <div class="summary-cards">
                <div class="summary-card"><div class="card-icon icon-blue"><i class="fa-solid fa-envelope"></i></div><div class="card-info"><h3>${t('totalMessages')}</h3><p>${total}</p></div></div>
                <div class="summary-card"><div class="card-icon icon-red"><i class="fa-solid fa-heart-crack"></i></div><div class="card-info"><h3>${t('negative')}</h3><p>${negative}</p></div></div>
                <div class="summary-card"><div class="card-icon icon-yellow"><i class="fa-solid fa-bolt"></i></div><div class="card-info"><h3>${t('urgentCases')}</h3><p>${urgent}</p></div></div>
                <div class="summary-card"><div class="card-icon icon-green"><i class="fa-regular fa-clock"></i></div><div class="card-info"><h3>${t('pendingCases')}</h3><p>${pending}</p></div></div>
            </div>

            <div class="filter-bar">
                <input type="text" id="localSearch" class="search-input" placeholder="${t('searchPlaceholder')}" value="${state.filters.search}" style="padding-left:16px;">
                <select id="sentimentFilter" class="filter-select">
                    <option value="All" ${state.filters.sentiment === 'All' ? 'selected' : ''}>${t('allSentiments')}</option>
                    <option value="Positive" ${state.filters.sentiment === 'Positive' ? 'selected' : ''}>${t('positive')}</option>
                    <option value="Neutral"  ${state.filters.sentiment === 'Neutral'  ? 'selected' : ''}>${t('neutral')}</option>
                    <option value="Negative" ${state.filters.sentiment === 'Negative' ? 'selected' : ''}>${t('negative')}</option>
                </select>
                <select id="urgencyFilter" class="filter-select">
                    <option value="All"    ${state.filters.urgency === 'All'    ? 'selected' : ''}>${t('allUrgencies')}</option>
                    <option value="Low"    ${state.filters.urgency === 'Low'    ? 'selected' : ''}>${t('low')}</option>
                    <option value="Medium" ${state.filters.urgency === 'Medium' ? 'selected' : ''}>${t('medium')}</option>
                    <option value="High"   ${state.filters.urgency === 'High'   ? 'selected' : ''}>${t('high')}</option>
                </select>
                <select id="channelFilter" class="filter-select">
                    <option value="All" ${state.filters.channel === 'All' ? 'selected' : ''}>All Channels</option>
                    <option value="whatsapp" ${state.filters.channel === 'whatsapp' ? 'selected' : ''}>WhatsApp</option>
                    <option value="instagram" ${state.filters.channel === 'instagram' ? 'selected' : ''}>Instagram</option>
                    <option value="web" ${state.filters.channel === 'web' ? 'selected' : ''}>Web Chat</option>
                </select>
                <button id="clearFiltersBtn" class="btn btn-outline"><i class="fa-solid fa-rotate-left"></i> ${t('clear')}</button>
                <button id="refreshMsgsBtn" class="btn btn-outline" style="margin-left:auto;"><i class="fa-solid fa-rotate"></i> Refresh</button>
            </div>
            <div id="messagesList" class="messages-list"></div>
        `);

        document.getElementById('localSearch').addEventListener('input',    (e) => { state.filters.search = e.target.value.toLowerCase(); updateListDisplay(); });
        document.getElementById('sentimentFilter').addEventListener('change',(e) => { state.filters.sentiment = e.target.value; updateListDisplay(); });
        document.getElementById('urgencyFilter').addEventListener('change',  (e) => { state.filters.urgency = e.target.value; updateListDisplay(); });
        document.getElementById('channelFilter').addEventListener('change',  (e) => { state.filters.channel = e.target.value; updateListDisplay(); });
        document.getElementById('clearFiltersBtn').addEventListener('click', () => {
            state.filters.search = ''; state.filters.sentiment = 'All'; state.filters.urgency = 'All'; state.filters.channel = 'All';
            document.getElementById('localSearch').value = '';
            document.getElementById('sentimentFilter').value = 'All';
            document.getElementById('urgencyFilter').value = 'All';
            document.getElementById('channelFilter').value = 'All';
            if (globalSearch) globalSearch.value = '';
            updateListDisplay();
        });
        document.getElementById('refreshMsgsBtn').addEventListener('click', async (e) => {
            const btn = e.currentTarget;
            setButtonLoading(btn, true);
            try {
                await loadBackendMessages();
                updateListDisplay();
                showToast('Refreshed', 'Messages updated.', 'success');
            } catch (err) {
                showToast('Error', `Failed to refresh: ${err.message}`, 'error');
            } finally {
                setButtonLoading(btn, false);
            }
        });

        updateListDisplay();
    }

    function updateListDisplay() {
        const listContainer = document.getElementById('messagesList');
        if (!listContainer) return;

        const sourceMessages = getCurrentMessageList();
        const filtered = sourceMessages.filter(msg => {
            const matchSearch    = msg.customerName.toLowerCase().includes(state.filters.search) || String(msg.externalCustomerId || '').toLowerCase().includes(state.filters.search) || msg.intent.toLowerCase().includes(state.filters.search) || msg.messagePreview.toLowerCase().includes(state.filters.search);
            const matchSentiment = state.filters.sentiment === 'All' || msg.sentiment === state.filters.sentiment;
            const matchUrgency   = state.filters.urgency   === 'All' || msg.urgency   === state.filters.urgency;
            const matchChannel   = state.filters.channel   === 'All' || msg.channel === state.filters.channel;
            return matchSearch && matchSentiment && matchUrgency && matchChannel;
        });

        listContainer.innerHTML = '';

        if (filtered.length === 0) {
            listContainer.innerHTML = `<div class="empty-state"><i class="fa-solid fa-inbox"></i><h3>${t('noMessagesFound')}</h3><p>${t('adjustFilters')}</p></div>`;
            return;
        }

        filtered.forEach(msg => {
            const card = document.createElement('div');
            card.className = 'message-card';
            card.innerHTML = `
                <div class="msg-caller"><h4>${escapeHtml(msg.customerName)}</h4><p>${channelBadgeHtml(msg)} <span class="customer-external-id">${escapeHtml(msg.externalCustomerId || '')}</span></p></div>
                <div class="msg-preview">${escapeHtml(msg.messagePreview)}</div>
                <div class="msg-meta"><span class="badge badge-${msg.sentiment.toLowerCase()}">${msg.sentiment}</span><span style="font-size:0.8rem;">${escapeHtml(msg.intent)}</span></div>
                <div class="msg-meta"><span class="badge badge-${msg.urgency.toLowerCase()}">${msg.urgency}</span><span style="font-size:0.8rem;color:var(--primary);"><i class="fa-solid fa-user"></i> ${escapeHtml(getAgentDisplayName(msg.assignedAgent))}</span></div>
                <div><span class="badge badge-${msg.status.toLowerCase()}">${msg.status}</span></div>
            `;
            card.addEventListener('click', () => { navigateTo('details', msg.id); });
            listContainer.appendChild(card);
        });
    }

    // ═══════════════════════════════════════════════════
    // VIEW: MESSAGE DETAILS
    // ═══════════════════════════════════════════════════
    function renderMessageDetailsPage(container) {
        const msg = state.messages.find(m => m.id === state.selectedMessageId);
        if (!msg) { navigateTo('messages'); return; }

        const isHighUrgency   = msg.urgency === 'High';
        const isLowConfidence = msg.confidence < 70;
        const needsHuman      = isHighUrgency || isLowConfidence;

        let chatHtml = '';
        msg.conversationHistory.forEach(c => {
            chatHtml += `<div class="chat-bubble ${c.kind}">
                <div class="chat-header">${escapeHtml(c.sender)} • ${c.time}</div>
                <div class="chat-text">${escapeHtml(c.text)}</div>
            </div>`;
        });

        const fullTime = new Date(msg.timestamp).toLocaleString();
        const hasConversation = !!msg.conversationId;

        const escalationHtml = needsHuman
            ? `<div class="escalation-notice">
                <i class="fa-solid fa-triangle-exclamation"></i>
                <div><strong>${t('humanRequired')}</strong><p>${isHighUrgency ? t('highUrgencyReason') : t('lowConfidenceReason')}</p></div>
              </div>`
            : `<div class="auto-reply-success"><i class="fa-solid fa-circle-check"></i><span>${t('autoReplySentAuto')}</span></div>`;

        const replyAreaHtml = hasConversation
            ? `<div class="reply-box">
                <textarea id="replyTextarea" class="reply-textarea" placeholder="${t('replyPlaceholder')}" rows="3"></textarea>
                <div class="reply-box-footer">
                    <label class="bot-toggle" title="${msg.botEnabled ? t('botOnHint') : t('botOffHint')}">
                        <span class="bot-toggle-label"><i class="fa-solid fa-robot"></i> ${t('botStatus')}</span>
                        <span class="switch">
                            <input type="checkbox" id="botToggleInput" ${msg.botEnabled ? 'checked' : ''}>
                            <span class="switch-slider"></span>
                        </span>
                        <span class="bot-toggle-state ${msg.botEnabled ? 'on' : 'off'}" id="botToggleState">${msg.botEnabled ? t('botOn') : t('botOff')}</span>
                    </label>
                    <button class="btn btn-primary" id="sendReplyBtn"><i class="fa-solid fa-paper-plane"></i> ${t('sendReply')}</button>
                </div>
              </div>`
            : `<div class="no-conversation-note"><i class="fa-solid fa-circle-info"></i> ${t('noConversationLinked')}</div>`;

        container.insertAdjacentHTML('beforeend', `
            <div class="details-container">
                <button id="backToListBtn" class="back-btn"><i class="fa-solid fa-arrow-left"></i> ${t('backToList')}</button>
                <div class="details-header">
                    <div class="details-user"><h2>${escapeHtml(msg.customerName)}</h2><p>${channelBadgeHtml(msg)} <span class="customer-external-id">${escapeHtml(msg.externalCustomerId || '')}</span> • ${fullTime}</p></div>
                    <div style="text-align:right;">
                        <span class="badge badge-${msg.status.toLowerCase()}" style="margin-bottom:8px;display:inline-block;">${msg.status}</span><br>
                        <span style="font-size:0.85rem;color:var(--text-secondary);"><i class="fa-solid fa-user"></i> ${t('assignedTo')} <b>${escapeHtml(getAgentDisplayName(msg.assignedAgent))}</b></span>
                    </div>
                </div>
                <div class="full-message-card">"${escapeHtml(msg.fullMessage)}"</div>
                <div class="ai-analysis">
                    <h3><i class="fa-solid fa-wand-magic-sparkles" style="color:var(--primary)"></i> ${t('aiAnalysis')}</h3>
                    <div class="analysis-grid">
                        <div class="analysis-item"><span>${t('sentiment')}</span><div class="badge badge-${msg.sentiment.toLowerCase()}">${msg.sentiment}</div></div>
                        <div class="analysis-item"><span>${t('intent')}</span><div style="font-weight:600;">${msg.intent}</div></div>
                        <div class="analysis-item"><span>${t('urgency')}</span><div class="badge badge-${msg.urgency.toLowerCase()}">${msg.urgency}</div></div>
                        <div class="analysis-item">
                            <span>${t('confidence')}</span>
                            <div style="font-weight:600;font-size:1.1rem;color:var(--success);">${msg.confidence}%</div>
                            <div class="confidence-bar-container"><div class="confidence-bar" style="width:0%;" data-target="${msg.confidence}"></div></div>
                        </div>
                    </div>
                </div>
                <div class="chat-history">
                    <h3>${t('conversationHistory')}</h3>
                    <div style="display:flex;flex-direction:column;">${chatHtml}</div>
                    ${replyAreaHtml}
                </div>
                <div class="action-buttons" style="margin-top:20px;">
                    ${escalationHtml}
                    <button class="btn btn-outline" id="markResolvedBtn"><i class="fa-solid fa-check"></i> ${t('markResolved')}</button>
                </div>
            </div>
        `);

        setTimeout(() => {
            const bar = container.querySelector('.confidence-bar');
            if (bar) bar.style.width = bar.getAttribute('data-target') + '%';
        }, 100);

        document.getElementById('backToListBtn').addEventListener('click', () => { navigateTo('messages'); });

        const sendReplyBtn = document.getElementById('sendReplyBtn');
        if (sendReplyBtn) {
            sendReplyBtn.addEventListener('click', async () => {
                const textarea = document.getElementById('replyTextarea');
                const text = textarea.value.trim();
                if (!text) return;

                sendReplyBtn.disabled = true;
                try {
                    const res = await apiRequest(`/conversations/${msg.conversationId}/reply`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text })
                    });

                    msg.conversationHistory.push({
                        sender: state.currentUser ? state.currentUser.name : 'Agent',
                        kind: 'agent',
                        text,
                        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    });
                    msg.botEnabled = res.bot_enabled;
                    msg.status = 'Responded';

                    showToast('Reply Sent', t('replySentToast'), 'success');
                    navigateTo('details', msg.id);
                } catch (err) {
                    showToast('Error', `${t('replyFailedToast')}: ${err.message}`, 'error');
                } finally {
                    sendReplyBtn.disabled = false;
                }
            });
        }

        const botToggleInput = document.getElementById('botToggleInput');
        if (botToggleInput) {
            botToggleInput.addEventListener('change', async (e) => {
                const enabled = e.target.checked;
                try {
                    await apiRequest(`/conversations/${msg.conversationId}/bot`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ enabled })
                    });
                    msg.botEnabled = enabled;
                    const stateLabel = document.getElementById('botToggleState');
                    if (stateLabel) {
                        stateLabel.textContent = enabled ? t('botOn') : t('botOff');
                        stateLabel.className = `bot-toggle-state ${enabled ? 'on' : 'off'}`;
                    }
                    showToast('Bot Status', enabled ? t('botOnHint') : t('botOffHint'), 'success');
                } catch (err) {
                    e.target.checked = !enabled;
                    showToast('Error', `${t('botToggleFailedToast')}: ${err.message}`, 'error');
                }
            });
        }

        document.getElementById('markResolvedBtn').addEventListener('click', async () => {
            msg.status = 'Responded';
            if (msg.conversationId) {
                try {
                    await apiRequest(`/conversations/${msg.conversationId}/status`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ status: 'resolved' })
                    });
                } catch (err) {
                    showToast('Error', err.message, 'error');
                    return;
                }
            }
            showToast('Resolved', t('actionRecorded'), 'success');
            navigateTo('messages');
        });
    }

    // ═══════════════════════════════════════════════════
    // VIEW: FAQ
    // ═══════════════════════════════════════════════════
    function escapeHtml(value) {
        return String(value || '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
    }

    function renderFaqPage(container) {
        let faqListHtml = state.faqs.map(faq => {
            const enabledBadge = faq.enabled
                ? `<span class="badge badge-positive">Enabled</span>`
                : `<span class="badge badge-negative">Disabled</span>`;
            return `
            <div class="faq-item" id="faq-item-${faq.id}">
                <div class="faq-content" style="flex:1;">
                    <h4>${escapeHtml(faq.question)}</h4>
                    <p>${escapeHtml(faq.answer)}</p>
                    <div style="margin-top:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                        ${enabledBadge}
                        ${faq.category ? `<span style="font-size:0.8rem;color:var(--text-secondary);">Category: ${escapeHtml(faq.category)}</span>` : ''}
                        ${faq.intent   ? `<span style="font-size:0.8rem;color:var(--text-secondary);">Intent: ${escapeHtml(faq.intent)}</span>`   : ''}
                    </div>
                </div>
                <div class="faq-actions" style="display:flex;gap:8px;flex-wrap:wrap;">
                    <button class="btn btn-outline edit-faq-btn" data-id="${faq.id}" style="padding:8px 12px;border-radius:8px;" title="Edit"><i class="fa-solid fa-pen"></i></button>
                    <button class="btn btn-outline toggle-faq-btn" data-id="${faq.id}" data-enabled="${faq.enabled ? 'true' : 'false'}" style="padding:8px 12px;border-radius:8px;" title="${faq.enabled ? 'Disable' : 'Enable'}">
                        <i class="fa-solid ${faq.enabled ? 'fa-eye-slash' : 'fa-eye'}"></i>
                    </button>
                    <button class="btn btn-outline delete-faq-btn" data-id="${faq.id}" style="color:var(--danger);border-color:var(--danger);padding:8px 12px;border-radius:8px;" title="Delete"><i class="fa-solid fa-trash"></i></button>
                </div>
            </div>
            <form class="faq-form edit-faq-form" id="edit-form-${faq.id}" data-id="${faq.id}" style="display:none;margin-top:-10px;margin-bottom:20px;border-top-left-radius:0;border-top-right-radius:0;border-top:none;">
                <input type="text" class="edit-q" value="${escapeHtml(faq.question)}" required>
                <textarea class="edit-a" required>${escapeHtml(faq.answer)}</textarea>
                <div style="display:flex;gap:8px;">
                    <button type="submit" class="btn btn-primary">${t('saveChanges')}</button>
                    <button type="button" class="btn btn-outline cancel-edit-btn" data-id="${faq.id}">${t('cancel')}</button>
                </div>
            </form>
        `}).join('');

        if (state.faqs.length === 0) {
            faqListHtml = `<div class="empty-state"><i class="fa-solid fa-circle-question" style="font-size:3rem;color:var(--text-secondary);margin-bottom:16px;display:block;"></i><h3>${t('noFaqs')}</h3><p>${t('noFaqsDesc')}</p></div>`;
        }

        container.innerHTML = `
            <div class="page-section" style="max-width:900px;margin:0 auto;">
                <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:16px;">
                    <h2 style="margin:0;">${t('addNewFaq')}</h2>
                    <button id="refreshFaqBtn" class="btn btn-outline"><i class="fa-solid fa-rotate"></i> Refresh</button>
                </div>

                <form class="faq-form" id="faqForm">
                    <input type="text" id="faqQuestion" placeholder="${t('enterQuestion')}" required>
                    <textarea id="faqAnswer" placeholder="${t('enterAnswer')}" required></textarea>
                    <button type="submit" class="btn btn-primary" style="align-self:flex-start;"><i class="fa-solid fa-plus"></i> ${t('addFaq')}</button>
                </form>

                <h2>${t('existingFaqs')}</h2>
                <div class="faq-list">${faqListHtml}</div>
            </div>
        `;

        document.getElementById('refreshFaqBtn').addEventListener('click', async (e) => {
            const btn = e.currentTarget;
            setButtonLoading(btn, true);
            try {
                await loadBackendFaqs();
                renderFaqPage(container);
                showToast('Refreshed', 'FAQs updated.', 'success');
            } catch (err) {
                showToast('Error', `Failed to refresh FAQs: ${err.message}`, 'error');
                setButtonLoading(btn, false);
            }
        });

        document.getElementById('faqForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const q = document.getElementById('faqQuestion').value.trim();
            const a = document.getElementById('faqAnswer').value.trim();
            if (!q || !a) return;
            const btn = e.currentTarget.querySelector('[type="submit"]');
            setButtonLoading(btn, true);
            try {
                await createBackendFaq(q, a);
                await loadBackendFaqs();
                renderFaqPage(container);
                showToast('FAQ Added', 'New FAQ created successfully.', 'success');
            } catch (err) {
                showToast('Error', `Failed to create FAQ: ${err.message}`, 'error');
                setButtonLoading(btn, false);
            }
        });

        container.querySelectorAll('.delete-faq-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.currentTarget.getAttribute('data-id');
                showConfirmModal({
                    title: 'Delete FAQ',
                    message: 'Are you sure you want to delete this FAQ? This cannot be undone.',
                    icon: 'fa-solid fa-trash',
                    confirmLabel: 'Delete',
                    confirmClass: 'btn btn-primary',
                    onConfirm: async () => {
                        try {
                            await deleteBackendFaq(id);
                            await loadBackendFaqs();
                            renderFaqPage(container);
                            showToast('Deleted', 'FAQ deleted successfully.', 'success');
                        } catch (err) {
                            showToast('Error', `Failed to delete FAQ: ${err.message}`, 'error');
                        }
                    }
                });
            });
        });

        container.querySelectorAll('.toggle-faq-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const id = e.currentTarget.getAttribute('data-id');
                const currentlyEnabled = e.currentTarget.getAttribute('data-enabled') === 'true';
                setButtonLoading(e.currentTarget, true);
                try {
                    await setBackendFaqEnabled(id, !currentlyEnabled);
                    await loadBackendFaqs();
                    renderFaqPage(container);
                    showToast('Updated', `FAQ ${!currentlyEnabled ? 'enabled' : 'disabled'}.`, 'success');
                } catch (err) {
                    showToast('Error', `Failed to update FAQ: ${err.message}`, 'error');
                    setButtonLoading(e.currentTarget, false);
                }
            });
        });

        container.querySelectorAll('.edit-faq-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.currentTarget.getAttribute('data-id');
                document.getElementById(`edit-form-${id}`).style.display = 'flex';
                document.getElementById(`faq-item-${id}`).style.borderBottomLeftRadius = '0';
                document.getElementById(`faq-item-${id}`).style.borderBottomRightRadius = '0';
            });
        });

        container.querySelectorAll('.cancel-edit-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.currentTarget.getAttribute('data-id');
                document.getElementById(`edit-form-${id}`).style.display = 'none';
                document.getElementById(`faq-item-${id}`).style.borderBottomLeftRadius = '12px';
                document.getElementById(`faq-item-${id}`).style.borderBottomRightRadius = '12px';
            });
        });

        container.querySelectorAll('.edit-faq-form').forEach(form => {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const id = e.currentTarget.getAttribute('data-id');
                const existing = state.faqs.find(f => String(f.id) === String(id)) || {};
                const q = e.currentTarget.querySelector('.edit-q').value.trim();
                const a = e.currentTarget.querySelector('.edit-a').value.trim();
                const btn = e.currentTarget.querySelector('[type="submit"]');
                setButtonLoading(btn, true);
                try {
                    await updateBackendFaq(id, q, a, existing);
                    await loadBackendFaqs();
                    renderFaqPage(container);
                    showToast('Updated', 'FAQ updated successfully.', 'success');
                } catch (err) {
                    showToast('Error', `Failed to update FAQ: ${err.message}`, 'error');
                    setButtonLoading(btn, false);
                }
            });
        });
    }

    // ═══════════════════════════════════════════════════
    // VIEW: ANALYTICS
    // ═══════════════════════════════════════════════════
    async function renderAnalyticsPage(container) {
        container.innerHTML = `
            <div class="empty-state" style="padding:40px;">
                <div class="splash-spinner" style="margin:0 auto;"></div>
                <p style="margin-top:16px;color:var(--text-secondary);">Loading analytics...</p>
            </div>
        `;

        let analyticsData = null;
        try {
            analyticsData = await apiRequest('/analytics/summary');
        } catch (err) {
            container.innerHTML = `<div class="empty-state"><i class="fa-solid fa-chart-pie"></i><h3>Could not load analytics</h3><p>${err.message}</p></div>`;
            return;
        }

        const total = analyticsData.total_messages || 0;
        const sent  = analyticsData.sentiment || {};
        const cat   = analyticsData.category || {};
        const urg   = analyticsData.urgency   || {};

        const posPct = total ? Math.round(((sent.positive || 0) / total) * 100) : 0;
        const neuPct = total ? Math.round(((sent.neutral  || 0) / total) * 100) : 0;
        const negPct = total ? Math.round(((sent.negative || 0) / total) * 100) : 0;

        // Normalize backend/model urgency labels into the UI buckets.
        // Database/model may store: normal / urgent / critical.
        // Dashboard displays: Low / Medium / High.
        function urgencyCount(...aliases) {
            const keys = aliases.map(a => String(a).trim().toLowerCase());
            return Object.entries(urg).reduce((sum, [key, count]) => {
                const normalizedKey = String(key || '').trim().toLowerCase();
                return keys.includes(normalizedKey) ? sum + (Number(count) || 0) : sum;
            }, 0);
        }

        const lowUrg  = urgencyCount('low', 'normal');
        const midUrg  = urgencyCount('medium', 'urgent', 'human_handoff', 'pending_human');
        const highUrg = urgencyCount('high', 'critical', 'escalation', 'escalated', 'escalate');
        const urgTotal = lowUrg + midUrg + highUrg;

        function pct(count, denominator = urgTotal) {
            return denominator ? Math.round((Number(count || 0) / denominator) * 100) : 0;
        }

        const lowUrgPct = pct(lowUrg);
        const midUrgPct = pct(midUrg);
        const highUrgPct = pct(highUrg);

        const catEntries = Object.entries(cat);
        const topCatHtml = catEntries.map(([name, count]) => {
            const pct = total ? Math.round((count / total) * 100) : 0;
            return `<div class="chart-row">
                <span class="chart-label" style="width:120px;">${name}</span>
                <div class="chart-bar-container"><div class="chart-bar" style="background-color:var(--secondary);width:0;" data-width="${pct}%"></div></div>
                <span class="chart-value">${pct}%</span>
            </div>`;
        }).join('');

        container.innerHTML = `
            <div class="summary-cards" style="margin-bottom:24px;">
                <div class="summary-card">
                    <div class="card-icon icon-blue"><i class="fa-solid fa-envelope"></i></div>
                    <div class="card-info"><h3>Total Messages</h3><p>${total}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-green"><i class="fa-solid fa-heart"></i></div>
                    <div class="card-info"><h3>Positive</h3><p>${sent.positive || 0}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-red"><i class="fa-solid fa-heart-crack"></i></div>
                    <div class="card-info"><h3>Negative</h3><p>${sent.negative || 0}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-yellow"><i class="fa-solid fa-bolt"></i></div>
                    <div class="card-info"><h3>Urgent/Critical</h3><p>${midUrg + highUrg}</p></div>
                </div>
            </div>

            <div class="dashboard-grid" style="margin-bottom:24px;">
                <div class="page-section">
                    <h2>${t('smartInsights')}</h2>
                    <div class="insight-card">
                        <i class="fa-solid fa-lightbulb insight-icon"></i>
                        <div class="insight-content"><h4>${t('insightTitle1')}</h4><p>${t('insightDesc1')}</p></div>
                    </div>
                    <div class="insight-card">
                        <i class="fa-solid fa-arrow-trend-down insight-icon" style="color:var(--success);"></i>
                        <div class="insight-content"><h4>${t('insightTitle2')}</h4><p>${t('insightDesc2')}</p></div>
                    </div>
                </div>
                <div class="page-section">
                    <h2>${t('sentimentOverview')}</h2>
                    <div class="chart-card">
                        <div class="chart-row">
                            <span class="chart-label">${t('positive')}</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color:var(--success);width:0;" data-width="${posPct}%"></div></div>
                            <span class="chart-value">${posPct}%</span>
                        </div>
                        <div class="chart-row">
                            <span class="chart-label">${t('neutral')}</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color:var(--warning);width:0;" data-width="${neuPct}%"></div></div>
                            <span class="chart-value">${neuPct}%</span>
                        </div>
                        <div class="chart-row">
                            <span class="chart-label">${t('negative')}</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color:var(--danger);width:0;" data-width="${negPct}%"></div></div>
                            <span class="chart-value">${negPct}%</span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="dashboard-grid">
                <div class="page-section">
                    <h2>${t('topIntents')}</h2>
                    <div class="chart-card">${topCatHtml || '<p style="color:var(--text-secondary);">No category data.</p>'}</div>
                </div>
                <div class="page-section">
                    <h2>${t('urgencyBreakdown')}</h2>
                    <div class="chart-card">
                        <div class="chart-row">
                            <span class="chart-label">${t('low')}</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color:var(--success);width:0;" data-width="${lowUrgPct}%"></div></div>
                            <span class="chart-value">${lowUrgPct}%</span>
                        </div>
                        <div class="chart-row">
                            <span class="chart-label">${t('medium')}</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color:var(--warning);width:0;" data-width="${midUrgPct}%"></div></div>
                            <span class="chart-value">${midUrgPct}%</span>
                        </div>
                        <div class="chart-row">
                            <span class="chart-label">${t('high')}</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color:var(--danger);width:0;" data-width="${highUrgPct}%"></div></div>
                            <span class="chart-value">${highUrgPct}%</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        setTimeout(() => {
            container.querySelectorAll('.chart-bar').forEach(b => { b.style.width = b.getAttribute('data-width'); });
        }, 100);
    }

    // ═══════════════════════════════════════════════════
    // VIEW: USERS MANAGEMENT
    // ═══════════════════════════════════════════════════
    function renderUsersPage(container) {
        const users = state.users || [];
        const totalUsers   = users.length;
        const adminCount   = users.filter(u => ['super_admin','manager'].includes(u.role)).length;
        const activeCount  = users.filter(u => u.is_active).length;

        function roleLabel(role) {
            return { super_admin: 'Super Admin', manager: 'Manager', agent: 'Agent' }[role] || role;
        }
        function initials(name) {
            return (name || 'U').split(' ').map(p => p[0]).slice(0,2).join('').toUpperCase();
        }

        const rows = users.map(u => {
            const isMe = state.currentUser && u.id === state.currentUser.id;
            return `
            <tr>
                <td>
                    <div class="user-cell">
                        <div class="user-avatar-sm">${initials(u.name)}</div>
                        <div>
                            <div class="user-name">${u.name}${isMe ? ' <span style="font-size:0.72rem;color:var(--primary);">(you)</span>' : ''}</div>
                            <div class="user-email">${u.email}</div>
                        </div>
                    </div>
                </td>
                <td><span class="badge badge-role-${u.role}">${roleLabel(u.role)}</span></td>
                <td><span class="badge ${u.is_active ? 'badge-active' : 'badge-inactive'}">${u.is_active ? 'Active' : 'Inactive'}</span></td>
                <td style="font-size:0.8rem;color:var(--text-secondary);">${u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}</td>
                <td>
                    <div class="user-actions">
                        <button class="btn-icon" title="Change Password" data-action="password" data-id="${u.id}" data-name="${escapeHtml(u.name)}">
                            <i class="fa-solid fa-key"></i>
                        </button>
                        <button class="btn-icon ${u.is_active ? '' : 'success'}" title="${u.is_active ? 'Deactivate' : 'Activate'}" data-action="toggle" data-id="${u.id}" data-active="${u.is_active}" ${isMe ? 'disabled style="opacity:0.4;cursor:not-allowed;"' : ''}>
                            <i class="fa-solid ${u.is_active ? 'fa-ban' : 'fa-check-circle'}"></i>
                        </button>
                        ${isSuperAdmin() && !isMe ? `
                        <button class="btn-icon danger" title="Delete User" data-action="delete" data-id="${u.id}" data-name="${escapeHtml(u.name)}">
                            <i class="fa-solid fa-trash"></i>
                        </button>` : ''}
                    </div>
                </td>
            </tr>`;
        }).join('');

        const emptyRow = users.length === 0
            ? `<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--text-secondary);">${t('noUsers')}</td></tr>`
            : '';

        container.innerHTML = `
            <div class="users-stats">
                <div class="summary-card">
                    <div class="card-icon icon-blue"><i class="fa-solid fa-users"></i></div>
                    <div class="card-info"><h3>${t('totalUsers')}</h3><p>${totalUsers}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-yellow"><i class="fa-solid fa-user-shield"></i></div>
                    <div class="card-info"><h3>${t('admins')}</h3><p>${adminCount}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-green"><i class="fa-solid fa-user-check"></i></div>
                    <div class="card-info"><h3>${t('activeUsers')}</h3><p>${activeCount}</p></div>
                </div>
            </div>

            <div class="users-header">
                <h2><i class="fa-solid fa-user-shield" style="color:var(--primary);margin-right:8px;"></i>${t('titleUsers')}</h2>
                <button class="btn btn-primary" id="addUserBtn"><i class="fa-solid fa-plus"></i> ${t('addUser')}</button>
            </div>

            <div class="users-table-card">
                <table class="users-table">
                    <thead>
                        <tr>
                            <th>${t('name')}</th>
                            <th>${t('role')}</th>
                            <th>${t('activeStatus')}</th>
                            <th>Joined</th>
                            <th>${t('actions')}</th>
                        </tr>
                    </thead>
                    <tbody>${rows || emptyRow}</tbody>
                </table>
            </div>
        `;

        // Add User button
        document.getElementById('addUserBtn').addEventListener('click', () => {
            openAddUserModal();
        });

        // Row action buttons
        container.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const action = e.currentTarget.getAttribute('data-action');
                const userId = parseInt(e.currentTarget.getAttribute('data-id'));
                const userName = e.currentTarget.getAttribute('data-name') || '';

                if (action === 'password') {
                    openPasswordModal(userId, userName);
                } else if (action === 'toggle') {
                    const isActive = e.currentTarget.getAttribute('data-active') === 'true';
                    const newStatus = !isActive;
                    showConfirmModal({
                        title: `${newStatus ? 'Activate' : 'Deactivate'} User`,
                        message: `Are you sure you want to ${newStatus ? 'activate' : 'deactivate'} <b>${userName}</b>?`,
                        icon: `fa-solid ${newStatus ? 'fa-check-circle' : 'fa-ban'}`,
                        confirmLabel: newStatus ? 'Activate' : 'Deactivate',
                        confirmClass: 'btn btn-primary',
                        onConfirm: async () => {
                            try {
                                await apiRequest(`/auth/users/${userId}`, {
                                    method: 'PATCH',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ is_active: newStatus })
                                });
                                showToast(t('userUpdated'), `${userName} is now ${newStatus ? 'active' : 'inactive'}.`, 'success');
                                await reloadUsers();
                            } catch (err) {
                                showToast('Error', err.message, 'error');
                            }
                        }
                    });
                } else if (action === 'delete') {
                    showConfirmModal({
                        title: 'Delete User',
                        message: `${t('confirmDelete')}<br><br><b>${userName}</b>`,
                        icon: 'fa-solid fa-trash',
                        confirmLabel: 'Delete',
                        confirmClass: 'btn btn-primary',
                        onConfirm: async () => {
                            try {
                                await apiRequest(`/auth/users/${userId}`, { method: 'DELETE' });
                                showToast(t('userDeleted'), '', 'success');
                                await reloadUsers();
                            } catch (err) {
                                showToast('Error', err.message, 'error');
                            }
                        }
                    });
                }
            });
        });

        async function reloadUsers() {
            try {
                const data = await apiRequest('/auth/users');
                state.users = data.users || [];
                renderUsersPage(container);
            } catch (err) {
                showToast('Error', `Failed to reload users: ${err.message}`, 'error');
            }
        }

        function openPasswordModal(userId, userName) {
            showModal({
                title: t('changePassword'),
                icon: 'fa-solid fa-key',
                bodyHtml: `
                    <div class="modal-field">
                        <label>${t('name')}: <strong>${escapeHtml(userName)}</strong></label>
                    </div>
                    <div class="modal-field">
                        <label>${t('newPassword')}</label>
                        <div class="pw-row">
                            <input type="text" id="newPasswordInput" placeholder="Enter new password..." autocomplete="new-password">
                            <button type="button" class="pw-gen-btn" id="genPwBtn"><i class="fa-solid fa-wand-magic-sparkles"></i> ${t('generatePassword')}</button>
                        </div>
                        <div class="modal-hint"><i class="fa-solid fa-info-circle"></i> The original password will never be shown. A suggestion has been generated above.</div>
                    </div>
                `,
                footerHtml: `
                    <button class="btn btn-outline" id="cancelPwBtn">${t('cancel')}</button>
                    <button class="btn btn-primary" id="savePwBtn"><i class="fa-solid fa-floppy-disk"></i> ${t('saveChanges')}</button>
                `,
                onMount: async (overlay, closeModal) => {
                    const input = overlay.querySelector('#newPasswordInput');
                    const saveBtn = overlay.querySelector('#savePwBtn');

                    // Auto-generate a suggested password
                    try {
                        const res = await apiRequest('/auth/users/password-suggestion');
                        if (input && res.suggested_password) input.value = res.suggested_password;
                    } catch (_) {
                        // fallback
                        if (input) input.value = generateLocalPassword();
                    }

                    overlay.querySelector('#genPwBtn').addEventListener('click', async () => {
                        try {
                            const res = await apiRequest('/auth/users/password-suggestion');
                            if (res.suggested_password) input.value = res.suggested_password;
                        } catch (_) {
                            if (input) input.value = generateLocalPassword();
                        }
                    });

                    overlay.querySelector('#cancelPwBtn').addEventListener('click', closeModal);

                    saveBtn.addEventListener('click', async () => {
                        const newPw = input.value.trim();
                        if (!newPw || newPw.length < 6) {
                            showToast('Validation', 'Password must be at least 6 characters.', 'warning');
                            return;
                        }
                        setButtonLoading(saveBtn, true);
                        try {
                            await apiRequest(`/auth/users/${userId}/password`, {
                                method: 'PATCH',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ new_password: newPw })
                            });
                            closeModal();
                            showToast(t('passwordChanged'), `Password for ${userName} has been updated.`, 'success');
                        } catch (err) {
                            showToast('Error', err.message, 'error');
                            setButtonLoading(saveBtn, false);
                        }
                    });
                }
            });
        }

        function openAddUserModal() {
            showModal({
                title: t('addUser'),
                icon: 'fa-solid fa-user-plus',
                bodyHtml: `
                    <div class="modal-field">
                        <label>Full Name</label>
                        <input type="text" id="newUserName" placeholder="Enter full name">
                    </div>
                    <div class="modal-field">
                        <label>Email</label>
                        <input type="email" id="newUserEmail" placeholder="Enter email address">
                    </div>
                    <div class="modal-field">
                        <label>Role</label>
                        <select id="newUserRole">
                            <option value="agent">Agent</option>
                            <option value="manager">Manager</option>
                            ${isSuperAdmin() ? '<option value="super_admin">Super Admin</option>' : ''}
                        </select>
                    </div>
                    <div class="modal-field">
                        <label>${t('newPassword')}</label>
                        <div class="pw-row">
                            <input type="text" id="newUserPassword" placeholder="Password" autocomplete="new-password">
                            <button type="button" class="pw-gen-btn" id="genNewUserPw"><i class="fa-solid fa-wand-magic-sparkles"></i> ${t('generatePassword')}</button>
                        </div>
                    </div>
                `,
                footerHtml: `
                    <button class="btn btn-outline" id="cancelAddUser">${t('cancel')}</button>
                    <button class="btn btn-primary" id="saveAddUser"><i class="fa-solid fa-user-plus"></i> Create User</button>
                `,
                onMount: async (overlay, closeModal) => {
                    const pwInput = overlay.querySelector('#newUserPassword');

                    // Auto-gen password
                    try {
                        const res = await apiRequest('/auth/users/password-suggestion');
                        if (pwInput && res.suggested_password) pwInput.value = res.suggested_password;
                    } catch (_) {
                        if (pwInput) pwInput.value = generateLocalPassword();
                    }

                    overlay.querySelector('#genNewUserPw').addEventListener('click', async () => {
                        try {
                            const res = await apiRequest('/auth/users/password-suggestion');
                            if (res.suggested_password) pwInput.value = res.suggested_password;
                        } catch (_) {
                            if (pwInput) pwInput.value = generateLocalPassword();
                        }
                    });

                    overlay.querySelector('#cancelAddUser').addEventListener('click', closeModal);

                    overlay.querySelector('#saveAddUser').addEventListener('click', async (e) => {
                        const btn = e.currentTarget;
                        const name     = overlay.querySelector('#newUserName').value.trim();
                        const email    = overlay.querySelector('#newUserEmail').value.trim();
                        const role     = overlay.querySelector('#newUserRole').value;
                        const password = pwInput.value.trim();

                        if (!name || !email || !password) {
                            showToast('Validation', 'All fields are required.', 'warning');
                            return;
                        }
                        setButtonLoading(btn, true);
                        try {
                            await apiRequest('/auth/users', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ name, email, role, password })
                            });
                            closeModal();
                            showToast(t('userCreated'), `${name} has been added.`, 'success');
                            await reloadUsers();
                        } catch (err) {
                            showToast('Error', err.message, 'error');
                            setButtonLoading(btn, false);
                        }
                    });
                }
            });
        }
    }

    // Local password generator fallback
    function generateLocalPassword(len = 12) {
        const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$';
        return Array.from({length: len}, () => chars[Math.floor(Math.random() * chars.length)]).join('');
    }

});
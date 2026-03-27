document.addEventListener("DOMContentLoaded", () => {
    // --- State ---
    const state = {
        isLoggedIn: false,
        messages: window.messagesData || [],
        currentView: 'dashboard', 
        selectedMessageId: null,
        filters: {
            search: '',
            sentiment: 'All',
            urgency: 'All',
            routingStatus: 'All',
            routingUrgency: 'All',
            routingAssignment: 'All'
        },
        faqs: JSON.parse(localStorage.getItem('faqs')) || [
            { id: 1, question: "How to use the auto reply?", answer: "Click 'Send Auto Reply' in the message details view." },
            { id: 2, question: "How does sentiment analysis work?", answer: "The AI automatically analyzes message text and assigns Positive, Neutral, or Negative labels." }
        ],
        agents: ["John Carter", "Sarah Ali", "Michael Brown", "Noor Hassan"]
    };

    // --- DOM Elements ---
    const loginApp = document.getElementById('loginApp');
    const dashboardApp = document.getElementById('dashboardApp');
    const loginForm = document.getElementById('loginForm');
    const appContent = document.getElementById('appContent');
    const pageTitle = document.getElementById('pageTitle');
    const globalSearch = document.getElementById('globalSearch');
    
    // Sidebar
    const sidebar = document.getElementById('sidebar');
    const toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
    const closeSidebarBtn = document.getElementById('closeSidebarBtn');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    
    // Nav Items
    const navDashboard = document.getElementById('navDashboard');
    const navMessages = document.getElementById('navMessages');
    const navRouting = document.getElementById('navRouting');
    const navFaq = document.getElementById('navFaq');
    const navAnalytics = document.getElementById('navAnalytics');
    
    // Theme
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    const themeIcon = document.getElementById('themeIcon');

    // --- Initialization ---
    initTheme();
    setupEventListeners();
    renderApp();

    function setupEventListeners() {
        // Login Mock
        if(loginForm) {
            loginForm.addEventListener('submit', (e) => {
                e.preventDefault();
                state.isLoggedIn = true;
                navigateTo('dashboard');
            });
        }

        // Global Search
        if(globalSearch) {
            globalSearch.addEventListener('input', (e) => {
                state.filters.search = e.target.value.toLowerCase();
                if(state.currentView === 'messages') renderApp();
            });
        }

        // Sidebar navigation
        if (navDashboard) navDashboard.addEventListener('click', (e) => { e.preventDefault(); navigateTo('dashboard'); closeSidebar(); });
        if (navMessages) navMessages.addEventListener('click', (e) => { e.preventDefault(); navigateTo('messages'); closeSidebar(); });
        if (navRouting) navRouting.addEventListener('click', (e) => { e.preventDefault(); navigateTo('routing'); closeSidebar(); });
        if (navFaq) navFaq.addEventListener('click', (e) => { e.preventDefault(); navigateTo('faq'); closeSidebar(); });
        if (navAnalytics) navAnalytics.addEventListener('click', (e) => { e.preventDefault(); navigateTo('analytics'); closeSidebar(); });

        if(toggleSidebarBtn) toggleSidebarBtn.addEventListener('click', openSidebar);
        if(closeSidebarBtn) closeSidebarBtn.addEventListener('click', closeSidebar);
        if(sidebarOverlay) sidebarOverlay.addEventListener('click', closeSidebar);
        if(themeToggleBtn) themeToggleBtn.addEventListener('click', toggleTheme);
    }

    function openSidebar() {
        sidebar.classList.add('open');
        sidebarOverlay.classList.add('open');
    }
    function closeSidebar() {
        sidebar.classList.remove('open');
        sidebarOverlay.classList.remove('open');
    }

    function initTheme() {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            document.body.classList.add('dark');
            if(themeIcon) themeIcon.className = 'fa-solid fa-sun';
        } else {
            if(themeIcon) themeIcon.className = 'fa-regular fa-moon';
        }
    }

    function toggleTheme() {
        document.body.classList.toggle('dark');
        const isDark = document.body.classList.contains('dark');
        if(themeIcon) themeIcon.className = isDark ? 'fa-solid fa-sun' : 'fa-regular fa-moon';
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
    }

    function navigateTo(view, messageId = null) {
        state.currentView = view;
        state.selectedMessageId = messageId;
        if (view === 'messages' && globalSearch) {
            globalSearch.value = state.filters.search;
        }
        renderApp();
    }

    function renderApp() {
        if (!state.isLoggedIn) {
            if(loginApp) loginApp.style.display = 'flex';
            if(dashboardApp) dashboardApp.style.display = 'none';
            return;
        }

        if(loginApp) loginApp.style.display = 'none';
        if(dashboardApp) dashboardApp.style.display = 'flex';
        appContent.innerHTML = ''; 

        // Reset all active classes
        [navDashboard, navMessages, navRouting, navFaq, navAnalytics].forEach(el => {
            if(el) el.classList.remove('active');
        });

        if (state.currentView === 'dashboard') {
            pageTitle.innerText = "Dashboard Overview";
            if(navDashboard) navDashboard.classList.add('active');
            renderDashboardPage(appContent);
        } else if (state.currentView === 'messages') {
            pageTitle.innerText = "Incoming Messages";
            if(navMessages) navMessages.classList.add('active');
            renderMessagesPage(appContent);
        } else if (state.currentView === 'details') {
            pageTitle.innerText = "Message Details";
            if(navMessages) navMessages.classList.add('active');
            renderMessageDetailsPage(appContent);
        } else if (state.currentView === 'routing') {
            pageTitle.innerText = "Routing & Assignment";
            if(navRouting) navRouting.classList.add('active');
            renderRoutingPage(appContent);
        } else if (state.currentView === 'faq') {
            pageTitle.innerText = "FAQ Management";
            if(navFaq) navFaq.classList.add('active');
            renderFaqPage(appContent);
        } else if (state.currentView === 'analytics') {
            pageTitle.innerText = "Analytics & Reports";
            if(navAnalytics) navAnalytics.classList.add('active');
            renderAnalyticsPage(appContent);
        }
    }

    // --- View 1: Dashboard Page ---
    function renderDashboardPage(container) {
        const total = state.messages.length;
        const negative = state.messages.filter(m => m.sentiment === 'Negative').length;
        const urgent = state.messages.filter(m => m.urgency === 'High').length;
        const resolved = state.messages.filter(m => m.status === 'Responded').length;

        const recentMessages = state.messages.slice(0, 5);

        let recentHtml = '';
        recentMessages.forEach(msg => {
            const badgeSentiment = msg.sentiment.toLowerCase();
            const badgeStatus = msg.status.toLowerCase();
            recentHtml += `
            <div class="message-card" style="margin-bottom: 12px; grid-template-columns: 2fr 3fr; cursor: pointer;" onclick="document.dispatchEvent(new CustomEvent('navToDetails', {detail: '${msg.id}'}))">
                <div class="msg-caller">
                    <h4>${msg.customerName}</h4>
                    <p style="font-size: 0.8rem; color: var(--text-secondary);">${msg.intent}</p>
                </div>
                <div class="msg-preview">
                    ${msg.messagePreview}
                </div>
            </div>`;
        });

        const positive = state.messages.filter(m => m.sentiment === 'Positive').length;
        const neutral = state.messages.filter(m => m.sentiment === 'Neutral').length;
        const posPct = total ? Math.round((positive / total) * 100) : 0;
        const neuPct = total ? Math.round((neutral / total) * 100) : 0;
        const negPct = total ? Math.round((negative / total) * 100) : 0;

        const html = `
            <div class="summary-cards">
                <div class="summary-card">
                    <div class="card-icon icon-blue"><i class="fa-solid fa-envelope"></i></div>
                    <div class="card-info"><h3>Total</h3><p>${total}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-red"><i class="fa-solid fa-heart-crack"></i></div>
                    <div class="card-info"><h3>Negative</h3><p>${negative}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-yellow"><i class="fa-solid fa-bolt"></i></div>
                    <div class="card-info"><h3>Urgent</h3><p>${urgent}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-green"><i class="fa-solid fa-check-circle"></i></div>
                    <div class="card-info"><h3>Resolved</h3><p>${resolved}</p></div>
                </div>
            </div>

            <!-- Quick Navigation Shortcuts -->
            <div class="page-section">
                <h2>Quick Navigation</h2>
                <div class="summary-cards" style="grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));">
                    <div class="summary-card" style="cursor: pointer;" onclick="document.dispatchEvent(new CustomEvent('navToView', {detail: 'messages'}))">
                        <div class="card-icon" style="color: var(--primary);"><i class="fa-solid fa-inbox"></i></div>
                        <div class="card-info"><h3 style="font-size:1rem;color:var(--text-primary);font-weight:600;">Inbox</h3><p style="font-size:0.8rem;color:var(--text-secondary);font-weight:400;">View Messages</p></div>
                    </div>
                    <div class="summary-card" style="cursor: pointer;" onclick="document.dispatchEvent(new CustomEvent('navToView', {detail: 'routing'}))">
                        <div class="card-icon" style="color: var(--primary);"><i class="fa-solid fa-users-gear"></i></div>
                        <div class="card-info"><h3 style="font-size:1rem;color:var(--text-primary);font-weight:600;">Routing</h3><p style="font-size:0.8rem;color:var(--text-secondary);font-weight:400;">Manage Agents</p></div>
                    </div>
                    <div class="summary-card" style="cursor: pointer;" onclick="document.dispatchEvent(new CustomEvent('navToView', {detail: 'analytics'}))">
                        <div class="card-icon" style="color: var(--primary);"><i class="fa-solid fa-chart-pie"></i></div>
                        <div class="card-info"><h3 style="font-size:1rem;color:var(--text-primary);font-weight:600;">Reports</h3><p style="font-size:0.8rem;color:var(--text-secondary);font-weight:400;">View Analytics</p></div>
                    </div>
                    <div class="summary-card" style="cursor: pointer;" onclick="document.dispatchEvent(new CustomEvent('navToView', {detail: 'faq'}))">
                        <div class="card-icon" style="color: var(--primary);"><i class="fa-solid fa-circle-question"></i></div>
                        <div class="card-info"><h3 style="font-size:1rem;color:var(--text-primary);font-weight:600;">FAQ</h3><p style="font-size:0.8rem;color:var(--text-secondary);font-weight:400;">Manage Knowledge</p></div>
                    </div>
                </div>
            </div>

            <div class="dashboard-grid">
                <div class="page-section">
                    <h2>Recent Messages</h2>
                    <div class="messages-list" style="gap: 8px;">
                        ${recentHtml}
                    </div>
                </div>
                <div class="page-section">
                    <h2>Sentiment Overview</h2>
                    <div class="chart-card">
                        <div class="chart-row">
                            <span class="chart-label">Positive</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color: var(--success); width: 0;" data-width="${posPct}%"></div></div>
                            <span class="chart-value">${posPct}%</span>
                        </div>
                        <div class="chart-row">
                            <span class="chart-label">Neutral</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color: var(--warning); width: 0;" data-width="${neuPct}%"></div></div>
                            <span class="chart-value">${neuPct}%</span>
                        </div>
                        <div class="chart-row">
                            <span class="chart-label">Negative</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color: var(--danger); width: 0;" data-width="${negPct}%"></div></div>
                            <span class="chart-value">${negPct}%</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        container.innerHTML = html;

        document.addEventListener('navToDetails', (e) => { navigateTo('details', e.detail); }, { once: true });
        document.addEventListener('navToView', (e) => { navigateTo(e.detail); }, { once: true });

        setTimeout(() => {
            container.querySelectorAll('.chart-bar').forEach(b => { b.style.width = b.getAttribute('data-width'); });
        }, 50);
    }

    // --- View 2: Routing Page ---
    function renderRoutingPage(container) {
        const totalAssigned = state.messages.filter(m => m.assignedAgent !== 'Unassigned').length;
        const unassigned = state.messages.filter(m => m.assignedAgent === 'Unassigned').length;
        const escalated = state.messages.filter(m => m.status === 'Escalated').length;

        // Routing filters logic
        const searchVal = state.filters.search;
        const statFilt = state.filters.routingStatus;
        const urgFilt = state.filters.routingUrgency;
        const assFilt = state.filters.routingAssignment;

        let filtered = state.messages.filter(m => {
            const matchSearch = m.customerName.toLowerCase().includes(searchVal) || m.intent.toLowerCase().includes(searchVal);
            const matchStat = statFilt === 'All' || m.status === statFilt;
            const matchUrg = urgFilt === 'All' || m.urgency === urgFilt;
            
            let matchAss = true;
            if(assFilt === 'Assigned') matchAss = m.assignedAgent !== 'Unassigned';
            if(assFilt === 'Unassigned') matchAss = m.assignedAgent === 'Unassigned';

            return matchSearch && matchStat && matchUrg && matchAss;
        });

        let tableRows = filtered.map(msg => {
            const badgeSentiment = msg.sentiment.toLowerCase();
            const badgeUrgency = msg.urgency.toLowerCase();
            const badgeStatus = msg.status.toLowerCase();
            
            // Generate options based on agents state
            let options = `<option value="Unassigned" ${msg.assignedAgent === 'Unassigned' ? 'selected' : ''}>Unassigned</option>`;
            state.agents.forEach(agent => {
                options += `<option value="${agent}" ${msg.assignedAgent === agent ? 'selected' : ''}>${agent}</option>`;
            });

            return `
                <tr>
                    <td style="font-weight: 500;">${msg.customerName}</td>
                    <td>${msg.intent}</td>
                    <td><span class="badge badge-${badgeSentiment}">${msg.sentiment}</span></td>
                    <td><span class="badge badge-${badgeUrgency}">${msg.urgency}</span></td>
                    <td><span class="badge badge-${badgeStatus}">${msg.status}</span></td>
                    <td>
                        <select class="dropdown-agent" data-id="${msg.id}">
                            ${options}
                        </select>
                    </td>
                    <td>
                        <button class="btn btn-outline escalate-btn" data-id="${msg.id}" style="padding: 6px 12px; font-size: 0.8rem; color: var(--danger); border-color: var(--danger);">Escalate</button>
                    </td>
                </tr>
            `;
        }).join('');

        if(filtered.length === 0) {
            tableRows = '<tr><td colspan="7" style="text-align:center; padding: 40px;">No messages match your routing filters.</td></tr>';
        }

        const html = `
            <div class="summary-cards">
                <div class="summary-card">
                    <div class="card-icon icon-blue"><i class="fa-solid fa-user-check"></i></div>
                    <div class="card-info"><h3>Assigned</h3><p>${totalAssigned}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-yellow"><i class="fa-solid fa-user-clock"></i></div>
                    <div class="card-info"><h3>Unassigned</h3><p>${unassigned}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-red"><i class="fa-solid fa-triangle-exclamation"></i></div>
                    <div class="card-info"><h3>Escalated</h3><p>${escalated}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-green"><i class="fa-solid fa-users"></i></div>
                    <div class="card-info"><h3>Active Agents</h3><p>${state.agents.length}</p></div>
                </div>
            </div>

            <div class="filter-bar">
                <input type="text" id="routeSearch" class="search-input" placeholder="Search customer, intent..." value="${state.filters.search}">
                
                <select id="routeAssignment" class="filter-select">
                    <option value="All" ${assFilt === 'All' ? 'selected' : ''}>All Assignments</option>
                    <option value="Assigned" ${assFilt === 'Assigned' ? 'selected' : ''}>Assigned</option>
                    <option value="Unassigned" ${assFilt === 'Unassigned' ? 'selected' : ''}>Unassigned</option>
                </select>

                <select id="routeStatus" class="filter-select">
                    <option value="All" ${statFilt === 'All' ? 'selected' : ''}>All Statuses</option>
                    <option value="Pending" ${statFilt === 'Pending' ? 'selected' : ''}>Pending</option>
                    <option value="Responded" ${statFilt === 'Responded' ? 'selected' : ''}>Responded</option>
                    <option value="Escalated" ${statFilt === 'Escalated' ? 'selected' : ''}>Escalated</option>
                </select>

                <select id="routeUrgency" class="filter-select">
                    <option value="All" ${urgFilt === 'All' ? 'selected' : ''}>All Urgencies</option>
                    <option value="High" ${urgFilt === 'High' ? 'selected' : ''}>High</option>
                    <option value="Medium" ${urgFilt === 'Medium' ? 'selected' : ''}>Medium</option>
                    <option value="Low" ${urgFilt === 'Low' ? 'selected' : ''}>Low</option>
                </select>

                <button id="clearRouteFilters" class="btn btn-outline">Clear</button>
            </div>

            <div class="routing-table-card">
                <table class="routing-table">
                    <thead>
                        <tr>
                            <th>Customer</th>
                            <th>Intent</th>
                            <th>Sentiment</th>
                            <th>Urgency</th>
                            <th>Status</th>
                            <th>Assigned Agent</th>
                            <th>Quick Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${tableRows}
                    </tbody>
                </table>
            </div>
        `;
        container.innerHTML = html;

        // Filter Logic
        document.getElementById('routeSearch').addEventListener('input', (e) => { state.filters.search = e.target.value.toLowerCase(); renderRoutingPage(container); });
        document.getElementById('routeAssignment').addEventListener('change', (e) => { state.filters.routingAssignment = e.target.value; renderRoutingPage(container); });
        document.getElementById('routeStatus').addEventListener('change', (e) => { state.filters.routingStatus = e.target.value; renderRoutingPage(container); });
        document.getElementById('routeUrgency').addEventListener('change', (e) => { state.filters.routingUrgency = e.target.value; renderRoutingPage(container); });
        document.getElementById('clearRouteFilters').addEventListener('click', () => {
            state.filters.search = ''; state.filters.routingAssignment = 'All'; state.filters.routingStatus = 'All'; state.filters.routingUrgency = 'All';
            if(globalSearch) globalSearch.value = '';
            renderRoutingPage(container);
        });

        // Assignment logic
        container.querySelectorAll('.dropdown-agent').forEach(select => {
            select.addEventListener('change', (e) => {
                const id = e.target.getAttribute('data-id');
                const newAgent = e.target.value;
                const msg = state.messages.find(m => m.id === id);
                if(msg) {
                    msg.assignedAgent = newAgent;
                    renderRoutingPage(container); // Re-render to update summary counts dynamically
                }
            });
        });

        container.querySelectorAll('.escalate-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.getAttribute('data-id');
                const msg = state.messages.find(m => m.id === id);
                if(msg) {
                    msg.status = 'Escalated';
                    renderRoutingPage(container);
                }
            });
        });
    }

    // --- View 3: Messages Page ---
    function renderMessagesPage(container) {
        const total = state.messages.length;
        const negative = state.messages.filter(m => m.sentiment === 'Negative').length;
        const urgent = state.messages.filter(m => m.urgency === 'High').length;
        const pending = state.messages.filter(m => m.status === 'Pending').length;

        const html = `
            <div class="summary-cards">
                <div class="summary-card"><div class="card-icon icon-blue"><i class="fa-solid fa-envelope"></i></div><div class="card-info"><h3>Total Messages</h3><p>${total}</p></div></div>
                <div class="summary-card"><div class="card-icon icon-red"><i class="fa-solid fa-heart-crack"></i></div><div class="card-info"><h3>Negative</h3><p>${negative}</p></div></div>
                <div class="summary-card"><div class="card-icon icon-yellow"><i class="fa-solid fa-bolt"></i></div><div class="card-info"><h3>Urgent Cases</h3><p>${urgent}</p></div></div>
                <div class="summary-card"><div class="card-icon icon-green"><i class="fa-regular fa-clock"></i></div><div class="card-info"><h3>Pending Cases</h3><p>${pending}</p></div></div>
            </div>

            <div class="filter-bar">
                <input type="text" id="localSearch" class="search-input" placeholder="Search customer, intent..." value="${state.filters.search}">
                <select id="sentimentFilter" class="filter-select">
                    <option value="All" ${state.filters.sentiment === 'All' ? 'selected' : ''}>All Sentiments</option>
                    <option value="Positive" ${state.filters.sentiment === 'Positive' ? 'selected' : ''}>Positive</option>
                    <option value="Neutral" ${state.filters.sentiment === 'Neutral' ? 'selected' : ''}>Neutral</option>
                    <option value="Negative" ${state.filters.sentiment === 'Negative' ? 'selected' : ''}>Negative</option>
                </select>
                <select id="urgencyFilter" class="filter-select">
                    <option value="All" ${state.filters.urgency === 'All' ? 'selected' : ''}>All Urgencies</option>
                    <option value="Low" ${state.filters.urgency === 'Low' ? 'selected' : ''}>Low</option>
                    <option value="Medium" ${state.filters.urgency === 'Medium' ? 'selected' : ''}>Medium</option>
                    <option value="High" ${state.filters.urgency === 'High' ? 'selected' : ''}>High</option>
                </select>
                <button id="clearFiltersBtn" class="btn btn-outline"><i class="fa-solid fa-rotate-left"></i> Clear</button>
            </div>
            <div id="messagesList" class="messages-list"></div>
        `;
        container.insertAdjacentHTML('beforeend', html);

        document.getElementById('localSearch').addEventListener('input', (e) => { state.filters.search = e.target.value.toLowerCase(); updateListDisplay(); });
        document.getElementById('sentimentFilter').addEventListener('change', (e) => { state.filters.sentiment = e.target.value; updateListDisplay(); });
        document.getElementById('urgencyFilter').addEventListener('change', (e) => { state.filters.urgency = e.target.value; updateListDisplay(); });
        document.getElementById('clearFiltersBtn').addEventListener('click', () => {
            state.filters.search = ''; state.filters.sentiment = 'All'; state.filters.urgency = 'All';
            document.getElementById('localSearch').value = ''; document.getElementById('sentimentFilter').value = 'All'; document.getElementById('urgencyFilter').value = 'All';
            if(globalSearch) globalSearch.value = '';
            updateListDisplay();
        });

        updateListDisplay();
    }

    function updateListDisplay() {
        const listContainer = document.getElementById('messagesList');
        if(!listContainer) return;

        const filtered = state.messages.filter(msg => {
            const matchSearch = msg.customerName.toLowerCase().includes(state.filters.search) || msg.intent.toLowerCase().includes(state.filters.search) || msg.messagePreview.toLowerCase().includes(state.filters.search);
            const matchSentiment = state.filters.sentiment === 'All' || msg.sentiment === state.filters.sentiment;
            const matchUrgency = state.filters.urgency === 'All' || msg.urgency === state.filters.urgency;
            return matchSearch && matchSentiment && matchUrgency;
        });

        listContainer.innerHTML = '';

        if (filtered.length === 0) {
            listContainer.innerHTML = `<div class="empty-state"><i class="fa-solid fa-inbox"></i><h3>No messages found</h3><p>Try adjusting your filters or search terms.</p></div>`;
            return;
        }

        filtered.forEach(msg => {
            const card = document.createElement('div');
            card.className = 'message-card';
            const badgeSentiment = msg.sentiment.toLowerCase(); 
            const badgeUrgency = msg.urgency.toLowerCase();
            const badgeStatus = msg.status.toLowerCase();

            card.innerHTML = `
                <div class="msg-caller"><h4>${msg.customerName}</h4><p>${msg.email}</p></div>
                <div class="msg-preview">${msg.messagePreview}</div>
                <div class="msg-meta"><span class="badge badge-${badgeSentiment}">${msg.sentiment}</span><span style="font-size:0.8rem;">${msg.intent}</span></div>
                <div class="msg-meta"><span class="badge badge-${badgeUrgency}">${msg.urgency}</span><span style="font-size:0.8rem; color: var(--primary);"><i class="fa-solid fa-user"></i> ${msg.assignedAgent}</span></div>
                <div><span class="badge badge-${badgeStatus}">${msg.status}</span></div>
            `;

            card.addEventListener('click', () => { navigateTo('details', msg.id); });
            listContainer.appendChild(card);
        });
    }

    // --- View 4: Message Details Page ---
    function renderMessageDetailsPage(container) {
        const msg = state.messages.find(m => m.id === state.selectedMessageId);
        if (!msg) { navigateTo('messages'); return; }

        let chatHtml = '';
        msg.conversationHistory.forEach(c => {
            const isAgent = c.sender.includes("Agent") || c.sender.includes("System") || c.sender === msg.assignedAgent;
            chatHtml += `<div class="chat-bubble ${isAgent ? 'agent' : 'customer'}"><div class="chat-header">${c.sender} • ${c.time}</div><div class="chat-text">${c.text}</div></div>`;
        });

        const fullTime = new Date(msg.timestamp).toLocaleString();
        
        const html = `
            <div class="details-container">
                <button id="backToListBtn" class="back-btn"><i class="fa-solid fa-arrow-left"></i> Back to list</button>
                <div class="details-header">
                    <div class="details-user"><h2>${msg.customerName}</h2><p>${msg.email} • ${fullTime}</p></div>
                    <div style="text-align: right;">
                        <span class="badge badge-${msg.status.toLowerCase()}" style="margin-bottom: 8px; display: inline-block;">${msg.status}</span><br>
                        <span style="font-size: 0.85rem; color: var(--text-secondary);"><i class="fa-solid fa-user"></i> Assigned to: <b>${msg.assignedAgent}</b></span>
                    </div>
                </div>
                <div class="full-message-card">"${msg.fullMessage}"</div>
                <div class="ai-analysis">
                    <h3><i class="fa-solid fa-wand-magic-sparkles" style="color:var(--primary)"></i> AI Analysis</h3>
                    <div class="analysis-grid">
                        <div class="analysis-item"><span>Sentiment</span><div class="badge badge-${msg.sentiment.toLowerCase()}">${msg.sentiment}</div></div>
                        <div class="analysis-item"><span>Intent</span><div style="font-weight: 600;">${msg.intent}</div></div>
                        <div class="analysis-item"><span>Urgency</span><div class="badge badge-${msg.urgency.toLowerCase()}">${msg.urgency}</div></div>
                        <div class="analysis-item">
                            <span>Confidence</span><div style="font-weight: 600; font-size: 1.1rem; color: var(--success);">${msg.confidence}%</div>
                            <div class="confidence-bar-container"><div class="confidence-bar" style="width: 0%;" data-target="${msg.confidence}"></div></div>
                        </div>
                    </div>
                </div>
                <div class="suggested-reply">
                    <div class="suggested-reply-header"><i class="fa-solid fa-robot"></i> Suggested AI Response</div>
                    <div class="suggested-reply-text">${msg.suggestedReply}</div>
                    <div class="action-buttons">
                        <button class="btn btn-primary" onclick="alert('Auto reply sent!')"><i class="fa-solid fa-paper-plane"></i> Send Auto Reply</button>
                        <button class="btn btn-outline" onclick="alert('Action recorded.')"><i class="fa-solid fa-check"></i> Mark Resolved</button>
                    </div>
                </div>
                <div class="chat-history"><h3>Conversation History</h3><div style="display: flex; flex-direction: column;">${chatHtml}</div></div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', html);

        setTimeout(() => {
            const bar = container.querySelector('.confidence-bar');
            if(bar) bar.style.width = bar.getAttribute('data-target') + '%';
        }, 100);

        document.getElementById('backToListBtn').addEventListener('click', () => { navigateTo('messages'); });
    }

    // --- View 5: FAQ Management ---
    function renderFaqPage(container) {
        let faqListHtml = state.faqs.map(faq => `
            <div class="faq-item" id="faq-item-${faq.id}">
                <div class="faq-content" style="flex: 1;">
                    <h4>${faq.question}</h4>
                    <p>${faq.answer}</p>
                </div>
                <div class="faq-actions" style="display: flex; gap: 8px;">
                    <button class="btn btn-outline edit-faq-btn" data-id="${faq.id}" style="padding: 8px 12px; border-radius: 8px;">
                        <i class="fa-solid fa-pen"></i>
                    </button>
                    <button class="btn btn-outline delete-faq-btn" data-id="${faq.id}" style="color: var(--danger); border-color: var(--danger); padding: 8px 12px; border-radius: 8px;">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </div>
            
            <form class="faq-form edit-faq-form" id="edit-form-${faq.id}" data-id="${faq.id}" style="display: none; margin-top: -10px; margin-bottom: 20px; border-top-left-radius: 0; border-top-right-radius: 0; border-top: none;">
                <input type="text" class="edit-q" value="${faq.question}" required>
                <textarea class="edit-a" required>${faq.answer}</textarea>
                <div style="display: flex; gap: 8px;">
                    <button type="submit" class="btn btn-primary">Save Changes</button>
                    <button type="button" class="btn btn-outline cancel-edit-btn" data-id="${faq.id}">Cancel</button>
                </div>
            </form>
        `).join('');

        if (state.faqs.length === 0) {
            faqListHtml = '<div class="empty-state"><i class="fa-solid fa-circle-question" style="font-size:3rem;color:var(--text-secondary);margin-bottom:16px;display:block;"></i><h3>No FAQs added yet</h3><p>Use the form above to add a new FAQ.</p></div>';
        }

        const html = `
            <div class="page-section" style="max-width: 800px; margin: 0 auto;">
                <h2>Add New FAQ</h2>
                <form class="faq-form" id="faqForm">
                    <input type="text" id="faqQuestion" placeholder="Enter Question" required>
                    <textarea id="faqAnswer" placeholder="Enter Answer" required></textarea>
                    <button type="submit" class="btn btn-primary" style="align-self: flex-start;">
                        <i class="fa-solid fa-plus"></i> Add FAQ
                    </button>
                </form>

                <h2>Existing FAQs</h2>
                <div class="faq-list">
                    ${faqListHtml}
                </div>
            </div>
        `;
        container.innerHTML = html;

        // Add 
        document.getElementById('faqForm').addEventListener('submit', (e) => {
            e.preventDefault();
            const q = document.getElementById('faqQuestion').value;
            const a = document.getElementById('faqAnswer').value;
            state.faqs.push({ id: Date.now(), question: q, answer: a });
            localStorage.setItem('faqs', JSON.stringify(state.faqs));
            renderFaqPage(container);
        });

        // Delete
        container.querySelectorAll('.delete-faq-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idToRemove = parseInt(e.currentTarget.getAttribute('data-id'));
                state.faqs = state.faqs.filter(f => f.id !== idToRemove);
                localStorage.setItem('faqs', JSON.stringify(state.faqs));
                renderFaqPage(container);
            });
        });

        // Toggle Edit Form
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
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                const id = parseInt(e.currentTarget.getAttribute('data-id'));
                const newQ = e.currentTarget.querySelector('.edit-q').value;
                const newA = e.currentTarget.querySelector('.edit-a').value;
                const faqIndex = state.faqs.findIndex(f => f.id === id);
                if(faqIndex > -1){
                    state.faqs[faqIndex].question = newQ;
                    state.faqs[faqIndex].answer = newA;
                    localStorage.setItem('faqs', JSON.stringify(state.faqs));
                    renderFaqPage(container);
                }
            });
        });
    }

    // --- View 6: Analytics Page ---
    function renderAnalyticsPage(container) {
        const total = state.messages.length;
        if (total === 0) {
            container.innerHTML = '<div class="empty-state"><h3>No Data</h3></div>';
            return;
        }

        const intentCounts = {};
        state.messages.forEach(m => { intentCounts[m.intent] = (intentCounts[m.intent] || 0) + 1; });
        const topIntentsHtml = Object.keys(intentCounts).map(intent => {
            const pct = Math.round((intentCounts[intent] / total) * 100);
            return `
                <div class="chart-row">
                    <span class="chart-label" style="width: 120px;">${intent}</span>
                    <div class="chart-bar-container"><div class="chart-bar" style="background-color: var(--secondary); width: 0;" data-width="${pct}%"></div></div>
                    <span class="chart-value">${pct}%</span>
                </div>
            `;
        }).join('');

        const lowUrg = state.messages.filter(m => m.urgency === 'Low').length;
        const medUrg = state.messages.filter(m => m.urgency === 'Medium').length;
        const highUrg = state.messages.filter(m => m.urgency === 'High').length;

        // Abstract mock of visual volumes per day
        const mockDays = ["Mon", "Tue", "Wed", "Thu", "Fri"];
        const maxVol = 20; 
        const dailyVolumes = [12, 19, 8, 15, total]; // Using total as today's
        
        const timeBarsHtml = mockDays.map((day, idx) => {
            const val = dailyVolumes[idx];
            const heightPct = (val / maxVol) * 100;
            return `
                <div style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
                    <span style="font-size: 0.8rem; color: var(--text-secondary);">${val}</span>
                    <div style="height: 120px; width: 40px; background-color: var(--bg-color); border-radius: 6px; display: flex; align-items: flex-end; overflow: hidden;">
                        <div class="chart-bar-vertical" style="width: 100%; height: 0; background-color: var(--primary); transition: height 1s ease;" data-height="${heightPct}%"></div>
                    </div>
                    <span style="font-size: 0.85rem; font-weight: 500;">${day}</span>
                </div>
            `;
        }).join('');

        const html = `
            <div class="dashboard-grid" style="margin-bottom: 24px;">
                <div class="page-section">
                    <h2>Smart Insights</h2>
                    <div class="insight-card">
                        <i class="fa-solid fa-lightbulb insight-icon"></i>
                        <div class="insight-content">
                            <h4>High Negative Sentiment Detected</h4>
                            <p>37% of recent messages exhibit negative sentiment. Consider expediting routing for tickets mentioning "refund" or "login issues".</p>
                        </div>
                    </div>
                    <div class="insight-card">
                        <i class="fa-solid fa-arrow-trend-down insight-icon" style="color: var(--success);"></i>
                        <div class="insight-content">
                            <h4>Resolution Time Improved</h4>
                            <p>Auto-replies have successfully intercepted 15% of basic inquiries today, decreasing average manual workload.</p>
                        </div>
                    </div>
                </div>

                <div class="page-section">
                    <h2>Messages Over Time</h2>
                    <div class="chart-card" style="display: flex; justify-content: space-around; align-items: flex-end; padding-top: 40px; padding-bottom: 20px;">
                        ${timeBarsHtml}
                    </div>
                </div>
            </div>

            <div class="dashboard-grid">
                <div class="page-section">
                    <h2>Top Intents</h2>
                    <div class="chart-card">
                        ${topIntentsHtml}
                    </div>
                </div>
                <div class="page-section">
                    <h2>Urgency Breakdown</h2>
                    <div class="chart-card">
                        <div class="chart-row">
                            <span class="chart-label">Low</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color: var(--success); width: 0;" data-width="${Math.round((lowUrg/total)*100)}%"></div></div>
                            <span class="chart-value">${Math.round((lowUrg/total)*100)}%</span>
                        </div>
                        <div class="chart-row">
                            <span class="chart-label">Medium</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color: var(--warning); width: 0;" data-width="${Math.round((medUrg/total)*100)}%"></div></div>
                            <span class="chart-value">${Math.round((medUrg/total)*100)}%</span>
                        </div>
                        <div class="chart-row">
                            <span class="chart-label">High</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color: var(--danger); width: 0;" data-width="${Math.round((highUrg/total)*100)}%"></div></div>
                            <span class="chart-value">${Math.round((highUrg/total)*100)}%</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        container.innerHTML = html;

        setTimeout(() => {
            container.querySelectorAll('.chart-bar').forEach(b => { b.style.width = b.getAttribute('data-width'); });
            container.querySelectorAll('.chart-bar-vertical').forEach(b => { b.style.height = b.getAttribute('data-height'); });
        }, 100);
    }

});

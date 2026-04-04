document.addEventListener("DOMContentLoaded", () => {
    // --- State ---
    const state = {
        isLoggedIn: false,
        messages: window.messagesData || [],
        currentView: 'dashboard',
        selectedMessageId: null,
        currentLanguage: 'en',
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

    // --- Translations ---
    const T = {
        en: {
            // Login
            loginTitle: "Pal CustomerAI",
            loginSubtitle: "Sign in to access the customer support dashboard",
            emailLabel: "Email",
            emailPlaceholder: "Enter your email",
            passwordLabel: "Password",
            passwordPlaceholder: "Enter your password",
            rememberMe: "Remember me",
            signIn: "Sign In",
            loginFooter: "© 2026 Pal CustomerAI. All rights reserved.",
            // Nav
            navDashboard: "Dashboard",
            navMessages: "Messages",
            navRouting: "Routing",
            navFaq: "FAQ",
            navAnalytics: "Analytics",
            // Page titles
            titleDashboard: "Dashboard Overview",
            titleMessages: "Incoming Messages",
            titleDetails: "Message Details",
            titleRouting: "Routing & Assignment",
            titleFaq: "FAQ Management",
            titleAnalytics: "Analytics & Reports",
            // Dashboard
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
            // Messages page
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
            // Routing
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
            // Details
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
            // FAQ
            addNewFaq: "Add New FAQ",
            enterQuestion: "Enter Question",
            enterAnswer: "Enter Answer",
            addFaq: "Add FAQ",
            existingFaqs: "Existing FAQs",
            saveChanges: "Save Changes",
            cancel: "Cancel",
            noFaqs: "No FAQs added yet",
            noFaqsDesc: "Use the form above to add a new FAQ.",
            // Analytics
            smartInsights: "Smart Insights",
            insightTitle1: "High Negative Sentiment Detected",
            insightDesc1: "37% of recent messages exhibit negative sentiment. Consider expediting routing for tickets mentioning \"refund\" or \"login issues\".",
            insightTitle2: "Resolution Time Improved",
            insightDesc2: "Auto-replies have successfully intercepted 15% of basic inquiries today, decreasing average manual workload.",
            messagesOverTime: "Messages Over Time",
            topIntents: "Top Intents",
            urgencyBreakdown: "Urgency Breakdown",
            noData: "No Data",
            // Search
            searchGlobal: "Search...",
            // Lang button
            langBtn: "AR"
        },
        ar: {
            // Login
            loginTitle: "بال كستمر AI",
            loginSubtitle: "سجّل دخولك للوصول إلى لوحة دعم العملاء",
            emailLabel: "البريد الإلكتروني",
            emailPlaceholder: "أدخل بريدك الإلكتروني",
            passwordLabel: "كلمة المرور",
            passwordPlaceholder: "أدخل كلمة المرور",
            rememberMe: "تذكرني",
            signIn: "تسجيل الدخول",
            loginFooter: "© 2026 بال كستمر AI. جميع الحقوق محفوظة.",
            // Nav
            navDashboard: "لوحة التحكم",
            navMessages: "الرسائل",
            navRouting: "التوجيه",
            navFaq: "الأسئلة الشائعة",
            navAnalytics: "التحليلات",
            // Page titles
            titleDashboard: "نظرة عامة",
            titleMessages: "الرسائل الواردة",
            titleDetails: "تفاصيل الرسالة",
            titleRouting: "التوجيه والتعيين",
            titleFaq: "إدارة الأسئلة الشائعة",
            titleAnalytics: "التقارير والتحليلات",
            // Dashboard
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
            // Messages page
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
            // Routing
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
            // Details
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
            // FAQ
            addNewFaq: "إضافة سؤال جديد",
            enterQuestion: "أدخل السؤال",
            enterAnswer: "أدخل الإجابة",
            addFaq: "إضافة",
            existingFaqs: "الأسئلة الحالية",
            saveChanges: "حفظ التغييرات",
            cancel: "إلغاء",
            noFaqs: "لا توجد أسئلة بعد",
            noFaqsDesc: "استخدم النموذج أعلاه لإضافة سؤال جديد.",
            // Analytics
            smartInsights: "رؤى ذكية",
            insightTitle1: "نسبة عالية من المشاعر السلبية",
            insightDesc1: "37% من الرسائل الأخيرة تحمل مشاعر سلبية. يُنصح بتسريع توجيه التذاكر المتعلقة بـ \"الاسترداد\" أو \"مشاكل تسجيل الدخول\".",
            insightTitle2: "تحسّن في وقت الحل",
            insightDesc2: "نجحت الردود التلقائية في معالجة 15% من الاستفسارات الأساسية اليوم، مما قلل من العبء اليدوي.",
            messagesOverTime: "الرسائل عبر الوقت",
            topIntents: "أبرز النوايا",
            urgencyBreakdown: "توزيع الأولويات",
            noData: "لا توجد بيانات",
            // Search
            searchGlobal: "بحث...",
            // Lang button
            langBtn: "EN"
        }
    };

    function t(key) {
        return T[state.currentLanguage][key] || key;
    }

    // --- DOM Elements ---
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
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    const themeIcon      = document.getElementById('themeIcon');

    // --- Initialization ---
    initTheme();
    injectLangSwitch();
    setupEventListeners();
    applyLanguage(state.currentLanguage);
    renderApp();

    // --- Inject language switch into header nav-right ---
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

        // Insert before theme toggle
        const themeBtn = navRight.querySelector('.theme-toggle');
        if (themeBtn) {
            navRight.insertBefore(langSwitch, themeBtn);
        } else {
            navRight.appendChild(langSwitch);
        }

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

    // --- Apply language to static elements ---
    function applyLanguage(lang) {
        const isAr = lang === 'ar';
        document.documentElement.lang = lang;
        document.documentElement.dir = isAr ? 'rtl' : 'ltr';
        document.body.classList.toggle('rtl-mode', isAr);

        // Login page
        const systemName    = document.getElementById('systemName');
        const loginSubtitle = document.getElementById('loginSubtitle');
        const emailLabel    = document.getElementById('emailLabel');
        const emailInput    = document.getElementById('emailInput');
        const passwordLabel = document.getElementById('passwordLabel');
        const passwordInput = document.getElementById('passwordInput');
        const rememberSpan  = document.querySelector('#rememberLabel span');
        const signInBtn     = document.getElementById('signInBtn');
        const footerText    = document.getElementById('footerText');
        const langToggle    = document.getElementById('langToggleBtn');

        if (systemName)    systemName.textContent    = t('loginTitle');
        if (loginSubtitle) loginSubtitle.textContent = t('loginSubtitle');
        if (emailLabel)    emailLabel.textContent     = t('emailLabel');
        if (emailInput)    emailInput.placeholder     = t('emailPlaceholder');
        if (passwordLabel) passwordLabel.textContent  = t('passwordLabel');
        if (passwordInput) passwordInput.placeholder  = t('passwordPlaceholder');
        if (rememberSpan)  rememberSpan.textContent   = t('rememberMe');
        if (signInBtn)     signInBtn.textContent       = t('signIn');
        if (footerText)    footerText.textContent      = t('loginFooter');
        if (langToggle)    langToggle.textContent      = isAr ? 'English' : 'العربية';

        // Sidebar nav labels
        const navLabels = {
            navDashboard: 'navDashboard',
            navMessages:  'navMessages',
            navRouting:   'navRouting',
            navFaq:       'navFaq',
            navAnalytics: 'navAnalytics'
        };
        Object.entries(navLabels).forEach(([id, key]) => {
            const el = document.getElementById(id);
            if (el) {
                const span = el.querySelector('span');
                if (span) span.textContent = t(key);
            }
        });

        // Brand subtitle in sidebar
        const brandSubtitle = document.querySelector('.brand-subtitle');
        if (brandSubtitle) {
            brandSubtitle.textContent = isAr
                ? 'دعم العملاء بالذكاء الاصطناعي'
                : 'AI-powered Arabic Customer Support';
        }

        // Search placeholder
        if (globalSearch) globalSearch.placeholder = t('searchGlobal');

        // Update page title if dashboard is visible
        if (state.isLoggedIn) updatePageTitle();
    }

    function updatePageTitle() {
        const titleMap = {
            dashboard: 'titleDashboard',
            messages:  'titleMessages',
            details:   'titleDetails',
            routing:   'titleRouting',
            faq:       'titleFaq',
            analytics: 'titleAnalytics'
        };
        if (pageTitle && titleMap[state.currentView]) {
            pageTitle.innerText = t(titleMap[state.currentView]);
        }
    }

    // --- Event Listeners ---
    function setupEventListeners() {
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => {
                e.preventDefault();
                state.isLoggedIn = true;
                navigateTo('dashboard');
            });
        }

        if (globalSearch) {
            globalSearch.addEventListener('input', (e) => {
                state.filters.search = e.target.value.toLowerCase();
                if (state.currentView === 'messages') renderApp();
            });
        }

        if (navDashboard) navDashboard.addEventListener('click', (e) => { e.preventDefault(); navigateTo('dashboard'); closeSidebar(); });
        if (navMessages)  navMessages.addEventListener('click',  (e) => { e.preventDefault(); navigateTo('messages');  closeSidebar(); });
        if (navRouting)   navRouting.addEventListener('click',   (e) => { e.preventDefault(); navigateTo('routing');   closeSidebar(); });
        if (navFaq)       navFaq.addEventListener('click',       (e) => { e.preventDefault(); navigateTo('faq');       closeSidebar(); });
        if (navAnalytics) navAnalytics.addEventListener('click', (e) => { e.preventDefault(); navigateTo('analytics'); closeSidebar(); });

        if (toggleSidebarBtn) toggleSidebarBtn.addEventListener('click', openSidebar);
        if (closeSidebarBtn)  closeSidebarBtn.addEventListener('click',  closeSidebar);
        if (sidebarOverlay)   sidebarOverlay.addEventListener('click',   closeSidebar);
        if (themeToggleBtn)   themeToggleBtn.addEventListener('click',   toggleTheme);

        // Login page lang toggle (already exists in HTML)
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

        // Close dropdown when clicking outside
        document.addEventListener('click', () => {
            if (profileDropdown) profileDropdown.classList.remove('open');
        });

        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                state.isLoggedIn = false;
                profileDropdown.classList.remove('open');
                renderApp();
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

    function navigateTo(view, messageId = null) {
        state.currentView       = view;
        state.selectedMessageId = messageId;
        if (view === 'messages' && globalSearch) {
            globalSearch.value = state.filters.search;
        }
        renderApp();
    }

    // --- Render App ---
    function renderApp() {
        if (!state.isLoggedIn) {
            if (loginApp)     loginApp.style.display     = 'flex';
            if (dashboardApp) dashboardApp.style.display = 'none';
            return;
        }

        if (loginApp)     loginApp.style.display     = 'none';
        if (dashboardApp) dashboardApp.style.display = 'flex';
        appContent.innerHTML = '';

        [navDashboard, navMessages, navRouting, navFaq, navAnalytics].forEach(el => {
            if (el) el.classList.remove('active');
        });

        updatePageTitle();

        if (state.currentView === 'dashboard') {
            if (navDashboard) navDashboard.classList.add('active');
            renderDashboardPage(appContent);
        } else if (state.currentView === 'messages') {
            if (navMessages) navMessages.classList.add('active');
            renderMessagesPage(appContent);
        } else if (state.currentView === 'details') {
            if (navMessages) navMessages.classList.add('active');
            renderMessageDetailsPage(appContent);
        } else if (state.currentView === 'routing') {
            if (navRouting) navRouting.classList.add('active');
            renderRoutingPage(appContent);
        } else if (state.currentView === 'faq') {
            if (navFaq) navFaq.classList.add('active');
            renderFaqPage(appContent);
        } else if (state.currentView === 'analytics') {
            if (navAnalytics) navAnalytics.classList.add('active');
            renderAnalyticsPage(appContent);
        }
    }

    // --- View 1: Dashboard ---
    function renderDashboardPage(container) {
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

        container.innerHTML = `
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
                        <div class="card-icon" style="color:var(--primary);"><i class="fa-solid fa-inbox"></i></div>
                        <div class="card-info"><h3 style="font-size:1rem;color:var(--text-primary);font-weight:600;">${t('inbox')}</h3><p style="font-size:0.8rem;color:var(--text-secondary);font-weight:400;">${t('viewMessages')}</p></div>
                    </div>
                    <div class="summary-card" style="cursor:pointer;" onclick="document.dispatchEvent(new CustomEvent('navToView',{detail:'routing'}))">
                        <div class="card-icon" style="color:var(--primary);"><i class="fa-solid fa-users-gear"></i></div>
                        <div class="card-info"><h3 style="font-size:1rem;color:var(--text-primary);font-weight:600;">${t('routing')}</h3><p style="font-size:0.8rem;color:var(--text-secondary);font-weight:400;">${t('manageAgents')}</p></div>
                    </div>
                    <div class="summary-card" style="cursor:pointer;" onclick="document.dispatchEvent(new CustomEvent('navToView',{detail:'analytics'}))">
                        <div class="card-icon" style="color:var(--primary);"><i class="fa-solid fa-chart-pie"></i></div>
                        <div class="card-info"><h3 style="font-size:1rem;color:var(--text-primary);font-weight:600;">${t('reports')}</h3><p style="font-size:0.8rem;color:var(--text-secondary);font-weight:400;">${t('viewAnalytics')}</p></div>
                    </div>
                    <div class="summary-card" style="cursor:pointer;" onclick="document.dispatchEvent(new CustomEvent('navToView',{detail:'faq'}))">
                        <div class="card-icon" style="color:var(--primary);"><i class="fa-solid fa-circle-question"></i></div>
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

        setTimeout(() => {
            container.querySelectorAll('.chart-bar').forEach(b => { b.style.width = b.getAttribute('data-width'); });
        }, 50);
    }

    // --- View 2: Routing ---
    function renderRoutingPage(container) {
        const totalAssigned = state.messages.filter(m => m.assignedAgent !== 'Unassigned').length;
        const unassigned    = state.messages.filter(m => m.assignedAgent === 'Unassigned').length;
        const escalated     = state.messages.filter(m => m.status === 'Escalated').length;

        const searchVal = state.filters.search;
        const statFilt  = state.filters.routingStatus;
        const urgFilt   = state.filters.routingUrgency;
        const assFilt   = state.filters.routingAssignment;

        let filtered = state.messages.filter(m => {
            const matchSearch = m.customerName.toLowerCase().includes(searchVal) || m.intent.toLowerCase().includes(searchVal);
            const matchStat   = statFilt === 'All' || m.status === statFilt;
            const matchUrg    = urgFilt === 'All'  || m.urgency === urgFilt;
            let matchAss = true;
            if (assFilt === 'Assigned')   matchAss = m.assignedAgent !== 'Unassigned';
            if (assFilt === 'Unassigned') matchAss = m.assignedAgent === 'Unassigned';
            return matchSearch && matchStat && matchUrg && matchAss;
        });

        let tableRows = filtered.map(msg => {
            let options = `<option value="Unassigned" ${msg.assignedAgent === 'Unassigned' ? 'selected' : ''}>
                ${state.currentLanguage === 'ar' ? 'غير مُعيَّن' : 'Unassigned'}
            </option>`;
            state.agents.forEach(agent => {
                options += `<option value="${agent}" ${msg.assignedAgent === agent ? 'selected' : ''}>${agent}</option>`;
            });

            return `
                <tr>
                    <td style="font-weight:500;">${msg.customerName}</td>
                    <td>${msg.intent}</td>
                    <td><span class="badge badge-${msg.sentiment.toLowerCase()}">${msg.sentiment}</span></td>
                    <td><span class="badge badge-${msg.urgency.toLowerCase()}">${msg.urgency}</span></td>
                    <td><span class="badge badge-${msg.status.toLowerCase()}">${msg.status}</span></td>
                    <td><select class="dropdown-agent" data-id="${msg.id}">${options}</select></td>
                    <td><button class="btn btn-outline escalate-btn" data-id="${msg.id}"
                        style="padding:6px 12px;font-size:0.8rem;color:var(--danger);border-color:var(--danger);">
                        ${t('escalate')}
                    </button></td>
                </tr>`;
        }).join('');

        if (filtered.length === 0) {
            tableRows = `<tr><td colspan="7" style="text-align:center;padding:40px;">${t('noRoutingMatch')}</td></tr>`;
        }

        container.innerHTML = `
            <div class="summary-cards">
                <div class="summary-card">
                    <div class="card-icon icon-blue"><i class="fa-solid fa-user-check"></i></div>
                    <div class="card-info"><h3>${t('assigned')}</h3><p>${totalAssigned}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-yellow"><i class="fa-solid fa-user-clock"></i></div>
                    <div class="card-info"><h3>${t('unassigned')}</h3><p>${unassigned}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-red"><i class="fa-solid fa-triangle-exclamation"></i></div>
                    <div class="card-info"><h3>${t('escalated')}</h3><p>${escalated}</p></div>
                </div>
                <div class="summary-card">
                    <div class="card-icon icon-green"><i class="fa-solid fa-users"></i></div>
                    <div class="card-info"><h3>${t('activeAgents')}</h3><p>${state.agents.length}</p></div>
                </div>
            </div>

            <div class="filter-bar">
                <input type="text" id="routeSearch" class="search-input" placeholder="${t('searchPlaceholder')}" value="${state.filters.search}">
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
                <button id="clearRouteFilters" class="btn btn-outline">${t('clear')}</button>
            </div>

            <div class="routing-table-card">
                <table class="routing-table">
                    <thead>
                        <tr>
                            <th>${t('customer')}</th>
                            <th>${t('intent')}</th>
                            <th>${t('sentiment')}</th>
                            <th>${t('urgency')}</th>
                            <th>${t('status')}</th>
                            <th>${t('assignedAgent')}</th>
                            <th>${t('quickAction')}</th>
                        </tr>
                    </thead>
                    <tbody>${tableRows}</tbody>
                </table>
            </div>
        `;

        document.getElementById('routeSearch').addEventListener('input', (e) => { state.filters.search = e.target.value.toLowerCase(); renderRoutingPage(container); });
        document.getElementById('routeAssignment').addEventListener('change', (e) => { state.filters.routingAssignment = e.target.value; renderRoutingPage(container); });
        document.getElementById('routeStatus').addEventListener('change', (e) => { state.filters.routingStatus = e.target.value; renderRoutingPage(container); });
        document.getElementById('routeUrgency').addEventListener('change', (e) => { state.filters.routingUrgency = e.target.value; renderRoutingPage(container); });
        document.getElementById('clearRouteFilters').addEventListener('click', () => {
            state.filters.search = ''; state.filters.routingAssignment = 'All';
            state.filters.routingStatus = 'All'; state.filters.routingUrgency = 'All';
            if (globalSearch) globalSearch.value = '';
            renderRoutingPage(container);
        });

        container.querySelectorAll('.dropdown-agent').forEach(select => {
            select.addEventListener('change', (e) => {
                const msg = state.messages.find(m => m.id === e.target.getAttribute('data-id'));
                if (msg) { msg.assignedAgent = e.target.value; renderRoutingPage(container); }
            });
        });

        container.querySelectorAll('.escalate-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const msg = state.messages.find(m => m.id === e.target.getAttribute('data-id'));
                if (msg) { msg.status = 'Escalated'; renderRoutingPage(container); }
            });
        });
    }

    // --- View 3: Messages ---
    function renderMessagesPage(container) {
        const total    = state.messages.length;
        const negative = state.messages.filter(m => m.sentiment === 'Negative').length;
        const urgent   = state.messages.filter(m => m.urgency === 'High').length;
        const pending  = state.messages.filter(m => m.status === 'Pending').length;

        container.insertAdjacentHTML('beforeend', `
            <div class="summary-cards">
                <div class="summary-card"><div class="card-icon icon-blue"><i class="fa-solid fa-envelope"></i></div><div class="card-info"><h3>${t('totalMessages')}</h3><p>${total}</p></div></div>
                <div class="summary-card"><div class="card-icon icon-red"><i class="fa-solid fa-heart-crack"></i></div><div class="card-info"><h3>${t('negative')}</h3><p>${negative}</p></div></div>
                <div class="summary-card"><div class="card-icon icon-yellow"><i class="fa-solid fa-bolt"></i></div><div class="card-info"><h3>${t('urgentCases')}</h3><p>${urgent}</p></div></div>
                <div class="summary-card"><div class="card-icon icon-green"><i class="fa-regular fa-clock"></i></div><div class="card-info"><h3>${t('pendingCases')}</h3><p>${pending}</p></div></div>
            </div>

            <div class="filter-bar">
                <input type="text" id="localSearch" class="search-input" placeholder="${t('searchPlaceholder')}" value="${state.filters.search}">
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
                <button id="clearFiltersBtn" class="btn btn-outline"><i class="fa-solid fa-rotate-left"></i> ${t('clear')}</button>
            </div>
            <div id="messagesList" class="messages-list"></div>
        `);

        document.getElementById('localSearch').addEventListener('input', (e) => { state.filters.search = e.target.value.toLowerCase(); updateListDisplay(); });
        document.getElementById('sentimentFilter').addEventListener('change', (e) => { state.filters.sentiment = e.target.value; updateListDisplay(); });
        document.getElementById('urgencyFilter').addEventListener('change', (e) => { state.filters.urgency = e.target.value; updateListDisplay(); });
        document.getElementById('clearFiltersBtn').addEventListener('click', () => {
            state.filters.search = ''; state.filters.sentiment = 'All'; state.filters.urgency = 'All';
            document.getElementById('localSearch').value = '';
            document.getElementById('sentimentFilter').value = 'All';
            document.getElementById('urgencyFilter').value = 'All';
            if (globalSearch) globalSearch.value = '';
            updateListDisplay();
        });

        updateListDisplay();
    }

    function updateListDisplay() {
        const listContainer = document.getElementById('messagesList');
        if (!listContainer) return;

        const filtered = state.messages.filter(msg => {
            const matchSearch    = msg.customerName.toLowerCase().includes(state.filters.search) || msg.intent.toLowerCase().includes(state.filters.search) || msg.messagePreview.toLowerCase().includes(state.filters.search);
            const matchSentiment = state.filters.sentiment === 'All' || msg.sentiment === state.filters.sentiment;
            const matchUrgency   = state.filters.urgency   === 'All' || msg.urgency   === state.filters.urgency;
            return matchSearch && matchSentiment && matchUrgency;
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
                <div class="msg-caller"><h4>${msg.customerName}</h4><p>${msg.email}</p></div>
                <div class="msg-preview">${msg.messagePreview}</div>
                <div class="msg-meta"><span class="badge badge-${msg.sentiment.toLowerCase()}">${msg.sentiment}</span><span style="font-size:0.8rem;">${msg.intent}</span></div>
                <div class="msg-meta"><span class="badge badge-${msg.urgency.toLowerCase()}">${msg.urgency}</span><span style="font-size:0.8rem;color:var(--primary);"><i class="fa-solid fa-user"></i> ${msg.assignedAgent}</span></div>
                <div><span class="badge badge-${msg.status.toLowerCase()}">${msg.status}</span></div>
            `;
            card.addEventListener('click', () => { navigateTo('details', msg.id); });
            listContainer.appendChild(card);
        });
    }

    // --- View 4: Message Details ---
    function renderMessageDetailsPage(container) {
        const msg = state.messages.find(m => m.id === state.selectedMessageId);
        if (!msg) { navigateTo('messages'); return; }

        // ── Auto-routing logic ──────────────────────────────
        const isHighUrgency  = msg.urgency === 'High';
        const isLowConfidence = msg.confidence < 70;
        const needsHuman     = isHighUrgency || isLowConfidence;

        // Auto-fire reply if eligible and not already responded
        if (!needsHuman && msg.status === 'Pending') {
            msg.status       = 'Responded';
            msg.autoReplied  = true;
        }
        // ────────────────────────────────────────────────────

        let chatHtml = '';
        msg.conversationHistory.forEach(c => {
            const isAgent = c.sender.includes("Agent") || c.sender.includes("System") || c.sender === msg.assignedAgent;
            chatHtml += `<div class="chat-bubble ${isAgent ? 'agent' : 'customer'}">
                <div class="chat-header">${c.sender} • ${c.time}</div>
                <div class="chat-text">${c.text}</div>
            </div>`;
        });

        // Add auto-reply bubble to chat history if just fired
        if (msg.autoReplied) {
            chatHtml += `<div class="chat-bubble agent auto-reply-bubble">
                <div class="chat-header"> ${t('autoBot')} • ${new Date().toLocaleTimeString()}</div>
                <div class="chat-text">${msg.suggestedReply}</div>
            </div>`;
        }

        const fullTime = new Date(msg.timestamp).toLocaleString();

        // Action area: differs based on routing decision
        const actionAreaHtml = needsHuman
            ? `<div class="escalation-notice">
                <i class="fa-solid fa-triangle-exclamation"></i>
                <div>
                    <strong>${t('humanRequired')}</strong>
                    <p>${isHighUrgency ? t('highUrgencyReason') : t('lowConfidenceReason')}</p>
                </div>
            </div>
            <div class="action-buttons">
                <button class="btn btn-primary" id="sendAutoReplyBtn">
                    <i class="fa-solid fa-paper-plane"></i> ${t('sendManualReply')}
                </button>
                <button class="btn btn-outline" id="markResolvedBtn">
                    <i class="fa-solid fa-check"></i> ${t('markResolved')}
                </button>
            </div>`
            : `<div class="auto-reply-success">
                <i class="fa-solid fa-circle-check"></i>
                <span>${t('autoReplySentAuto')}</span>
            </div>
            <div class="action-buttons">
                <button class="btn btn-outline" id="markResolvedBtn">
                    <i class="fa-solid fa-check"></i> ${t('markResolved')}
                </button>
            </div>`;

        container.insertAdjacentHTML('beforeend', `
            <div class="details-container">
                <button id="backToListBtn" class="back-btn">
                    <i class="fa-solid fa-arrow-left"></i> ${t('backToList')}
                </button>
                <div class="details-header">
                    <div class="details-user"><h2>${msg.customerName}</h2><p>${msg.email} • ${fullTime}</p></div>
                    <div style="text-align:right;">
                        <span class="badge badge-${msg.status.toLowerCase()}" style="margin-bottom:8px;display:inline-block;">${msg.status}</span><br>
                        <span style="font-size:0.85rem;color:var(--text-secondary);">
                            <i class="fa-solid fa-user"></i> ${t('assignedTo')} <b>${msg.assignedAgent}</b>
                        </span>
                    </div>
                </div>
                <div class="full-message-card">"${msg.fullMessage}"</div>
                <div class="ai-analysis">
                    <h3><i class="fa-solid fa-wand-magic-sparkles" style="color:var(--primary)"></i> ${t('aiAnalysis')}</h3>
                    <div class="analysis-grid">
                        <div class="analysis-item"><span>${t('sentiment')}</span><div class="badge badge-${msg.sentiment.toLowerCase()}">${msg.sentiment}</div></div>
                        <div class="analysis-item"><span>${t('intent')}</span><div style="font-weight:600;">${msg.intent}</div></div>
                        <div class="analysis-item"><span>${t('urgency')}</span><div class="badge badge-${msg.urgency.toLowerCase()}">${msg.urgency}</div></div>
                        <div class="analysis-item">
                            <span>${t('confidence')}</span>
                            <div style="font-weight:600;font-size:1.1rem;color:var(--success);">${msg.confidence}%</div>
                            <div class="confidence-bar-container">
                                <div class="confidence-bar" style="width:0%;" data-target="${msg.confidence}"></div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="suggested-reply">
                    <div class="suggested-reply-header"><i class="fa-solid fa-robot"></i> ${t('suggestedReply')}</div>
                    <div class="suggested-reply-text">${msg.suggestedReply}</div>
                    ${actionAreaHtml}
                </div>
                <div class="chat-history">
                    <h3>${t('conversationHistory')}</h3>
                    <div style="display:flex;flex-direction:column;">${chatHtml}</div>
                </div>
            </div>
        `);

        setTimeout(() => {
            const bar = container.querySelector('.confidence-bar');
            if (bar) bar.style.width = bar.getAttribute('data-target') + '%';
        }, 100);

        document.getElementById('backToListBtn').addEventListener('click', () => { navigateTo('messages'); });
        
        const manualBtn = document.getElementById('sendAutoReplyBtn');
        if (manualBtn) {
            manualBtn.addEventListener('click', () => {
                msg.status = 'Responded';
                alert(t('autoReplySent'));
                navigateTo('details', msg.id);
            });
        }
        document.getElementById('markResolvedBtn').addEventListener('click', () => {
            msg.status = 'Responded';
            alert(t('actionRecorded'));
            navigateTo('messages');
        });
    }

    // --- View 5: FAQ ---
    function renderFaqPage(container) {
        let faqListHtml = state.faqs.map(faq => `
            <div class="faq-item" id="faq-item-${faq.id}">
                <div class="faq-content" style="flex:1;"><h4>${faq.question}</h4><p>${faq.answer}</p></div>
                <div class="faq-actions" style="display:flex;gap:8px;">
                    <button class="btn btn-outline edit-faq-btn" data-id="${faq.id}" style="padding:8px 12px;border-radius:8px;"><i class="fa-solid fa-pen"></i></button>
                    <button class="btn btn-outline delete-faq-btn" data-id="${faq.id}" style="color:var(--danger);border-color:var(--danger);padding:8px 12px;border-radius:8px;"><i class="fa-solid fa-trash"></i></button>
                </div>
            </div>
            <form class="faq-form edit-faq-form" id="edit-form-${faq.id}" data-id="${faq.id}" style="display:none;margin-top:-10px;margin-bottom:20px;border-top-left-radius:0;border-top-right-radius:0;border-top:none;">
                <input type="text" class="edit-q" value="${faq.question}" required>
                <textarea class="edit-a" required>${faq.answer}</textarea>
                <div style="display:flex;gap:8px;">
                    <button type="submit" class="btn btn-primary">${t('saveChanges')}</button>
                    <button type="button" class="btn btn-outline cancel-edit-btn" data-id="${faq.id}">${t('cancel')}</button>
                </div>
            </form>
        `).join('');

        if (state.faqs.length === 0) {
            faqListHtml = `<div class="empty-state"><i class="fa-solid fa-circle-question" style="font-size:3rem;color:var(--text-secondary);margin-bottom:16px;display:block;"></i><h3>${t('noFaqs')}</h3><p>${t('noFaqsDesc')}</p></div>`;
        }

        container.innerHTML = `
            <div class="page-section" style="max-width:800px;margin:0 auto;">
                <h2>${t('addNewFaq')}</h2>
                <form class="faq-form" id="faqForm">
                    <input type="text" id="faqQuestion" placeholder="${t('enterQuestion')}" required>
                    <textarea id="faqAnswer" placeholder="${t('enterAnswer')}" required></textarea>
                    <button type="submit" class="btn btn-primary" style="align-self:flex-start;"><i class="fa-solid fa-plus"></i> ${t('addFaq')}</button>
                </form>
                <h2>${t('existingFaqs')}</h2>
                <div class="faq-list">${faqListHtml}</div>
            </div>
        `;

        document.getElementById('faqForm').addEventListener('submit', (e) => {
            e.preventDefault();
            const q = document.getElementById('faqQuestion').value;
            const a = document.getElementById('faqAnswer').value;
            state.faqs.push({ id: Date.now(), question: q, answer: a });
            localStorage.setItem('faqs', JSON.stringify(state.faqs));
            renderFaqPage(container);
        });

        container.querySelectorAll('.delete-faq-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = parseInt(e.currentTarget.getAttribute('data-id'));
                state.faqs = state.faqs.filter(f => f.id !== id);
                localStorage.setItem('faqs', JSON.stringify(state.faqs));
                renderFaqPage(container);
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
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                const id  = parseInt(e.currentTarget.getAttribute('data-id'));
                const idx = state.faqs.findIndex(f => f.id === id);
                if (idx > -1) {
                    state.faqs[idx].question = e.currentTarget.querySelector('.edit-q').value;
                    state.faqs[idx].answer   = e.currentTarget.querySelector('.edit-a').value;
                    localStorage.setItem('faqs', JSON.stringify(state.faqs));
                    renderFaqPage(container);
                }
            });
        });
    }

    // --- View 6: Analytics ---
    function renderAnalyticsPage(container) {
        const total = state.messages.length;
        if (total === 0) {
            container.innerHTML = `<div class="empty-state"><h3>${t('noData')}</h3></div>`;
            return;
        }

        const intentCounts = {};
        state.messages.forEach(m => { intentCounts[m.intent] = (intentCounts[m.intent] || 0) + 1; });

        const topIntentsHtml = Object.keys(intentCounts).map(intent => {
            const pct = Math.round((intentCounts[intent] / total) * 100);
            return `
                <div class="chart-row">
                    <span class="chart-label" style="width:120px;">${intent}</span>
                    <div class="chart-bar-container"><div class="chart-bar" style="background-color:var(--secondary);width:0;" data-width="${pct}%"></div></div>
                    <span class="chart-value">${pct}%</span>
                </div>`;
        }).join('');

        const lowUrg = state.messages.filter(m => m.urgency === 'Low').length;
        const medUrg = state.messages.filter(m => m.urgency === 'Medium').length;
        const highUrg = state.messages.filter(m => m.urgency === 'High').length;

        const mockDays    = ["Mon", "Tue", "Wed", "Thu", "Fri"];
        const maxVol      = 20;
        const dailyVolumes = [12, 19, 8, 15, total];

        const timeBarsHtml = mockDays.map((day, idx) => {
            const val = dailyVolumes[idx];
            const heightPct = (val / maxVol) * 100;
            return `
                <div style="display:flex;flex-direction:column;align-items:center;gap:8px;">
                    <span style="font-size:0.8rem;color:var(--text-secondary);">${val}</span>
                    <div style="height:120px;width:40px;background-color:var(--bg-color);border-radius:6px;display:flex;align-items:flex-end;overflow:hidden;">
                        <div class="chart-bar-vertical" style="width:100%;height:0;background-color:var(--primary);transition:height 1s ease;" data-height="${heightPct}%"></div>
                    </div>
                    <span style="font-size:0.85rem;font-weight:500;">${day}</span>
                </div>`;
        }).join('');

        container.innerHTML = `
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
                    <h2>${t('messagesOverTime')}</h2>
                    <div class="chart-card" style="display:flex;justify-content:space-around;align-items:flex-end;padding-top:40px;padding-bottom:20px;">
                        ${timeBarsHtml}
                    </div>
                </div>
            </div>
            <div class="dashboard-grid">
                <div class="page-section">
                    <h2>${t('topIntents')}</h2>
                    <div class="chart-card">${topIntentsHtml}</div>
                </div>
                <div class="page-section">
                    <h2>${t('urgencyBreakdown')}</h2>
                    <div class="chart-card">
                        <div class="chart-row">
                            <span class="chart-label">${t('low')}</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color:var(--success);width:0;" data-width="${Math.round((lowUrg/total)*100)}%"></div></div>
                            <span class="chart-value">${Math.round((lowUrg/total)*100)}%</span>
                        </div>
                        <div class="chart-row">
                            <span class="chart-label">${t('medium')}</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color:var(--warning);width:0;" data-width="${Math.round((medUrg/total)*100)}%"></div></div>
                            <span class="chart-value">${Math.round((medUrg/total)*100)}%</span>
                        </div>
                        <div class="chart-row">
                            <span class="chart-label">${t('high')}</span>
                            <div class="chart-bar-container"><div class="chart-bar" style="background-color:var(--danger);width:0;" data-width="${Math.round((highUrg/total)*100)}%"></div></div>
                            <span class="chart-value">${Math.round((highUrg/total)*100)}%</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        setTimeout(() => {
            container.querySelectorAll('.chart-bar').forEach(b => { b.style.width = b.getAttribute('data-width'); });
            container.querySelectorAll('.chart-bar-vertical').forEach(b => { b.style.height = b.getAttribute('data-height'); });
        }, 100);
    }

});
document.addEventListener('DOMContentLoaded', () => {
    initAuth();
    initNavigation();
    initModalEvents();
    initFormEvents();

    setInterval(() => {
        if (isLoggedIn) {
            loadDashboardStats();
            loadSalesList();
            loadInbox();
            loadInvoicesList();
            loadNotifications();
        }
    }, 30000);
});

let isLoggedIn = false;
let lastToastMsg = '';
let lastToastTime = 0;

async function initAuth() {
    const loginForm = document.getElementById('login-form');

    if (localStorage.getItem('isLoggedIn') === 'true') {
        showAppUI();
    }

    try {
        const res = await fetch('/api/check-auth');
        if (res.ok) {
            const data = await res.json();
            if (data.authenticated) {
                localStorage.setItem('isLoggedIn', 'true');
                showAppUI();
                return;
            }
        }
    } catch (e) {}

    if (localStorage.getItem('isLoggedIn') !== 'true') {
        showLoginUI();
    }

    if (loginForm && !loginForm.dataset.bound) {
        loginForm.dataset.bound = 'true';
        loginForm.addEventListener('submit', handleLoginSubmit);
    }
}

async function handleLoginSubmit(e) {
    if (e) e.preventDefault();

    const loginError = document.getElementById('login-error');
    if (loginError) loginError.style.display = 'none';

    const usernameInput = document.getElementById('login-username') || document.getElementById('username');
    const passwordInput = document.getElementById('login-password') || document.getElementById('password');

    const username = usernameInput ? usernameInput.value.trim() : '';
    const password = passwordInput ? passwordInput.value.trim() : '';

    if (!username || !password) return;

    try {
        const res = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await res.json();
        if (res.ok && data.success) {
            localStorage.setItem('isLoggedIn', 'true');

            showToast('Giriş başarılı!', 'success');

            if (window.location.search) {
                window.history.replaceState({}, document.title, window.location.pathname);
            }

            showAppUI();
        } else {
            localStorage.removeItem('isLoggedIn');
            if (loginError) {
                loginError.innerText = data.message || 'Kullanıcı adı veya şifre hatalı!';
                loginError.style.display = 'block';
            } else {
                alert(data.message || 'Kullanıcı adı veya şifre hatalı!');
            }
        }
    } catch (err) {
        console.error('Login submit error:', err);
        if (loginError) {
            loginError.innerText = 'Giriş yapılırken bir sunucu hatası oluştu.';
            loginError.style.display = 'block';
        } else {
            alert('Giriş yapılırken bir hata oluştu.');
        }
    }
}
window.handleLoginSubmit = handleLoginSubmit;

document.addEventListener('click', function(e) {
    if (!e || !e.target) return;
    const isLogoutBtn = e.target.id === 'logout-btn' || 
                        e.target.id === 'btn-logout' || 
                        e.target.closest('#logout-btn') || 
                        e.target.closest('#btn-logout') || 
                        e.target.closest('.logout-action');
    if (isLogoutBtn) {
        e.preventDefault();
        handleLogout();
    }
});

async function handleLogout() {
    try {
        await fetch('/logout', { method: 'POST' });
        await fetch('/api/logout', { method: 'POST' });
    } catch(err) {
        console.error('Logout error:', err);
    } finally {
        localStorage.clear();
        sessionStorage.clear();

        document.cookie.split(";").forEach(function(c) { 
            document.cookie = c.replace(/^ +/, "").replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/"); 
        });

        showLoginUI();
        if (window.location.pathname !== '/login') {
            window.location.replace('/login');
        }
    }
}
window.handleLogout = handleLogout;

function showAppUI() {
    isLoggedIn = true;
    document.getElementById('login-screen').classList.remove('active');
    document.getElementById('app-wrapper').style.display = 'flex';
    loadDashboardStats();
    loadSalesList();
    loadInbox();
    loadTemplates();
    loadSettings();
    loadInvoicesList();
    loadNotifications();
}

function showLoginUI() {
    isLoggedIn = false;
    localStorage.clear();
    sessionStorage.clear();
    document.cookie.split(";").forEach(function(c) { 
        document.cookie = c.replace(/^ +/, "").replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/"); 
    });

    const appWrapper = document.getElementById('app-wrapper');
    const loginScreen = document.getElementById('login-screen');

    if (appWrapper) appWrapper.style.display = 'none';
    if (loginScreen) loginScreen.classList.add('active');

    const usernameInput = document.getElementById('login-username');
    const passwordInput = document.getElementById('login-password');
    const loginError = document.getElementById('login-error');
    if (usernameInput) usernameInput.value = '';
    if (passwordInput) passwordInput.value = '';
    if (loginError) loginError.style.display = 'none';
}

async function authFetch(url, options = {}) {
    const res = await fetch(url, options);
    if (res.status === 401) {
        showLoginUI();
        showToast('Oturum süreniz doldu, lütfen tekrar giriş yapın.', 'error');
        throw new Error('Unauthorized');
    }
    return res;
}

function showToast(message, type = 'success') {
    const now = Date.now();
    if (message === lastToastMsg && (now - lastToastTime) < 2000) {
        return;
    }
    lastToastMsg = message;
    lastToastTime = now;

    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <i class="fa-solid ${type === 'success' ? 'fa-circle-check' : 'fa-circle-exclamation'}"></i>
        <span>${message}</span>
    `;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function initNavigation() {
    const links = document.querySelectorAll('.nav-link');
    links.forEach(link => {
        link.addEventListener('click', () => {
            const targetTab = link.getAttribute('data-tab');
            switchTab(targetTab);
        });
    });

    document.getElementById('btn-run-check').addEventListener('click', async () => {
        try {
            const res = await authFetch('/api/run-scheduler', { method: 'POST' });
            const data = await res.json();
            showToast(data.message, 'success');
            loadDashboardStats();
            loadSalesList();
            loadInbox();
            loadInvoicesList();
            loadNotifications();
        } catch (e) {}
    });
}

function switchTab(tabId) {
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    document.querySelectorAll('.tab-page').forEach(p => p.classList.remove('active'));

    const activeLink = document.querySelector(`.nav-link[data-tab="${tabId}"]`);
    const activePage = document.getElementById(tabId);

    if (activeLink) activeLink.classList.add('active');
    if (activePage) activePage.classList.add('active');

    const titles = {
        'dashboard-tab': ['Piramit Lisans Takip', 'Lisans durumları ve istatistik özetleri'],
        'sales-tab': ['Satış & Lisans Takibi', 'Kayıtlı lisanslar, süreler ve hatırlatma zamanlamaları'],
        'invoices-tab': ['Ödenmemiş Faturalar', 'Vadesi yaklaşan/geçmiş faturalar ve hatırlatma durumları'],
        'inbox-tab': ['Sanal Gelen Kutusu (Mock Inbox)', 'Gönderilen canlı ve simüle edilmiş hatırlatma e-postaları'],
        'templates-tab': ['E-posta Şablonları', 'Müşterilere gidecek HTML e-posta metinlerini düzenleyin'],
        'settings-tab': ['Sistem & SMTP Ayarları', 'E-posta modu ve SMTP sunucu yapılandırması']
    };

    if (titles[tabId]) {
        document.getElementById('page-title').innerText = titles[tabId][0];
        document.getElementById('page-subtitle').innerText = titles[tabId][1];
    }

    document.querySelectorAll('.header-action-btn').forEach(btn => {
        const showOn = (btn.getAttribute('data-show-on') || '').split(',');
        btn.style.display = showOn.includes(tabId) ? '' : 'none';
    });
}

function initModalEvents() {
    const modal = document.getElementById('new-sale-modal');
    const openBtn = document.getElementById('open-new-sale-modal');
    const closeBtns = document.querySelectorAll('.modal-close');

    openBtn.addEventListener('click', () => {
        document.getElementById('new-sale-date').value = new Date().toISOString().split('T')[0];
        calculateLiveExpiration();
        modal.classList.add('active');
    });

    closeBtns.forEach(btn => {
        btn.addEventListener('click', () => modal.classList.remove('active'));
    });

    const durationSelect = document.getElementById('new-duration-type');
    const customContainer = document.getElementById('custom-duration-container');
    const saleDateInput = document.getElementById('new-sale-date');
    const customMonthsInput = document.getElementById('new-custom-months');

    durationSelect.addEventListener('change', () => {
        if (durationSelect.value === 'CUSTOM') {
            customContainer.style.display = 'block';
        } else {
            customContainer.style.display = 'none';
        }
        calculateLiveExpiration();
    });

    saleDateInput.addEventListener('input', calculateLiveExpiration);
    customMonthsInput.addEventListener('input', calculateLiveExpiration);

    const invoiceModal = document.getElementById('new-invoice-modal');
    const openInvoiceBtn = document.getElementById('open-new-invoice-modal');
    openInvoiceBtn.addEventListener('click', () => {
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('new-invoice-issue-date').value = today;
        invoiceModal.classList.add('active');
    });
    invoiceModal.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', () => invoiceModal.classList.remove('active'));
    });
}

function calculateLiveExpiration() {
    const saleDateStr = document.getElementById('new-sale-date').value;
    if (!saleDateStr) return;

    const durationSelect = document.getElementById('new-duration-type');
    let months = 36;

    if (durationSelect.value === 'CUSTOM') {
        months = parseInt(document.getElementById('new-custom-months').value) || 12;
    } else {
        const selectedOpt = durationSelect.options[durationSelect.selectedIndex];
        months = parseInt(selectedOpt.getAttribute('data-months')) || 36;
    }

    const saleDate = new Date(saleDateStr);
    const expDate = new Date(saleDate);
    expDate.setMonth(expDate.getMonth() + months);

    const formattedExp = expDate.toISOString().split('T')[0];
    document.getElementById('calc-exp-date').innerText = `${formattedExp} (${months} Ay / ${(months/12).toFixed(1)} Yıl)`;
}

function initFormEvents() {
    document.getElementById('new-sale-form').addEventListener('submit', async (e) => {
        e.preventDefault();

        const durationType = document.getElementById('new-duration-type').value;
        let durationMonths = 36;
        if (durationType === 'CUSTOM') {
            durationMonths = parseInt(document.getElementById('new-custom-months').value) || 12;
        } else {
            const selectedOpt = document.getElementById('new-duration-type').options[document.getElementById('new-duration-type').selectedIndex];
            durationMonths = parseInt(selectedOpt.getAttribute('data-months')) || 36;
        }

        const payload = {
            product_name: document.getElementById('new-product-name').value,
            client_name: document.getElementById('new-client-name').value,
            client_email: document.getElementById('new-client-email').value,
            sales_rep: document.getElementById('new-sales-rep').value,
            license_key: document.getElementById('new-license-key').value,
            sale_date: document.getElementById('new-sale-date').value,
            duration_type: durationType,
            duration_months: durationMonths,
            reminder_type: document.getElementById('new-reminder-type').value,
            notes: document.getElementById('new-notes').value
        };

        try {
            const res = await authFetch('/api/sales', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                showToast(data.message, 'success');
                document.getElementById('new-sale-modal').classList.remove('active');
                document.getElementById('new-sale-form').reset();
                loadDashboardStats();
                loadSalesList();
            } else {
                showToast(data.message, 'error');
            }
        } catch (err) {}
    });

    document.getElementById('sales-search-input').addEventListener('input', filterSalesTable);
    document.getElementById('sales-status-filter').addEventListener('change', filterSalesTable);

    document.getElementById('btn-clear-inbox').addEventListener('click', async () => {
        if (!confirm('Sanal gelen kutusunu temizlemek istediğinizden emin misiniz?')) return;
        await authFetch('/api/sent-emails/clear', { method: 'POST' });
        loadInbox();
        loadDashboardStats();
        showToast('Gelen kutusu temizlendi.');
    });

    document.getElementById('template-edit-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const key = document.getElementById('edit-template-key').value;
        const payload = {
            subject: document.getElementById('edit-template-subject').value,
            body_html: document.getElementById('edit-template-body').value
        };

        const res = await authFetch(`/api/templates/${key}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message);
            loadTemplates();
        }
    });

    document.getElementById('settings-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const mode = document.querySelector('input[name="mode"]:checked').value;
        const payload = {
            mode: mode,
            internal_recipients: document.getElementById('setting-internal-recipients').value,
            smtp_host: document.getElementById('setting-smtp-host').value,
            smtp_port: document.getElementById('setting-smtp-port').value,
            smtp_user: document.getElementById('setting-smtp-user').value,
            smtp_password: document.getElementById('setting-smtp-password').value,
            sender_email: document.getElementById('setting-sender-email').value,
            sender_name: document.getElementById('setting-sender-name').value
        };

        const res = await authFetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message);
        }
    });

    document.getElementById('logo-settings-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            logo_sql_server: document.getElementById('setting-logo-server').value,
            logo_sql_port: document.getElementById('setting-logo-port').value,
            logo_sql_db: document.getElementById('setting-logo-db').value,
            logo_sql_user: document.getElementById('setting-logo-user').value,
            logo_sql_pass: document.getElementById('setting-logo-pass').value,
            logo_firm_no: document.getElementById('setting-logo-firm').value,
            logo_period_no: document.getElementById('setting-logo-period').value,
            logo_auto_sync: document.getElementById('setting-logo-auto').value
        };

        const res = await authFetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showToast('Logo ERP ayarları kaydedildi.');
        }
    });

    document.getElementById('btn-test-logo').addEventListener('click', async () => {
        try {
            const res = await authFetch('/api/logo/test-connection', { method: 'POST' });
            const data = await res.json();
            showToast(data.message, data.success ? 'success' : 'error');
        } catch (e) {
            showToast('Bağlantı testi yapılamadı.', 'error');
        }
    });

    document.getElementById('btn-sync-logo').addEventListener('click', async () => {
        try {
            showToast('Logo fatura senkronizasyonu başlatıldı...', 'success');
            const res = await authFetch('/api/logo/sync', { method: 'POST' });
            const data = await res.json();
            showToast(data.message, 'success');
            loadDashboardStats();
            loadSalesList();
        } catch (e) {
            showToast('Aktarım sırasında hata oluştu.', 'error');
        }
    });

    document.getElementById('new-invoice-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            invoice_no: document.getElementById('new-invoice-no').value,
            amount: parseFloat(document.getElementById('new-invoice-amount').value) || 0,
            currency: document.getElementById('new-invoice-currency').value,
            client_name: document.getElementById('new-invoice-client-name').value,
            client_email: document.getElementById('new-invoice-client-email').value,
            issue_date: document.getElementById('new-invoice-issue-date').value,
            due_date: document.getElementById('new-invoice-due-date').value,
            notes: document.getElementById('new-invoice-notes').value
        };

        try {
            const res = await authFetch('/api/invoices', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                showToast(data.message, 'success');
                document.getElementById('new-invoice-modal').classList.remove('active');
                document.getElementById('new-invoice-form').reset();
                loadInvoicesList();
                loadNotifications();
            } else {
                showToast(data.message, 'error');
            }
        } catch (err) {}
    });

    document.getElementById('account-settings-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            current_password: document.getElementById('account-current-password').value,
            new_username: document.getElementById('account-new-username').value,
            new_password: document.getElementById('account-new-password').value
        };

        try {
            const res = await authFetch('/api/account', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            showToast(data.message, data.success ? 'success' : 'error');
            if (data.success) {
                document.getElementById('account-settings-form').reset();
            }
        } catch (err) {}
    });
}

async function loadDashboardStats() {
    try {
        const res = await authFetch('/api/stats');
        const stats = await res.json();
        document.getElementById('stat-total-sales').innerText = stats.total_sales;
        document.getElementById('stat-active-licenses').innerText = stats.active_licenses;
        document.getElementById('stat-expiring-soon').innerText = stats.expiring_soon;
        document.getElementById('stat-reminders-sent').innerText = stats.reminders_sent;
        document.getElementById('stat-expired-licenses').innerText = stats.expired_licenses;
        document.getElementById('inbox-count-badge').innerText = stats.reminders_sent;
    } catch (e) {}
}

let cachedSales = [];

async function loadSalesList() {
    try {
        const res = await authFetch('/api/sales');
        cachedSales = await res.json();
        renderDashboardTable(cachedSales.slice(0, 5));
        renderFullSalesTable(cachedSales);
    } catch (e) {}
}

function renderStatusPill(status) {
    const map = {
        'PENDING': '<span class="status-pill pending"><i class="fa-solid fa-clock"></i> Beklemede</span>',
        'FIRST_REMINDER_SENT': '<span class="status-pill first-sent"><i class="fa-solid fa-envelope"></i> 1 Ay Kala Bildirildi</span>',
        'FINAL_REMINDER_SENT': '<span class="status-pill final-sent"><i class="fa-solid fa-bell"></i> 1 Hafta Kala Bildirildi</span>',
        'EXPIRED': '<span class="status-pill expired"><i class="fa-solid fa-ban"></i> Süresi Doldu</span>'
    };
    return map[status] || status;
}

function renderReminderType(type) {
    const map = {
        'STAGED': '<span class="text-primary"><i class="fa-solid fa-layer-group"></i> Kademeli (30G + 7G)</span>',
        '1_MONTH': '<span><i class="fa-solid fa-calendar-day"></i> 1 Ay Önce</span>',
        '1_WEEK': '<span><i class="fa-solid fa-bolt"></i> 1 Hafta Önce</span>'
    };
    return map[type] || type;
}

function renderDashboardTable(sales) {
    const tbody = document.querySelector('#dashboard-sales-table tbody');
    if (sales.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center p-4 text-muted">Henüz kayıtlı satış lisansı bulunmuyor.</td></tr>';
        return;
    }

    tbody.innerHTML = sales.map(s => `
        <tr>
            <td><strong>${s.product_name}</strong></td>
            <td>${s.client_name}</td>
            <td>${s.sale_date}</td>
            <td><strong>${s.expiration_date}</strong></td>
            <td><span class="${s.days_left <= 30 ? 'text-warning font-bold' : ''}">${s.days_left} Gün</span></td>
            <td>${renderReminderType(s.reminder_type)}</td>
            <td>${renderStatusPill(s.status)}</td>
        </tr>
    `).join('');
}

function renderFullSalesTable(sales) {
    const tbody = document.querySelector('#full-sales-table tbody');
    if (sales.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center p-4 text-muted">Kayıtlı lisans bulunamadı.</td></tr>';
        return;
    }

    tbody.innerHTML = sales.map(s => `
        <tr>
            <td>#${s.id}</td>
            <td>
                <strong>${s.product_name}</strong>
                ${s.license_key ? `<br><code class="text-muted" style="font-size:11px;">${s.license_key}</code>` : ''}
            </td>
            <td>
                ${s.client_name}<br>
                <small class="text-muted">${s.client_email}</small>
            </td>
            <td>${s.sales_rep || '-'}</td>
            <td>${s.duration_months} Ay (${(s.duration_months/12).toFixed(1)} Yıl)</td>
            <td><strong>${s.expiration_date}</strong></td>
            <td><strong class="${s.days_left <= 30 ? (s.days_left <= 7 ? 'text-danger' : 'text-warning') : 'text-success'}">${s.days_left} Gün</strong></td>
            <td>${renderReminderType(s.reminder_type)}</td>
            <td>${renderStatusPill(s.status)}</td>
            <td>
                <div class="flex-gap-2">
                    <button class="btn btn-sm btn-outline-primary" onclick="sendTestEmail(${s.id})" title="Test / Manuel E-posta Gönder">
                        <i class="fa-solid fa-paper-plane"></i>
                    </button>
                    <button class="btn btn-sm btn-danger-outline" onclick="deleteSale(${s.id})" title="Sil">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

function filterSalesTable() {
    const query = document.getElementById('sales-search-input').value.toLowerCase();
    const status = document.getElementById('sales-status-filter').value;

    const filtered = cachedSales.filter(s => {
        const matchesQuery = s.product_name.toLowerCase().includes(query) ||
                             s.client_name.toLowerCase().includes(query) ||
                             (s.license_key && s.license_key.toLowerCase().includes(query));
        const matchesStatus = (status === 'ALL') || (s.status === status);
        return matchesQuery && matchesStatus;
    });

    renderFullSalesTable(filtered);
}

async function sendTestEmail(saleId) {
    if (!confirm('Bu lisans için müşteri ve satış temsilcisine manuel hatırlatma e-postası göndermek istediğinizden emin misiniz?')) return;

    try {
        const res = await authFetch(`/api/sales/${saleId}/send-reminder`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stage: 'FINAL_REMINDER' })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            loadInbox();
            loadDashboardStats();
        } else {
            showToast(data.message, 'error');
        }
    } catch (e) {}
}

async function deleteSale(saleId) {
    if (!confirm('Bu satış lisans kaydını silmek istediğinize emin misiniz?')) return;
    try {
        const res = await authFetch(`/api/sales/${saleId}`, { method: 'DELETE' });
        const data = await res.json();
        showToast(data.message);
        loadDashboardStats();
        loadSalesList();
    } catch (e) {}
}

async function loadInbox() {
    try {
        const res = await authFetch('/api/sent-emails');
        const emails = await res.json();

        const listContainer = document.getElementById('inbox-messages-list');
        if (emails.length === 0) {
            listContainer.innerHTML = '<div class="p-4 text-center text-muted">Sanal gelen kutunuz boş.</div>';
            return;
        }

        listContainer.innerHTML = emails.map((em, idx) => `
            <div class="inbox-item ${idx === 0 ? 'active' : ''}" onclick="previewInboxMessage(${em.id})">
                <div class="inbox-item-header">
                    <span><i class="fa-solid fa-paper-plane"></i> Mod: ${em.delivery_mode}</span>
                    <span>${em.sent_at}</span>
                </div>
                <div class="inbox-item-subject">${em.subject}</div>
                <div class="inbox-item-recipient">Alıcı: ${em.recipient_name} &lt;${em.recipient_email}&gt;</div>
            </div>
        `).join('');

        window.cachedEmails = emails;
        if (emails.length > 0) {
            previewInboxMessage(emails[0].id);
        }
    } catch (e) {}
}

function previewInboxMessage(emailId) {
    document.querySelectorAll('.inbox-item').forEach(el => el.classList.remove('active'));
    const targetEmail = window.cachedEmails.find(e => e.id === emailId);
    if (!targetEmail) return;

    const panel = document.getElementById('inbox-preview-panel');
    panel.innerHTML = `
        <div style="border-bottom: 1px solid var(--border-color); padding-bottom: 16px; margin-bottom: 20px;">
            <h2>${targetEmail.subject}</h2>
            <div style="margin-top: 8px; font-size: 13px; color: var(--text-muted);">
                <p><strong>Alıcı:</strong> ${targetEmail.recipient_name} &lt;${targetEmail.recipient_email}&gt;</p>
                <p><strong>Gönderim Tarihi:</strong> ${targetEmail.sent_at}</p>
                <p><strong>Hatırlatma Aşaması:</strong> ${targetEmail.reminder_stage} (${targetEmail.delivery_mode})</p>
            </div>
        </div>
        <div class="email-rendered-body">
            ${targetEmail.body_html}
        </div>
    `;
}

async function loadTemplates() {
    try {
        const res = await authFetch('/api/templates');
        const templates = await res.json();

        const container = document.getElementById('templates-list-container');
        container.innerHTML = templates.map((t, idx) => `
            <div class="template-item ${idx === 0 ? 'active' : ''}" data-key="${t.template_key}" onclick="loadTemplateToEditor('${t.template_key}')">
                <h4><i class="fa-solid fa-file-code"></i> ${t.title}</h4>
                <p class="template-item-subject">Konu: ${t.subject}</p>
            </div>
        `).join('');

        window.cachedTemplates = templates;
        if (templates.length > 0) {
            loadTemplateToEditor(templates[0].template_key);
        }
    } catch (e) {}
}

function loadTemplateToEditor(key) {
    document.querySelectorAll('.template-item').forEach(el => {
        if (el.getAttribute('data-key') === key) {
            el.classList.add('active');
        } else {
            el.classList.remove('active');
        }
    });

    const tmpl = window.cachedTemplates.find(t => t.template_key === key);
    if (!tmpl) return;

    document.getElementById('edit-template-key').value = tmpl.template_key;
    document.getElementById('edit-template-subject').value = tmpl.subject;
    document.getElementById('edit-template-body').value = tmpl.body_html;
    document.getElementById('editor-title').innerText = `Düzenlenen: ${tmpl.title}`;
}

function insertTag(tag) {
    const textarea = document.getElementById('edit-template-body');
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = textarea.value;
    textarea.value = text.substring(0, start) + tag + text.substring(end);
    textarea.focus();
}

async function loadSettings() {
    try {
        const res = await authFetch('/api/settings');
        const settings = await res.json();

        if (settings.mode) {
            const radio = document.querySelector(`input[name="mode"][value="${settings.mode}"]`);
            if (radio) radio.checked = true;
        }

        if (settings.internal_recipients) document.getElementById('setting-internal-recipients').value = settings.internal_recipients;
        if (settings.smtp_host) document.getElementById('setting-smtp-host').value = settings.smtp_host;
        if (settings.smtp_port) document.getElementById('setting-smtp-port').value = settings.smtp_port;
        if (settings.smtp_user) document.getElementById('setting-smtp-user').value = settings.smtp_user;
        if (settings.smtp_password) document.getElementById('setting-smtp-password').value = settings.smtp_password;
        if (settings.sender_email) document.getElementById('setting-sender-email').value = settings.sender_email;
        if (settings.sender_name) document.getElementById('setting-sender-name').value = settings.sender_name;

        if (settings.logo_sql_server) document.getElementById('setting-logo-server').value = settings.logo_sql_server;
        if (settings.logo_sql_port) document.getElementById('setting-logo-port').value = settings.logo_sql_port;
        if (settings.logo_sql_db) document.getElementById('setting-logo-db').value = settings.logo_sql_db;
        if (settings.logo_sql_user) document.getElementById('setting-logo-user').value = settings.logo_sql_user;
        if (settings.logo_sql_pass) document.getElementById('setting-logo-pass').value = settings.logo_sql_pass;
        if (settings.logo_firm_no) document.getElementById('setting-logo-firm').value = settings.logo_firm_no;
        if (settings.logo_period_no) document.getElementById('setting-logo-period').value = settings.logo_period_no;
        if (settings.logo_auto_sync) document.getElementById('setting-logo-auto').value = settings.logo_auto_sync;
    } catch (e) {}
}

let cachedInvoices = [];

async function loadInvoicesList() {
    try {
        const res = await authFetch('/api/invoices');
        cachedInvoices = await res.json();
        renderInvoicesTable(cachedInvoices);

        const dueSoon = cachedInvoices.filter(i => i.status === 'UNPAID' && i.days_left >= 0 && i.days_left <= 7).length;
        const overdue = cachedInvoices.filter(i => i.status === 'UNPAID' && i.days_left < 0).length;
        const totalAmount = cachedInvoices.filter(i => i.status === 'UNPAID').reduce((sum, i) => sum + i.amount, 0);

        document.getElementById('stat-invoices-due-soon').innerText = dueSoon;
        document.getElementById('stat-invoices-overdue').innerText = overdue;
        document.getElementById('stat-invoices-total-amount').innerText = totalAmount.toLocaleString('tr-TR', { minimumFractionDigits: 2 });
    } catch (e) {}
}

function renderInvoiceStatusPill(inv) {
    if (inv.status === 'PAID') {
        return '<span class="status-pill first-sent"><i class="fa-solid fa-circle-check"></i> Ödendi</span>';
    }
    if (inv.days_left < 0) {
        return '<span class="status-pill expired"><i class="fa-solid fa-triangle-exclamation"></i> Vadesi Geçti</span>';
    }
    if (inv.days_left <= 7) {
        return '<span class="status-pill final-sent"><i class="fa-solid fa-bell"></i> Yaklaşıyor</span>';
    }
    return '<span class="status-pill pending"><i class="fa-solid fa-clock"></i> Beklemede</span>';
}

function renderInvoicesTable(invoices) {
    const tbody = document.querySelector('#full-invoices-table tbody');
    if (invoices.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center p-4 text-muted">Kayıtlı fatura bulunamadı.</td></tr>';
        return;
    }

    tbody.innerHTML = invoices.map(i => `
        <tr>
            <td>#${i.id}</td>
            <td>${i.invoice_no || '-'}</td>
            <td>
                ${i.client_name}
                ${i.client_email ? `<br><small class="text-muted">${i.client_email}</small>` : ''}
            </td>
            <td><strong>${i.amount.toLocaleString('tr-TR', { minimumFractionDigits: 2 })} ${i.currency}</strong></td>
            <td>${i.issue_date}</td>
            <td><strong>${i.due_date}</strong></td>
            <td><strong class="${i.days_left < 0 ? 'text-danger' : (i.days_left <= 7 ? 'text-warning' : 'text-success')}">${i.days_left} Gün</strong></td>
            <td>${renderInvoiceStatusPill(i)}</td>
            <td>
                <div class="flex-gap-2">
                    ${i.status === 'UNPAID' ? `
                    <button class="btn btn-sm btn-outline-primary" onclick="sendInvoiceTestEmail(${i.id})" title="Hatırlatma Gönder">
                        <i class="fa-solid fa-paper-plane"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-primary" onclick="markInvoicePaid(${i.id})" title="Ödendi Olarak İşaretle">
                        <i class="fa-solid fa-check"></i>
                    </button>` : ''}
                    <button class="btn btn-sm btn-danger-outline" onclick="deleteInvoice(${i.id})" title="Sil">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

async function sendInvoiceTestEmail(invoiceId) {
    if (!confirm('Bu fatura için müşteriye hatırlatma e-postası göndermek istediğinizden emin misiniz?')) return;
    try {
        const res = await authFetch(`/api/invoices/${invoiceId}/send-reminder`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stage: 'WEEK' })
        });
        const data = await res.json();
        showToast(data.message, data.success ? 'success' : 'error');
        if (data.success) { loadInbox(); loadNotifications(); }
    } catch (e) {}
}

async function markInvoicePaid(invoiceId) {
    if (!confirm('Bu faturayı ödendi olarak işaretlemek istediğinize emin misiniz?')) return;
    try {
        const res = await authFetch(`/api/invoices/${invoiceId}/mark-paid`, { method: 'POST' });
        const data = await res.json();
        showToast(data.message);
        loadInvoicesList();
        loadNotifications();
    } catch (e) {}
}

async function deleteInvoice(invoiceId) {
    if (!confirm('Bu fatura kaydını silmek istediğinize emin misiniz?')) return;
    try {
        const res = await authFetch(`/api/invoices/${invoiceId}`, { method: 'DELETE' });
        const data = await res.json();
        showToast(data.message);
        loadInvoicesList();
        loadNotifications();
    } catch (e) {}
}

async function loadNotifications() {
    try {
        const res = await authFetch('/api/notifications/pending');
        const data = await res.json();

        const licenseBadge = document.getElementById('license-alert-badge');
        const invoiceBadge = document.getElementById('invoice-alert-badge');

        if (data.license_alerts > 0) {
            licenseBadge.innerText = data.license_alerts;
            licenseBadge.style.display = '';
        } else {
            licenseBadge.style.display = 'none';
        }

        if (data.invoice_alerts > 0) {
            invoiceBadge.innerText = data.invoice_alerts;
            invoiceBadge.style.display = '';
        } else {
            invoiceBadge.style.display = 'none';
        }
    } catch (e) {}
}

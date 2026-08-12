document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initAuth();
    initNavigation();
    initModalEvents();
    initFormEvents();

    setInterval(() => {
        if (isLoggedIn) {
            loadDashboardStats();
            loadSalesList();
            loadRenewals();
            loadOffers();
            loadInbox();
            loadInvoicesList();
            loadSubscriptions();
            loadNotifications();
        }
    }, 30000);
});

let isLoggedIn = false;
let lastToastMsg = '';
let lastToastTime = 0;

function initTheme() {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;

    const isDark = () => document.documentElement.getAttribute('data-theme') === 'dark';

    const paintIcon = () => {
        btn.innerHTML = `<i class="fa-solid fa-${isDark() ? 'sun' : 'moon'}"></i>`;
        btn.title = isDark() ? 'Açık temaya geç' : 'Koyu temaya geç';
    };

    paintIcon();
    btn.addEventListener('click', () => {
        if (isDark()) {
            document.documentElement.removeAttribute('data-theme');
            localStorage.setItem('piramit.tema', 'acik');
        } else {
            document.documentElement.setAttribute('data-theme', 'dark');
            localStorage.setItem('piramit.tema', 'koyu');
        }
        paintIcon();
    });
}

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
        localStorage.removeItem('isLoggedIn');
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
    loadRenewals();
    loadOffers();
    loadInbox();
    loadSettings();
    loadInvoicesList();
    loadSubscriptions();
    loadNotifications();
}

function showLoginUI() {
    isLoggedIn = false;
    localStorage.removeItem('isLoggedIn');
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

document.addEventListener('click', (e) => {
    const link = e.target.closest('.client-link');
    if (link) showCustomerDetail(link.dataset.client);
});

function showCustomerDetail(clientName) {
    const urunler = cachedSales.filter(s => s.client_name === clientName);
    document.getElementById('customer-detail-name').innerText = clientName;

    const list = document.getElementById('customer-products-list');
    if (urunler.length === 0) {
        list.innerHTML = '<p class="text-muted p-4 text-center">Bu müşteriye ait ürün bulunamadı.</p>';
    } else {
        list.innerHTML = urunler.map(s => `
            <div class="customer-product-row">
                <div>
                    <strong>${s.product_name}</strong>
                    ${s.license_key ? `<br><code class="text-muted" style="font-size:11px;">${s.license_key}</code>` : ''}
                </div>
                <div class="customer-product-meta">
                    <span class="text-muted">Bitiş: ${s.expiration_date}</span>
                    ${renderStatusPill(s.status)}
                </div>
            </div>
        `).join('');
    }

    document.getElementById('customer-detail-modal').classList.add('active');
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
            loadSubscriptions();
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
        'dashboard-tab': ['Gösterge Paneli', 'Lisans ve fatura durumlarının genel özeti'],
        'sales-tab': ['Lisanslar', 'Kayıtlı lisanslar, süreler ve hatırlatma zamanlamaları'],
        'subscriptions-tab': ['Abonelikler', 'Aylık faturalanan hizmetlerde kayıp müşteri takibi'],
        'offers-tab': ['Teklifler', 'E-posta ile yapılan teklifler ve sonuçları'],
        'invoices-tab': ['Faturalar', 'Vadesi yaklaşan ve geçmiş ödenmemiş faturalar'],
        'inbox-tab': ['Gönderim Geçmişi', 'Sistemin gönderdiği hatırlatma ve test e-postaları'],
        'settings-tab': ['Ayarlar', 'E-posta gönderimi, hesap ve Logo ERP yapılandırması']
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


    const offerModal = document.getElementById('new-offer-modal');
    const openOfferBtn = document.getElementById('open-new-offer-modal');
    if (offerModal && openOfferBtn) {
        openOfferBtn.addEventListener('click', () => {
            document.getElementById('offer-date').value = new Date().toISOString().split('T')[0];
            offerModal.classList.add('active');
        });
        offerModal.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', () => offerModal.classList.remove('active'));
        });
    }

    const customerModal = document.getElementById('customer-detail-modal');
    customerModal.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', () => customerModal.classList.remove('active'));
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
    initLicenseStatusTabs();

    document.getElementById('btn-clear-inbox').addEventListener('click', async () => {
        if (!confirm('Gönderim geçmişini temizlemek istediğinizden emin misiniz?')) return;
        await authFetch('/api/sent-emails/clear', { method: 'POST' });
        loadInbox();
        loadDashboardStats();
        showToast('Gönderim geçmişi temizlendi.');
    });

    document.getElementById('settings-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
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


    const offerForm = document.getElementById('new-offer-form');
    if (offerForm) {
        offerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                client_name: document.getElementById('offer-client').value,
                offer_date: document.getElementById('offer-date').value,
                product_name: document.getElementById('offer-product').value,
                quantity: parseInt(document.getElementById('offer-quantity').value) || 1,
                offer_price: parseFloat(document.getElementById('offer-price').value) || 0,
                currency: document.getElementById('offer-currency').value,
                sales_rep: document.getElementById('offer-rep').value,
                status: document.getElementById('offer-status').value,
                notes: document.getElementById('offer-notes').value
            };
            try {
                const res = await authFetch('/api/offers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.success) {
                    showToast(data.message, 'success');
                    document.getElementById('new-offer-modal').classList.remove('active');
                    offerForm.reset();
                    document.getElementById('offer-quantity').value = 1;
                    loadOffers();
                } else {
                    showToast(data.message, 'error');
                }
            } catch (err) {}
        });
    }

    const offerAy = document.getElementById('offer-month-filter');
    if (offerAy) offerAy.addEventListener('change', renderOffers);

    document.getElementById('btn-test-email').addEventListener('click', async () => {
        const btn = document.getElementById('btn-test-email');
        const eski = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Gönderiliyor...';
        try {
            const res = await authFetch('/api/test-email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ recipients: document.getElementById('setting-internal-recipients').value })
            });
            const data = await res.json();
            showToast(data.message, data.success ? 'success' : 'error');
            if (data.success) loadInbox();
        } catch (e) {
            showToast('Test e-postası gönderilemedi.', 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = eski;
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
            showToast(data.message, data.success ? 'success' : 'error');
            loadDashboardStats();
            loadSalesList();
            loadSubscriptions();
            loadNotifications();
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
        const inboxBadge = document.getElementById('inbox-count-badge');
        inboxBadge.innerText = stats.reminders_sent;
        inboxBadge.style.display = stats.reminders_sent > 0 ? '' : 'none';
    } catch (e) {}
}

let cachedSales = [];

async function loadSalesList() {
    try {
        const res = await authFetch('/api/sales');
        cachedSales = await res.json();
        renderDashboardTable(cachedSales.slice(0, 5));
        durumSayilariniGuncelle();
        filterSalesTable();
    } catch (e) {}
}

function renderStatusPill(status) {
    const map = {
        'NEEDS_DURATION': '<span class="status-pill needs-duration"><i class="fa-solid fa-circle-question"></i> Süre girilmeli</span>',
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


// ============ TEKLIFLER ============
// Renkler durum paleti (kategorik degil): kabul=iyi, ret=kritik, geri
// donmedi=notr. Dilim sirasi bilerek yesil -> notr -> kirmizi: kirmizi ile
// yesil yan yana gelirse deuteranopide ayirt edilemiyor (olcum: dE 4.1).
// Aralarina notr girince en kotu komsu cift dE 11.9'a cikiyor. Renk tek
// basina anlam tasimasin diye her dilimin ikonu, etiketi ve sayisi
// lejantta yaziyla da veriliyor.
const TEKLIF_DURUMLARI = [
    { kod: 'ACCEPTED', ad: 'Kabul',        renk: '#0ca30c', ikon: 'fa-circle-check' },
    { kod: 'PENDING',  ad: 'Geri dönmedi', renk: '#83838f', ikon: 'fa-clock' },
    { kod: 'REJECTED', ad: 'Ret',          renk: '#d03b3b', ikon: 'fa-circle-xmark' },
];

let cachedOffers = [];

async function loadOffers() {
    try {
        const res = await authFetch('/api/offers');
        cachedOffers = await res.json();
        ayFiltresiniDoldur();
        renderOffers();
    } catch (e) {}
}

function ayFiltresiniDoldur() {
    const sec = document.getElementById('offer-month-filter');
    if (!sec) return;
    const oncekiDeger = sec.value;

    const aylar = [...new Set(cachedOffers.map(t => (t.offer_date || '').slice(0, 7)))]
        .filter(Boolean).sort().reverse();
    if (aylar.length === 0) aylar.push(new Date().toISOString().slice(0, 7));

    const adlar = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
                   'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
    sec.innerHTML = aylar.map(a => {
        const [y, m] = a.split('-');
        return `<option value="${a}">${adlar[parseInt(m, 10) - 1]} ${y}</option>`;
    }).join('');

    if (oncekiDeger && aylar.includes(oncekiDeger)) sec.value = oncekiDeger;
}

function renderOffers() {
    const ay = document.getElementById('offer-month-filter')?.value || '';
    const ayinTeklifleri = cachedOffers.filter(t => (t.offer_date || '').startsWith(ay));

    renderOfferDonut(ayinTeklifleri);
    renderOfferTable(cachedOffers);
}

function renderOfferDonut(teklifler) {
    const kap = document.getElementById('offer-donut');
    const lejant = document.getElementById('offer-legend');
    if (!kap) return;

    const sayilar = TEKLIF_DURUMLARI.map(d => ({
        ...d, adet: teklifler.filter(t => t.status === d.kod).length
    }));
    const toplam = sayilar.reduce((s, d) => s + d.adet, 0);

    if (toplam === 0) {
        kap.innerHTML = '<p class="text-muted" style="padding:28px 0">Bu ayda teklif kaydı yok.</p>';
        lejant.innerHTML = '';
        return;
    }

    const R = 78, KALINLIK = 22, C = 100;
    const cevre = 2 * Math.PI * R;
    // Dilimler arasinda 2px yuzey boslugu: sinir cizgisi cizmek yerine
    // bosluk birakiliyor, boylece renk ayrimi kaybolsa da sinir gorunur.
    const BOSLUK = 2;

    let offset = 0;
    const dilimler = sayilar.filter(d => d.adet > 0).map(d => {
        const uzunluk = (d.adet / toplam) * cevre;
        const cizgi = Math.max(uzunluk - BOSLUK, 1);
        const el = `<circle cx="${C}" cy="${C}" r="${R}" fill="none"
            stroke="${d.renk}" stroke-width="${KALINLIK}"
            stroke-dasharray="${cizgi} ${cevre - cizgi}"
            stroke-dashoffset="${-offset}"
            transform="rotate(-90 ${C} ${C})"><title>${d.ad}: ${d.adet}</title></circle>`;
        offset += uzunluk;
        return el;
    }).join('');

    const kabul = sayilar.find(d => d.kod === 'ACCEPTED').adet;
    const oran = Math.round((kabul / toplam) * 100);

    kap.innerHTML = `
      <svg viewBox="0 0 200 200" width="200" height="200" role="img"
           aria-label="Teklif durumları: ${sayilar.map(d => d.ad + ' ' + d.adet).join(', ')}">
        <circle cx="${C}" cy="${C}" r="${R}" fill="none"
                stroke="var(--surface-3)" stroke-width="${KALINLIK}"></circle>
        ${dilimler}
        <text x="${C}" y="${C - 6}" text-anchor="middle"
              style="font-size:30px;font-weight:700;fill:var(--text)">${toplam}</text>
        <text x="${C}" y="${C + 15}" text-anchor="middle"
              style="font-size:12px;fill:var(--text-3)">teklif</text>
      </svg>`;

    // Ikon hem renk hem sekil tasiyor; ayrica bir renk karesi koymak fazlalik.
    lejant.innerHTML = sayilar.map(d => `
        <div class="lejant-satir">
            <i class="fa-solid ${d.ikon}" style="color:${d.renk}"></i>
            <span class="lejant-ad">${d.ad}</span>
            <span class="lejant-sayi">${d.adet}</span>
            <span class="lejant-yuzde">${toplam ? Math.round((d.adet / toplam) * 100) : 0}%</span>
        </div>`).join('') +
        `<p class="lejant-ozet">Kabul oranı: <strong>%${oran}</strong></p>`;
}

function renderOfferTable(teklifler) {
    const tbody = document.querySelector('#offers-table tbody');
    if (!tbody) return;

    if (teklifler.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center p-4 text-muted">Henüz teklif kaydı yok.</td></tr>';
        return;
    }

    tbody.innerHTML = teklifler.map(t => {
        const fiyat = t.offer_price
            ? `${t.offer_price.toLocaleString('tr-TR', { minimumFractionDigits: 2 })} ${t.currency}`
            : '-';
        return `
        <tr>
            <td>${t.offer_date}</td>
            <td><strong>${t.client_name}</strong></td>
            <td>${t.product_name}</td>
            <td>${t.quantity}</td>
            <td><strong>${fiyat}</strong></td>
            <td>${t.sales_rep || '-'}</td>
            <td>
                <select class="teklif-durum-sec" onchange="teklifDurumGuncelle(${t.id}, this.value)">
                    ${TEKLIF_DURUMLARI.map(o => `
                        <option value="${o.kod}" ${o.kod === t.status ? 'selected' : ''}>${o.ad}</option>
                    `).join('')}
                </select>
            </td>
            <td>
                <button class="btn btn-sm btn-danger-outline" onclick="teklifSil(${t.id})" title="Sil">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </td>
        </tr>`;
    }).join('');
}

async function teklifDurumGuncelle(offerId, durum) {
    try {
        const res = await authFetch(`/api/offers/${offerId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: durum })
        });
        const data = await res.json();
        showToast(data.message, data.success ? 'success' : 'error');
        if (data.success) {
            const t = cachedOffers.find(x => x.id === offerId);
            if (t) t.status = durum;
            renderOffers();
        }
    } catch (e) {}
}

async function teklifSil(offerId) {
    if (!confirm('Bu teklif kaydını silmek istediğinize emin misiniz?')) return;
    try {
        const res = await authFetch(`/api/offers/${offerId}`, { method: 'DELETE' });
        const data = await res.json();
        showToast(data.message);
        loadOffers();
    } catch (e) {}
}

let cachedRenewals = [];

async function loadRenewals() {
    try {
        const res = await authFetch('/api/renewals');
        cachedRenewals = await res.json();
        const rozet = document.getElementById('count-RENEWAL');
        if (rozet) rozet.innerText = cachedRenewals.length;
    } catch (e) {}
}

function renderRenewals(query) {
    const kap = document.getElementById('license-groups');
    if (!kap) return;

    const liste = cachedRenewals.filter(r => !query ||
        r.musteri.toLowerCase().includes(query) ||
        r.eski_urun.toLowerCase().includes(query) ||
        r.yeni_urun.toLowerCase().includes(query));

    if (liste.length === 0) {
        kap.innerHTML = '<div class="card glass-card"><div class="card-body text-center text-muted">' +
                        'Onay bekleyen yenileme yok.</div></div>';
        return;
    }

    kap.innerHTML = `
      <div class="card glass-card mb-4">
        <div class="card-body" style="padding:16px 20px">
          <p class="text-muted" style="margin:0;font-size:13.5px">
            Bu kayıtların süresi dolmuş görünüyor, ama aynı müşteriye daha sonra
            benzer bir ürün satılmış. Ürün kodları değiştiği için eşleşme kesin değil —
            doğruysa onaylayın, değilse reddedin (kayıt "süresi doldu" listesinde kalır).
          </p>
        </div>
      </div>` +
      liste.map(r => `
        <div class="card glass-card musteri-grup" id="renewal-${r.eski_id}">
            <div class="card-header musteri-grup-bas">
                <h3><i class="fa-solid fa-building"></i> ${r.musteri}</h3>
                <div class="flex-gap-2">
                    <button class="btn btn-sm btn-primary" onclick="karaVerRenewal(${r.eski_id}, 'CONFIRMED')">
                        <i class="fa-solid fa-check"></i> Yenilenmiş
                    </button>
                    <button class="btn btn-sm btn-danger-outline" onclick="karaVerRenewal(${r.eski_id}, 'REJECTED')">
                        <i class="fa-solid fa-xmark"></i> Değil
                    </button>
                </div>
            </div>
            <div class="card-body">
                <div class="yenileme-kiyas">
                    <div class="yenileme-kutu eski">
                        <span class="yenileme-etiket">Süresi dolan</span>
                        <strong>${r.eski_urun}</strong>
                        <span class="text-muted">${r.eski_satis} → ${r.eski_bitis}</span>
                    </div>
                    <i class="fa-solid fa-arrow-right yenileme-ok"></i>
                    <div class="yenileme-kutu yeni">
                        <span class="yenileme-etiket">Yerine geçmiş olabilir</span>
                        <strong>${r.yeni_urun}</strong>
                        <span class="text-muted">${r.yeni_satis} → ${r.yeni_bitis}</span>
                    </div>
                </div>
            </div>
        </div>`).join('');
}

async function karaVerRenewal(saleId, karar) {
    try {
        const res = await authFetch(`/api/sales/${saleId}/renewal`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ karar })
        });
        const data = await res.json();
        showToast(data.message, data.success ? 'success' : 'error');
        if (data.success) {
            cachedRenewals = cachedRenewals.filter(r => r.eski_id !== saleId);
            await loadSalesList();
            filterSalesTable();
        }
    } catch (e) {}
}

let aktifDurum = 'PENDING';

function initLicenseStatusTabs() {
    document.querySelectorAll('#license-status-tabs .status-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#license-status-tabs .status-tab')
                .forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            aktifDurum = btn.dataset.status;
            filterSalesTable();
        });
    });
}

// PENDING sekmesi hatirlatmasi gonderilmis olanlari da kapsar: hepsi hala
// "yenilenmeyi bekliyor" durumunda, sadece bildirim asamasi farkli.
const DURUM_GRUPLARI = {
    PENDING: ['PENDING', 'FIRST_REMINDER_SENT', 'FINAL_REMINDER_SENT'],
    NEEDS_DURATION: ['NEEDS_DURATION'],
    EXPIRED: ['EXPIRED'],
};

function durumSayilariniGuncelle() {
    const say = (durumlar) => cachedSales.filter(s => durumlar.includes(s.status)).length;
    document.getElementById('count-PENDING').innerText = say(DURUM_GRUPLARI.PENDING);
    document.getElementById('count-NEEDS_DURATION').innerText = say(DURUM_GRUPLARI.NEEDS_DURATION);
    document.getElementById('count-EXPIRED').innerText = say(DURUM_GRUPLARI.EXPIRED);
    document.getElementById('count-RENEWAL').innerText = cachedRenewals.length;
    document.getElementById('count-ALL').innerText = cachedSales.length;
}

function renderLicenseGroups(sales) {
    const kap = document.getElementById('license-groups');
    if (!kap) return;

    if (sales.length === 0) {
        kap.innerHTML = '<div class="card glass-card"><div class="card-body text-center text-muted">' +
                        'Bu başlıkta kayıt yok.</div></div>';
        return;
    }

    // Ayni musteriye satilanlar tek kart altinda toplanir.
    const gruplar = new Map();
    sales.forEach(s => {
        if (!gruplar.has(s.client_name)) gruplar.set(s.client_name, []);
        gruplar.get(s.client_name).push(s);
    });

    // En acil musteri en ustte: gruptaki en az kalan gune gore siralanir.
    const sirali = [...gruplar.entries()].sort((a, b) => {
        const enAz = (liste) => Math.min(...liste.map(x => x.days_left));
        return enAz(a[1]) - enAz(b[1]);
    });

    kap.innerHTML = sirali.map(([musteri, urunler]) => {
        const enAzGun = Math.min(...urunler.map(u => u.days_left));
        const mail = urunler.find(u => u.client_email)?.client_email || '';
        const temsilci = urunler.find(u => u.sales_rep)?.sales_rep || '';

        const satirlar = urunler.map(u => `
            <tr>
                <td>
                    <strong>${u.product_name}</strong>
                    ${u.license_key ? `<br><code class="text-muted" style="font-size:11px;">${u.license_key}</code>` : ''}
                </td>
                <td>${u.sale_date}</td>
                <td>${u.duration_months ? u.duration_months + ' Ay' : '-'}</td>
                <td><strong>${u.expiration_date}</strong></td>
                <td><strong class="${gunRengi(u.days_left)}">${u.days_left} Gün</strong></td>
                <td>${renderStatusPill(u.status)}</td>
                <td>
                    <div class="flex-gap-2">
                        <button class="btn btn-sm btn-outline-primary" onclick="sendTestEmail(${u.id})" title="Hatırlatma gönder">
                            <i class="fa-solid fa-paper-plane"></i>
                        </button>
                        <button class="btn btn-sm btn-danger-outline" onclick="deleteSale(${u.id})" title="Sil">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');

        return `
        <div class="card glass-card musteri-grup">
            <div class="card-header musteri-grup-bas">
                <div>
                    <h3><i class="fa-solid fa-building"></i> ${musteri}</h3>
                    <p class="text-muted">
                        ${urunler.length} ürün
                        ${temsilci ? ' · Satış temsilcisi: ' + temsilci : ''}
                        ${mail ? ' · ' + mail : ''}
                    </p>
                </div>
                <span class="musteri-grup-rozet ${gunRengi(enAzGun)}">
                    ${enAzGun < 0 ? Math.abs(enAzGun) + ' gün geçti' : 'En yakın: ' + enAzGun + ' gün'}
                </span>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="custom-table">
                        <thead>
                            <tr>
                                <th>Ürün / Lisans</th>
                                <th>Satış Tarihi</th>
                                <th>Süre</th>
                                <th>Bitiş Tarihi</th>
                                <th>Kalan Gün</th>
                                <th>Durum</th>
                                <th>İşlemler</th>
                            </tr>
                        </thead>
                        <tbody>${satirlar}</tbody>
                    </table>
                </div>
            </div>
        </div>`;
    }).join('');
}

function gunRengi(gun) {
    if (gun < 0) return 'text-danger';
    if (gun <= 7) return 'text-danger';
    if (gun <= 30) return 'text-warning';
    return 'text-success';
}

function filterSalesTable() {
    const query = (document.getElementById('sales-search-input')?.value || '').toLowerCase();

    if (aktifDurum === 'RENEWAL') {
        renderRenewals(query);
        return;
    }

    const durumlar = DURUM_GRUPLARI[aktifDurum];

    const filtered = cachedSales.filter(s => {
        const aramaUydu = !query ||
            s.product_name.toLowerCase().includes(query) ||
            s.client_name.toLowerCase().includes(query) ||
            (s.license_key && s.license_key.toLowerCase().includes(query));
        const durumUydu = !durumlar || durumlar.includes(s.status);
        return aramaUydu && durumUydu;
    });

    renderLicenseGroups(filtered);
}

async function sendTestEmail(saleId) {
    if (!confirm('Bu lisans için muhasebe/satış ekibine hatırlatma e-postası gönderilsin mi?')) return;

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

async function setDuration(saleId) {
    const kayit = cachedSales.find(s => s.id === saleId);
    const girdi = prompt(
        `"${kayit ? kayit.product_name : ''}"\n\n` +
        'Bu lisansın süresi kaç AY? (1 yıl = 12, 3 yıl = 36)',
        '12'
    );
    if (girdi === null) return;

    const ay = parseInt(girdi, 10);
    if (!ay || ay < 1) {
        showToast('Geçerli bir ay sayısı girin.', 'error');
        return;
    }

    try {
        const res = await authFetch(`/api/sales/${saleId}/set-duration`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ duration_months: ay })
        });
        const data = await res.json();
        showToast(data.message, data.success ? 'success' : 'error');
        if (data.success) {
            loadSalesList();
            loadDashboardStats();
            loadNotifications();
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
            listContainer.innerHTML = '<div class="p-4 text-center text-muted">Henüz e-posta gönderilmedi.</div>';
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

async function loadSettings() {
    try {
        const res = await authFetch('/api/settings');
        const settings = await res.json();

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
    if (!confirm('Bu fatura için muhasebe/satış ekibine hatırlatma e-postası gönderilsin mi?')) return;
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

async function loadSubscriptions() {
    try {
        const res = await authFetch('/api/subscriptions');
        const abonelikler = await res.json();

        const say = (d) => abonelikler.filter(a => a.status === d).length;
        document.getElementById('stat-subs-active').innerText = say('ACTIVE');
        document.getElementById('stat-subs-risk').innerText = say('AT_RISK');
        document.getElementById('stat-subs-lost').innerText = say('LOST');

        const rozet = document.getElementById('subscription-alert-badge');
        const dikkat = say('AT_RISK');
        rozet.innerText = dikkat;
        rozet.style.display = dikkat > 0 ? '' : 'none';

        const tbody = document.querySelector('#subscriptions-table tbody');
        if (abonelikler.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center p-4 text-muted">' +
                'Abonelik kaydı yok. Ayarlar sekmesinden Logo aktarımı yapın.</td></tr>';
            return;
        }

        const durumRozeti = {
            ACTIVE: '<span class="status-pill first-sent"><i class="fa-solid fa-circle-check"></i> Aktif</span>',
            AT_RISK: '<span class="status-pill final-sent"><i class="fa-solid fa-triangle-exclamation"></i> Riskli</span>',
            LOST: '<span class="status-pill expired"><i class="fa-solid fa-user-slash"></i> Kayıp görünüyor</span>'
        };

        tbody.innerHTML = abonelikler.map(a => `
            <tr>
                <td>
                    <strong>${a.client_name}</strong>
                    ${a.client_email ? `<br><small class="text-muted">${a.client_email}</small>` : ''}
                </td>
                <td>${a.product_name}</td>
                <td>${a.invoice_count}</td>
                <td>${a.avg_interval_days ? Math.round(a.avg_interval_days) + ' gün' : '-'}</td>
                <td>${a.last_invoice_date}</td>
                <td><strong class="${a.status === 'LOST' ? 'text-danger' : (a.status === 'AT_RISK' ? 'text-warning' : '')}">${a.days_since_last} gün</strong></td>
                <td>${durumRozeti[a.status] || a.status}</td>
            </tr>
        `).join('');
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

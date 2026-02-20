// === 공통 인증 유틸 ===

let currentUser = null;

async function checkAuth() {
    try {
        const resp = await fetch('/api/auth/me');
        if (!resp.ok) {
            if (window.location.pathname !== '/login') {
                window.location.href = '/login';
            }
            return null;
        }
        currentUser = await resp.json();
        updateNavForRole(currentUser.role);
        return currentUser;
    } catch (e) {
        if (window.location.pathname !== '/login') {
            window.location.href = '/login';
        }
        return null;
    }
}

function updateNavForRole(role) {
    // 관리 링크 숨김 (비관리자)
    document.querySelectorAll('.admin-only').forEach(el => {
        el.style.display = role === 'admin' ? '' : 'none';
    });

    // 유저 정보 표시
    const userInfo = document.getElementById('navUserInfo');
    const usernameEl = document.getElementById('navUsername');
    if (userInfo && usernameEl) {
        usernameEl.textContent = currentUser.display_name || currentUser.username;
        userInfo.style.display = 'flex';
    }
}

async function doLogout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/login';
}

function getAuthHeaders() {
    // Cookie는 httpOnly이므로 same-origin 요청에 자동 포함
    return {};
}

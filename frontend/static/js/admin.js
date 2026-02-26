// admin.js — auth.js의 checkAuth()를 사용

// === 페이지네이션 상태 ===
const PAGE_SIZE = 10;
let docPage = 1;
let docTotalPages = 1;
let allDocuments = [];
let userPage = 1;
let userTotalPages = 1;
let allUsers = [];

// === 초기화 ===
document.addEventListener('DOMContentLoaded', async () => {
    // 업로드 영역 초기 상태 보장
    resetUploadUI();

    // 인증 확인 (auth.js)
    const user = await checkAuth();
    if (!user) return; // 미인증 → login 리다이렉트
    if (user.role !== 'admin') {
        window.location.href = '/';
        return;
    }

    // 데이터 로드
    loadStatus();
    loadDocuments();
    loadBaseDirs();
    loadUsers();
});

function resetUploadUI() {
    const uploadArea = document.getElementById('uploadArea');
    const uploadProgress = document.getElementById('uploadProgress');
    if (uploadArea) uploadArea.style.display = '';
    if (uploadProgress) uploadProgress.style.display = 'none';
}

// === 모달 ===
function showModal(id) {
    document.getElementById(id).style.display = 'flex';
}

function closeModal(id) {
    document.getElementById(id).style.display = 'none';
}

// === 시스템 상태 ===
async function loadStatus() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        document.getElementById('docCount').textContent = data.document_count || 0;
        document.getElementById('chunkCount').textContent = data.total_chunks || 0;
        document.getElementById('llmProvider').textContent = data.llm_provider || '-';

        // NAS 상태
        const nasStatusEl = document.getElementById('nasStatus');
        if (data.nas_connected) {
            nasStatusEl.textContent = '연결됨';
            nasStatusEl.style.color = 'var(--success, #22c55e)';
        } else {
            nasStatusEl.textContent = '미연결';
            nasStatusEl.style.color = 'var(--text-secondary)';
        }
        document.getElementById('baseDirCount').textContent = data.nas_base_dir_count || 0;
    } catch (e) {
        console.error('상태 로드 실패:', e);
    }
}

// === 문서 관리 ===
async function loadDocuments() {
    const listDiv = document.getElementById('docList');
    const countEl = document.getElementById('docTotalCount');

    try {
        const response = await fetch('/api/documents');
        if (!response.ok) throw new Error('인증 필요');

        const data = await response.json();
        allDocuments = data.documents || [];

        if (allDocuments.length === 0) {
            listDiv.innerHTML = '<div class="empty-state">등록된 문서가 없습니다.</div>';
            countEl.textContent = '';
            document.getElementById('docPagination').style.display = 'none';
            return;
        }

        countEl.textContent = `${allDocuments.length}건`;
        docTotalPages = Math.ceil(allDocuments.length / PAGE_SIZE);
        if (docPage > docTotalPages) docPage = docTotalPages;
        renderDocPage();
    } catch (e) {
        listDiv.innerHTML = '<div class="empty-state">문서 목록을 불러올 수 없습니다.</div>';
        countEl.textContent = '';
    }
}

function renderDocPage() {
    const listDiv = document.getElementById('docList');
    const start = (docPage - 1) * PAGE_SIZE;
    const pageItems = allDocuments.slice(start, start + PAGE_SIZE);

    let html = '<table class="doc-table"><thead><tr>';
    html += '<th>파일명</th><th>업로드 일시</th><th>청크 수</th><th>상태</th><th>작업</th>';
    html += '</tr></thead><tbody>';

    for (const doc of pageItems) {
        const date = new Date(doc.uploaded_at).toLocaleDateString('ko-KR');
        html += `<tr>
            <td title="${escapeAttr(doc.filename)}">${escapeAttr(doc.filename)}</td>
            <td>${date}</td>
            <td>${doc.total_chunks}</td>
            <td><span class="status-badge ${doc.status}">${doc.status}</span></td>
            <td><button class="btn btn-danger btn-sm" onclick="deleteDocument('${doc.id}', '${escapeAttr(doc.filename)}')">삭제</button></td>
        </tr>`;
    }

    html += '</tbody></table>';
    listDiv.innerHTML = html;

    renderPagination('docPagination', docPage, docTotalPages, (p) => {
        docPage = p;
        renderDocPage();
    });
}

function handleDrop(event) {
    event.preventDefault();
    event.target.classList.remove('dragover');
    const files = event.dataTransfer.files;
    if (files.length > 0) uploadMultipleFiles(Array.from(files));
}

function handleFileSelect(event) {
    const files = event.target.files;
    if (files.length > 0) uploadMultipleFiles(Array.from(files));
    event.target.value = '';
}

async function uploadMultipleFiles(files) {
    for (const file of files) {
        await uploadFile(file);
    }
}

function generateTaskId() {
    return 'task_' + Math.random().toString(36).substring(2, 10);
}

function formatTime(seconds) {
    seconds = Math.max(0, Math.round(seconds));
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}시간 ${m}분 ${s}초`;
    if (m > 0) return `${m}분 ${s}초`;
    return `${s}초`;
}

function startProgressPolling(taskId, barId, textId) {
    const bar = document.getElementById(barId);
    const text = document.getElementById(textId);
    let firstProgressTime = null;
    let firstProgressPct = 0;

    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/api/documents/progress/${taskId}`);
            const data = await res.json();
            if (data.step === 'error') {
                bar.style.width = '100%';
                bar.classList.add('error');
                text.textContent = data.detail || '오류 발생';
            } else if (data.percent > 0) {
                bar.classList.remove('error');
                bar.style.width = data.percent + '%';
                const detail = data.detail || data.step;

                let eta = '';
                if (data.percent < 100) {
                    if (!firstProgressTime && data.percent > 5) {
                        firstProgressTime = Date.now();
                        firstProgressPct = data.percent;
                    }
                    if (firstProgressTime && data.percent > firstProgressPct) {
                        const elapsed = (Date.now() - firstProgressTime) / 1000;
                        const pctDone = data.percent - firstProgressPct;
                        const pctLeft = 100 - data.percent;
                        const remaining = (elapsed / pctDone) * pctLeft;
                        eta = ` — 약 ${formatTime(remaining)} 남음`;
                    }
                }
                text.textContent = `${detail} (${data.percent}%)${eta}`;
            }
        } catch (e) { /* ignore */ }
    }, 500);
    return interval;
}

async function uploadFile(file) {
    const maxMB = window.MAX_UPLOAD_SIZE_MB || 200;
    if (file.size > maxMB * 1024 * 1024) {
        showUploadAlert(`파일 크기는 ${maxMB}MB 이하여야 합니다.`, 'error');
        return;
    }

    const progressDiv = document.getElementById('uploadProgress');
    const uploadArea = document.getElementById('uploadArea');
    const bar = document.getElementById('uploadProgressBar');
    const text = document.getElementById('uploadProgressText');

    bar.style.width = '0%';
    text.textContent = '업로드 중...';
    progressDiv.style.display = 'block';
    uploadArea.style.display = 'none';

    const taskId = generateTaskId();
    const pollInterval = startProgressPolling(taskId, 'uploadProgressBar', 'uploadProgressText');

    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('task_id', taskId);

        const response = await fetch('/api/documents/upload', {
            method: 'POST',
            body: formData,
        });

        const data = await response.json();

        if (response.ok) {
            bar.style.width = '100%';
            bar.classList.remove('error');
            text.textContent = '완료!';
            showUploadAlert(`${data.filename} 업로드 완료! (${data.total_chunks}개 청크)`, 'success');
            loadDocuments();
            loadStatus();
        } else {
            bar.style.width = '100%';
            bar.classList.add('error');
            text.textContent = '업로드 실패';
            showUploadAlert(data.detail || '업로드 실패', 'error');
            loadDocuments();
        }
    } catch (error) {
        bar.style.width = '100%';
        bar.classList.add('error');
        text.textContent = '오류 발생';
        showUploadAlert('업로드 중 오류가 발생했습니다.', 'error');
    } finally {
        clearInterval(pollInterval);
        setTimeout(() => {
            progressDiv.style.display = 'none';
            uploadArea.style.display = 'block';
            bar.classList.remove('error');
        }, 2000);
    }
}

function showUploadAlert(message, type) {
    const alertDiv = document.getElementById('uploadAlert');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    alertDiv.style.display = 'block';
    setTimeout(() => { alertDiv.style.display = 'none'; }, 5000);
}

async function deleteDocument(docId, filename) {
    if (!confirm(`"${filename}" 문서를 삭제하시겠습니까?`)) return;

    try {
        const response = await fetch(`/api/documents/${docId}`, { method: 'DELETE' });

        if (response.ok) {
            loadDocuments();
            loadStatus();
        } else {
            alert('문서 삭제에 실패했습니다.');
        }
    } catch (error) {
        alert('오류가 발생했습니다.');
    }
}

// === NAS 기본 디렉토리 관리 ===

async function loadBaseDirs() {
    const listDiv = document.getElementById('baseDirList');

    try {
        const response = await fetch('/api/nas/base-dirs');
        if (!response.ok) throw new Error('인증 필요');

        const dirs = await response.json();

        if (dirs.length === 0) {
            listDiv.innerHTML = '<div class="empty-state">등록된 기본 디렉토리가 없습니다.</div>';
            return;
        }

        let html = '';
        for (const d of dirs) {
            const date = d.created_at ? new Date(d.created_at).toLocaleDateString('ko-KR') : '';
            html += `<div class="nas-path-item">
                <div class="path-info">
                    <div class="path-name">${escapeAttr(d.label)}</div>
                    <div class="path-location">${escapeAttr(d.path)}</div>
                    ${d.description ? `<div class="path-desc">${escapeAttr(d.description)}</div>` : ''}
                    ${date ? `<div class="path-date">등록일: ${date}</div>` : ''}
                </div>
                <button class="btn btn-danger btn-sm" onclick="deleteBaseDir('${d.id}')">삭제</button>
            </div>`;
        }
        listDiv.innerHTML = html;
    } catch (e) {
        listDiv.innerHTML = '<div class="empty-state">디렉토리 목록을 불러올 수 없습니다.</div>';
    }
}

async function validateBaseDirPath() {
    const path = document.getElementById('baseDirPath').value.trim();
    const label = document.getElementById('baseDirLabel').value.trim() || path;
    const alertDiv = document.getElementById('baseDirAlert');

    if (!path) {
        alert('NAS 경로를 입력하세요.');
        return;
    }

    try {
        const response = await fetch('/api/nas/base-dirs/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path, label }),
        });
        const data = await response.json();

        if (response.ok && data.exists) {
            alertDiv.className = 'alert alert-success';
            alertDiv.textContent = `경로 확인됨: ${path}`;
        } else if (response.ok) {
            alertDiv.className = 'alert alert-error';
            alertDiv.textContent = `경로가 NAS에 존재하지 않습니다: ${path}`;
        } else {
            alertDiv.className = 'alert alert-error';
            alertDiv.textContent = data.detail || '경로 확인 실패';
        }
        alertDiv.style.display = 'block';
        setTimeout(() => { alertDiv.style.display = 'none'; }, 5000);
    } catch (error) {
        alertDiv.className = 'alert alert-error';
        alertDiv.textContent = 'NAS 연결에 실패했습니다.';
        alertDiv.style.display = 'block';
        setTimeout(() => { alertDiv.style.display = 'none'; }, 5000);
    }
}

async function addBaseDir() {
    const path = document.getElementById('baseDirPath').value.trim();
    const label = document.getElementById('baseDirLabel').value.trim();
    const description = document.getElementById('baseDirDesc').value.trim();
    const alertDiv = document.getElementById('baseDirAlert');

    if (!path || !label) {
        alert('NAS 경로와 표시 이름은 필수입니다.');
        return;
    }

    try {
        const response = await fetch('/api/nas/base-dirs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path, label, description }),
        });

        if (response.ok) {
            document.getElementById('baseDirPath').value = '';
            document.getElementById('baseDirLabel').value = '';
            document.getElementById('baseDirDesc').value = '';
            alertDiv.className = 'alert alert-success';
            alertDiv.textContent = '디렉토리가 추가되었습니다.';
            alertDiv.style.display = 'block';
            setTimeout(() => { alertDiv.style.display = 'none'; }, 3000);
            loadBaseDirs();
            loadStatus();
        } else {
            const data = await response.json();
            alertDiv.className = 'alert alert-error';
            alertDiv.textContent = data.detail || '디렉토리 추가에 실패했습니다.';
            alertDiv.style.display = 'block';
            setTimeout(() => { alertDiv.style.display = 'none'; }, 5000);
        }
    } catch (error) {
        alert('오류가 발생했습니다.');
    }
}

async function deleteBaseDir(dirId) {
    if (!confirm('이 기본 디렉토리를 제거하시겠습니까?')) return;

    try {
        const response = await fetch(`/api/nas/base-dirs/${dirId}`, { method: 'DELETE' });

        if (response.ok) {
            loadBaseDirs();
            loadStatus();
        } else {
            alert('디렉토리 제거에 실패했습니다.');
        }
    } catch (error) {
        alert('오류가 발생했습니다.');
    }
}

// === 사용자 관리 ===

async function loadUsers() {
    const listDiv = document.getElementById('userList');
    const countEl = document.getElementById('userTotalCount');

    try {
        const response = await fetch('/api/admin/users');
        if (!response.ok) throw new Error('권한 없음');

        const data = await response.json();
        allUsers = data.users || [];

        if (allUsers.length === 0) {
            listDiv.innerHTML = '<div class="empty-state">등록된 사용자가 없습니다.</div>';
            countEl.textContent = '';
            document.getElementById('userPagination').style.display = 'none';
            return;
        }

        countEl.textContent = `${allUsers.length}명`;
        userTotalPages = Math.ceil(allUsers.length / PAGE_SIZE);
        if (userPage > userTotalPages) userPage = userTotalPages;
        renderUserPage();
    } catch (e) {
        listDiv.innerHTML = '<div class="empty-state">사용자 목록을 불러올 수 없습니다.</div>';
        countEl.textContent = '';
    }
}

function renderUserPage() {
    const listDiv = document.getElementById('userList');
    const start = (userPage - 1) * PAGE_SIZE;
    const pageItems = allUsers.slice(start, start + PAGE_SIZE);

    let html = '<table class="doc-table"><thead><tr>';
    html += '<th>아이디</th><th>이름</th><th>역할</th><th>생성일</th><th>작업</th>';
    html += '</tr></thead><tbody>';

    for (const u of pageItems) {
        const date = new Date(u.created_at).toLocaleDateString('ko-KR');
        const roleBadge = u.role === 'admin'
            ? '<span class="status-badge stored">관리자</span>'
            : '<span class="status-badge indexed">사용자</span>';
        const actions = u.username === 'admin'
            ? '<span class="default-account-label">기본 계정</span>'
            : `<button class="btn btn-secondary btn-sm" onclick="showResetPassword(${u.id}, '${escapeAttr(u.display_name || u.username)}')">비밀번호</button>
               <button class="btn btn-danger btn-sm" onclick="deleteUser(${u.id}, '${escapeAttr(u.username)}')">삭제</button>`;

        html += `<tr>
            <td>${escapeAttr(u.username)}</td>
            <td>${escapeAttr(u.display_name || '-')}</td>
            <td>${roleBadge}</td>
            <td>${date}</td>
            <td class="actions-cell">${actions}</td>
        </tr>`;
    }

    html += '</tbody></table>';
    listDiv.innerHTML = html;

    renderPagination('userPagination', userPage, userTotalPages, (p) => {
        userPage = p;
        renderUserPage();
    });
}

// === 페이지네이션 렌더링 ===
function renderPagination(containerId, currentPage, totalPages, onPageChange) {
    const container = document.getElementById(containerId);

    if (totalPages <= 1) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'flex';
    container.innerHTML = '';

    // 이전 버튼
    const prevBtn = document.createElement('button');
    prevBtn.className = 'pagination-btn';
    prevBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>';
    prevBtn.disabled = currentPage === 1;
    prevBtn.onclick = () => onPageChange(currentPage - 1);
    container.appendChild(prevBtn);

    // 페이지 번호 (최대 7개 표시)
    const pages = getPageNumbers(currentPage, totalPages);
    for (const p of pages) {
        if (p === '...') {
            const ellipsis = document.createElement('span');
            ellipsis.className = 'pagination-ellipsis';
            ellipsis.textContent = '...';
            container.appendChild(ellipsis);
        } else {
            const btn = document.createElement('button');
            btn.className = 'pagination-btn' + (p === currentPage ? ' active' : '');
            btn.textContent = p;
            btn.onclick = () => onPageChange(p);
            container.appendChild(btn);
        }
    }

    // 다음 버튼
    const nextBtn = document.createElement('button');
    nextBtn.className = 'pagination-btn';
    nextBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>';
    nextBtn.disabled = currentPage === totalPages;
    nextBtn.onclick = () => onPageChange(currentPage + 1);
    container.appendChild(nextBtn);
}

function getPageNumbers(current, total) {
    if (total <= 7) {
        return Array.from({ length: total }, (_, i) => i + 1);
    }

    const pages = [];
    if (current <= 4) {
        for (let i = 1; i <= 5; i++) pages.push(i);
        pages.push('...', total);
    } else if (current >= total - 3) {
        pages.push(1, '...');
        for (let i = total - 4; i <= total; i++) pages.push(i);
    } else {
        pages.push(1, '...');
        for (let i = current - 1; i <= current + 1; i++) pages.push(i);
        pages.push('...', total);
    }

    return pages;
}

// === 유틸리티 ===

function escapeAttr(text) {
    if (!text) return '';
    return text.replace(/&/g, '&amp;').replace(/'/g, '&#39;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

async function createUser() {
    const username = document.getElementById('newUsername').value.trim();
    const display_name = document.getElementById('newDisplayName').value.trim();
    const password = document.getElementById('newPassword').value;
    const role = document.getElementById('newRole').value;

    if (!username || !password) {
        alert('아이디와 비밀번호는 필수입니다.');
        return;
    }

    try {
        const response = await fetch('/api/admin/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, display_name, password, role }),
        });

        if (response.ok) {
            closeModal('createUserModal');
            document.getElementById('newUsername').value = '';
            document.getElementById('newDisplayName').value = '';
            document.getElementById('newPassword').value = '';
            document.getElementById('newRole').value = 'user';
            loadUsers();
        } else {
            const data = await response.json();
            alert(data.detail || '사용자 생성에 실패했습니다.');
        }
    } catch (error) {
        alert('오류가 발생했습니다.');
    }
}

function showResetPassword(userId, displayName) {
    document.getElementById('resetTargetId').value = userId;
    document.getElementById('resetTargetName').textContent = displayName;
    document.getElementById('resetNewPassword').value = '';
    showModal('resetPasswordModal');
}

async function confirmResetPassword() {
    const userId = document.getElementById('resetTargetId').value;
    const newPassword = document.getElementById('resetNewPassword').value;

    if (!newPassword) {
        alert('새 비밀번호를 입력하세요.');
        return;
    }

    try {
        const response = await fetch(`/api/admin/users/${userId}/password`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_password: newPassword }),
        });

        if (response.ok) {
            closeModal('resetPasswordModal');
            alert('비밀번호가 변경되었습니다.');
        } else {
            const data = await response.json();
            alert(data.detail || '비밀번호 변경에 실패했습니다.');
        }
    } catch (error) {
        alert('오류가 발생했습니다.');
    }
}

async function deleteUser(userId, username) {
    if (!confirm(`"${username}" 사용자를 삭제하시겠습니까?`)) return;

    try {
        const response = await fetch(`/api/admin/users/${userId}`, { method: 'DELETE' });

        if (response.ok) {
            loadUsers();
        } else {
            const data = await response.json();
            alert(data.detail || '사용자 삭제에 실패했습니다.');
        }
    } catch (error) {
        alert('오류가 발생했습니다.');
    }
}

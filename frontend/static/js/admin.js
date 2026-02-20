// admin.js — auth.js의 checkAuth()를 사용

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
    loadNasPaths();
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
        document.getElementById('nasFileCount').textContent = data.nas_file_count || 0;
    } catch (e) {
        console.error('상태 로드 실패:', e);
    }
}

// === 문서 관리 ===
async function loadDocuments() {
    const listDiv = document.getElementById('docList');

    try {
        const response = await fetch('/api/documents');
        if (!response.ok) throw new Error('인증 필요');

        const data = await response.json();

        if (data.documents.length === 0) {
            listDiv.innerHTML = '<div class="empty-state">등록된 문서가 없습니다.</div>';
            return;
        }

        let html = '<table class="doc-table"><thead><tr>';
        html += '<th>파일명</th><th>업로드 일시</th><th>청크 수</th><th>상태</th><th>작업</th>';
        html += '</tr></thead><tbody>';

        for (const doc of data.documents) {
            const date = new Date(doc.uploaded_at).toLocaleDateString('ko-KR');
            html += `<tr>
                <td>${doc.filename}</td>
                <td>${date}</td>
                <td>${doc.total_chunks}</td>
                <td><span class="status-badge ${doc.status}">${doc.status}</span></td>
                <td><button class="btn btn-danger btn-sm" onclick="deleteDocument('${doc.id}', '${doc.filename}')">삭제</button></td>
            </tr>`;
        }

        html += '</tbody></table>';
        listDiv.innerHTML = html;
    } catch (e) {
        listDiv.innerHTML = '<div class="empty-state">문서 목록을 불러올 수 없습니다.</div>';
    }
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

// === 파일 동기화 ===

async function syncFiles() {
    const btn = document.getElementById('syncBtn');
    const statusEl = document.getElementById('syncStatus');
    const alertDiv = document.getElementById('syncAlert');

    btn.disabled = true;
    btn.textContent = '동기화 중...';
    statusEl.textContent = '파일 스캔 및 인덱싱 진행 중...';

    try {
        const response = await fetch('/api/files/sync', { method: 'POST' });
        const data = await response.json();

        if (response.ok) {
            const parts = [];
            if (data.indexed > 0) parts.push(`${data.indexed}개 인덱싱`);
            if (data.removed > 0) parts.push(`${data.removed}개 제거`);
            if (data.skipped > 0) parts.push(`${data.skipped}개 스킵`);

            const msg = parts.length > 0
                ? `동기화 완료: ${parts.join(', ')}`
                : '변경 사항이 없습니다. 이미 최신 상태입니다.';

            alertDiv.className = 'alert alert-success';
            alertDiv.textContent = msg;
            alertDiv.style.display = 'block';
            statusEl.textContent = '';
            loadStatus();
        } else {
            alertDiv.className = 'alert alert-error';
            alertDiv.textContent = data.detail || '동기화 실패';
            alertDiv.style.display = 'block';
            statusEl.textContent = '';
        }
    } catch (error) {
        alertDiv.className = 'alert alert-error';
        alertDiv.textContent = '동기화 중 오류가 발생했습니다.';
        alertDiv.style.display = 'block';
        statusEl.textContent = '';
    } finally {
        btn.disabled = false;
        btn.textContent = '동기화 실행';
        setTimeout(() => { alertDiv.style.display = 'none'; }, 8000);
    }
}

// === NAS 경로 관리 ===
async function loadNasPaths() {
    const listDiv = document.getElementById('nasPathList');

    try {
        const response = await fetch('/api/nas/paths');
        if (!response.ok) throw new Error('인증 필요');

        const paths = await response.json();
        document.getElementById('nasPathCount').textContent = paths.length;

        if (paths.length === 0) {
            listDiv.innerHTML = '<div class="empty-state">등록된 NAS 경로가 없습니다.</div>';
            return;
        }

        let html = '';
        for (const p of paths) {
            html += `<div class="nas-path-item">
                <div class="path-info">
                    <div class="path-name">${p.name} <span class="status-badge indexed">${p.category || ''}</span></div>
                    <div class="path-location">${p.path}</div>
                    ${p.description ? `<div style="font-size:12px; color:var(--text-secondary); margin-top:2px;">${p.description}</div>` : ''}
                </div>
                <button class="btn btn-danger btn-sm" onclick="deleteNasPath('${p.id}')">삭제</button>
            </div>`;
        }
        listDiv.innerHTML = html;
    } catch (e) {
        listDiv.innerHTML = '<div class="empty-state">NAS 경로를 불러올 수 없습니다.</div>';
    }
}

async function addNasPath() {
    const name = document.getElementById('nasName').value.trim();
    const path = document.getElementById('nasPath').value.trim();
    const category = document.getElementById('nasCategory').value.trim();
    const description = document.getElementById('nasDescription').value.trim();
    const tagsStr = document.getElementById('nasTags').value.trim();

    if (!name || !path) {
        alert('파일명과 경로는 필수입니다.');
        return;
    }

    const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(Boolean) : [];

    try {
        const response = await fetch('/api/nas/paths', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, path, category, description, tags }),
        });

        if (response.ok) {
            document.getElementById('nasName').value = '';
            document.getElementById('nasPath').value = '';
            document.getElementById('nasCategory').value = '';
            document.getElementById('nasDescription').value = '';
            document.getElementById('nasTags').value = '';
            loadNasPaths();
            loadStatus();
        } else {
            alert('NAS 경로 추가에 실패했습니다.');
        }
    } catch (error) {
        alert('오류가 발생했습니다.');
    }
}

async function deleteNasPath(pathId) {
    if (!confirm('이 NAS 경로를 삭제하시겠습니까?')) return;

    try {
        const response = await fetch(`/api/nas/paths/${pathId}`, { method: 'DELETE' });

        if (response.ok) {
            loadNasPaths();
            loadStatus();
        } else {
            alert('경로 삭제에 실패했습니다.');
        }
    } catch (error) {
        alert('오류가 발생했습니다.');
    }
}

// === 사용자 관리 ===

async function loadUsers() {
    const listDiv = document.getElementById('userList');

    try {
        const response = await fetch('/api/admin/users');
        if (!response.ok) throw new Error('권한 없음');

        const data = await response.json();

        if (data.users.length === 0) {
            listDiv.innerHTML = '<div class="empty-state">등록된 사용자가 없습니다.</div>';
            return;
        }

        let html = '<table class="doc-table"><thead><tr>';
        html += '<th>아이디</th><th>이름</th><th>역할</th><th>생성일</th><th>작업</th>';
        html += '</tr></thead><tbody>';

        for (const u of data.users) {
            const date = new Date(u.created_at).toLocaleDateString('ko-KR');
            const roleBadge = u.role === 'admin'
                ? '<span class="status-badge stored">관리자</span>'
                : '<span class="status-badge indexed">사용자</span>';
            const actions = u.username === 'admin'
                ? '<span style="color:var(--text-secondary); font-size:12px;">기본 계정</span>'
                : `<button class="btn btn-secondary btn-sm" onclick="showResetPassword(${u.id}, '${escapeAttr(u.display_name || u.username)}')">비밀번호</button>
                   <button class="btn btn-danger btn-sm" onclick="deleteUser(${u.id}, '${escapeAttr(u.username)}')">삭제</button>`;

            html += `<tr>
                <td>${u.username}</td>
                <td>${u.display_name || '-'}</td>
                <td>${roleBadge}</td>
                <td>${date}</td>
                <td class="actions-cell">${actions}</td>
            </tr>`;
        }

        html += '</tbody></table>';
        listDiv.innerHTML = html;
    } catch (e) {
        listDiv.innerHTML = '<div class="empty-state">사용자 목록을 불러올 수 없습니다.</div>';
    }
}

function escapeAttr(text) {
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

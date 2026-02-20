// === 파일 브라우저 ===

let currentPath = '/';
let viewMode = 'grid'; // 'grid' | 'list'
let lastFolders = [];
let lastFiles = [];
let isAdmin = false;

// === 초기화 ===
document.addEventListener('DOMContentLoaded', async () => {
    const user = await checkAuth();
    if (!user) return; // 미인증 → login 리다이렉트

    isAdmin = user.role === 'admin';

    // 비관리자: 업로드/폴더 생성 버튼 숨김
    if (!isAdmin) {
        document.querySelectorAll('.admin-only-action').forEach(el => {
            el.style.display = 'none';
        });
    }

    loadFolder('/');
});

// === 뷰 모드 전환 ===

function setViewMode(mode) {
    viewMode = mode;
    document.getElementById('gridViewBtn').classList.toggle('active', mode === 'grid');
    document.getElementById('listViewBtn').classList.toggle('active', mode === 'list');
    renderFiles(lastFolders, lastFiles);
}

// === 폴더 탐색 ===

async function loadFolder(path) {
    currentPath = path;
    try {
        const response = await fetch(`/api/files/browse?path=${encodeURIComponent(path)}`);
        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }
        const data = await response.json();
        lastFolders = data.folders;
        lastFiles = data.files;
        renderBreadcrumbs(data.breadcrumbs);
        renderFiles(data.folders, data.files);
    } catch (e) {
        console.error('Load folder error:', e);
    }
}

function renderBreadcrumbs(breadcrumbs) {
    const el = document.getElementById('breadcrumbs');
    el.innerHTML = breadcrumbs.map((b, i) => {
        const isLast = i === breadcrumbs.length - 1;
        const sep = i > 0 ? '<span class="breadcrumb-sep">&rsaquo;</span>' : '';
        if (isLast) {
            return `${sep}<span class="breadcrumb-item current">${escapeHtml(b.name)}</span>`;
        }
        return `${sep}<span class="breadcrumb-item" onclick="loadFolder('${b.path}')">${escapeHtml(b.name)}</span>`;
    }).join('');
}

function renderFiles(folders, files) {
    const view = document.getElementById('filesView');
    const empty = document.getElementById('emptyState');

    if (folders.length === 0 && files.length === 0 && currentPath === '/') {
        view.innerHTML = '';
        empty.style.display = 'flex';
        return;
    }
    empty.style.display = 'none';

    if (viewMode === 'list') {
        renderListView(view, folders, files);
    } else {
        renderGridView(view, folders, files);
    }
}

// === 그리드 뷰 렌더링 ===

function renderGridView(view, folders, files) {
    view.className = 'files-view grid-view';
    let html = '';

    // 상위 폴더
    if (currentPath !== '/') {
        const parent = currentPath.substring(0, currentPath.lastIndexOf('/')) || '/';
        html += `
        <div class="file-item folder" ondblclick="loadFolder('${parent}')">
            <div class="file-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" stroke-width="1.5"><polyline points="15 18 9 12 15 6"/></svg>
            </div>
            <div class="file-name">..</div>
        </div>`;
    }

    for (const folder of folders) {
        const fp = currentPath === '/' ? '/' + folder.name : currentPath + '/' + folder.name;
        const ctx = isAdmin ? ` oncontextmenu="showContextMenu(event, '${escapeAttr(folder.name)}', 'folder', '', '${escapeAttr(folder.name)}')"` : '';
        html += `
        <div class="file-item folder" ondblclick="loadFolder('${fp}')"${ctx}>
            <div class="file-icon">
                <svg viewBox="0 0 24 24" fill="#f59e0b" stroke="#f59e0b" stroke-width="1.5" fill-opacity="0.15"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>
            </div>
            <div class="file-name">${escapeHtml(folder.name)}</div>
        </div>`;
    }

    for (const file of files) {
        const icon = getFileIcon(file.name);
        const info = formatSize(file.file_size);
        html += `
        <div class="file-item document" ondblclick="downloadFile('${escapeAttr(file.name)}')" oncontextmenu="showContextMenu(event, '${escapeAttr(file.name)}', 'file', '', '${escapeAttr(file.name)}')">
            <div class="file-icon">${icon}</div>
            <div class="file-name" title="${escapeAttr(file.name)}">${escapeHtml(truncateName(file.name, 18))}</div>
            <div class="file-meta"><span>${info}</span></div>
        </div>`;
    }

    view.innerHTML = html;
}

// === 리스트 뷰 렌더링 ===

function renderListView(view, folders, files) {
    view.className = 'files-view list-view';
    let html = `
    <div class="list-header">
        <span>이름</span>
        <span>유형</span>
        <span>크기</span>
        <span>상태</span>
    </div>`;

    // 상위 폴더
    if (currentPath !== '/') {
        const parent = currentPath.substring(0, currentPath.lastIndexOf('/')) || '/';
        html += `
        <div class="file-item folder" ondblclick="loadFolder('${parent}')">
            <div class="file-name-col">
                <div class="file-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" stroke-width="1.5"><polyline points="15 18 9 12 15 6"/></svg>
                </div>
                <div class="file-name">..</div>
            </div>
            <div class="file-type-col"></div>
            <div class="file-size-col"></div>
            <div class="file-status-col"></div>
        </div>`;
    }

    for (const folder of folders) {
        const fp = currentPath === '/' ? '/' + folder.name : currentPath + '/' + folder.name;
        const ctx = isAdmin ? ` oncontextmenu="showContextMenu(event, '${escapeAttr(folder.name)}', 'folder', '', '${escapeAttr(folder.name)}')"` : '';
        html += `
        <div class="file-item folder" ondblclick="loadFolder('${fp}')"${ctx}>
            <div class="file-name-col">
                <div class="file-icon">
                    <svg viewBox="0 0 24 24" fill="#f59e0b" stroke="#f59e0b" stroke-width="1.5" fill-opacity="0.15"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>
                </div>
                <div class="file-name">${escapeHtml(folder.name)}</div>
            </div>
            <div class="file-type-col">폴더</div>
            <div class="file-size-col">-</div>
            <div class="file-status-col"></div>
        </div>`;
    }

    for (const file of files) {
        const icon = getFileIcon(file.name);
        const ext = file.name.split('.').pop().toUpperCase();
        const size = formatSize(file.file_size);
        html += `
        <div class="file-item document" ondblclick="downloadFile('${escapeAttr(file.name)}')" oncontextmenu="showContextMenu(event, '${escapeAttr(file.name)}', 'file', '', '${escapeAttr(file.name)}')">
            <div class="file-name-col">
                <div class="file-icon">${icon}</div>
                <div class="file-name" title="${escapeAttr(file.name)}">${escapeHtml(file.name)}</div>
            </div>
            <div class="file-type-col">${ext}</div>
            <div class="file-size-col">${size}</div>
            <div class="file-status-col"></div>
        </div>`;
    }

    view.innerHTML = html;
}

// === 폴더 생성 ===

async function createFolder() {
    const name = document.getElementById('newFolderName').value.trim();
    if (!name) return;

    try {
        const response = await fetch('/api/files/folders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, parent_path: currentPath }),
        });
        if (response.ok) {
            closeModal('createFolderModal');
            document.getElementById('newFolderName').value = '';
            showAlert('폴더가 생성되었습니다.', 'success');
            loadFolder(currentPath);
        } else {
            const data = await response.json();
            showAlert(data.detail || '폴더 생성 실패', 'error');
        }
    } catch (e) {
        showAlert('오류가 발생했습니다.', 'error');
    }
}

// === 파일 업로드 ===

function handleFileDrop(event) {
    const files = event.dataTransfer.files;
    if (files.length > 0) uploadFiles(files);
}

function handleFileSelect(event) {
    const files = event.target.files;
    if (files.length > 0) uploadFiles(files);
    event.target.value = '';
}

async function uploadFiles(fileList) {
    const fileType = document.getElementById('uploadFileType').value;
    const category = document.getElementById('uploadCategory')?.value || '';

    for (const file of fileList) {
        await uploadSingleFile(file, fileType, category);
    }
    loadFolder(currentPath);
}

async function uploadSingleFile(file, fileType, category) {
    const taskId = 'upload_' + Date.now();
    const formData = new FormData();
    formData.append('file', file);
    formData.append('folder_path', currentPath);
    formData.append('file_type', fileType);
    formData.append('category', category);
    formData.append('task_id', taskId);

    const progressWrap = document.getElementById('uploadProgressWrap');
    const progressBar = document.getElementById('uploadProgressBar');
    const progressText = document.getElementById('uploadProgressText');
    progressWrap.style.display = 'block';
    progressBar.style.width = '0%';
    progressText.textContent = '업로드 시작...';

    const pollInterval = setInterval(async () => {
        try {
            const r = await fetch(`/api/files/progress/${taskId}`);
            const p = await r.json();
            if (p.percent > 0) {
                progressBar.style.width = p.percent + '%';
                progressText.textContent = p.detail || p.step;
            }
            if (p.step === 'done' || p.step === 'error') {
                clearInterval(pollInterval);
            }
        } catch (e) { /* ignore */ }
    }, 500);

    try {
        const response = await fetch('/api/files/upload', {
            method: 'POST',
            body: formData,
        });
        clearInterval(pollInterval);

        if (response.ok) {
            const data = await response.json();
            progressBar.style.width = '100%';
            progressText.textContent = data.message || '완료';
            showAlert(`${file.name} 업로드 완료`, 'success');
        } else {
            const data = await response.json();
            progressText.textContent = data.detail || '오류 발생';
            showAlert(data.detail || '업로드 실패', 'error');
        }
    } catch (e) {
        clearInterval(pollInterval);
        progressText.textContent = '오류 발생';
        showAlert('업로드 중 오류가 발생했습니다.', 'error');
    }

    setTimeout(() => {
        progressWrap.style.display = 'none';
        progressBar.style.width = '0%';
    }, 2000);
}

// === 다운로드 ===

function downloadFile(filename) {
    const url = `/api/files/download?path=${encodeURIComponent(currentPath)}&filename=${encodeURIComponent(filename)}`;
    window.open(url, '_blank');
}

// === 삭제 ===

async function deleteItem(id, type, sourceType, name) {
    if (!confirm(`"${name}"을(를) 삭제하시겠습니까?`)) return;

    let url = '';
    if (type === 'folder') {
        url = `/api/files/folders?path=${encodeURIComponent(currentPath)}&name=${encodeURIComponent(name)}`;
    } else {
        url = `/api/files/file?path=${encodeURIComponent(currentPath)}&filename=${encodeURIComponent(name)}`;
    }

    try {
        const response = await fetch(url, { method: 'DELETE' });
        if (response.ok) {
            showAlert(`"${name}" 삭제 완료`, 'success');
            loadFolder(currentPath);
        } else {
            const data = await response.json();
            showAlert(data.detail || '삭제 실패', 'error');
        }
    } catch (e) {
        showAlert('삭제 중 오류가 발생했습니다.', 'error');
    }
}

// === 컨텍스트 메뉴 ===

function showContextMenu(event, id, type, sourceType, name) {
    event.preventDefault();
    const existing = document.getElementById('contextMenu');
    if (existing) existing.remove();

    const menu = document.createElement('div');
    menu.id = 'contextMenu';
    menu.className = 'context-menu';
    menu.style.left = event.clientX + 'px';
    menu.style.top = event.clientY + 'px';

    let items = '';
    if (type === 'folder') {
        const folderPath = currentPath === '/' ? '/' + name : currentPath + '/' + name;
        items += `<div class="context-menu-item" onclick="loadFolder('${folderPath}'); removeContextMenu()">열기</div>`;
    } else {
        items += `<div class="context-menu-item" onclick="downloadFile('${escapeAttr(name)}'); removeContextMenu()">다운로드</div>`;
    }
    if (isAdmin) {
        items += `<div class="context-menu-item danger" onclick="deleteItem('${id}', '${type}', '${sourceType}', '${escapeAttr(name)}'); removeContextMenu()">삭제</div>`;
    }

    menu.innerHTML = items;
    document.body.appendChild(menu);

    setTimeout(() => {
        document.addEventListener('click', removeContextMenu, { once: true });
    }, 0);
}

function removeContextMenu() {
    const menu = document.getElementById('contextMenu');
    if (menu) menu.remove();
}

// === 유틸리티 ===

function showModal(id) {
    document.getElementById(id).style.display = 'flex';
    if (id === 'uploadModal') {
        const pathLabel = currentPath === '/' ? '루트' : currentPath;
        document.getElementById('uploadPathInfo').textContent = `업로드 위치: ${pathLabel}`;
    }
}

function closeModal(id) {
    document.getElementById(id).style.display = 'none';
}

function showAlert(message, type) {
    const el = document.getElementById('filesAlert');
    el.textContent = message;
    el.className = `upload-alert ${type}`;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 4000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeAttr(text) {
    return text.replace(/&/g, '&amp;').replace(/'/g, '&#39;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function truncateName(name, maxLen) {
    if (name.length <= maxLen) return name;
    const ext = name.lastIndexOf('.');
    if (ext > 0 && name.length - ext <= 6) {
        return name.substring(0, maxLen - (name.length - ext) - 2) + '..' + name.substring(ext);
    }
    return name.substring(0, maxLen - 2) + '..';
}

function formatSize(bytes) {
    if (!bytes) return '-';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const colors = {
        pdf: '#ef4444',
        docx: '#2563eb', doc: '#2563eb',
        xlsx: '#22c55e', xls: '#22c55e',
        pptx: '#f59e0b', ppt: '#f59e0b',
        txt: '#64748b', md: '#64748b', csv: '#64748b',
    };
    const color = colors[ext] || 'var(--primary)';

    return `<svg viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="1.5">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <text x="12" y="17" text-anchor="middle" fill="${color}" stroke="none" font-size="5" font-weight="bold">${ext.toUpperCase().substring(0, 4)}</text>
    </svg>`;
}

// NAS 파일 선택 시 카테고리 필드 표시
document.getElementById('uploadFileType')?.addEventListener('change', function() {
    const catEl = document.getElementById('uploadFileType_nasCategory');
    if (catEl) catEl.style.display = this.value === 'nas_file' ? 'block' : 'none';
});

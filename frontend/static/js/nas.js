// nas.js — NAS 탐색 페이지 (관리자 전용)

let currentPath = '';
let currentViewMode = 'grid';
let baseDirs = [];
let contextTarget = null; // 우클릭 대상 {name, path, is_dir}
let pendingFiles = [];     // 업로드 대기 파일

// === 초기화 ===
document.addEventListener('DOMContentLoaded', async () => {
    const user = await checkAuth();
    if (!user) return;

    // 관리자가 아니면 채팅으로 리다이렉트
    if (user.role !== 'admin') {
        window.location.href = '/';
        return;
    }

    await loadBaseDirs();

    // 전역 클릭 시 컨텍스트 메뉴 닫기
    document.addEventListener('click', () => {
        document.getElementById('contextMenu').style.display = 'none';
    });

    // 드래그앤드롭 지원
    const uploadArea = document.getElementById('uploadArea');
    if (uploadArea) {
        uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); uploadArea.classList.add('dragover'); });
        uploadArea.addEventListener('dragleave', () => { uploadArea.classList.remove('dragover'); });
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                document.getElementById('uploadFileInput').files = e.dataTransfer.files;
                handleFileSelect(document.getElementById('uploadFileInput'));
            }
        });
    }
});

// === 기본 디렉토리 로드 ===
async function loadBaseDirs() {
    showLoading(true);
    try {
        const response = await fetch('/api/nas/base-dirs');
        if (response.status === 403) {
            window.location.href = '/';
            return;
        }
        if (!response.ok) throw new Error('로드 실패');

        baseDirs = await response.json();

        if (baseDirs.length === 0) {
            showEmpty('등록된 NAS 디렉토리가 없습니다. 관리 페이지에서 등록하세요.');
            updateBreadcrumbs([]);
            return;
        }

        showBaseDirList();
        updateBreadcrumbs([]);
    } catch (e) {
        showEmpty('NAS 디렉토리를 불러올 수 없습니다.');
    } finally {
        showLoading(false);
    }
}

function showBaseDirList() {
    const view = document.getElementById('nasView');
    const empty = document.getElementById('emptyState');
    empty.style.display = 'none';

    // 루트에서는 업로드/새폴더 비활성화
    toggleManageButtons(false);

    if (currentViewMode === 'grid') {
        let html = '';
        for (const d of baseDirs) {
            html += `<div class="file-item" onclick="browseDirectory('${escapeAttr(d.path)}')">
                <div class="file-icon">${folderSvg(44)}</div>
                <div class="file-name">${escapeHtml(d.label)}</div>
                <div class="file-meta">${escapeHtml(d.description || d.path)}</div>
            </div>`;
        }
        view.innerHTML = html;
    } else {
        let html = `<div class="list-header">
            <div>이름</div><div>경로</div><div>설명</div><div></div>
        </div>`;
        for (const d of baseDirs) {
            html += `<div class="file-item" onclick="browseDirectory('${escapeAttr(d.path)}')">
                <div class="file-name-col">
                    <div class="file-icon">${folderSvg(24)}</div>
                    <div class="file-name">${escapeHtml(d.label)}</div>
                </div>
                <div class="file-type-col">${escapeHtml(d.path)}</div>
                <div class="file-size-col">${escapeHtml(d.description || '')}</div>
                <div class="file-status-col"></div>
            </div>`;
        }
        view.innerHTML = html;
    }

    view.style.display = '';
    currentPath = '';
}

// === 디렉토리 탐색 ===
async function browseDirectory(path) {
    showLoading(true);
    try {
        const response = await fetch(`/api/nas/browse?path=${encodeURIComponent(path)}`);
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '탐색 실패');
        }

        const data = await response.json();
        currentPath = data.current_path;
        renderItems(data.items, data.current_path, data.parent_path);
        updateBreadcrumbs(data.breadcrumbs);
        toggleManageButtons(true);
    } catch (e) {
        showAlert(e.message, 'error');
        showEmpty(e.message);
    } finally {
        showLoading(false);
    }
}

function renderItems(items, path, parentPath) {
    const view = document.getElementById('nasView');
    const empty = document.getElementById('emptyState');

    if (items.length === 0) {
        view.style.display = 'none';
        showEmpty('이 폴더는 비어 있습니다');
        return;
    }

    empty.style.display = 'none';
    view.style.display = '';

    const folders = items.filter(i => i.is_dir);
    const files = items.filter(i => !i.is_dir);
    const sorted = [...folders, ...files];

    if (currentViewMode === 'grid') {
        let html = '';
        for (const item of sorted) {
            const ctx = `oncontextmenu="showContextMenu(event, '${escapeAttr(item.path)}', '${escapeAttr(item.name)}', ${item.is_dir})"`;
            if (item.is_dir) {
                html += `<div class="file-item" onclick="browseDirectory('${escapeAttr(item.path)}')" ${ctx}>
                    <div class="file-icon">${folderSvg(44)}</div>
                    <div class="file-name">${escapeHtml(item.name)}</div>
                    <div class="file-meta"></div>
                </div>`;
            } else {
                html += `<div class="file-item" ondblclick="downloadFile('${escapeAttr(item.path)}')" ${ctx} title="${escapeAttr(item.name)}&#10;${formatSize(item.size)}">
                    <div class="file-icon">${fileSvg(44, item.extension)}</div>
                    <div class="file-name">${escapeHtml(item.name)}</div>
                    <div class="file-meta">${formatSize(item.size)}</div>
                </div>`;
            }
        }
        view.innerHTML = html;
    } else {
        let html = `<div class="list-header">
            <div>이름</div><div>크기</div><div>수정일</div><div></div>
        </div>`;
        for (const item of sorted) {
            const icon = item.is_dir ? folderSvg(24) : fileSvg(24, item.extension);
            const ctx = `oncontextmenu="showContextMenu(event, '${escapeAttr(item.path)}', '${escapeAttr(item.name)}', ${item.is_dir})"`;
            const clickAction = item.is_dir
                ? `onclick="browseDirectory('${escapeAttr(item.path)}')"`
                : `ondblclick="downloadFile('${escapeAttr(item.path)}')"`;

            html += `<div class="file-item" ${clickAction} ${ctx}>
                <div class="file-name-col">
                    <div class="file-icon">${icon}</div>
                    <div class="file-name">${escapeHtml(item.name)}</div>
                </div>
                <div class="file-size-col">${item.is_dir ? '-' : formatSize(item.size)}</div>
                <div class="file-type-col">${item.modified_time ? formatDate(item.modified_time) : ''}</div>
                <div class="file-status-col">
                    ${!item.is_dir ? `<button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); downloadFile('${escapeAttr(item.path)}')">다운로드</button>` : ''}
                </div>
            </div>`;
        }
        view.innerHTML = html;
    }
}

// === 파일 검색 ===
async function searchNasFiles() {
    const query = document.getElementById('nasSearchInput').value.trim();
    if (!query) return;

    showLoading(true);
    try {
        let url = `/api/nas/search?q=${encodeURIComponent(query)}`;
        if (currentPath) {
            url += `&path=${encodeURIComponent(currentPath)}`;
        }

        const response = await fetch(url);
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '검색 실패');
        }

        const data = await response.json();
        if (data.results.length === 0) {
            showEmpty(`"${query}"에 대한 검색 결과가 없습니다.`);
            document.getElementById('nasView').style.display = 'none';
        } else {
            renderItems(data.results, currentPath, null);
            updateBreadcrumbs([{ name: `검색: "${query}"`, path: '' }]);
        }
    } catch (e) {
        showAlert(e.message, 'error');
    } finally {
        showLoading(false);
    }
}

// === 다운로드 ===
function downloadFile(path) {
    const url = `/api/nas/download?path=${encodeURIComponent(path)}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

// === 컨텍스트 메뉴 ===
function showContextMenu(e, path, name, isDir) {
    e.preventDefault();
    e.stopPropagation();
    contextTarget = { path, name, is_dir: isDir };

    const menu = document.getElementById('contextMenu');
    // 폴더면 다운로드 숨김
    menu.children[0].style.display = isDir ? 'none' : '';

    menu.style.display = 'block';
    menu.style.left = Math.min(e.clientX, window.innerWidth - 180) + 'px';
    menu.style.top = Math.min(e.clientY, window.innerHeight - 120) + 'px';
}

function contextDownload() {
    if (contextTarget && !contextTarget.is_dir) downloadFile(contextTarget.path);
}

function contextRename() {
    if (!contextTarget) return;
    document.getElementById('renamePath').value = contextTarget.path;
    document.getElementById('renameInput').value = contextTarget.name;
    document.getElementById('renameModal').style.display = 'flex';
    setTimeout(() => {
        const input = document.getElementById('renameInput');
        input.focus();
        const dotIdx = contextTarget.name.lastIndexOf('.');
        if (dotIdx > 0 && !contextTarget.is_dir) {
            input.setSelectionRange(0, dotIdx);
        } else {
            input.select();
        }
    }, 100);
}

function contextDelete() {
    if (!contextTarget) return;
    const type = contextTarget.is_dir ? '폴더' : '파일';
    document.getElementById('deleteMessage').textContent = `"${contextTarget.name}" ${type}를 삭제하시겠습니까?`;
    document.getElementById('deletePath').value = contextTarget.path;
    document.getElementById('deleteModal').style.display = 'flex';
}

// === 이름 변경 ===
function closeRenameDialog() {
    document.getElementById('renameModal').style.display = 'none';
}

async function submitRename() {
    const path = document.getElementById('renamePath').value;
    const newName = document.getElementById('renameInput').value.trim();
    if (!newName) return;

    try {
        const formData = new FormData();
        formData.append('path', path);
        formData.append('new_name', newName);

        const resp = await fetch('/api/nas/rename', { method: 'POST', body: formData });
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || '이름 변경 실패');
        }
        closeRenameDialog();
        showAlert('이름이 변경되었습니다.', 'success');
        refreshCurrentView();
    } catch (e) {
        showAlert(e.message, 'error');
    }
}

// === 삭제 ===
function closeDeleteDialog() {
    document.getElementById('deleteModal').style.display = 'none';
}

async function submitDelete() {
    const path = document.getElementById('deletePath').value;

    try {
        const resp = await fetch(`/api/nas/delete?path=${encodeURIComponent(path)}`, { method: 'DELETE' });
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || '삭제 실패');
        }
        closeDeleteDialog();
        showAlert('삭제되었습니다.', 'success');
        refreshCurrentView();
    } catch (e) {
        showAlert(e.message, 'error');
    }
}

// === 새 폴더 ===
function showNewFolderDialog() {
    if (!currentPath) {
        showAlert('기본 디렉토리 안에서만 폴더를 만들 수 있습니다.', 'error');
        return;
    }
    document.getElementById('newFolderName').value = '';
    document.getElementById('newFolderModal').style.display = 'flex';
    setTimeout(() => document.getElementById('newFolderName').focus(), 100);
}

function closeNewFolderDialog() {
    document.getElementById('newFolderModal').style.display = 'none';
}

async function submitNewFolder() {
    const name = document.getElementById('newFolderName').value.trim();
    if (!name) return;

    try {
        const formData = new FormData();
        formData.append('folder_path', currentPath);
        formData.append('name', name);

        const resp = await fetch('/api/nas/folder', { method: 'POST', body: formData });
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || '폴더 생성 실패');
        }
        closeNewFolderDialog();
        showAlert(`"${name}" 폴더가 생성되었습니다.`, 'success');
        refreshCurrentView();
    } catch (e) {
        showAlert(e.message, 'error');
    }
}

// === 파일 업로드 ===
function showUploadDialog() {
    if (!currentPath) {
        showAlert('기본 디렉토리 안에서만 업로드할 수 있습니다.', 'error');
        return;
    }
    pendingFiles = [];
    document.getElementById('uploadPath').textContent = currentPath;
    document.getElementById('uploadFileList').innerHTML = '';
    document.getElementById('uploadFileInput').value = '';
    document.getElementById('uploadSubmitBtn').disabled = true;
    document.getElementById('uploadModal').style.display = 'flex';
}

function closeUploadDialog() {
    document.getElementById('uploadModal').style.display = 'none';
    pendingFiles = [];
}

function handleFileSelect(input) {
    pendingFiles = Array.from(input.files);
    const listEl = document.getElementById('uploadFileList');

    if (pendingFiles.length === 0) {
        listEl.innerHTML = '';
        document.getElementById('uploadSubmitBtn').disabled = true;
        return;
    }

    let html = '';
    for (const f of pendingFiles) {
        html += `<div class="upload-file-item">
            <span class="upload-file-name">${escapeHtml(f.name)}</span>
            <span class="upload-file-size">${formatSize(f.size)}</span>
        </div>`;
    }
    listEl.innerHTML = html;
    document.getElementById('uploadSubmitBtn').disabled = false;
}

async function submitUpload() {
    if (pendingFiles.length === 0) return;

    const btn = document.getElementById('uploadSubmitBtn');
    btn.disabled = true;
    btn.textContent = '업로드 중...';

    let successCount = 0;
    let failCount = 0;

    for (const file of pendingFiles) {
        try {
            const formData = new FormData();
            formData.append('path', currentPath);
            formData.append('file', file);
            formData.append('overwrite', 'false');

            const resp = await fetch('/api/nas/upload', { method: 'POST', body: formData });
            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail);
            }
            successCount++;
        } catch (e) {
            failCount++;
        }
    }

    closeUploadDialog();
    btn.textContent = '업로드';

    if (failCount === 0) {
        showAlert(`${successCount}개 파일 업로드 완료`, 'success');
    } else {
        showAlert(`${successCount}개 성공, ${failCount}개 실패`, 'error');
    }
    refreshCurrentView();
}

// === 뷰 모드 ===
function setViewMode(mode) {
    currentViewMode = mode;
    const view = document.getElementById('nasView');

    document.getElementById('gridViewBtn').classList.toggle('active', mode === 'grid');
    document.getElementById('listViewBtn').classList.toggle('active', mode === 'list');

    view.className = `files-view ${mode}-view`;

    if (currentPath) {
        browseDirectory(currentPath);
    } else {
        showBaseDirList();
    }
}

// === Breadcrumbs ===
function updateBreadcrumbs(crumbs) {
    const container = document.getElementById('breadcrumbs');
    let html = `<span class="breadcrumb-item ${!crumbs.length ? 'current' : ''}" onclick="goHome()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg>
        NAS
    </span>`;

    for (let i = 0; i < crumbs.length; i++) {
        const c = crumbs[i];
        html += '<span class="breadcrumb-sep">/</span>';
        if (i === crumbs.length - 1) {
            html += `<span class="breadcrumb-item current">${escapeHtml(c.name)}</span>`;
        } else {
            html += `<span class="breadcrumb-item" onclick="browseDirectory('${escapeAttr(c.path)}')">${escapeHtml(c.name)}</span>`;
        }
    }

    container.innerHTML = html;
}

function goHome() {
    currentPath = '';
    document.getElementById('nasSearchInput').value = '';
    showBaseDirList();
    updateBreadcrumbs([]);
}

// === 헬퍼 ===
function toggleManageButtons(enabled) {
    const uploadBtn = document.getElementById('uploadBtn');
    const newFolderBtn = document.getElementById('newFolderBtn');
    if (uploadBtn) uploadBtn.disabled = !enabled;
    if (newFolderBtn) newFolderBtn.disabled = !enabled;
}

function refreshCurrentView() {
    if (currentPath) {
        browseDirectory(currentPath);
    } else {
        loadBaseDirs();
    }
}

function showLoading(show) {
    document.getElementById('loadingState').style.display = show ? 'flex' : 'none';
    if (show) {
        document.getElementById('nasView').style.display = 'none';
        document.getElementById('emptyState').style.display = 'none';
    }
}

function showEmpty(message) {
    const el = document.getElementById('emptyState');
    document.getElementById('emptyMessage').textContent = message;
    el.style.display = 'flex';
}

function showAlert(message, type) {
    const el = document.getElementById('nasAlert');
    el.className = `upload-alert ${type}`;
    el.textContent = message;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 4000);
}

// === 포맷 유틸 ===
function formatSize(bytes) {
    if (!bytes) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
}

function formatDate(isoStr) {
    if (!isoStr) return '';
    try {
        return new Date(isoStr).toLocaleDateString('ko-KR');
    } catch {
        return isoStr;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeAttr(text) {
    return text.replace(/&/g, '&amp;').replace(/'/g, '&#39;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// === SVG 아이콘 ===
function folderSvg(size) {
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="#fbbf24" stroke="#d97706" stroke-width="1.5"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>`;
}

function fileSvg(size, ext) {
    const colors = {
        pdf: { fill: '#ef4444', label: 'PDF' },
        docx: { fill: '#2563eb', label: 'DOC' },
        doc: { fill: '#2563eb', label: 'DOC' },
        xlsx: { fill: '#22c55e', label: 'XLS' },
        xls: { fill: '#22c55e', label: 'XLS' },
        pptx: { fill: '#f59e0b', label: 'PPT' },
        ppt: { fill: '#f59e0b', label: 'PPT' },
        txt: { fill: '#64748b', label: 'TXT' },
        csv: { fill: '#22c55e', label: 'CSV' },
        jpg: { fill: '#8b5cf6', label: 'IMG' },
        jpeg: { fill: '#8b5cf6', label: 'IMG' },
        png: { fill: '#8b5cf6', label: 'IMG' },
        zip: { fill: '#f97316', label: 'ZIP' },
        hwp: { fill: '#0ea5e9', label: 'HWP' },
        hwpx: { fill: '#0ea5e9', label: 'HWP' },
    };
    const c = colors[ext] || { fill: '#94a3b8', label: '' };
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="${c.fill}" stroke-width="1.5">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" fill="${c.fill}20"/>
        <polyline points="14 2 14 8 20 8"/>
        ${c.label ? `<text x="12" y="17" text-anchor="middle" fill="${c.fill}" font-size="6" font-weight="bold" font-family="sans-serif">${c.label}</text>` : ''}
    </svg>`;
}

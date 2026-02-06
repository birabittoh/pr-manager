let publications = [];
let allWorkflows = [];
let currentPage = 1;
const workflowsPerPage = 20;
const refreshInterval = 30000; // 30 seconds

// UI Management
function toggleSidebar(show) {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (show) {
        sidebar.classList.remove('-translate-x-full');
        overlay.classList.remove('hidden');
    } else {
        sidebar.classList.add('-translate-x-full');
        overlay.classList.add('hidden');
    }
}

function showSection(sectionId) {
    // Update navigation
    const navItems = ['workflows', 'publications'];
    navItems.forEach(item => {
        const btn = document.getElementById(`nav-${item}`);
        if (item === sectionId) {
            btn.classList.add('bg-blue-600', 'text-white');
            btn.classList.remove('text-slate-400', 'hover:bg-slate-800', 'hover:text-white');
        } else {
            btn.classList.remove('bg-blue-600', 'text-white');
            btn.classList.add('text-slate-400', 'hover:bg-slate-800', 'hover:text-white');
        }
    });

    // Update sections
    document.getElementById('section-workflows').classList.add('hidden');
    document.getElementById('section-publications').classList.add('hidden');
    document.getElementById(`section-${sectionId}`).classList.remove('hidden');

    // Update title
    document.getElementById('section-title').textContent = sectionId.charAt(0).toUpperCase() + sectionId.slice(1);

    if (sectionId === 'workflows') loadWorkflow(currentPage, document.getElementById('workflowSearch').value);
    if (sectionId === 'publications') loadPublications();

    // Close sidebar on mobile
    if (window.innerWidth < 1024) toggleSidebar(false);
}

function refreshCurrentSection() {
    const isWorkflows = !document.getElementById('section-workflows').classList.contains('hidden');
    if (isWorkflows) loadWorkflow(currentPage, document.getElementById('workflowSearch').value);
    else loadPublications();

    checkHealth();
    loadThreads();
}

// Modal Management
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    modal.classList.remove('opacity-0', 'pointer-events-none');
    document.body.classList.add('modal-active');

    if (modalId === 'modal-manual-download') {
        const container = document.getElementById('manualDatesContainer');
        if (container.children.length === 0) {
            addDateInput();
        }
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    modal.classList.add('opacity-0', 'pointer-events-none');
    document.body.classList.remove('modal-active');
}

// API Calls
async function checkHealth() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();

        const online = data.status === 'ok';
        const serverTime = new Date(data.timestamp);
        const serverTimeStr = serverTime.getHours().toString().padStart(2, '0') + ':' + serverTime.getMinutes().toString().padStart(2, '0');

        const indicator = document.getElementById('server-status-indicator');
        indicator.className = 'h-2 w-2 rounded-full mr-1.5 ' + (online ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-red-500');
        
        const nextSecs = Math.max(0, Math.floor(Number(data.next_check_in_seconds) || 0));
        const fmtNext = (secs) => {
            const h = Math.floor(secs / 3600);
            const m = Math.floor((secs % 3600) / 60);
            if (h > 0 && m > 0) return `${h}h ${m}m`;
            if (h > 0) return `${h}h`;
            if (m > 0) return `${m}m`;
            return '<1m';
        };

        const nextText = nextSecs ? `Next check in ${fmtNext(nextSecs)}` : '';
        document.getElementById('server-status-text').textContent = online ? `Online (${serverTimeStr})` : 'Offline';
        document.getElementById('next-check-text').textContent = nextText;
    } catch (error) {
        document.getElementById('server-status-indicator').className = 'h-2 w-2 rounded-full bg-red-500 mr-1.5';
        document.getElementById('server-status-text').textContent = 'Offline';
    }
}

async function loadThreads() {
    try {
        const response = await fetch('/api/threads');
        const threads = await response.json();

        const threadList = document.getElementById('thread-list');
        threadList.innerHTML = '';

        threads.forEach(t => {
            const item = document.createElement('div');
            item.className = 'flex flex-col';

            let statusColor = 'bg-slate-600';
            let statusText = 'Stopped';
            let pulseClass = '';

            if (t.is_alive) {
                if (t.status === 'running') {
                    statusColor = 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]';
                    statusText = 'Running';
                    pulseClass = 'animate-pulse';
                } else {
                    statusColor = 'bg-blue-500';
                    statusText = 'Waiting';
                }
            }

            const displayName = t.name.replace('Thread', '');

            item.innerHTML = `
                <div class="flex items-center justify-between">
                    <span class="text-xs font-medium text-slate-300">${displayName}</span>
                    <div class="flex items-center">
                        <span class="h-1.5 w-1.5 rounded-full ${statusColor} ${pulseClass} mr-2"></span>
                        <span class="text-[10px] text-slate-500 font-medium uppercase tracking-tight">${statusText}</span>
                    </div>
                </div>
            `;
            threadList.appendChild(item);
        });
    } catch (error) {
        console.error('Error loading threads:', error);
    }
}

async function forceCheck() {
    if (!confirm('Are you sure you want to check for new issues right now?')) return;
    try {
        const response = await fetch('/api/check', { method: 'POST' });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        const count = Array.isArray(data) ? data.length : 0;
        alert(count === 0 ? 'No new issues found.' : `Found ${count} new issues. Refreshing...`);
        loadWorkflow(1);
    } catch (error) {
        alert('Error checking for new issues.');
    }
}

async function loadPublications() {
    try {
        const response = await fetch('/api/publications');
        publications = await response.json();
        publications.sort((a, b) => getPublicationDisplayName(a).localeCompare(getPublicationDisplayName(b)));
        
        const list = document.getElementById('publicationsList');
        const select = document.getElementById('manualPub');
        
        list.innerHTML = '';
        select.innerHTML = '<option value="">Select publication...</option>';
        
        publications.forEach(pub => {
            const displayName = getPublicationDisplayName(pub);
            const card = document.createElement('div');
            card.className = `bg-slate-900 border ${pub.enabled ? 'border-slate-800' : 'border-red-900/30 opacity-75'} rounded-xl p-5 hover:border-slate-700 transition-colors`;
            card.innerHTML = `
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <h3 class="text-lg font-bold text-white">${displayName}</h3>
                        <p class="text-xs text-slate-500 font-mono">${pub.name}</p>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" class="sr-only peer" ${pub.enabled ? 'checked' : ''} onchange="togglePublication('${pub.name}', this.checked)">
                        <div class="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                </div>
                <div class="space-y-2 mb-6">
                    <div class="flex justify-between text-xs">
                        <span class="text-slate-500">Issue ID</span>
                        <span class="text-slate-300 font-medium">${pub.issue_id}</span>
                    </div>
                    <div class="flex justify-between text-xs">
                        <span class="text-slate-500">Max Scale</span>
                        <span class="text-slate-300 font-medium">${pub.max_scale}</span>
                    </div>
                    <div class="flex justify-between text-xs">
                        <span class="text-slate-500">Language</span>
                        <span class="text-slate-300 font-medium uppercase">${pub.language}</span>
                    </div>
                </div>
                <div class="flex gap-2">
                    <button onclick="showEditPublicationForm('${pub.name}')" class="flex-1 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-md text-xs font-medium transition-colors">Edit</button>
                    <button onclick="deletePublication('${pub.name}')" class="px-3 py-1.5 bg-red-900/20 hover:bg-red-900/40 text-red-500 rounded-md text-xs font-medium transition-colors">Delete</button>
                </div>
            `;
            list.appendChild(card);
            
            const option = document.createElement('option');
            option.value = pub.name;
            option.textContent = displayName;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading publications:', error);
    }
}

async function togglePublication(name, enabled) {
    try {
        await fetch(`/api/publications/${name}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        loadPublications();
    } catch (error) {
        console.error('Error toggling publication:', error);
        loadPublications();
    }
}

async function deletePublication(name) {
    if (!confirm(`Are you sure you want to delete publication "${name}"?`)) return;
    try {
        await fetch(`/api/publications/${name}`, { method: 'DELETE' });
        loadPublications();
    } catch (error) {
        console.error('Error deleting publication:', error);
    }
}

function showEditPublicationForm(name) {
    const pub = publications.find(p => p.name === name);
    if (!pub) return;
    
    document.getElementById('editName').value = pub.name;
    document.getElementById('editDisplayName').value = pub.display_name || '';
    document.getElementById('editIssueId').value = pub.issue_id;
    document.getElementById('editMaxScale').value = pub.max_scale;
    document.getElementById('editLanguage').value = pub.language;
    
    openModal('modal-edit-publication');
}

async function addPublication(event) {
    event.preventDefault();
    const data = {
        name: document.getElementById('newName').value,
        display_name: document.getElementById('newDisplayName').value || null,
        issue_id: document.getElementById('newIssueId').value,
        max_scale: parseInt(document.getElementById('newMaxScale').value),
        language: document.getElementById('newLanguage').value
    };
    try {
        const res = await fetch('/api/publications', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to add publication');
        }
        closeModal('modal-add-publication');
        loadPublications();
        event.target.reset();
    } catch (error) {
        alert(error.message);
    }
}

async function updatePublication(event) {
    event.preventDefault();
    const name = document.getElementById('editName').value;
    const data = {
        display_name: document.getElementById('editDisplayName').value || null,
        issue_id: document.getElementById('editIssueId').value,
        max_scale: parseInt(document.getElementById('editMaxScale').value),
        language: document.getElementById('editLanguage').value
    };
    try {
        await fetch(`/api/publications/${name}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        closeModal('modal-edit-publication');
        loadPublications();
    } catch (error) {
        alert('Error updating publication');
    }
}

function addDateInput(value = '') {
    const container = document.getElementById('manualDatesContainer');
    const div = document.createElement('div');
    div.className = 'flex items-center space-x-2';
    div.innerHTML = `
        <input type="date" name="manualDate" value="${value}" required class="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded-md text-slate-200 focus:ring-blue-500 focus:border-blue-500 outline-none [color-scheme:dark]">
        <button type="button" onclick="this.parentElement.remove()" class="text-slate-500 hover:text-red-500 p-1">
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
        </button>
    `;
    container.appendChild(div);
}

async function manualDownload(event) {
    event.preventDefault();
    const publication_name = document.getElementById('manualPub').value;
    const dateInputs = document.getElementsByName('manualDate');
    const dates = Array.from(dateInputs)
        .map(input => input.value.replace(/-/g, ''))
        .filter(val => val !== '');

    if (dates.length === 0) {
        alert('Please add at least one date');
        return;
    }

    try {
        await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ publication_name, dates })
        });
        alert(`Queued ${dates.length} downloads`);
        closeModal('modal-manual-download');
        event.target.reset();
        document.getElementById('manualDatesContainer').innerHTML = '';
        loadWorkflow(1);
    } catch (error) {
        alert('Error queuing downloads');
    }
}

async function loadWorkflow(page = 1, search = '') {
    try {
        const params = new URLSearchParams({ page, limit: workflowsPerPage, search });
        const response = await fetch(`/api/workflow?${params}`);
        const data = await response.json();
        
        allWorkflows = data.workflows;
        currentPage = page;
        renderWorkflows(allWorkflows);
        renderPagination(currentPage, data.total_pages);
    } catch (error) {
        console.error('Error loading workflow:', error);
    }
}

function searchWorkflows() {
    currentPage = 1;
    loadWorkflow(currentPage, document.getElementById('workflowSearch').value);
}

function renderWorkflows(workflows) {
    const list = document.getElementById('workflowList');
    const noWorkflows = document.getElementById('no-workflows');
    list.innerHTML = '';
    
    if (workflows.length === 0) {
        noWorkflows.classList.remove('hidden');
        return;
    }
    noWorkflows.classList.add('hidden');
    
    workflows.forEach(wf => {
        const pub = publications.find(p => p.name === wf.publication_name);
        const pubDisplayName = pub ? getPublicationDisplayName(pub) : parsePublicationName(wf.publication_name);
        
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-800/30 transition-colors';
        
        const statusHtml = `
            <div class="flex items-center justify-center space-x-2">
                ${wf.downloaded ?
                    '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-green-900/30 text-green-500 border border-green-900/50">DOWNLOADED</span>' :
                    '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-500 border border-slate-700">PENDING</span>'}
                ${wf.ocr_processed ?
                    '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-900/30 text-blue-400 border border-blue-900/50">OCR</span>' :
                    '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-500 border border-slate-700">NO OCR</span>'}
                ${wf.uploaded ?
                    '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-900/30 text-purple-400 border border-purple-900/50">UPLOADED</span>' :
                    '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-500 border border-slate-700">NOT UPLOADED</span>'}
            </div>
        `;

        tr.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm font-medium text-white">${pubDisplayName}</div>
                <div class="text-xs text-slate-500 font-mono">${wf.publication_name}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-400">
                ${parsePublicationDate(wf.key)}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-center">
                ${statusHtml}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                ${wf.uploaded ? `
                    <a href="/api/workflow/${wf.publication_name}/${getDateFromKey(wf.key)}" target="_blank" class="text-blue-500 hover:text-blue-400 inline-flex items-center">
                        <svg class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                        Download
                    </a>
                ` : '<span class="text-slate-600">—</span>'}
            </td>
        `;
        list.appendChild(tr);
    });
}

function renderPagination(currentPage, totalPages) {
    const pagination = document.getElementById('workflowPagination');
    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }
    
    const search = document.getElementById('workflowSearch').value;
    
    pagination.innerHTML = `
        <div class="flex-1 flex justify-between sm:hidden">
            <button onclick="loadWorkflow(${currentPage - 1}, '${search}')" ${currentPage === 1 ? 'disabled' : ''} class="relative inline-flex items-center px-4 py-2 border border-slate-700 text-sm font-medium rounded-md text-slate-400 bg-slate-800 hover:bg-slate-700 disabled:opacity-50">Previous</button>
            <button onclick="loadWorkflow(${currentPage + 1}, '${search}')" ${currentPage === totalPages ? 'disabled' : ''} class="ml-3 relative inline-flex items-center px-4 py-2 border border-slate-700 text-sm font-medium rounded-md text-slate-400 bg-slate-800 hover:bg-slate-700 disabled:opacity-50">Next</button>
        </div>
        <div class="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
            <div>
                <p class="text-sm text-slate-500">
                    Page <span class="font-medium text-slate-300">${currentPage}</span> of <span class="font-medium text-slate-300">${totalPages}</span>
                </p>
            </div>
            <div>
                <nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                    <button onclick="loadWorkflow(1, '${search}')" ${currentPage === 1 ? 'disabled' : ''} class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-slate-700 bg-slate-800 text-sm font-medium text-slate-500 hover:bg-slate-700 disabled:opacity-50">«</button>
                    <button onclick="loadWorkflow(${currentPage - 1}, '${search}')" ${currentPage === 1 ? 'disabled' : ''} class="relative inline-flex items-center px-4 py-2 border border-slate-700 bg-slate-800 text-sm font-medium text-slate-500 hover:bg-slate-700 disabled:opacity-50">Previous</button>
                    <button onclick="loadWorkflow(${currentPage + 1}, '${search}')" ${currentPage === totalPages ? 'disabled' : ''} class="relative inline-flex items-center px-4 py-2 border border-slate-700 bg-slate-800 text-sm font-medium text-slate-500 hover:bg-slate-700 disabled:opacity-50">Next</button>
                    <button onclick="loadWorkflow(${totalPages}, '${search}')" ${currentPage === totalPages ? 'disabled' : ''} class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-slate-700 bg-slate-800 text-sm font-medium text-slate-500 hover:bg-slate-700 disabled:opacity-50">»</button>
                </nav>
            </div>
        </div>
    `;
}

// Helpers
function getPublicationDisplayName(pub) {
    return pub.display_name || parsePublicationName(pub.name);
}

function parsePublicationName(name) {
    return name.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

function getDateFromKey(keyStr) {
    return keyStr.slice(4, 12);
}

function parsePublicationDate(keyStr) {
    const dateStr = getDateFromKey(keyStr);
    const year = dateStr.slice(0, 4);
    const month = dateStr.slice(4, 6);
    const day = dateStr.slice(6, 8);
    return `${day}/${month}/${year}`;
}

// Initialize
async function init() {
    await loadPublications();
    checkHealth();
    loadThreads();
    loadWorkflow();

    setInterval(() => {
        checkHealth();
        loadThreads();
        const isWorkflows = !document.getElementById('section-workflows').classList.contains('hidden');
        if (isWorkflows) loadWorkflow(currentPage, document.getElementById('workflowSearch').value);
    }, refreshInterval);
}

init();

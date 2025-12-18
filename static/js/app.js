let publications = [];
let allWorkflows = [];
let filteredWorkflows = [];
let currentPage = 1;
const workflowsPerPage = 20;

// Check health status
async function checkHealth() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();

        const online = data.status === 'ok';
        const serverTime = new Date(data.timestamp);
        const serverTimeStr = serverTime.getHours().toString().padStart(2, '0') + ':' + serverTime.getMinutes().toString().padStart(2, '0')
        document.getElementById('statusIndicator').className = 'status-indicator' + (online ? ' online' : '');
        
        const nextSecs = Math.max(0, Math.floor(Number(data.next_check_in_seconds) || 0));
        const fmtNext = (secs) => {
            const h = Math.floor(secs / 3600);
            const m = Math.floor((secs % 3600) / 60);
            if (h > 0 && m > 0) return `${h}h ${m}m`;
            if (h > 0) return `${h}h`;
            if (m > 0) return `${m}m`;
            return '<1m';
        };

        const nextText = nextSecs ? ` — Next check in ${fmtNext(nextSecs)}` : '';
        document.getElementById('statusText').textContent = (online ? `Online (${serverTimeStr})` : 'Warning') + nextText;
    } catch (error) {
        document.getElementById('statusIndicator').className = 'status-indicator';
        document.getElementById('statusText').textContent = 'Offline';
    }
}

function parsePublicationName(name) {
    return name.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

function getPublicationDisplayName(pub) {
    if (pub.display_name) {
        return pub.display_name;
    }

    return parsePublicationName(pub.name);
}

function parsePublicationDate(dateStr) { // dateStr in YYYYMMDD
    const year = dateStr.slice(0, 4);
    const month = dateStr.slice(4, 6);
    const day = dateStr.slice(6, 8);
    return `${day}/${month}/${year}`;
}

function getWorkflowKey(name, date) {
    return `${name}_${date}`;
}

// Toggle panel collapse
function togglePanel(panelId) {
    const panel = document.getElementById(panelId);
    const icon = document.getElementById(panelId + 'Icon');
    
    panel.classList.toggle('collapsed');
    icon.classList.toggle('collapsed');
}

// Load publications
async function loadPublications() {
    try {
        const response = await fetch('/api/publications');
        publications = await response.json();
        
        const list = document.getElementById('publicationsList');
        const select = document.getElementById('manualPub');
        
        list.innerHTML = '';
        select.innerHTML = '<option value="">Select publication...</option>';
        
        publications.forEach(pub => {
            // Add to list
            const displayName = getPublicationDisplayName(pub);
            const item = document.createElement('div');
            item.id = `pub_${pub.name}`;
            item.className = 'publication-item';
            item.innerHTML = `
                <div class="publication-info">
                    <div class="publication-name">${displayName}</div>
                    <div class="publication-details">
                        Name: ${pub.name} | Issue ID: ${pub.issue_id} | Max Scale: ${pub.max_scale} | Language: ${pub.language}
                    </div>
                </div>
                <div class="publication-actions">
                    <label class="toggle-switch">
                        <input type="checkbox" ${pub.enabled ? 'checked' : ''} 
                               onchange="togglePublication('${pub.name}', this.checked)">
                        <span class="slider"></span>
                    </label>
                    <button class="btn-warning" onclick="showEditPublicationForm('${pub.name}')">Edit</button>
                    <button class="btn-danger" onclick="deletePublication('${pub.name}')">Delete</button>
                </div>
            `;
            list.appendChild(item);
            
            // Add to select
            const option = document.createElement('option');
            option.value = pub.name;
            option.textContent = displayName;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading publications:', error);
    }
}

// Toggle publication
async function togglePublication(name, enabled) {
    try {
        await fetch(`/api/publications/${name}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
    } catch (error) {
        console.error('Error toggling publication:', error);
        loadPublications();
    }
}

// Delete publication
async function deletePublication(name) {
    if (!confirm(`Delete publication "${name}"?`)) return;
    
    try {
        await fetch(`/api/publications/${name}`, { method: 'DELETE' });
        loadPublications();
    } catch (error) {
        console.error('Error deleting publication:', error);
    }
}

// Show add publication form
function showAddPublicationForm() {
    hideEditPublicationForm(false);
    const addPublicationForm = document.getElementById('addPublicationForm');
    addPublicationForm.style.display = 'block';
    addPublicationForm.scrollIntoView({ behavior: 'smooth' });
}

// Hide add publication form
function hideAddPublicationForm() {
    document.getElementById('addPublicationForm').style.display = 'none';
    document.getElementById('newName').value = '';
    document.getElementById('newDisplayName').value = '';
    document.getElementById('newIssueId').value = '';
    document.getElementById('newMaxScale').value = '357';
    document.getElementById('newLanguage').value = 'ita';
}

// Show edit publication form
function showEditPublicationForm(name) {
    hideAddPublicationForm();
    
    const pub = publications.find(p => p.name === name);
    if (!pub) return;
    
    document.getElementById('editName').value = pub.name;
    document.getElementById('editDisplayName').value = pub.display_name || '';
    document.getElementById('editIssueId').value = pub.issue_id;
    document.getElementById('editMaxScale').value = pub.max_scale;
    document.getElementById('editLanguage').value = pub.language;
    
    const editPublicationForm = document.getElementById('editPublicationForm');
    editPublicationForm.style.display = 'block';
    editPublicationForm.scrollIntoView({ behavior: 'smooth' });
}

// Hide edit publication form
function hideEditPublicationForm(scrollBack) {
    document.getElementById('editPublicationForm').style.display = 'none';
    if (scrollBack) {
        const name = document.getElementById('editName').value;
        document.getElementById(`pub_${name}`).scrollIntoView({ behavior: 'smooth' });
    }
}

// Add publication
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
        await fetch('/api/publications', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        hideAddPublicationForm();
        loadPublications();
    } catch (error) {
        console.error('Error adding publication:', error);
        alert('Error adding publication');
    }
}

// Update publication
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
        hideEditPublicationForm(true);
        loadPublications();
    } catch (error) {
        console.error('Error updating publication:', error);
        alert('Error updating publication');
    }
}

// Manual download
async function manualDownload(event) {
    event.preventDefault();
    
    const publication_name = document.getElementById('manualPub').value;
    const dates = document.getElementById('manualDates').value.split(',').map(d => d.trim());
    
    try {
        await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ publication_name, dates })
        });
        alert(`Queued ${dates.length} downloads`);
        document.getElementById('manualDates').value = '';
    } catch (error) {
        console.error('Error queuing downloads:', error);
        alert('Error queuing downloads');
    }
}

// Load workflow
async function loadWorkflow(page = 1, search = '') {
    try {
        const params = new URLSearchParams({
            page: page,
            limit: workflowsPerPage,
            search: search
        });
        
        const response = await fetch(`/api/workflow?${params}`);
        const data = await response.json();
        
        allWorkflows = data.workflows;
        const totalPages = data.total_pages;
        currentPage = page;
        
        renderWorkflows(allWorkflows);
        renderPagination(currentPage, totalPages);
    } catch (error) {
        console.error('Error loading workflow:', error);
    }
}

// Search workflows
function searchWorkflows() {
    const search = document.getElementById('workflowSearch').value;
    currentPage = 1;
    loadWorkflow(currentPage, search);
}

// Render workflows
function renderWorkflows(workflows) {
    const list = document.getElementById('workflowList');
    list.innerHTML = '';
    
    if (workflows.length === 0) {
        list.innerHTML = '<div style="text-align: center; color: #999; padding: 20px;">No workflows found</div>';
        return;
    }
    
    workflows.forEach(wf => {
        const item = document.createElement('div');
        item.className = 'workflow-item';

        pub = publications.find(p => p.name === wf.publication_name);
        if (pub) {
            wf.publication_display_name = getPublicationDisplayName(pub);
        } else {
            wf.publication_display_name = parsePublicationName(wf.publication_name);
        }
        
        const statuses = [];
        if (wf.downloaded) statuses.push('<span class="status-badge completed">Downloaded</span>');
        else statuses.push('<span class="status-badge pending">Not Downloaded</span>');
        
        if (wf.ocr_processed) statuses.push('<span class="status-badge completed">OCR</span>');
        else statuses.push('<span class="status-badge pending">No OCR</span>');
        
        if (wf.uploaded) statuses.push(`<a href="/api/workflow/${wf.publication_name}/${wf.date}" target="_blank" class="download-btn"><span class="status-badge completed">Uploaded</span></a>`);
        else statuses.push('<span class="status-badge pending">Not Uploaded</span>');
        
        item.innerHTML = `
            <div class="workflow-info">
                <div class="workflow-name">${wf.publication_display_name}</div>
                <div class="workflow-date">${parsePublicationDate(wf.date)}</div>
            </div>
            <div class="workflow-status">
                ${statuses.join('')}
            </div>
        `;
        list.appendChild(item);
    });
}

// Render pagination
function renderPagination(currentPage, totalPages) {
    const pagination = document.getElementById('workflowPagination');
    
    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }
    
    const search = document.getElementById('workflowSearch').value;
    
    pagination.innerHTML = `
        <button onclick="loadWorkflow(1, '${search}')" ${currentPage === 1 ? 'disabled' : ''}>««</button>
        <button onclick="loadWorkflow(${currentPage - 1}, '${search}')" ${currentPage === 1 ? 'disabled' : ''}>«</button>
        <span class="page-info">Page ${currentPage} of ${totalPages}</span>
        <button onclick="loadWorkflow(${currentPage + 1}, '${search}')" ${currentPage === totalPages ? 'disabled' : ''}>»</button>
        <button onclick="loadWorkflow(${totalPages}, '${search}')" ${currentPage === totalPages ? 'disabled' : ''}>»»</button>
    `;
}

// Initialize
checkHealth();
loadPublications();
loadWorkflow();

// Refresh every 30 seconds
setInterval(() => {
    checkHealth();
    loadWorkflow(currentPage, document.getElementById('workflowSearch').value);
}, 30000);

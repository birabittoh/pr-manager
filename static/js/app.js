// Check health status
async function checkHealth() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        document.getElementById('statusIndicator').className = 'status-indicator online';
        document.getElementById('statusText').textContent = 'Online';
    } catch (error) {
        document.getElementById('statusIndicator').className = 'status-indicator';
        document.getElementById('statusText').textContent = 'Offline';
    }
}

// Load publications
async function loadPublications() {
    try {
        const response = await fetch('/api/publications');
        const publications = await response.json();
        
        const list = document.getElementById('publicationsList');
        const select = document.getElementById('manualPub');
        
        list.innerHTML = '';
        select.innerHTML = '<option value="">Select publication...</option>';
        
        publications.forEach(pub => {
            // Add to list
            const item = document.createElement('div');
            item.className = 'publication-item';
            item.innerHTML = `
                <div class="publication-info">
                    <div class="publication-name">${pub.name}</div>
                    <div class="publication-details">
                        Issue ID: ${pub.issue_id} | Max Scale: ${pub.max_scale} | Language: ${pub.language}
                    </div>
                </div>
                <div class="publication-actions">
                    <label class="toggle-switch">
                        <input type="checkbox" ${pub.enabled ? 'checked' : ''} 
                               onchange="togglePublication('${pub.name}', this.checked)">
                        <span class="slider"></span>
                    </label>
                    <button class="btn-danger" onclick="deletePublication('${pub.name}')">Delete</button>
                </div>
            `;
            list.appendChild(item);
            
            // Add to select
            const option = document.createElement('option');
            option.value = pub.name;
            option.textContent = pub.name;
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
    document.getElementById('addPublicationForm').style.display = 'block';
}

// Hide add publication form
function hideAddPublicationForm() {
    document.getElementById('addPublicationForm').style.display = 'none';
    document.getElementById('newName').value = '';
    document.getElementById('newIssueId').value = '';
    document.getElementById('newMaxScale').value = '';
    document.getElementById('newLanguage').value = '';
}

// Add publication
async function addPublication(event) {
    event.preventDefault();
    
    const data = {
        name: document.getElementById('newName').value,
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
async function loadWorkflow() {
    try {
        const response = await fetch('/api/workflow');
        const workflows = await response.json();
        
        const list = document.getElementById('workflowList');
        list.innerHTML = '';
        
        workflows.forEach(wf => {
            const item = document.createElement('div');
            item.className = 'workflow-item';
            
            const statuses = [];
            if (wf.downloaded) statuses.push('<span class="status-badge completed">Downloaded</span>');
            else statuses.push('<span class="status-badge pending">Not Downloaded</span>');
            
            if (wf.ocr_processed) statuses.push('<span class="status-badge completed">OCR</span>');
            else statuses.push('<span class="status-badge pending">No OCR</span>');
            
            if (wf.uploaded) statuses.push('<span class="status-badge completed">Uploaded</span>');
            else statuses.push('<span class="status-badge pending">Not Uploaded</span>');
            
            item.innerHTML = `
                <div class="workflow-info">
                    <div class="workflow-name">${wf.publication_name}</div>
                    <div class="workflow-date">${wf.date}</div>
                </div>
                <div class="workflow-status">
                    ${statuses.join('')}
                </div>
            `;
            list.appendChild(item);
        });
    } catch (error) {
        console.error('Error loading workflow:', error);
    }
}

// Initialize
checkHealth();
loadPublications();
loadWorkflow();

// Refresh every 30 seconds
setInterval(() => {
    checkHealth();
    loadWorkflow();
}, 30000);

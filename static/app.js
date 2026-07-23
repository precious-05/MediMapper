// App State
let allLeads = [];
let availableCities = [];
let clinicTypes = [];

// DOM Elements
const selectCountry = document.getElementById('select-country');
const selectCity = document.getElementById('select-city');
const selectType = document.getElementById('select-type');
const generatorForm = document.getElementById('generator-form');
const btnGenerate = document.getElementById('btn-generate');
const logOutput = document.getElementById('log-output');
const btnClearLogs = document.getElementById('btn-clear-logs');

const searchInput = document.getElementById('search-input');
const filterCountry = document.getElementById('filter-country');
const filterPriority = document.getElementById('filter-priority');
const filterAutomation = document.getElementById('filter-automation');
const btnClearFilters = document.getElementById('btn-clear-filters');
const btnRefresh = document.getElementById('btn-refresh');

const leadsTable = document.getElementById('leads-table');
const leadsTbody = document.getElementById('leads-tbody');
const leadsCountBadge = document.getElementById('leads-count-badge');

const btnExportSheet = document.getElementById('btn-export-sheet');
const toastContainer = document.getElementById('toast-container');

// Stats Elements
const statTotalLeads = document.getElementById('stat-total-leads');
const statCountries = document.getElementById('stat-countries');
const statHighPriority = document.getElementById('stat-high-priority');
const statEnriched = document.getElementById('stat-enriched');

// Modal Elements
const detailsModal = document.getElementById('details-modal');
const modalTitle = document.getElementById('modal-title');
const modalBody = document.getElementById('modal-body');
const btnCloseModal = document.getElementById('btn-close-modal');

// Init application
document.addEventListener('DOMContentLoaded', () => {
    loadConfiguration();
    loadDashboardData();
    setupEventListeners();
});

// Setup Event Listeners
function setupEventListeners() {
    // Country selection in form triggers city list loading
    selectCountry.addEventListener('change', () => {
        const country = selectCountry.value;
        populateCitiesDropdown(country);
    });

    // Form submit for generation
    generatorForm.addEventListener('submit', (e) => {
        e.preventDefault();
        startLeadGeneration();
    });

    // Clear logs
    btnClearLogs.addEventListener('click', () => {
        logOutput.innerHTML = '';
        addLog('Logs cleared.', 'info');
    });

    // Refresh button
    btnRefresh.addEventListener('click', () => {
        const refreshIcon = btnRefresh.querySelector('i');
        refreshIcon.classList.add('spinning');
        loadDashboardData().finally(() => {
            setTimeout(() => refreshIcon.classList.remove('spinning'), 500);
        });
    });

    // Filters and Search
    searchInput.addEventListener('input', debounce(applyFiltersAndSearch, 300));
    filterCountry.addEventListener('change', applyFiltersAndSearch);
    filterPriority.addEventListener('change', applyFiltersAndSearch);
    filterAutomation.addEventListener('change', applyFiltersAndSearch);
    
    btnClearFilters.addEventListener('click', () => {
        searchInput.value = '';
        filterCountry.value = '';
        filterPriority.value = '';
        filterAutomation.value = '';
        applyFiltersAndSearch();
    });

    // Export to sheet
    btnExportSheet.addEventListener('click', syncLeadsToGoogleSheet);

    // Modal close
    btnCloseModal.addEventListener('click', () => detailsModal.classList.remove('show'));
    detailsModal.addEventListener('click', (e) => {
        if (e.target === detailsModal) detailsModal.classList.remove('show');
    });
}

// Load configurations (Cities & Clinic Types) from API
async function loadConfiguration() {
    try {
        // Fetch Cities
        const citiesRes = await fetch('/cities');
        const citiesData = await citiesRes.json();
        availableCities = citiesData.cities || [];

        // Fetch Clinic Types
        const typesRes = await fetch('/clinic-types');
        const typesData = await typesRes.json();
        clinicTypes = typesData.clinic_types || [];

        // Populate Clinic Types in generator form
        selectType.innerHTML = '<option value="" disabled selected>Select clinic type</option>';
        clinicTypes.forEach(type => {
            const opt = document.createElement('option');
            opt.value = type;
            opt.textContent = type;
            selectType.appendChild(opt);
        });
        
        addLog('Configuration loaded successfully.', 'info');
    } catch (err) {
        console.error('Failed to load configuration:', err);
        addLog('Failed to load cities/clinic types configuration from API.', 'error');
    }
}

// Populate Cities based on Country selected
function populateCitiesDropdown(country) {
    selectCity.innerHTML = '<option value="" disabled selected>Select city</option>';
    
    const filteredCities = availableCities.filter(c => c.country === country);
    
    if (filteredCities.length > 0) {
        filteredCities.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.city;
            opt.textContent = c.city;
            selectCity.appendChild(opt);
        });
        selectCity.disabled = false;
    } else {
        selectCity.disabled = true;
    }
}

// Load statistics and leads
async function loadDashboardData() {
    try {
        const statsPromise = fetch('/stats').then(res => res.json());
        const leadsPromise = fetch('/leads').then(res => res.json());

        const [statsData, leadsData] = await Promise.all([statsPromise, leadsPromise]);

        // Render Stats
        statTotalLeads.textContent = statsData.total_leads || 0;
        statCountries.textContent = Object.keys(statsData.by_country || {}).length || 0;
        
        allLeads = leadsData.leads || [];
        
        // Count high priority and enriched
        let highPriorityCount = 0;
        let enrichedCount = 0;
        
        allLeads.forEach(lead => {
            if (lead['Lead Priority'] === 'High') highPriorityCount++;
            if (lead['Email'] || lead['Website URL']) enrichedCount++;
        });

        statHighPriority.textContent = highPriorityCount;
        statEnriched.textContent = enrichedCount;

        // Render table
        applyFiltersAndSearch();
        
    } catch (err) {
        console.error('Error fetching dashboard data:', err);
        showToast('Failed to fetch lead data.', 'error');
    }
}

// Apply UI search and dropdown filters
function applyFiltersAndSearch() {
    const query = searchInput.value.toLowerCase().trim();
    const country = filterCountry.value;
    const priority = filterPriority.value;
    const automation = filterAutomation.value;

    const filtered = allLeads.filter(lead => {
        // Search text match
        const matchesSearch = !query || 
            (lead['Clinic Name'] && lead['Clinic Name'].toLowerCase().includes(query)) ||
            (lead['Address'] && lead['Address'].toLowerCase().includes(query)) ||
            (lead['Email'] && lead['Email'].toLowerCase().includes(query)) ||
            (lead['Website URL'] && lead['Website URL'].toLowerCase().includes(query)) ||
            (lead['Doctor/Owner Name'] && lead['Doctor/Owner Name'].toLowerCase().includes(query));

        // Dropdown matches
        const matchesCountry = !country || lead['Country'] === country;
        const matchesPriority = !priority || lead['Lead Priority'] === priority;
        const matchesAutomation = !automation || lead['Automation Status'] === automation;

        return matchesSearch && matchesCountry && matchesPriority && matchesAutomation;
    });

    renderLeadsTable(filtered);
}

// Render leads array into HTML Table
function renderLeadsTable(leads) {
    leadsCountBadge.textContent = `${leads.length} record${leads.length === 1 ? '' : 's'}`;

    if (leads.length === 0) {
        leadsTbody.innerHTML = `
            <tr>
                <td colspan="8" class="empty-state">
                    <div class="empty-icon"><i class="fa-solid fa-circle-nodes"></i></div>
                    <h3>No Leads Found</h3>
                    <p>Try modifying your search query or filters.</p>
                </td>
            </tr>
        `;
        return;
    }

    leadsTbody.innerHTML = '';
    leads.forEach(lead => {
        const tr = document.createElement('tr');
        
        // Priority Badge Class
        const priorityClass = `priority-${(lead['Lead Priority'] || 'Medium').toLowerCase()}`;
        
        // Automation Badge Class
        let autoClass = 'auto-unknown';
        const autoText = lead['Automation Status'] || 'Unknown';
        if (autoText === 'Automated') autoClass = 'auto-automated';
        else if (autoText === 'Semi-Automated') autoClass = 'auto-semi-automated';
        else if (autoText === 'Manual') autoClass = 'auto-manual';

        // Rating display
        let ratingHtml = '<span class="text-secondary">N/A</span>';
        if (lead['Google Rating']) {
            const ratingNum = parseFloat(lead['Google Rating']);
            if (!isNaN(ratingNum)) {
                ratingHtml = `
                    <div class="rating-stars">
                        <span class="rating-val">${ratingNum.toFixed(1)}</span>
                        <i class="fa-solid fa-star"></i>
                    </div>
                    <div class="reviews-count">(${lead['Reviews Count'] || 0} reviews)</div>
                `;
            }
        }

        // Clinic Name Cell
        let nameHtml = `<div class="clinic-name-cell">${lead['Clinic Name']}</div>`;
        if (lead['Website URL']) {
            nameHtml = `
                <div class="clinic-name-cell">
                    <a href="${lead['Website URL']}" target="_blank" rel="noopener noreferrer">
                        ${lead['Clinic Name']} <i class="fa-solid fa-up-right-from-square" style="font-size: 0.75rem;"></i>
                    </a>
                </div>
            `;
        }

        // Contact Info Cell
        let contactHtml = '';
        if (lead['Phone Number']) {
            contactHtml += `
                <div class="contact-item">
                    <i class="fa-solid fa-phone"></i>
                    <span>${lead['Phone Number']}</span>
                    <button class="copy-btn" onclick="copyText('${lead['Phone Number']}', 'Phone copied!')" title="Copy phone">
                        <i class="fa-solid fa-copy"></i>
                    </button>
                </div>
            `;
        }
        if (lead['Email']) {
            contactHtml += `
                <div class="contact-item">
                    <i class="fa-solid fa-envelope"></i>
                    <span style="font-size: 0.8rem; word-break: break-all;">${lead['Email']}</span>
                    <button class="copy-btn" onclick="copyText('${lead['Email']}', 'Email copied!')" title="Copy email">
                        <i class="fa-solid fa-copy"></i>
                    </button>
                </div>
            `;
        }
        if (!contactHtml) {
            contactHtml = '<span class="text-secondary">No contact info</span>';
        }

        tr.innerHTML = `
            <td>${nameHtml}</td>
            <td>
                <div class="location-cell">
                    <span class="city">${lead['City']}</span>
                    <span class="country">${lead['Country']}</span>
                </div>
            </td>
            <td>${ratingHtml}</td>
            <td>${contactHtml}</td>
            <td><span style="font-weight: 500;">${lead['Appointment Method'] || 'Unknown'}</span></td>
            <td><span class="badge ${autoClass}"><i class="fa-solid ${getAutomationIcon(autoText)}"></i> ${autoText}</span></td>
            <td><span class="badge ${priorityClass}">${lead['Lead Priority']}</span></td>
            <td>
                <button class="btn btn-light btn-link" style="padding: 0.4rem 0.75rem;" onclick="viewLeadDetails(${lead['Lead ID']})">
                    <i class="fa-solid fa-circle-info"></i> View
                </button>
            </td>
        `;
        leadsTbody.appendChild(tr);
    });
}

function getAutomationIcon(status) {
    if (status === 'Automated') return 'fa-robot';
    if (status === 'Semi-Automated') return 'fa-circle-dot';
    return 'fa-hand';
}

// View individual lead details in modal
function viewLeadDetails(leadId) {
    const lead = allLeads.find(l => l['Lead ID'] === leadId);
    if (!lead) return;

    modalTitle.innerHTML = `<i class="fa-solid fa-house-medical text-primary"></i> ${lead['Clinic Name']}`;
    
    let socialHtml = '<span class="text-secondary">None</span>';
    if (lead['Social Media Links']) {
        const links = lead['Social Media Links'].split(',');
        socialHtml = links.map(link => {
            const trimmed = link.trim();
            let icon = 'fa-link';
            if (trimmed.includes('instagram.com')) icon = 'fa-brands fa-instagram';
            else if (trimmed.includes('facebook.com')) icon = 'fa-brands fa-facebook';
            return `<a href="${trimmed}" target="_blank" rel="noopener noreferrer" style="margin-right: 10px; display: inline-flex; align-items: center; gap: 4px;">
                <i class="${icon}"></i> ${trimmed.split('/').pop() || 'Social'}
            </a>`;
        }).join(' ');
    }

    modalBody.innerHTML = `
        <div class="detail-grid">
            <div class="detail-item">
                <h4>Clinic Type</h4>
                <p>${lead['Clinic Type'] || 'N/A'}</p>
            </div>
            <div class="detail-item">
                <h4>Location</h4>
                <p>${lead['City']}, ${lead['Country']}</p>
            </div>
            <div class="detail-item-full">
                <h4>Full Address</h4>
                <p><i class="fa-solid fa-map-pin text-secondary"></i> ${lead['Address'] || 'N/A'}</p>
            </div>
            <div class="detail-item">
                <h4>Phone Number</h4>
                <p>${lead['Phone Number'] ? `<i class="fa-solid fa-phone"></i> ${lead['Phone Number']}` : 'N/A'}</p>
            </div>
            <div class="detail-item">
                <h4>Email Address</h4>
                <p>${lead['Email'] ? `<i class="fa-solid fa-envelope"></i> ${lead['Email']}` : 'N/A'}</p>
            </div>
            <div class="detail-item">
                <h4>Website</h4>
                <p>${lead['Website URL'] ? `<a href="${lead['Website URL']}" target="_blank" rel="noopener noreferrer"><i class="fa-solid fa-globe"></i> Visit Website</a>` : 'N/A'}</p>
            </div>
            <div class="detail-item">
                <h4>Doctor/Owner Name</h4>
                <p><i class="fa-solid fa-user-md text-secondary"></i> ${lead['Doctor/Owner Name'] || 'N/A'}</p>
            </div>
            <div class="detail-item">
                <h4>Appointment Method</h4>
                <p><i class="fa-solid fa-calendar-check text-secondary"></i> ${lead['Appointment Method'] || 'Unknown'}</p>
            </div>
            <div class="detail-item">
                <h4>Automation Status</h4>
                <p>${lead['Automation Status'] || 'Unknown'}</p>
            </div>
            <div class="detail-item-full">
                <h4>Social Media Links</h4>
                <p>${socialHtml}</p>
            </div>
            <div class="detail-item-full">
                <h4>Notes</h4>
                <p>${lead['Notes'] || 'No notes added yet.'}</p>
            </div>
        </div>
    `;
    
    detailsModal.classList.add('show');
}

// Start Lead Generation Process
async function startLeadGeneration() {
    const country = selectCountry.value;
    const city = selectCity.value;
    const type = selectType.value;

    if (!city || !type) return;

    btnGenerate.disabled = true;
    const generateIcon = btnGenerate.querySelector('i');
    generateIcon.className = 'fa-solid fa-spinner spinning btn-icon';
    btnGenerate.textContent = 'Extracting...';

    addLog(`Initiating scraping: Search for "${type}" in ${city}, ${country}...`, 'info');
    
    try {
        const response = await fetch(`/generate/${city}/${type}`, { method: 'POST' });
        const result = await response.json();

        if (response.ok) {
            addLog(`Server responded: ${result.message}`, 'success');
            addLog(`Job queued. Scraping will run in the background. Polling for updates...`, 'info');
            
            // Start polling to detect new leads being added
            startDatabasePolling();
        } else {
            throw new Error(result.detail || 'Extraction failed to queue');
        }
    } catch (err) {
        console.error('Scraping trigger error:', err);
        addLog(`Extraction trigger error: ${err.message}`, 'error');
        showToast('Failed to trigger lead extraction.', 'error');
        resetGeneratorButton();
    }
}

// Poll database for lead additions
let pollInterval = null;
let pollTicks = 0;
let initialLeadsCount = 0;

function startDatabasePolling() {
    if (pollInterval) clearInterval(pollInterval);
    
    initialLeadsCount = allLeads.length;
    pollTicks = 0;
    
    pollInterval = setInterval(async () => {
        pollTicks++;
        addLog(`Polling database... (attempt ${pollTicks})`, 'info');
        
        try {
            // Load stats and leads again
            await loadDashboardData();
            
            const newCount = allLeads.length;
            const added = newCount - initialLeadsCount;
            
            if (added > 0) {
                addLog(`Database updated! Found and loaded ${added} new clinic lead(s).`, 'success');
                showToast(`Found ${added} new leads!`, 'success');
                stopDatabasePolling();
            } else if (pollTicks >= 30) { // Timeout after 2.5 minutes (30 * 5s)
                addLog(`Polling timed out. Checking background tasks or logs is recommended.`, 'warning');
                stopDatabasePolling();
            }
        } catch (err) {
            console.error('Polling error:', err);
        }
    }, 5000);
}

function stopDatabasePolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
    resetGeneratorButton();
}

function resetGeneratorButton() {
    btnGenerate.disabled = false;
    btnGenerate.innerHTML = '<i class="fa-solid fa-magnifying-glass-location btn-icon"></i>Start Extraction';
}

// Sync leads to Google Sheet
async function syncLeadsToGoogleSheet() {
    btnExportSheet.disabled = true;
    const exportIcon = btnExportSheet.querySelector('i');
    exportIcon.className = 'fa-solid fa-sync spinning btn-icon';
    btnExportSheet.textContent = 'Syncing...';
    
    addLog('Exporting database leads to Google Sheets...', 'info');

    try {
        const response = await fetch('/export', { method: 'POST' });
        const result = await response.json();

        if (result.status === 'Success') {
            addLog(`Google Sheet updated! ${result.message}`, 'success');
            showToast('Google Sheets synced successfully!', 'success');
        } else if (result.status === 'Warning') {
            addLog(`Export Warning: ${result.message}`, 'warning');
            showToast(result.message, 'warning');
        } else {
            throw new Error(result.message || 'Export error');
        }
    } catch (err) {
        console.error('Google Sheets Sync failed:', err);
        addLog(`Sheets sync error: ${err.message}`, 'error');
        showToast('Sheets sync failed.', 'error');
    } finally {
        btnExportSheet.disabled = false;
        btnExportSheet.innerHTML = '<i class="fa-solid fa-file-excel btn-icon"></i>Sync to Google Sheet';
    }
}

// Copy helper function
function copyText(text, successMsg) {
    navigator.clipboard.writeText(text).then(() => {
        showToast(successMsg, 'success');
    }).catch(err => {
        console.error('Failed to copy:', err);
        showToast('Failed to copy to clipboard.', 'error');
    });
}

// Log box updates
function addLog(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    let icon = '<i class="fa-solid fa-info-circle"></i>';
    
    if (type === 'success') icon = '<i class="fa-solid fa-circle-check"></i>';
    else if (type === 'warning') icon = '<i class="fa-solid fa-circle-exclamation"></i>';
    else if (type === 'error') icon = '<i class="fa-solid fa-triangle-exclamation"></i>';
    
    const logLine = document.createElement('div');
    logLine.className = `log-line log-${type}`;
    logLine.innerHTML = `<span>[${timestamp}]</span> ${icon} <span>${escapeHTML(message)}</span>`;
    
    logOutput.appendChild(logLine);
    logOutput.scrollTop = logOutput.scrollHeight;
}

// Helper to escape HTML characters
function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, 
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag)
    );
}

// Show temporary float toasts
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = '<i class="fa-solid fa-info-circle"></i>';
    if (type === 'success') icon = '<i class="fa-solid fa-circle-check" style="color: var(--success-color)"></i>';
    else if (type === 'error') icon = '<i class="fa-solid fa-triangle-exclamation" style="color: var(--danger-color)"></i>';
    else if (type === 'warning') icon = '<i class="fa-solid fa-circle-exclamation" style="color: var(--warning-color)"></i>';

    toast.innerHTML = `${icon} <span>${message}</span>`;
    toastContainer.appendChild(toast);

    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 50);

    // Remove toast
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Debounce helper
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

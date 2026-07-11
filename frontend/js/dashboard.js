/* ============================================================
   SEJIS — Dashboard Page Logic
   Fetches interview records and renders the history table
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  if (!requireAuth()) return;

  loadDashboard();
  setupLogout();
});

/**
 * Set up the logout button.
 */
function setupLogout() {
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', (e) => {
      e.preventDefault();
      logout();
    });
  }
}

/**
 * Fetch dashboard data and render the table.
 */
async function loadDashboard() {
  const tableBody = document.getElementById('dashboard-table-body');
  const emptyState = document.getElementById('empty-state');
  const tableWrap = document.getElementById('table-wrap');
  const statsSection = document.getElementById('stats-section');

  try {
    const records = await apiGet('/api/v1/dashboard/dashboard');

    if (!records || records.length === 0) {
      // Show empty state
      if (emptyState) emptyState.classList.remove('hidden');
      if (tableWrap) tableWrap.classList.add('hidden');
      if (statsSection) statsSection.classList.add('hidden');
      return;
    }

    // Show table, hide empty state
    if (emptyState) emptyState.classList.add('hidden');
    if (tableWrap) tableWrap.classList.remove('hidden');
    if (statsSection) statsSection.classList.remove('hidden');

    // Update stats
    updateStats(records);

    // Render table rows
    tableBody.innerHTML = '';
    records.forEach((record, index) => {
      const row = createTableRow(record, index + 1);
      tableBody.appendChild(row);
    });

  } catch (error) {
    showToast(error.message || 'Failed to load dashboard data.', 'error');
  }
}

/**
 * Update stats cards with aggregate data.
 */
function updateStats(records) {
  const totalInterviews = records.length;
  const avgScore = records.length > 0
    ? Math.round(records.reduce((sum, r) => sum + (r.total_score || 0), 0) / records.length)
    : 0;
  const bestScore = records.length > 0
    ? Math.max(...records.map(r => r.total_score || 0))
    : 0;

  const totalEl = document.getElementById('stat-total');
  const avgEl = document.getElementById('stat-avg');
  const bestEl = document.getElementById('stat-best');

  if (totalEl) totalEl.textContent = totalInterviews;
  if (avgEl) avgEl.textContent = avgScore;
  if (bestEl) bestEl.textContent = bestScore;
}

/**
 * Create a table row element for an interview record.
 */
function createTableRow(record, index) {
  const tr = document.createElement('tr');

  const date = new Date(record.created_at);
  const formattedDate = date.toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric'
  });

  tr.innerHTML = `
    <td>${index}</td>
    <td><strong>${escapeHtml(record.job_role)}</strong></td>
    <td class="${getScoreClass(record.intro.mark, 50)}">${record.intro.mark}/50</td>
    <td class="${getScoreClass(record.dsa.mark, 100)}">${record.dsa.mark}/100</td>
    <td class="${getScoreClass(record.system_design.mark, 100)}">${record.system_design.mark}/100</td>
    <td class="${getScoreClass(record.hr_final.mark, 50)}">${record.hr_final.mark}/50</td>
    <td class="total-score-cell">${record.total_score}/300</td>
    <td>${formattedDate}</td>
    <td>
      <button class="btn-download" onclick="downloadReport('${record.id}', '${escapeHtml(record.job_role)}')">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        PDF
      </button>
    </td>
  `;

  return tr;
}

/**
 * Get CSS class based on score percentage.
 */
function getScoreClass(score, max) {
  const pct = (score / max) * 100;
  if (pct >= 70) return 'score-cell score-high';
  if (pct >= 40) return 'score-cell score-mid';
  return 'score-cell score-low';
}

/**
 * Download a PDF report for a specific interview record.
 */
async function downloadReport(recordId, jobRole) {
  try {
    showToast('Generating PDF report...', 'info');
    const cleanRole = jobRole.toLowerCase().replace(/\s+/g, '-').replace(/[()]/g, '');
    await apiDownloadFile(
      `/api/v1/download/interview/${recordId}/pdf`,
      `interview-report-${cleanRole}.pdf`
    );
    showToast('Report downloaded successfully!', 'success');
  } catch (error) {
    showToast(error.message || 'Failed to download report.', 'error');
  }
}

/**
 * Escape HTML to prevent XSS.
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

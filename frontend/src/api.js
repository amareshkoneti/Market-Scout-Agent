/**
 * API base URL resolution:
 * 1. VITE_API_URL if set (/api for same-origin proxy, or https://api.market-scout.me)
 * 2. Dev: local FastAPI (or /api via vite.config.js proxy)
 * 3. Production: https://api.market-scout.me (CORS allowed on backend)
 */
const API_BASE = (
    import.meta.env.VITE_API_URL?.replace(/\/$/, '') ||
    (import.meta.env.DEV ? 'http://44.195.79.94:8000' : 'https://api.market-scout.me')
);

async function apiFetch(path, options = {}) {
    const url = `${API_BASE}${path}`;
    try {
        const res = await fetch(url, {
            ...options,
            headers: {
                ...options.headers,
            },
        });
        return res;
    } catch (err) {
        const host = (() => {
            try {
                return new URL(url).host;
            } catch {
                return API_BASE;
            }
        })();
        throw new Error(
            err?.message?.includes('fetch')
                ? `Failed to reach the API (${host}). Check that the backend is running and CORS/proxy is configured.`
                : err.message
        );
    }
}

function getSessionId() {
    let sid = localStorage.getItem('rag_session_id');
    if (!sid) {
        sid = (crypto.randomUUID && crypto.randomUUID()) ||
              `${Date.now()}-${Math.random().toString(36).slice(2)}`;
        localStorage.setItem('rag_session_id', sid);
    }
    return sid;
}

export { getSessionId, API_BASE };

export async function runPipeline(companyName, options = {}) {
    const res = await apiFetch('/run-agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            company_name: companyName,
            date_window_days: options.dateWindowDays,
            session_id: getSessionId(),
            force_refresh: options.forceRefresh || false,
        }),
        signal: options.signal,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Error ${res.status}`);
    }
    return res.json();
}

export async function getReports(companyName) {
    const res = await apiFetch(`/reports/${encodeURIComponent(companyName)}`);
    if (!res.ok) throw new Error(`Error ${res.status}`);
    return res.json();
}

export async function deleteReport(reportId) {
    const res = await apiFetch(`/reports/${reportId}`, { method: 'DELETE' });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Error ${res.status}`);
    }
}

export async function getFeatures(companyName) {
    const res = await apiFetch(`/features/${encodeURIComponent(companyName)}`);
    if (!res.ok) throw new Error(`Error ${res.status}`);
    return res.json();
}

export async function getCompetitors() {
    const res = await apiFetch('/competitors');
    if (!res.ok) throw new Error(`Error ${res.status}`);
    return res.json();
}

export async function getHealth() {
    const res = await apiFetch('/health');
    if (!res.ok) throw new Error(`Error ${res.status}`);
    return res.json();
}

export async function deleteCompetitor(competitorId) {
    const res = await apiFetch(`/competitors/${competitorId}`, {
        method: 'DELETE',
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Error ${res.status}`);
    }
}

export async function createSchedule(data) {
    const res = await apiFetch('/schedules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Error ${res.status}`);
    }
    return res.json();
}

export async function getSchedules() {
    const res = await apiFetch('/schedules');
    if (!res.ok) throw new Error(`Error ${res.status}`);
    return res.json();
}

export async function deleteSchedule(jobId) {
    const res = await apiFetch(`/schedules/${jobId}`, {
        method: 'DELETE',
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Error ${res.status}`);
    }
}

export async function indexReport(report) {
    const name = report.company_name || report.competitor_name || 'default';
    const sessionId = `rag_${name.replace(/\s+/g, '_').toLowerCase()}`;
    const res = await apiFetch('/rag/index', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            report: report,
            session_id: sessionId,
        }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Error ${res.status}`);
    }
    return res.json();
}

export async function askRagQuestion(query, companyName) {
    const name = companyName || 'default';
    const sessionId = `rag_${name.replace(/\s+/g, '_').toLowerCase()}`;
    const res = await apiFetch(`/rag/ask?query=${encodeURIComponent(query)}`, {
        headers: { 'X-Session-Id': sessionId },
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Error ${res.status}`);
    }

    return res.json();
}

export async function clearCache() {
    const res = await apiFetch('/system/clear-cache', { method: 'POST' });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Error ${res.status}`);
    }
    return res.json();
}

export async function clearStorage() {
    const res = await apiFetch('/system/clear-storage', { method: 'POST' });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Error ${res.status}`);
    }
    return res.json();
}

export async function getTaskStatus(taskId) {
    const res = await apiFetch(`/task-status/${taskId}`);
    if (!res.ok) {
        throw new Error(`Error ${res.status}`);
    }
    return res.json();
}

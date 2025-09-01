// /static/js/api.js
export async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(endpoint, options);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(errorData.detail || 'API request failed');
        }
        
        return response.json();
    } catch (error) {
        console.error(`API Call Error (${endpoint}):`, error);
        throw error;
    }
}
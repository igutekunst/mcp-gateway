import { API_BASE_URL } from '../config'
import { getApiKey } from './auth'

export interface LogEntry {
    id: number
    app_id: number
    timestamp: string
    level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
    message: string
    connection_id?: string
    log_metadata?: Record<string, any>
}

export interface LogsResponse {
    logs: LogEntry[]
    total: number
}

export interface LogsFilter {
    start_time?: string
    end_time?: string
    level?: LogEntry['level']
    connection_id?: string
    limit?: number
    offset?: number
}

export const fetchLogs = async (appId: number, filter: LogsFilter): Promise<LogsResponse> => {
    const params = new URLSearchParams();

    Object.entries(filter).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
            if (key === 'start_time' || key === 'end_time') {
                // Convert local datetime to UTC ISO string
                const date = new Date(value);
                if (!isNaN(date.getTime())) {
                    params.append(key, date.toISOString());
                }
            } else {
                params.append(key, value.toString());
            }
        }
    });

    const response = await fetch(`${API_BASE_URL}/api/bridge/logs/${appId}?${params.toString()}`, {
        headers: {
            'X-API-Key': getApiKey(),
        },
    });

    if (!response.ok) {
        throw new Error(`Failed to fetch logs: ${response.statusText}`);
    }

    return response.json();
}; 
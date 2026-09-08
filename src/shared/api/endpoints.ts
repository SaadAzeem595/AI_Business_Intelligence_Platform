export const API_ENDPOINTS = {
  AUTH: {
    LOGIN: "/auth/login",
    REGISTER: "/auth/register",
    REFRESH: "/auth/refresh",
    LOGOUT: "/auth/logout",
    ME: "/auth/me",
  },
  DASHBOARD: {
    METRICS: "/dashboard/metrics",
    TRENDS: "/dashboard/trends",
  },
  DATASETS: {
    LIST: "/datasets",
    DETAIL: (id: string) => `/datasets/${id}`,
    STATS: (id: string) => `/datasets/${id}/stats`,
    UPLOAD: "/datasets/upload",
    CLEAN: (id: string) => `/datasets/${id}/clean`,
  },
  CHAT: {
    SESSION: "/chat/sessions",
    MESSAGE: "/agents/chat",
  },
  ANALYTICS: {
    FORECAST: "/analytics/forecast",
    SEGMENT: "/analytics/segment",
    ANOMALIES: "/analytics/anomalies",
  },
  SQL: {
    RUN: "/sql/run",
    SCHEMA: "/sql/schema",
  },
  REPORTS: {
    LIST: "/reports",
    GENERATE: "/reports/generate",
    DETAIL: (id: string) => `/reports/${id}`,
    REGENERATE: (id: string) => `/reports/${id}/regenerate`,
    EMAIL: (id: string) => `/reports/${id}/email`,
    DOWNLOAD: (id: string, format?: string) => `/reports/${id}/download${format ? `?format=${format}` : ""}`,
    DELETE: (id: string) => `/reports/${id}`,
    SCHEDULE: "/reports/schedule",
    SCHEDULES: "/reports/schedules/list",
    CANCEL_SCHEDULE: (id: string) => `/reports/schedules/${id}`,
  },
  SETTINGS: {
    PROFILE: "/settings/profile",
    BILLING: "/settings/billing",
    TEAM: "/settings/team",
    API_KEYS: "/settings/api-keys",
  },
};

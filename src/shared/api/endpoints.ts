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
    SESSION: "/chat/session",
    MESSAGE: "/chat/message",
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
    DELETE: (id: string) => `/reports/${id}`,
  },
  SETTINGS: {
    PROFILE: "/settings/profile",
    BILLING: "/settings/billing",
    TEAM: "/settings/team",
    API_KEYS: "/settings/api-keys",
  },
};

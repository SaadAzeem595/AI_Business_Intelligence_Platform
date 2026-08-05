import axios from "axios";
import { API_ENDPOINTS } from "./endpoints";

const getBaseURL = () => {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (!url) {
    return "http://localhost:8000/api/v1";
  }
  // Ensure the baseURL has /api/v1 appended if it's pointing to the root host
  if (url.endsWith("/")) {
    return url + "api/v1";
  }
  if (!url.endsWith("/api/v1")) {
    return url + "/api/v1";
  }
  return url;
};

export const apiClient = axios.create({
  baseURL: getBaseURL(),
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

// ==========================================
// Token Helpers
// ==========================================
const getAccessToken = () => {
  if (typeof window !== "undefined") {
    return localStorage.getItem("accessToken");
  }
  return null;
};

const setAccessToken = (token: string) => {
  if (typeof window !== "undefined") {
    localStorage.setItem("accessToken", token);
  }
};

const getRefreshToken = () => {
  if (typeof window !== "undefined") {
    return localStorage.getItem("refreshToken");
  }
  return null;
};

const setRefreshToken = (token: string) => {
  if (typeof window !== "undefined") {
    localStorage.setItem("refreshToken", token);
  }
};

const removeTokens = () => {
  if (typeof window !== "undefined") {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
  }
};

// ==========================================
// Request Interceptors
// ==========================================

// 1. Debug log requests (runs second due to reverse execution in Axios)
apiClient.interceptors.request.use(
  (config) => {
    if (process.env.NODE_ENV === "development") {
      const fullURL = `${config.baseURL || ""}${config.url || ""}`;
      console.log(`[HTTP Request] ${config.method?.toUpperCase()} ${fullURL}`, {
        headers: config.headers,
        payload: config.data,
        config: config,
      });
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 2. Inject JWT Authorization header (runs first due to reverse execution in Axios)
apiClient.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ==========================================
// Response Interceptors
// ==========================================

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// 1. Token Refresh cycle (runs first in response interceptors)
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (originalRequest.url === API_ENDPOINTS.AUTH.REFRESH) {
        removeTokens();
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        return Promise.reject(error);
      }

      originalRequest._retry = true;

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      isRefreshing = true;

      try {
        const refreshToken = getRefreshToken();
        const params = new URLSearchParams();
        params.append("refreshToken", refreshToken || "");

        // Make refresh post request as form URL-encoded payload
        const response = await apiClient.post<{ accessToken: string; refreshToken?: string }>(
          API_ENDPOINTS.AUTH.REFRESH,
          params,
          {
            headers: {
              "Content-Type": "application/x-www-form-urlencoded",
            },
          }
        );
        const { accessToken, refreshToken: newRefreshToken } = response.data;

        setAccessToken(accessToken);
        if (newRefreshToken) {
          setRefreshToken(newRefreshToken);
        }
        apiClient.defaults.headers.common["Authorization"] = `Bearer ${accessToken}`;

        processQueue(null, accessToken);
        isRefreshing = false;

        originalRequest.headers.Authorization = `Bearer ${accessToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        isRefreshing = false;
        removeTokens();
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// 2. Rich debugging, log execution, and descriptive error formatting (runs second)
apiClient.interceptors.response.use(
  (response) => {
    if (process.env.NODE_ENV === "development") {
      console.log(`[HTTP Response] ${response.status} from ${response.config.url}`, {
        body: response.data,
        headers: response.headers,
      });
    }
    return response;
  },
  (error) => {
    const config = error.config || {};
    const fullURL = `${config.baseURL || ""}${config.url || ""}`;
    const responseData = error.response?.data;
    const status = error.response?.status;

    if (process.env.NODE_ENV === "development") {
      console.error(`[HTTP Error Debug]`, {
        requestURL: fullURL,
        method: config.method?.toUpperCase(),
        requestPayload: config.data,
        responseStatus: status,
        responseBody: responseData,
        axiosConfig: config,
        originalError: error,
      });
    }

    let descriptiveMessage = "An unexpected network error occurred.";

    if (error.code === "ECONNABORTED") {
      descriptiveMessage = "The request timed out. The backend took too long to respond.";
    } else if (!error.response) {
      // No response was received (Connection refused or CORS error)
      if (error.message && error.message.toLowerCase().includes("network error")) {
        descriptiveMessage = `CORS or Network Connection Error: Unable to connect to the backend server at '${apiClient.defaults.baseURL}'. Please verify that the FastAPI backend is running and that CORS allows requests from this origin.`;
      } else {
        descriptiveMessage = `Connection Refused: Backend server is unreachable at '${apiClient.defaults.baseURL}'.`;
      }
    } else {
      // Response was received with a non-2xx status code
      if (status === 404) {
        descriptiveMessage = `Endpoint Not Found (404): The requested path '${config.url}' does not exist on the server.`;
      } else if (status === 500) {
        descriptiveMessage = `Internal Server Error (500): The server encountered an error while processing the request. Details: ${JSON.stringify(responseData)}`;
      } else if (status === 403) {
        descriptiveMessage = "Forbidden (403): You do not have permission to access this resource.";
      } else if (status === 401) {
        descriptiveMessage = "Unauthorized (401): Please log in to complete this action.";
      } else {
        descriptiveMessage = `Server Error (${status}): ${responseData?.detail || responseData?.message || JSON.stringify(responseData)}`;
      }
    }

    // Override message field so Axios throws have clear descriptive messages
    error.message = descriptiveMessage;
    return Promise.reject(error);
  }
);

// ==========================================
// Startup Environment URL Validation
// ==========================================
const validateApiUrl = () => {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (!url) {
    if (process.env.NODE_ENV === "development") {
      console.warn(
        "%c[API Client Warning] NEXT_PUBLIC_API_URL is missing. Using default http://localhost:8000",
        "color: orange; font-weight: bold;"
      );
    }
    return;
  }
  try {
    new URL(url);
    if (process.env.NODE_ENV === "development") {
      console.log(`[API Client Initialized] baseURL = ${apiClient.defaults.baseURL}`);
    }
  } catch (e) {
    console.error(
      `%c[API Client Error] NEXT_PUBLIC_API_URL is not a valid URL: "${url}".`,
      "color: red; font-weight: bold;"
    );
  }
};
validateApiUrl();

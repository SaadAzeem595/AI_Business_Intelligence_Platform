import axios from "axios";
import { API_ENDPOINTS } from "./endpoints";

// Defensive check to prevent enabling dev auth bypass in production
const isProductionEnv =
  process.env.ENVIRONMENT === "production" ||
  process.env.APP_ENV === "production";

if (isProductionEnv && process.env.NEXT_PUBLIC_DEV_AUTH_BYPASS === "true") {
  throw new Error(
    "CRITICAL CONFIGURATION ERROR: NEXT_PUBLIC_DEV_AUTH_BYPASS cannot be enabled in a production environment!"
  );
}

const isDevAuthBypass =
  process.env.NEXT_PUBLIC_DEV_AUTH_BYPASS === "true" && !isProductionEnv;


const getBaseURL = () => {
  let url = process.env.NEXT_PUBLIC_API_URL || "/api/v1";
  url = url.trim().replace(/\/+$/, "");
  if (url.startsWith("/")) {
    return url.endsWith("/api/v1") ? url : `${url}/api/v1`;
  }
  if (process.env.NODE_ENV !== "production") {
    url = url.replace("://localhost", "://127.0.0.1");
  }
  if (!url.endsWith("/api/v1")) {
    url = `${url}/api/v1`;
  }
  return url;
};

export const apiClient = axios.create({
  baseURL: getBaseURL(),
  timeout: 300000,
  headers: {
    "Content-Type": "application/json",
  },
});

// ==========================================
// Token Helpers
// ==========================================
const getAccessToken = async () => {
  if (typeof window !== "undefined") {
    let Clerk = (window as any).Clerk;
    if (!Clerk) {
      // If Clerk script/SDK is still mounting on initial window load, wait up to 1500ms for window.Clerk
      await new Promise((resolve) => {
        const timeoutId = setTimeout(() => {
          clearInterval(intervalId);
          resolve(null);
        }, 1500);

        const intervalId = setInterval(() => {
          if ((window as any).Clerk) {
            clearInterval(intervalId);
            clearTimeout(timeoutId);
            Clerk = (window as any).Clerk;
            resolve(null);
          }
        }, 50);
      });
    }

    if (Clerk) {
      if (!Clerk.isReady) {
        // Wait for Clerk to be ready with a safety timeout to prevent hanging requests
        await new Promise((resolve) => {
          const timeoutId = setTimeout(() => {
            clearInterval(intervalId);
            console.warn("[API Client] Clerk initialization timed out after 2000ms. Continuing without token.");
            resolve(null);
          }, 2000);

          const intervalId = setInterval(() => {
            if (Clerk.isReady) {
              clearInterval(intervalId);
              clearTimeout(timeoutId);
              resolve(null);
            }
          }, 50);
        });
      }
      try {
        let tokenPromise = Clerk.session?.getToken({ skipCache: true });
        if (!tokenPromise) {
          tokenPromise = Clerk.session?.getToken();
        }
        if (tokenPromise) {
          const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error("Clerk token retrieval timed out")), 3000)
          );
          const token = await Promise.race([tokenPromise, timeoutPromise]);
          if (token && typeof token === "string") {
            return token;
          }
        }
      } catch (err) {
        try {
          const fallback = await Clerk.session?.getToken();
          if (fallback && typeof fallback === "string") {
            return fallback;
          }
        } catch {}
        console.error("Failed to retrieve Clerk token:", err);
      }
    }
  }
  return null;
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
  async (config) => {
    // If dev auth bypass is active, check if a Clerk session is signed in; if not, bypass cleanly
    if (isDevAuthBypass) {
      const Clerk = typeof window !== "undefined" ? (window as any).Clerk : null;
      if (Clerk?.session) {
        try {
          const token = await Clerk.session.getToken();
          if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`;
            return config;
          }
        } catch {}
      }
      return config;
    }

    let token = await getAccessToken();
    if (!token && typeof window !== "undefined") {
      token = localStorage.getItem("accessToken");
    }

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
      console.error(
        `[HTTP Error Debug] ${config.method?.toUpperCase() || "GET"} ${fullURL} -> Status: ${status || "Network/CORS Error"} | Code: ${error.code || "N/A"}`
      );
      if (responseData) {
        console.error(`[HTTP Response Data]:`, responseData);
      } else {
        console.error(`[HTTP Error Details]:`, error.message || error);
      }
    }

    let descriptiveMessage = "An unexpected network error occurred.";
    let errorType: 
      | "NETWORK_ERROR" 
      | "CORS_ERROR" 
      | "401_UNAUTHORIZED" 
      | "403_FORBIDDEN" 
      | "404_ENDPOINT_NOT_FOUND" 
      | "422_VALIDATION_ERROR" 
      | "500_SERVER_ERROR" 
      | "FORECAST_DATA_ERROR" = "NETWORK_ERROR";

    const isForecastRequest = config.url?.includes("/forecast");

    if (error.code === "ECONNABORTED") {
      errorType = "NETWORK_ERROR";
      const isProjectCreation = config.url?.includes("/projects") && config.method?.toUpperCase() === "POST";
      if (isProjectCreation) {
        descriptiveMessage = "Project creation timed out. Please check that the backend and database are running.";
      } else {
        descriptiveMessage = "Request timed out. Please verify that the backend server is responding.";
      }
    } else if (!error.response) {
      // Differentiate between network disconnection, connection refusal, and CORS failures
      if (typeof navigator !== "undefined" && !navigator.onLine) {
        errorType = "NETWORK_ERROR";
        descriptiveMessage = "Network Offline: Your browser is currently disconnected from the internet.";
      } else if (error.message && error.message.toLowerCase().includes("network error")) {
        errorType = "CORS_ERROR";
        descriptiveMessage = `CORS Error: The backend response was blocked by CORS policy or connection was refused at '${apiClient.defaults.baseURL}'.`;
      } else {
        errorType = "NETWORK_ERROR";
        descriptiveMessage = `Network Error: Unable to establish connection to the backend at '${apiClient.defaults.baseURL}'.`;
      }
    } else {
      // Response was received with a non-2xx status code
      const detailMsg = responseData?.detail || responseData?.message || responseData?.error;
      const parsedDetail = typeof detailMsg === "string" 
        ? detailMsg 
        : (Array.isArray(detailMsg) 
            ? detailMsg.map((e: any) => e.msg || JSON.stringify(e)).join("; ") 
            : (detailMsg ? JSON.stringify(detailMsg) : null));

      if (status === 401) {
        errorType = "401_UNAUTHORIZED";
        descriptiveMessage = parsedDetail || "Unauthorized (401): Your session has expired or is invalid. Please log in.";
      } else if (status === 403) {
        errorType = "403_FORBIDDEN";
        descriptiveMessage = parsedDetail || "Forbidden (403): You do not have permission or subscription entitlement for this feature.";
      } else if (status === 404) {
        errorType = "404_ENDPOINT_NOT_FOUND";
        descriptiveMessage = parsedDetail || `Endpoint Not Found (404): The requested path '${config.url}' does not exist on the server.`;
      } else if (status === 422) {
        if (isForecastRequest) {
          errorType = "FORECAST_DATA_ERROR";
          descriptiveMessage = parsedDetail || `Forecasting Data Error (422): Invalid parameters or non-temporal columns provided.`;
        } else {
          errorType = "422_VALIDATION_ERROR";
          descriptiveMessage = parsedDetail || `Validation Error (422): Invalid request parameters passed to '${config.url}'.`;
        }
      } else if (status === 400) {
        if (isForecastRequest) {
          errorType = "FORECAST_DATA_ERROR";
          descriptiveMessage = parsedDetail || "Forecasting Data Error (400): Unable to compute time-series forecast on the selected dataset.";
        } else {
          descriptiveMessage = parsedDetail || `Bad Request (400): ${JSON.stringify(responseData)}`;
        }
      } else if (status === 500) {
        if (isForecastRequest) {
          errorType = "FORECAST_DATA_ERROR";
          descriptiveMessage = parsedDetail ? `Forecasting Server Error (500): ${parsedDetail}` : "Forecasting Error (500): Server encountered an error processing forecasting model.";
        } else {
          errorType = "500_SERVER_ERROR";
          descriptiveMessage = parsedDetail ? `Internal Server Error (500): ${parsedDetail}` : `Internal Server Error (500): The server encountered an error while processing the request.`;
        }
      } else {
        descriptiveMessage = parsedDetail || `Server Error (${status}): ${JSON.stringify(responseData)}`;
      }
    }

    // Attach errorType to error object
    (error as any).errorType = errorType;
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
        "%c[API Client Warning] NEXT_PUBLIC_API_URL is missing. Using default /api/v1",
        "color: orange; font-weight: bold;"
      );
    }
    return;
  }
  if (url.startsWith("/")) {
    if (process.env.NODE_ENV === "development") {
      console.log(`[API Client Initialized] baseURL = ${apiClient.defaults.baseURL}`);
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

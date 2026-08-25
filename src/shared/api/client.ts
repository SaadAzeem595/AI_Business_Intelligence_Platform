import axios from "axios";
import { API_ENDPOINTS } from "./endpoints";

// Defensive check to prevent enabling dev auth bypass in production
const isProductionEnv =
  process.env.NODE_ENV === "production" ||
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
  let url = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
  url = url.trim().replace(/\/+$/, "");
  if (!url.endsWith("/api/v1")) {
    url = `${url}/api/v1`;
  }
  return url;
};

export const apiClient = axios.create({
  baseURL: getBaseURL(),
  timeout: 60000,
  headers: {
    "Content-Type": "application/json",
  },
});

// ==========================================
// Token Helpers
// ==========================================
const getAccessToken = async () => {
  if (typeof window !== "undefined") {
    const Clerk = (window as any).Clerk;
    if (Clerk) {
      if (!Clerk.isReady) {
        // Wait for Clerk to be ready with a safety timeout to prevent hanging requests
        await new Promise((resolve) => {
          const timeoutId = setTimeout(() => {
            clearInterval(intervalId);
            console.warn("[API Client] Clerk initialization timed out after 1000ms. Continuing without token.");
            resolve(null);
          }, 1000);

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
        const tokenPromise = Clerk.session?.getToken();
        if (tokenPromise) {
          const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error("Clerk token retrieval timed out")), 2000)
          );
          const token = await Promise.race([tokenPromise, timeoutPromise]);
          if (token && typeof token === "string") {
            return token;
          }
        }
      } catch (err) {
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
    // If dev auth bypass is active, do not block or try to query Clerk
    if (isDevAuthBypass) {
      return config;
    }
    const token = await getAccessToken();
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

    if (error.code === "ECONNABORTED") {
      const isProjectCreation = config.url?.includes("/projects") && config.method?.toUpperCase() === "POST";
      if (isProjectCreation) {
        descriptiveMessage = "Project creation timed out. Please check that the backend and database are running.";
      } else {
        descriptiveMessage = "Request timed out. Please verify that the backend server is responding.";
      }
    } else if (!error.response) {
      // No response was received (Connection refused or CORS error)
      if (error.message && error.message.toLowerCase().includes("network error")) {
        descriptiveMessage = `CORS or Network Connection Error: Unable to connect to the DataPilot API at '${apiClient.defaults.baseURL}'. Verify that the FastAPI backend is running and CORS allows requests from this origin.`;
      } else {
        descriptiveMessage = `Unable to connect to the DataPilot API at '${apiClient.defaults.baseURL}'. Verify that the FastAPI backend is running.`;
      }
    } else {
      // Response was received with a non-2xx status code
      const detailMsg = responseData?.detail || responseData?.message || responseData?.error;
      const parsedDetail = typeof detailMsg === "string" 
        ? detailMsg 
        : (Array.isArray(detailMsg) 
            ? detailMsg.map((e: any) => e.msg || JSON.stringify(e)).join("; ") 
            : (detailMsg ? JSON.stringify(detailMsg) : null));

      if (parsedDetail) {
        descriptiveMessage = parsedDetail;
      } else if (status === 422) {
        descriptiveMessage = `Validation Error (422): Invalid request parameters passed to '${config.url}'.`;
      } else if (status === 400) {
        descriptiveMessage = `Bad Request (400): ${JSON.stringify(responseData)}`;
      } else if (status === 404) {
        descriptiveMessage = `Endpoint Not Found (404): The requested path '${config.url}' does not exist on the server.`;
      } else if (status === 500) {
        descriptiveMessage = `Internal Server Error (500): The server encountered an error while processing the request.`;
      } else if (status === 403) {
        descriptiveMessage = "Forbidden (403): You do not have permission to access this resource.";
      } else if (status === 401) {
        descriptiveMessage = "Unauthorized (401): Please log in to complete this action.";
      } else {
        descriptiveMessage = `Server Error (${status}): ${JSON.stringify(responseData)}`;
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

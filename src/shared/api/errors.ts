import axios from "axios";

export interface NormalizedError {
  message: string;
  status?: number;
  code?: string;
  details?: Record<string, string[]>;
}

export function normalizeError(error: unknown): NormalizedError {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    const data = error.response?.data;
    
    let message = "An error occurred with the network request.";
    let details: Record<string, string[]> | undefined = undefined;
    let code: string | undefined = undefined;

    if (data) {
      if (typeof data === "string") {
        message = data;
      } else if (typeof data === "object" && data !== null) {
        // Handle FastAPI validation error formatting or custom exceptions
        const detailPayload = data.detail;
        if (Array.isArray(detailPayload)) {
          message = "Validation check failed on input fields.";
          details = {};
          detailPayload.forEach((err: any) => {
            const fieldPath = err.loc ? err.loc.slice(1).join(".") : "field";
            if (details) {
              details[fieldPath] = details[fieldPath] || [];
              details[fieldPath].push(err.msg);
            }
          });
        } else {
          message = data.message || data.detail || message;
        }
        code = data.code;
      }
    }

    if (status === 401) {
      message = "Your session expired. Please sign in again.";
    } else if (status === 403) {
      message = "You do not have access credentials for this resource.";
    } else if (status === 404) {
      message = "The requested resource could not be found.";
    } else if (status === 500) {
      message = "An internal server database error occurred. Try again later.";
    } else if (error.code === "ECONNABORTED") {
      message = "Request timed out. The server is taking too long to reply.";
    } else if (!error.response) {
      message = "Cannot contact backend API. Check your internet connection.";
    }

    return {
      message,
      status,
      code,
      details,
    };
  }

  if (error instanceof Error) {
    return { message: error.message };
  }

  return { message: "An unexpected client-side error occurred." };
}

import { apiClient } from "@/shared/api/client";
import { API_ENDPOINTS } from "@/shared/api/endpoints";
import { LoginInput, SignupInput } from "../schemas/auth.schema";
import { SessionInfo, User } from "@/shared/types/auth";

export const AuthService = {
  async login(data: LoginInput): Promise<SessionInfo> {
    const params = new URLSearchParams();
    params.append("username", data.email);
    params.append("password", data.password);

    const response = await apiClient.post<SessionInfo>(API_ENDPOINTS.AUTH.LOGIN, params, {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    });
    return response.data;
  },

  async register(data: SignupInput): Promise<SessionInfo> {
    const params = new URLSearchParams();
    params.append("email", data.email);
    params.append("password", data.password);
    if (data.name) {
      params.append("name", data.name);
    }

    const response = await apiClient.post<SessionInfo>(API_ENDPOINTS.AUTH.REGISTER, params, {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    });
    return response.data;
  },

  async me(): Promise<User> {
    const response = await apiClient.get<User>(API_ENDPOINTS.AUTH.ME);
    return response.data;
  },

  async logout(): Promise<void> {
    await apiClient.post(API_ENDPOINTS.AUTH.LOGOUT);
  },
};

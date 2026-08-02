import { apiClient } from "@/shared/api/client";
import { API_ENDPOINTS } from "@/shared/api/endpoints";
import { LoginInput, SignupInput } from "../schemas/auth.schema";
import { SessionInfo, User } from "@/shared/types/auth";

export const AuthService = {
  async login(data: LoginInput): Promise<SessionInfo> {
    const response = await apiClient.post<SessionInfo>(API_ENDPOINTS.AUTH.LOGIN, data);
    return response.data;
  },

  async register(data: SignupInput): Promise<SessionInfo> {
    const response = await apiClient.post<SessionInfo>(API_ENDPOINTS.AUTH.REGISTER, data);
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

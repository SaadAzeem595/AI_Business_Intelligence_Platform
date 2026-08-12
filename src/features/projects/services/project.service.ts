import { apiClient } from "@/shared/api/client";

export interface Project {
  id: string;
  name: string;
  description?: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
  datasetsCount?: number;
  status?: "Active" | "Draft" | "Archived";
  lastUpdated?: string;
  teamSize?: number;
}

export const ProjectService = {
  async getList(): Promise<Project[]> {
    const response = await apiClient.get<Project[]>("/projects");
    return response.data;
  },

  async get(id: string): Promise<Project> {
    const response = await apiClient.get<Project>(`/projects/${id}`);
    return response.data;
  },

  async create(name: string, description?: string): Promise<Project> {
    const response = await apiClient.post<Project>("/projects", { name, description });
    return response.data;
  },

  async delete(id: string): Promise<void> {
    await apiClient.delete(`/projects/${id}`);
  },
};

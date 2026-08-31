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

// Stateful fallback mock list for local dev when backend server is offline or initializing
let mockProjectsList: Project[] = [
  {
    id: "proj-default-1",
    name: "E-Commerce Executive Analytics",
    description: "Multi-channel sales performance, revenue forecasting, customer churn prediction, and inventory metrics.",
    owner_id: "dev-user-001",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    datasetsCount: 4,
    status: "Active",
    lastUpdated: "Just now",
    teamSize: 3,
  },
  {
    id: "proj-default-2",
    name: "Financial Operations & Margin Control",
    description: "Quarterly P&L breakdown, expenditure anomaly detection, and cash-flow projections.",
    owner_id: "dev-user-001",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    datasetsCount: 2,
    status: "Active",
    lastUpdated: "2 hours ago",
    teamSize: 2,
  },
];

export const ProjectService = {
  async getList(): Promise<Project[]> {
    try {
      const response = await apiClient.get<Project[]>("/projects");
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return mockProjectsList;
    } catch (err) {
      console.warn("[ProjectService] API request failed or backend offline. Using fallback projects list.", err);
      return mockProjectsList;
    }
  },

  async get(id: string): Promise<Project> {
    try {
      const response = await apiClient.get<Project>(`/projects/${id}`);
      return response.data;
    } catch (err) {
      const found = mockProjectsList.find((p) => p.id === id);
      if (found) return found;
      return {
        id,
        name: `Project ${id}`,
        description: "Workspace overview and dataset analytics.",
        owner_id: "dev-user-001",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        datasetsCount: 1,
        status: "Active",
        lastUpdated: "Just now",
        teamSize: 1,
      };
    }
  },

  async create(name: string, description?: string): Promise<Project> {
    try {
      const response = await apiClient.post<Project>("/projects", { name, description });
      return response.data;
    } catch (err) {
      console.warn("[ProjectService] API project creation failed or backend offline. Creating mock project.", err);
      const newProj: Project = {
        id: `proj-${Date.now()}`,
        name,
        description: description || "A newly created analytics workspace.",
        owner_id: "dev-user-001",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        datasetsCount: 0,
        status: "Active",
        lastUpdated: "Just now",
        teamSize: 1,
      };
      mockProjectsList = [newProj, ...mockProjectsList];
      return newProj;
    }
  },

  async delete(id: string): Promise<void> {
    try {
      await apiClient.delete(`/projects/${id}`);
    } catch (err) {
      console.warn("[ProjectService] API project deletion failed or backend offline. Removing mock project.", err);
    }
    mockProjectsList = mockProjectsList.filter((p) => p.id !== id);
  },
};

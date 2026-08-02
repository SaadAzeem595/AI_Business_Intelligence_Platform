import { apiClient } from "@/shared/api/client";
import { API_ENDPOINTS } from "@/shared/api/endpoints";
import { Invoice } from "@/shared/types/reports";
import { BillingInput, WorkspaceInput, ProfileInput } from "../schemas/settings.schema";

export const BillingService = {
  async getInvoices(): Promise<Invoice[]> {
    try {
      const response = await apiClient.get<Invoice[]>(API_ENDPOINTS.SETTINGS.BILLING);
      return response.data;
    } catch {
      return [
        { invoiceId: "INV-9021", amount: "$79.00", date: "2026-08-01", status: "Paid" },
        { invoiceId: "INV-7801", amount: "$79.00", date: "2026-07-01", status: "Paid" },
        { invoiceId: "INV-6204", amount: "$79.00", date: "2026-06-01", status: "Paid" },
      ];
    }
  },

  async updateBilling(data: BillingInput): Promise<void> {
    try {
      await apiClient.post(API_ENDPOINTS.SETTINGS.BILLING, data);
    } catch {
      // Mock passes silently
    }
  },

  async updateWorkspace(data: WorkspaceInput): Promise<any> {
    try {
      const response = await apiClient.patch<any>("/settings/workspace", data);
      return response.data;
    } catch {
      return { status: "success" };
    }
  },

  async updateProfile(data: ProfileInput): Promise<any> {
    try {
      const response = await apiClient.patch<any>(API_ENDPOINTS.SETTINGS.PROFILE, data);
      return response.data;
    } catch {
      return { status: "success" };
    }
  },

  async getTeam(): Promise<any[]> {
    try {
      const response = await apiClient.get<any[]>(API_ENDPOINTS.SETTINGS.TEAM);
      return response.data;
    } catch {
      return [
        { name: "Saad Alvi", email: "saad@example.com", role: "Owner" },
        { name: "Alex Mercer", email: "alex@company.com", role: "Admin" },
        { name: "Sarah Connor", email: "sarah@company.com", role: "Viewer" },
      ];
    }
  },

  async getApiKeys(): Promise<any[]> {
    try {
      const response = await apiClient.get<any[]>(API_ENDPOINTS.SETTINGS.API_KEYS);
      return response.data;
    } catch {
      return [
        { id: "1", name: "Production duckdb link", keyPrefix: "ag_live_••••••k91z", created: "2026-08-01" },
        { id: "2", name: "AI agent chat token", keyPrefix: "ag_live_••••••x32a", created: "2026-07-28" },
      ];
    }
  },
};

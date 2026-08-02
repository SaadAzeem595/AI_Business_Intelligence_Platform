import { create } from "zustand";

interface UIState {
  isSidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (val: boolean) => void;
  activeOrg: string;
  setActiveOrg: (org: string) => void;
  activeProject: string;
  setActiveProject: (proj: string) => void;
}

export const useUIStore = create<UIState>((set) => ({
  isSidebarCollapsed: false,
  toggleSidebar: () => set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),
  setSidebarCollapsed: (val) => set({ isSidebarCollapsed: val }),
  activeOrg: "Acme Corp",
  setActiveOrg: (org) => set({ activeOrg: org }),
  activeProject: "Q3 Sales Analytics",
  setActiveProject: (proj) => set({ activeProject: proj }),
}));

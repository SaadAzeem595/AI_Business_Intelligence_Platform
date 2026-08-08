export interface User {
  id: string;
  email: string;
  name: string;
  role: "Owner" | "Admin" | "Viewer";
  avatarUrl?: string;
  createdAt: string;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  ownerId: string;
  createdAt: string;
}

export interface SessionInfo {
  user: User;
  workspace: Workspace;
  accessToken: string;
  refreshToken?: string;
}

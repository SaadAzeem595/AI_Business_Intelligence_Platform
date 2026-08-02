"use client";

import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Badge } from "@/shared/components/ui/badge";
import { BaseTable, type Column } from "@/shared/components/data-display/BaseTable";
import { User, Key, Users, Copy, Plus, Trash2 } from "lucide-react";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { useWorkspaceSettings } from "@/features/settings/hooks/useBilling";

interface APIKey {
  id: string;
  name: string;
  keyPrefix: string;
  created: string;
}

interface TeamMember {
  name: string;
  email: string;
  role: "Owner" | "Admin" | "Viewer";
}

export default function ProfileSettingsPage() {
  const [activeTab, setActiveTab] = useState<"profile" | "team" | "api">("profile");

  const { user } = useAuth();
  const { team, apiKeys: queriedKeys, updateProfile, updateWorkspace, isLoadingTeam, isLoadingApiKeys } = useWorkspaceSettings();

  // Profile fields state
  const [profile, setProfile] = useState({
    name: user?.name || "Saad Alvi",
    email: user?.email || "saad@example.com",
    role: "Workspace Owner",
  });

  // API keys state
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);

  // Team members list
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);

  React.useEffect(() => {
    if (user) {
      setProfile({
        name: user.name,
        email: user.email,
        role: "Workspace Owner",
      });
    }
  }, [user]);

  React.useEffect(() => {
    if (queriedKeys) {
      setApiKeys(queriedKeys);
    }
  }, [queriedKeys]);

  React.useEffect(() => {
    if (team) {
      setTeamMembers(team);
    }
  }, [team]);

  const apiColumns: Column<APIKey>[] = [
    { header: "Key Identifier", accessorKey: "name", cell: (row) => <span className="font-semibold text-foreground">{row.name}</span> },
    { header: "Token Prefix", accessorKey: "keyPrefix", cell: (row) => <span className="font-mono text-muted-foreground">{row.keyPrefix}</span> },
    { header: "Created At", accessorKey: "created" },
    {
      header: "Action",
      accessorKey: "actions",
      align: "right",
      cell: (row) => (
        <Button size="icon" variant="ghost" className="h-8 w-8 hover:bg-rose-500/10 text-muted-foreground hover:text-rose-500" onClick={() => handleDeleteKey(row.id)}>
          <Trash2 className="h-4 w-4" />
        </Button>
      ),
    },
  ];

  const teamColumns: Column<TeamMember>[] = [
    { header: "Collaborator", accessorKey: "name", cell: (row) => <span className="font-semibold text-foreground">{row.name}</span> },
    { header: "Email Address", accessorKey: "email" },
    {
      header: "Workspace Role",
      accessorKey: "role",
      cell: (row) => <Badge variant={row.role === "Owner" ? "default" : "secondary"}>{row.role}</Badge>,
    },
  ];

  const handleDeleteKey = (id: string) => {
    setApiKeys(apiKeys.filter((k) => k.id !== id));
  };

  const handleCreateKey = () => {
    const newKey: APIKey = {
      id: String(apiKeys.length + 1),
      name: "Local dev client",
      keyPrefix: "ag_live_••••••w40q",
      created: new Date().toISOString().split("T")[0],
    };
    setApiKeys([...apiKeys, newKey]);
  };

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/40 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Settings & Workspace</h1>
          <p className="text-xs text-muted-foreground">Manage personal profiles, coordinate team permissions, and configure API access tokens.</p>
        </div>
        <div className="flex border border-border/80 rounded-md overflow-hidden p-0.5 bg-muted/20 w-fit shrink-0">
          {[
            { id: "profile", label: "My Profile", icon: User },
            { id: "team", label: "Team Members", icon: Users },
            { id: "api", label: "API Keys", icon: Key },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`text-[10px] font-bold px-3 py-1.5 capitalize rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
                  activeTab === tab.id
                    ? "bg-card text-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {activeTab === "profile" && (
        <Card className="border-border/80 max-w-xl">
          <CardHeader>
            <CardTitle className="text-base font-bold">Personal Profile Details</CardTitle>
            <CardDescription className="text-[11px]">Update your name and work communication addresses.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">Full Name</label>
              <Input value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">Email Address</label>
              <Input value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">Access Role</label>
              <Input value={profile.role} disabled className="bg-muted/10 opacity-70" />
            </div>
            <Button size="sm" variant="brand" className="mt-2" onClick={() => updateProfile(profile)}>
              Update Profile
            </Button>
          </CardContent>
        </Card>
      )}

      {activeTab === "team" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold tracking-tight">Active collaborators</h2>
            <Button size="sm" className="gap-1.5 text-xs">
              <Plus className="h-3.5 w-3.5" /> Invite Member
            </Button>
          </div>
          <BaseTable columns={teamColumns as any} data={teamMembers} isLoading={isLoadingTeam} />
        </div>
      )}

      {activeTab === "api" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold tracking-tight">Programmatic Access Tokens</h2>
            <Button size="sm" className="gap-1.5 text-xs" onClick={handleCreateKey}>
              <Plus className="h-3.5 w-3.5" /> Generate Key
            </Button>
          </div>
          <BaseTable columns={apiColumns as any} data={apiKeys} isLoading={isLoadingApiKeys} />
        </div>
      )}
    </div>
  );
}

"use client";

import React from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { 
  FolderKanban, 
  Plus, 
  Database, 
  Clock, 
  ArrowRight, 
  Share2, 
  Users, 
  TrendingUp
} from "lucide-react";
import { useProjects } from "@/features/projects/hooks/useProjects";

export default function ProjectsPage() {
  const { projects, isLoading, createProject } = useProjects();

  const handleCreateProject = async () => {
    const name = prompt("Enter project name:", "New Project");
    if (!name) return;
    const description = prompt("Enter project description (optional):", "An analytics workspace.");
    try {
      await createProject({ name, description: description || undefined });
    } catch (err) {
      console.error("Failed to create project:", err);
      alert("Failed to create project");
    }
  };

  const projectsData = projects.map(p => ({
    id: p.id,
    name: p.name,
    description: p.description || "A newly created analytics workspace. Connect datasets and start exploring dashboards.",
    datasetsCount: p.datasetsCount || 0,
    status: p.status || "Active",
    lastUpdated: p.lastUpdated || "Just now",
    teamSize: p.teamSize || 1,
  }));

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Projects</h1>
          <p className="text-xs text-muted-foreground">Manage your business intelligence workspaces, predictive models, and shared analysis boards.</p>
        </div>
        <Button size="sm" onClick={handleCreateProject} className="self-start sm:self-auto cursor-pointer">
          <Plus className="h-4 w-4 mr-1.5" /> Create Project
        </Button>
      </div>

      {/* Overview stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-card/50 border-border/80 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-semibold">Active Workspaces</span>
            <div className="p-1 bg-brand-indigo/10 text-brand-indigo rounded">
              <FolderKanban className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-bold">{isLoading ? "..." : projectsData.length}</span>
            <p className="text-[10px] text-emerald-500 font-medium mt-0.5">🚀 Fully synchronized</p>
          </div>
        </Card>

        <Card className="bg-card/50 border-border/80 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-semibold">Connected Sources</span>
            <div className="p-1 bg-brand-indigo/10 text-brand-indigo rounded">
              <Database className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-bold">
              {projectsData.reduce((acc, p) => acc + p.datasetsCount, 0)}
            </span>
            <p className="text-[10px] text-muted-foreground mt-0.5">DuckDB relational index</p>
          </div>
        </Card>

        <Card className="bg-card/50 border-border/80 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-semibold">Team Contributors</span>
            <div className="p-1 bg-brand-indigo/10 text-brand-indigo rounded">
              <Users className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-bold">
              {projectsData.reduce((acc, p) => acc + p.teamSize, 0)}
            </span>
            <p className="text-[10px] text-muted-foreground mt-0.5">Cross-workspace roles</p>
          </div>
        </Card>

        <Card className="bg-card/50 border-border/80 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-semibold">Pipelines Triggered</span>
            <div className="p-1 bg-brand-indigo/10 text-brand-indigo rounded">
              <TrendingUp className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-bold">99.8%</span>
            <p className="text-[10px] text-emerald-500 font-medium mt-0.5">🟢 Uptime operational</p>
          </div>
        </Card>
      </div>

      {/* Projects List Grid */}
      {isLoading ? (
        <div className="text-center text-xs text-muted-foreground py-10">Loading workspaces...</div>
      ) : projectsData.length === 0 ? (
        <div className="text-center text-xs text-muted-foreground py-10 border border-dashed border-border rounded-lg bg-card/40">
          No projects found. Click "Create Project" to get started.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projectsData.map((project) => (
            <Card key={project.id} className="bg-card border-border/80 hover:border-brand-indigo/40 hover:bg-muted/5 transition-all flex flex-col justify-between select-none">
              <div>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant={project.status === "Active" ? "success" : "warning"}>
                      {project.status}
                    </Badge>
                    <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <span>{project.lastUpdated}</span>
                    </div>
                  </div>
                  <CardTitle className="text-base font-bold mt-2.5 line-clamp-1">{project.name}</CardTitle>
                  <CardDescription className="text-xs text-muted-foreground leading-relaxed line-clamp-2 mt-1.5">
                    {project.description}
                  </CardDescription>
                </CardHeader>
                
                <CardContent className="py-3 border-t border-border/40 flex items-center justify-between text-xs text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <Database className="h-3.5 w-3.5 text-brand-indigo shrink-0" />
                    <span>{project.datasetsCount} Datasets Connected</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Users className="h-3.5 w-3.5 shrink-0" />
                    <span>{project.teamSize}</span>
                  </div>
                </CardContent>
              </div>

              <div className="p-4 pt-0 border-t border-border/40 mt-auto flex items-center justify-between gap-2">
                <Button size="icon" variant="ghost" className="h-8 w-8 hover:bg-muted text-muted-foreground hover:text-foreground shrink-0">
                  <Share2 className="h-4 w-4" />
                </Button>
                <Link href={`/projects/${project.id}`} className="grow">
                  <Button size="sm" variant="outline" className="w-full text-xs font-semibold hover:bg-brand-indigo hover:text-brand-indigo-foreground cursor-pointer transition-all">
                    Open Workspace <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
                  </Button>
                </Link>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

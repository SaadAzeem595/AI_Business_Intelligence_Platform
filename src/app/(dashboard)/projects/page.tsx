"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { Input } from "@/shared/components/ui/input";
import { 
  FolderKanban, 
  Plus, 
  Database, 
  Clock, 
  ArrowRight, 
  Share2, 
  Users, 
  TrendingUp,
  X,
  AlertCircle,
  CheckCircle2,
  RefreshCw
} from "lucide-react";
import { useProjects } from "@/features/projects/hooks/useProjects";
import { AnimatePresence, motion } from "framer-motion";
import { cn } from "@/shared/lib/utils";

export default function ProjectsPage() {
  const { projects, isLoading, isError, refetch, createProject, isCreating } = useProjects();
  
  // Dialog state
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [errors, setErrors] = useState<{ name?: string }>({});
  const [apiError, setApiError] = useState<string | null>(null);
  
  // Success Toast state
  const [successToast, setSuccessToast] = useState<string | null>(null);

  const isBusy = isCreating || isSubmitting;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isBusy) return;
    setApiError(null);
    
    // Validations
    const newErrors: { name?: string } = {};
    if (!name.trim()) {
      newErrors.name = "Project name is required.";
    } else if (name.trim().length < 2) {
      newErrors.name = "Project name must be at least 2 characters.";
    } else if (name.length > 100) {
      newErrors.name = "Project name must not exceed 100 characters.";
    }
    
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }
    
    try {
      setIsSubmitting(true);
      await createProject({
        name: name.trim(),
        description: description.trim() || undefined
      });
      
      // Reset form and close dialog
      setName("");
      setDescription("");
      setErrors({});
      setIsDialogOpen(false);
      
      // Trigger success toast
      setSuccessToast(`Project "${name.trim()}" created successfully.`);
      setTimeout(() => setSuccessToast(null), 3000);
    } catch (err: any) {
      console.error("Failed to create project:", err);
      const errMsg = err?.response?.data?.detail || err.message || "Failed to create project.";
      setApiError(errMsg);
    } finally {
      setIsSubmitting(false);
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
        <Button size="sm" onClick={() => setIsDialogOpen(true)} className="self-start sm:self-auto cursor-pointer">
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
            <span className="text-2xl font-bold">{(isLoading || isError) ? "..." : projectsData.length}</span>
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
              {(isLoading || isError) ? "..." : projectsData.reduce((acc, p) => acc + p.datasetsCount, 0)}
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
              {(isLoading || isError) ? "..." : projectsData.reduce((acc, p) => acc + p.teamSize, 0)}
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

      {/* Projects List Grid / States */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-3 border border-border/40 rounded-xl bg-card/20 select-none">
          <RefreshCw className="h-8 w-8 text-brand-indigo animate-spin" />
          <p className="text-sm font-medium text-muted-foreground">Loading projects...</p>
        </div>
      ) : isError ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-4 border border-border/40 rounded-xl bg-card/20 select-none">
          <AlertCircle className="h-8 w-8 text-rose-500" />
          <div className="text-center space-y-1">
            <p className="text-sm font-semibold text-foreground">Unable to load projects</p>
            <p className="text-xs text-muted-foreground">The request to fetch your workspaces failed.</p>
          </div>
          <Button size="sm" onClick={() => refetch()} className="cursor-pointer">
            <RefreshCw className="h-3.5 w-3.5 mr-1.5" /> Retry
          </Button>
        </div>
      ) : projectsData.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-4 border border-dashed border-border rounded-xl bg-card/20 select-none text-center p-6">
          <FolderKanban className="h-10 w-10 text-muted-foreground/60" />
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-foreground">No projects yet</h3>
            <p className="text-xs text-muted-foreground max-w-xs leading-relaxed">
              You don't have any workspaces in this organization. Create a project to start importing datasets.
            </p>
          </div>
          <Button size="sm" onClick={() => setIsDialogOpen(true)} className="cursor-pointer">
            <Plus className="h-4 w-4 mr-1.5" /> Create Project
          </Button>
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

      {/* Create Project Modal */}
      <AnimatePresence>
        {isDialogOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => !isBusy && setIsDialogOpen(false)}
              className="fixed inset-0 bg-background/80 backdrop-blur-xs"
            />
            
            {/* Dialog Content */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2 }}
              className="w-full max-w-md bg-card border border-border/85 rounded-xl shadow-lg relative overflow-hidden z-10"
            >
              <div className="p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-border/40 pb-3">
                  <h3 className="text-lg font-semibold text-foreground">Create Project</h3>
                  <button
                    onClick={() => setIsDialogOpen(false)}
                    disabled={isBusy}
                    className="text-muted-foreground hover:text-foreground cursor-pointer rounded-md p-1 hover:bg-muted transition-colors disabled:opacity-50 disabled:pointer-events-none"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                
                {apiError && (
                  <div className="bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs p-3 rounded-lg flex items-center gap-2">
                    <AlertCircle className="h-4.5 w-4.5 shrink-0" />
                    <span>{apiError}</span>
                  </div>
                )}
                
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="space-y-1.5">
                    <label htmlFor="projectName" className="text-xs font-semibold text-muted-foreground">
                      Project Name
                    </label>
                    <Input
                      id="projectName"
                      value={name}
                      onChange={(e) => {
                        setName(e.target.value);
                        if (errors.name) setErrors(prev => ({ ...prev, name: "" }));
                      }}
                      placeholder="e.g. Olist E-Commerce Analytics"
                      className={cn(errors.name && "border-rose-500 focus-visible:ring-rose-500")}
                      disabled={isBusy}
                      autoFocus
                    />
                    {errors.name && (
                      <p className="text-[11px] text-rose-500 font-medium">{errors.name}</p>
                    )}
                  </div>
                  
                  <div className="space-y-1.5">
                    <label htmlFor="projectDesc" className="text-xs font-semibold text-muted-foreground">
                      Description
                    </label>
                    <textarea
                      id="projectDesc"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="A brief summary of what this project analyzes..."
                      disabled={isBusy}
                      rows={3}
                      className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-none"
                    />
                  </div>
                  
                  <div className="flex items-center justify-end gap-3 pt-3 border-t border-border/40">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setIsDialogOpen(false)}
                      disabled={isBusy}
                      className="cursor-pointer"
                    >
                      Cancel
                    </Button>
                    <Button
                      type="submit"
                      variant="brand"
                      size="sm"
                      disabled={isBusy}
                      className="cursor-pointer font-semibold min-w-[100px]"
                    >
                      {isBusy ? "Creating..." : "Create Project"}
                    </Button>
                  </div>
                </form>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Toast Notification */}
      <AnimatePresence>
        {successToast && (
          <motion.div
            initial={{ opacity: 0, y: 50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.9 }}
            className="fixed bottom-5 right-5 z-50 bg-emerald-500 text-white rounded-lg px-4 py-3 shadow-lg flex items-center gap-2.5 text-xs font-semibold select-none border border-emerald-400"
          >
            <CheckCircle2 className="h-4.5 w-4.5 shrink-0" />
            <span>{successToast}</span>
            <button onClick={() => setSuccessToast(null)} className="ml-2 hover:bg-emerald-600 rounded p-0.5 transition-colors cursor-pointer">
              <X className="h-3.5 w-3.5" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

"use client";

import React from "react";
import Link from "next/link";
import { Sparkles, BarChart3, Database, MessageSquare, ShieldAlert, Cpu, ArrowRight, CheckCircle2 } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { Card, CardContent } from "@/shared/components/ui/card";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col font-sans select-none antialiased">
      {/* Top Navbar Header */}
      <header className="border-b border-border/80 bg-background/80 backdrop-blur-md sticky top-0 z-50 h-16 flex items-center justify-between px-6 md:px-12">
        <Link 
          href="/" 
          onClick={(e) => {
            if (window.location.pathname === "/") {
              e.preventDefault();
              window.location.reload();
            }
          }}
          className="flex items-center gap-2 font-bold tracking-tight"
        >
          <div className="p-1 bg-brand-indigo rounded text-brand-indigo-foreground shrink-0">
            <Sparkles className="h-5 w-5" />
          </div>
          <span className="text-base font-extrabold">DataPilot AI</span>
        </Link>
        <nav className="hidden md:flex items-center gap-8 text-sm font-semibold text-muted-foreground">
          <a href="#features" className="hover:text-foreground transition-colors">Features</a>
          <a href="#pricing" className="hover:text-foreground transition-colors">Pricing</a>
          <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">Docs</a>
        </nav>
        <div className="flex items-center gap-4">
          <Link href="/login">
            <Button variant="ghost" size="sm">Sign In</Button>
          </Link>
          <Link href="/dashboard">
            <Button size="sm" variant="brand">Go to Dashboard</Button>
          </Link>
        </div>
      </header>

      {/* Hero Section */}
      <section className="flex flex-col items-center text-center px-6 py-20 md:py-32 max-w-5xl mx-auto space-y-6 relative overflow-hidden">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-brand-indigo/30 bg-brand-indigo/10 text-xs font-semibold text-brand-indigo mb-4 animate-fade-in">
          <Sparkles className="h-3.5 w-3.5" /> Introducing Next-Gen Predictive Analytics
        </div>
        <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight leading-tight max-w-4xl bg-gradient-to-b from-foreground to-foreground/75 bg-clip-text">
          Enterprise Business Intelligence <br/> Powered by AI & DuckDB
        </h1>
        <p className="text-sm md:text-lg text-muted-foreground max-w-2xl font-normal leading-relaxed">
          Upload spreadsheets, CSVs, or unstructured documents. Instantly forecast trends, detect anomalies, segment users, and compile PDF reports using clean natural language interfaces.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-4 pt-4">
          <Link href="/dashboard">
            <Button size="lg" variant="brand">
              Get Started for Free <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
          </Link>
          <a href="#features">
            <Button size="lg" variant="outline">Learn More</Button>
          </a>
        </div>

        {/* Dynamic Mock Visualization Dashboard */}
        <div className="pt-12 w-full max-w-4xl animate-fade-in select-none pointer-events-none">
          <div className="border border-border rounded-xl shadow-2xl bg-card/65 p-4 overflow-hidden relative">
            <div className="flex items-center gap-2 border-b border-border/80 pb-3 mb-4 text-xs font-semibold text-muted-foreground">
              <span className="w-3 h-3 rounded-full bg-rose-500/80" />
              <span className="w-3 h-3 rounded-full bg-amber-500/80" />
              <span className="w-3 h-3 rounded-full bg-emerald-500/80" />
              <span className="ml-2 font-mono">dashboard_q3_forecast.xlsx</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="border border-border/80 rounded-lg p-4 bg-muted/20 space-y-1 text-left">
                <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider">Gross Revenue</span>
                <p className="text-lg font-bold">$1,248,390</p>
                <span className="text-[10px] text-emerald-500 font-semibold inline-flex items-center">+14.2% since last month</span>
              </div>
              <div className="border border-border/80 rounded-lg p-4 bg-muted/20 space-y-1 text-left">
                <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider">Active Customers</span>
                <p className="text-lg font-bold">14,204</p>
                <span className="text-[10px] text-emerald-500 font-semibold inline-flex items-center">+8.7% since last month</span>
              </div>
              <div className="border border-border/80 rounded-lg p-4 bg-muted/20 space-y-1 text-left">
                <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider">Anomalies Detected</span>
                <p className="text-lg font-bold">2</p>
                <span className="text-[10px] text-rose-500 font-semibold inline-flex items-center">Requires attention</span>
              </div>
            </div>
            {/* Visual Chart bar mimics */}
            <div className="mt-4 h-48 border border-border/80 bg-muted/10 rounded-lg flex items-end justify-between p-4 gap-2">
              <div className="h-[20%] w-full bg-brand-indigo/35 rounded-sm" />
              <div className="h-[45%] w-full bg-brand-indigo/35 rounded-sm" />
              <div className="h-[30%] w-full bg-brand-indigo/35 rounded-sm" />
              <div className="h-[65%] w-full bg-brand-indigo/35 rounded-sm" />
              <div className="h-[55%] w-full bg-brand-indigo/35 rounded-sm" />
              <div className="h-[90%] w-full bg-brand-indigo rounded-sm" />
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="border-t border-border/85 bg-card/25 py-24 px-6 md:px-12 select-none">
        <div className="max-w-6xl mx-auto space-y-16">
          <div className="text-center space-y-4 max-w-xl mx-auto">
            <h2 className="text-2xl md:text-4xl font-extrabold tracking-tight">Complete AI Analytics Suite</h2>
            <p className="text-sm text-muted-foreground">
              Everything you need to extract and forecast value from your corporate documents and transaction tables.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <Card className="border-border/80">
              <CardContent className="p-6 space-y-4">
                <div className="p-3 bg-brand-indigo/10 rounded-lg text-brand-indigo w-fit">
                  <Database className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold tracking-tight">DuckDB Analytics Engine</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Run SQL queries, filter millions of rows, and compute correlations directly in memory at extreme speeds.
                </p>
              </CardContent>
            </Card>

            <Card className="border-border/80">
              <CardContent className="p-6 space-y-4">
                <div className="p-3 bg-emerald-500/10 rounded-lg text-emerald-500 w-fit">
                  <MessageSquare className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold tracking-tight">Enterprise Chat Workspace</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Ask natural language questions about your datasets, get query responses, and generate instant Rechart overlays.
                </p>
              </CardContent>
            </Card>

            <Card className="border-border/80">
              <CardContent className="p-6 space-y-4">
                <div className="p-3 bg-amber-500/10 rounded-lg text-amber-500 w-fit">
                  <BarChart3 className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold tracking-tight">Predictive Forecasting</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Configure predictive modeling parameters (ARIMA/Prophet) to project monthly trends and evaluate errors.
                </p>
              </CardContent>
            </Card>

            <Card className="border-border/80">
              <CardContent className="p-6 space-y-4">
                <div className="p-3 bg-rose-500/10 rounded-lg text-rose-500 w-fit">
                  <ShieldAlert className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold tracking-tight">Anomaly & Outlier Flags</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Identify outlier transaction events, standard deviation metrics spikes, and map sensitive risk clusters.
                </p>
              </CardContent>
            </Card>

            <Card className="border-border/80">
              <CardContent className="p-6 space-y-4">
                <div className="p-3 bg-violet-500/10 rounded-lg text-violet-500 w-fit">
                  <Cpu className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold tracking-tight">Document Search (RAG)</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Index workspace Word files, PDF booklets, and scan cross-references using vector semantic engines.
                </p>
              </CardContent>
            </Card>

            <Card className="border-border/80">
              <CardContent className="p-6 space-y-4">
                <div className="p-3 bg-sky-500/10 rounded-lg text-sky-500 w-fit">
                  <Sparkles className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold tracking-tight">Executive Report Builder</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Format visual components lists, draft summaries, and download presentation slides or PDFs on active schedules.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="border-t border-border/85 py-24 px-6 md:px-12 select-none bg-background">
        <div className="max-w-6xl mx-auto space-y-16">
          <div className="text-center space-y-4 max-w-xl mx-auto">
            <h2 className="text-2xl md:text-4xl font-extrabold tracking-tight">Transparent Pricing Plans</h2>
            <p className="text-sm text-muted-foreground">
              Select the plan optimized for your organization. Upgrade or downgrade at any time.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {/* Free Tier */}
            <Card className="border-border/80 flex flex-col justify-between">
              <CardContent className="p-6 space-y-6 flex-1">
                <div>
                  <h3 className="text-base font-bold text-foreground">Starter</h3>
                  <p className="text-xs text-muted-foreground mt-1">For individual analysts testing the engine.</p>
                </div>
                <div className="flex items-baseline">
                  <span className="text-3xl font-extrabold">$0</span>
                  <span className="text-xs text-muted-foreground ml-1">/ month</span>
                </div>
                <ul className="space-y-2 text-xs text-muted-foreground">
                  <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> 1 active dataset file</li>
                  <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Basic SQL Playground</li>
                  <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Standard AI Chat queries</li>
                </ul>
              </CardContent>
              <div className="p-6 pt-0 border-t border-border/40 mt-4">
                <Link href="/dashboard" className="w-full">
                  <Button variant="outline" className="w-full mt-4">Get Started</Button>
                </Link>
              </div>
            </Card>

            {/* Growth Tier */}
            <Card className="border-brand-indigo/50 border-2 bg-brand-indigo/5 flex flex-col justify-between relative">
              <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-2.5 py-0.5 rounded-full bg-brand-indigo text-[10px] font-bold text-brand-indigo-foreground uppercase tracking-wider">Most Popular</div>
              <CardContent className="p-6 space-y-6 flex-1 pt-8">
                <div>
                  <h3 className="text-base font-bold text-foreground">Growth</h3>
                  <p className="text-xs text-muted-foreground mt-1">For scaling businesses and data departments.</p>
                </div>
                <div className="flex items-baseline">
                  <span className="text-3xl font-extrabold">$79</span>
                  <span className="text-xs text-muted-foreground ml-1">/ month</span>
                </div>
                <ul className="space-y-2 text-xs text-muted-foreground">
                  <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Unlimited datasets uploading</li>
                  <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Advanced Forecasting & Outliers</li>
                  <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Scheduled Executive PDF reports</li>
                  <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Shared team collaboration spaces</li>
                </ul>
              </CardContent>
              <div className="p-6 pt-0 border-t border-border/40 mt-4">
                <Link href="/dashboard" className="w-full">
                  <Button variant="brand" className="w-full mt-4">Upgrade Now</Button>
                </Link>
              </div>
            </Card>

            {/* Enterprise Tier */}
            <Card className="border-border/80 flex flex-col justify-between">
              <CardContent className="p-6 space-y-6 flex-1">
                <div>
                  <h3 className="text-base font-bold text-foreground">Enterprise</h3>
                  <p className="text-xs text-muted-foreground mt-1">For multi-tenant compliance and custom setups.</p>
                </div>
                <div className="flex items-baseline">
                  <span className="text-3xl font-extrabold">Custom</span>
                </div>
                <ul className="space-y-2 text-xs text-muted-foreground">
                  <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Custom integrations</li>
                  <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> SSO, SAML, & Auditing keys</li>
                  <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Dedicated DuckDB cloud scaling</li>
                  <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> SLA support guarantees</li>
                </ul>
              </CardContent>
              <div className="p-6 pt-0 border-t border-border/40 mt-4">
                <Link href="mailto:sales@example.com" className="w-full">
                  <Button variant="outline" className="w-full mt-4">Contact Sales</Button>
                </Link>
              </div>
            </Card>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/80 bg-card py-12 px-6 md:px-12 text-center text-xs text-muted-foreground select-none mt-auto">
        <p>© {new Date().getFullYear()} DataPilot AI Inc. All rights reserved. Platform architecture certified production-ready.</p>
      </footer>
    </div>
  );
}

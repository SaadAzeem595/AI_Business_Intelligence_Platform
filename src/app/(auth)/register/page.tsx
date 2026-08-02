"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/shared/components/ui/card";
import { ShieldCheck } from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    // Simulate workspace creation delay
    setTimeout(() => {
      setIsLoading(false);
      router.push("/dashboard");
    }, 600);
  };

  return (
    <Card className="border border-border/80">
      <CardHeader className="space-y-1">
        <CardTitle className="text-xl font-bold tracking-tight text-center">Create your workspace</CardTitle>
        <CardDescription className="text-xs text-muted-foreground text-center">
          Enter your details below to start analyzing data in seconds
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground">Full Name</label>
            <Input
              type="text"
              placeholder="Saad Alvi"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground">Work Email</label>
            <Input
              type="email"
              placeholder="name@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground">Password</label>
            <Input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <Button type="submit" className="w-full" variant="brand" disabled={isLoading}>
            {isLoading ? "Creating account..." : "Register Workspace"}
          </Button>
        </form>
      </CardContent>
      <CardFooter className="flex flex-col space-y-4 text-center mt-2 border-t border-border/40">
        <p className="text-xs text-muted-foreground mt-4">
          Already have an account?{" "}
          <Link href="/login" className="text-brand-indigo hover:underline font-semibold">
            Sign in
          </Link>
        </p>
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground/80 justify-center">
          <ShieldCheck className="h-3.5 w-3.5" /> No credit card required to start
        </div>
      </CardFooter>
    </Card>
  );
}

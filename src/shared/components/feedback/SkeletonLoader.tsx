import * as React from "react";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { Card, CardContent } from "@/shared/components/ui/card";

interface SkeletonLoaderProps {
  type: "dashboard" | "table" | "chat" | "card";
  count?: number;
}

export function SkeletonLoader({ type, count = 1 }: SkeletonLoaderProps) {
  const items = Array.from({ length: count });

  if (type === "card") {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 w-full">
        {items.map((_, i) => (
          <Card key={i} className="border-border/85">
            <CardContent className="p-6 space-y-3">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-8 w-2/3" />
              <Skeleton className="h-3 w-1/2" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (type === "table") {
    return (
      <div className="space-y-4 w-full">
        <Skeleton className="h-10 w-full animate-pulse" />
        <div className="border border-border/85 rounded-lg overflow-hidden divide-y divide-border/60 bg-card">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex p-4 items-center justify-between">
              <Skeleton className="h-4 w-1/4" />
              <Skeleton className="h-4 w-1/6" />
              <Skeleton className="h-4 w-1/5" />
              <Skeleton className="h-4 w-12" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (type === "chat") {
    return (
      <div className="space-y-6 w-full py-4">
        {items.map((_, i) => (
          <div key={i} className="flex flex-col gap-4">
            <div className="flex gap-3 max-w-[80%]">
              <Skeleton className="h-8 w-8 rounded-full shrink-0" />
              <div className="space-y-2">
                <Skeleton className="h-4 w-32" />
                <Card className="border-border/80">
                  <CardContent className="p-4 space-y-2">
                    <Skeleton className="h-4 w-64" />
                    <Skeleton className="h-4 w-48" />
                  </CardContent>
                </Card>
              </div>
            </div>
            <div className="flex gap-3 max-w-[80%] self-end flex-row-reverse">
              <Skeleton className="h-8 w-8 rounded-full shrink-0" />
              <div className="space-y-2">
                <Skeleton className="h-4 w-24 self-end" />
                <Card className="bg-primary text-primary-foreground border-transparent">
                  <CardContent className="p-4 bg-muted/20">
                    <Skeleton className="h-4 w-40 bg-primary-foreground/20" />
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Dashboard layout loader
  return (
    <div className="space-y-6 w-full">
      <SkeletonLoader type="card" count={4} />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 border-border/80">
          <CardContent className="p-6 space-y-4">
            <Skeleton className="h-4 w-1/4" />
            <Skeleton className="h-[250px] w-full" />
          </CardContent>
        </Card>
        <Card className="border-border/80">
          <CardContent className="p-6 space-y-4">
            <Skeleton className="h-4 w-1/3" />
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3">
                  <Skeleton className="h-8 w-8 rounded-md" />
                  <div className="space-y-1 flex-1">
                    <Skeleton className="h-3 w-3/4" />
                    <Skeleton className="h-2 w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

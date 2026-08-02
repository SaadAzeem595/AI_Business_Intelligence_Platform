import * as React from "react";
import { Card, CardContent } from "@/shared/components/ui/card";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";
import { cn } from "@/shared/lib/utils";

interface KPICardProps {
  title: string;
  value: string | number;
  change?: {
    value: number;
    type: "up" | "down";
    label?: string;
  };
  icon?: React.ReactNode;
  className?: string;
}

export function KPICard({ title, value, change, icon, className }: KPICardProps) {
  return (
    <Card className={cn("overflow-hidden border border-border/80 bg-card hover:border-border transition-all", className)}>
      <CardContent className="p-6">
        <div className="flex items-center justify-between space-y-0 pb-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</p>
          {icon && <div className="text-muted-foreground p-1 rounded-md bg-muted/30">{icon}</div>}
        </div>
        <div className="flex items-baseline justify-between mt-1">
          <h3 className="text-2xl font-bold tracking-tight">{value}</h3>
          {change && (
            <div
              className={cn(
                "inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full",
                change.type === "up"
                  ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                  : "bg-rose-500/10 text-rose-600 dark:text-rose-400"
              )}
            >
              {change.type === "up" ? (
                <ArrowUpRight className="mr-0.5 h-3.5 w-3.5 stroke-[2.5]" />
              ) : (
                <ArrowDownRight className="mr-0.5 h-3.5 w-3.5 stroke-[2.5]" />
              )}
              {change.value}%
            </div>
          )}
        </div>
        {change?.label && (
          <p className="text-xs text-muted-foreground mt-2">{change.label}</p>
        )}
      </CardContent>
    </Card>
  );
}

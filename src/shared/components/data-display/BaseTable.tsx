import * as React from "react";
import { cn } from "@/shared/lib/utils";
import { Skeleton } from "@/shared/components/ui/skeleton";

export interface Column<T> {
  header: string;
  accessorKey: keyof T | string;
  cell?: (row: T) => React.ReactNode;
  align?: "left" | "center" | "right";
}

interface BaseTableProps<T> {
  columns: Column<T>[];
  data: T[];
  isLoading?: boolean;
  emptyState?: React.ReactNode;
  className?: string;
}

export function BaseTable<T>({ columns, data, isLoading, emptyState, className }: BaseTableProps<T>) {
  return (
    <div className={cn("w-full overflow-x-auto rounded-lg border border-border/80 bg-card", className)}>
      <table className="w-full border-collapse text-left text-sm text-foreground">
        <thead>
          <tr className="border-b border-border/80 bg-muted/40 font-medium text-muted-foreground select-none">
            {columns.map((col, idx) => (
              <th
                key={idx}
                className={cn(
                  "px-6 py-3.5 text-xs font-semibold uppercase tracking-wider",
                  col.align === "center" && "text-center",
                  col.align === "right" && "text-right"
                )}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border/60">
          {isLoading ? (
            Array.from({ length: 5 }).map((_, rIdx) => (
              <tr key={rIdx} className="hover:bg-muted/10 transition-colors">
                {columns.map((col, cIdx) => (
                  <td key={cIdx} className="px-6 py-4">
                    <Skeleton className="h-4 w-4/5" />
                  </td>
                ))}
              </tr>
            ))
          ) : data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-6 py-12 text-center text-muted-foreground">
                {emptyState || (
                  <div className="flex flex-col items-center justify-center space-y-2 py-6">
                    <p className="text-sm font-medium text-foreground">No records found</p>
                    <p className="text-xs text-muted-foreground">Try uploading data or modifying filters</p>
                  </div>
                )}
              </td>
            </tr>
          ) : (
            data.map((row, rIdx) => (
              <tr key={rIdx} className="hover:bg-muted/15 transition-colors">
                {columns.map((col, cIdx) => {
                  const value = col.cell
                    ? col.cell(row)
                    : (row[col.accessorKey as keyof T] as React.ReactNode);
                  return (
                    <td
                      key={cIdx}
                      className={cn(
                        "px-6 py-4 font-normal text-muted-foreground text-foreground/80",
                        col.align === "center" && "text-center",
                        col.align === "right" && "text-right"
                      )}
                    >
                      {value}
                    </td>
                  );
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

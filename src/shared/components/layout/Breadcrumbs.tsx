"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home } from "lucide-react";

export function Breadcrumbs() {
  const pathname = usePathname();
  const paths = pathname.split("/").filter(Boolean);

  if (paths.length === 0) return null;

  return (
    <nav className="flex items-center space-x-1.5 text-xs text-muted-foreground select-none font-medium">
      <Link href="/dashboard" className="hover:text-foreground flex items-center transition-colors shrink-0">
        <Home className="h-3.5 w-3.5" />
      </Link>
      {paths.map((segment, index) => {
        const url = `/${paths.slice(0, index + 1).join("/")}`;
        const isLast = index === paths.length - 1;
        const formattedName = decodeURIComponent(segment)
          .replace(/-/g, " ")
          .replace(/\b\w/g, (c) => c.toUpperCase());

        // Skip numeric IDs or clean them up to generic 'Detail'
        const isNumeric = !isNaN(Number(segment));
        const displayLabel = isNumeric ? "Details" : formattedName;

        return (
          <React.Fragment key={url}>
            <ChevronRight className="h-3 w-3 stroke-[2.5] text-muted-foreground/50 shrink-0" />
            {isLast ? (
              <span className="font-semibold text-foreground font-sans truncate max-w-[120px] sm:max-w-none">
                {displayLabel}
              </span>
            ) : (
              <Link href={url} className="hover:text-foreground transition-colors truncate max-w-[100px] sm:max-w-none">
                {displayLabel}
              </Link>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}

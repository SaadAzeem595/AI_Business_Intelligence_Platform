import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse, type NextRequest } from "next/server";

const isProtectedRoute = createRouteMatcher([
  "/dashboard(.*)",
  "/projects(.*)",
  "/datasets(.*)",
  "/chat(.*)",
  "/forecasting(.*)",
  "/segmentation(.*)",
  "/anomaly-detection(.*)",
  "/sql-playground(.*)",
  "/knowledge-base(.*)",
  "/executive-reports(.*)",
  "/settings(.*)",
  "/billing(.*)",
]);

const clerkHandler = clerkMiddleware(async (auth, req) => {
  if (isProtectedRoute(req)) {
    await auth.protect();
  }
});

export default function proxy(req: NextRequest, event: any) {
  const isDevAuthBypass =
    process.env.NEXT_PUBLIC_DEV_AUTH_BYPASS === "true" &&
    process.env.NODE_ENV !== "production";

  if (isDevAuthBypass) {
    return NextResponse.next();
  }

  return clerkHandler(req, event);
}

export const config = {
  matcher: [
    // Skip Next.js internals and all static files
    "/((?!_next|[^?]*\\.[\\w]+$).*)",
    // Always run for API routes
    "/(api|trpc)(.*)",
  ],
};

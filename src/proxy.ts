import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

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

export default clerkMiddleware(async (auth, req) => {
  // Support local dev auth bypass check
  const isDevAuthBypass =
    process.env.NEXT_PUBLIC_DEV_AUTH_BYPASS === "true" &&
    process.env.NODE_ENV !== "production";
  if (isDevAuthBypass) {
    return;
  }

  if (isProtectedRoute(req)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    // Skip Next.js internals and all static files
    "/((?!_next|[^?]*\\.[\\w]+$).*)",
    // Always run for API routes
    "/(api|trpc)(.*)",
  ],
};

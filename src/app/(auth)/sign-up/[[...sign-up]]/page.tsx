"use client";

import { SignUp } from "@clerk/nextjs";
import { dark } from "@clerk/themes";
import { useTheme } from "@/shared/providers/ThemeProvider";

export default function SignUpPage() {
  const { theme } = useTheme();

  return (
    <div className="w-full flex justify-center">
      <SignUp
        appearance={{
          theme: theme === "dark" ? dark : undefined,
          variables: {
            colorPrimary: "#4f46e5", // Brand Indigo color
            colorBackground: theme === "dark" ? "hsl(var(--card))" : "#ffffff",
            colorForeground: "hsl(var(--foreground))",
            colorMutedForeground: "hsl(var(--muted-foreground))",
          },
          elements: {
            card: "border border-border bg-card text-card-foreground shadow-2xl rounded-xl",
            headerTitle: "text-foreground font-bold",
            headerSubtitle: "text-muted-foreground text-xs",
            formFieldLabel: "text-foreground/80 font-medium text-xs",
            formFieldInput: "!bg-zinc-50 !border-zinc-200 dark:!bg-zinc-900 dark:!border-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder-zinc-500 focus:!border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 transition-all duration-150 rounded-lg",
            otpCodeFieldInput: "!bg-zinc-50 !border-zinc-200 dark:!bg-zinc-900 dark:!border-zinc-800 text-zinc-900 dark:text-zinc-100 focus:!border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 transition-all duration-150 rounded-lg text-lg font-bold shadow-sm",
            formResendCodeLink: "text-indigo-400 hover:text-indigo-300 transition-colors duration-150 font-semibold",
            socialButtonsBlockButton: "border-border text-foreground bg-background hover:bg-muted hover:text-foreground transition-colors duration-150",
            formButtonPrimary: "bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition-colors duration-150 shadow-lg shadow-indigo-500/20",
            footerActionLink: "text-indigo-400 hover:text-indigo-300 font-semibold",
          },
        }}
      />
    </div>
  );
}

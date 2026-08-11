import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <div className="w-full flex justify-center">
      <SignUp
        appearance={{
          variables: {
            colorPrimary: "#4f46e5", // Brand Indigo color
            colorBackground: "#09090b", // Sleek dark mode card
            colorForeground: "#f4f4f5",
            colorMutedForeground: "#a1a1aa",
          },
          elements: {
            card: "border border-border/80 bg-zinc-950/50 backdrop-blur-md shadow-2xl rounded-xl",
            headerTitle: "text-zinc-100 font-bold",
            headerSubtitle: "text-zinc-400 text-xs",
            formFieldLabel: "text-zinc-300 font-medium text-xs",
            formFieldInput: "bg-zinc-900/60 border border-zinc-800 text-zinc-100 placeholder-zinc-500 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 transition-all duration-150 rounded-lg",
            otpCodeFieldInput: "bg-zinc-900/60 border border-zinc-800 text-zinc-100 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 transition-all duration-150 rounded-lg text-lg font-bold",
            formResendCodeLink: "text-indigo-400 hover:text-indigo-300 transition-colors duration-150 font-semibold",
            socialButtonsBlockButton: "border-border text-zinc-100 bg-zinc-900 hover:bg-zinc-800 hover:text-zinc-50 transition-colors duration-150",
            formButtonPrimary: "bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition-colors duration-150 shadow-lg shadow-indigo-500/20",
            footerActionLink: "text-indigo-400 hover:text-indigo-300 font-semibold",
          },
        }}
      />
    </div>
  );
}

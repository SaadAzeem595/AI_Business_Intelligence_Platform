"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AuthService } from "../services/auth.service";
import { LoginInput, SignupInput } from "../schemas/auth.schema";
import { useRouter } from "next/navigation";
import { useClerk } from "@clerk/nextjs";

export function useAuth() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { signOut } = useClerk();

  const userQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: AuthService.me,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const loginMutation = useMutation({
    mutationFn: (data: LoginInput) => AuthService.login(data),
    onSuccess: (session) => {
      localStorage.setItem("accessToken", session.accessToken);
      if (session.refreshToken) {
        localStorage.setItem("refreshToken", session.refreshToken);
      }
      queryClient.setQueryData(["auth", "me"], session.user);
      router.push("/dashboard");
    },
  });

  const signupMutation = useMutation({
    mutationFn: (data: SignupInput) => AuthService.register(data),
    onSuccess: (session) => {
      localStorage.setItem("accessToken", session.accessToken);
      if (session.refreshToken) {
        localStorage.setItem("refreshToken", session.refreshToken);
      }
      queryClient.setQueryData(["auth", "me"], session.user);
      router.push("/dashboard");
    },
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      try {
        await AuthService.logout();
      } catch (err) {
        // Ignore backend session cleanup failures
      }
      try {
        await signOut();
      } catch (err) {
        console.error("Clerk signOut error:", err);
      }
    },
    onSuccess: () => {
      localStorage.removeItem("accessToken");
      localStorage.removeItem("refreshToken");
      queryClient.setQueryData(["auth", "me"], null);
      queryClient.clear();
      router.push("/sign-in");
    },
  });

  return {
    user: userQuery.data || null,
    isLoading: userQuery.isLoading,
    login: loginMutation.mutateAsync,
    isLoggingIn: loginMutation.isPending,
    register: signupMutation.mutateAsync,
    isRegistering: signupMutation.isPending,
    logout: logoutMutation.mutateAsync,
    isLoggingOut: logoutMutation.isPending,
  };
}

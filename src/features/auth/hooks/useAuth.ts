"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AuthService } from "../services/auth.service";
import { LoginInput, SignupInput } from "../schemas/auth.schema";
import { useRouter } from "next/navigation";

export function useAuth() {
  const queryClient = useQueryClient();
  const router = useRouter();

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
      queryClient.setQueryData(["auth", "me"], session.user);
      router.push("/dashboard");
    },
  });

  const signupMutation = useMutation({
    mutationFn: (data: SignupInput) => AuthService.register(data),
    onSuccess: (session) => {
      localStorage.setItem("accessToken", session.accessToken);
      queryClient.setQueryData(["auth", "me"], session.user);
      router.push("/dashboard");
    },
  });

  const logoutMutation = useMutation({
    mutationFn: AuthService.logout,
    onSuccess: () => {
      localStorage.removeItem("accessToken");
      queryClient.setQueryData(["auth", "me"], null);
      queryClient.clear();
      router.push("/login");
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

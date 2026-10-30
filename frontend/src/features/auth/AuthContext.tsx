"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { UserResponse } from "@/types/api";
import { api, setAuthFailureHandler } from "@/services/apiClient";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export interface AuthContextType {
  user: UserResponse | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const refreshUser = useCallback(async () => {
    try {
      const userData = await api.get<UserResponse>("/auth/me");
      setUser(userData);
      setStatus("authenticated");
    } catch {
      setUser(null);
      setStatus("unauthenticated");
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    setAuthFailureHandler(() => {
      if (isMounted) {
        setUser(null);
        setStatus("unauthenticated");
      }
    });

    const initAuth = async () => {
      try {
        const userData = await api.get<UserResponse>("/auth/me");
        if (isMounted) {
          setUser(userData);
          setStatus("authenticated");
        }
      } catch {
        if (isMounted) {
          setUser(null);
          setStatus("unauthenticated");
        }
      }
    };

    initAuth();

    return () => {
      isMounted = false;
      setAuthFailureHandler(null);
    };
  }, []);

  const login = async (email: string, password: string) => {
    await api.post("/auth/login", { email, password });
    await refreshUser();
  };

  const register = async (email: string, password: string) => {
    await api.post("/auth/register", { email, password });
    await login(email, password);
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setUser(null);
      setStatus("unauthenticated");
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        status,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

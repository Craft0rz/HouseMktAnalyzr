'use client';

import { createContext, useContext, useCallback, useEffect, useState, type ReactNode } from 'react';
import { authApi, TOKEN_KEY, REFRESH_KEY } from './api';
import type { User, AuthResponse, RegisterRequest, LoginRequest } from './types';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

function storeTokens(tokens: { access_token: string; refresh_token: string }) {
  localStorage.setItem(TOKEN_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
}

function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount, check if we have a valid token and load user
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setIsLoading(false);
      return;
    }
    authApi.me()
      .then(setUser)
      .catch(() => clearTokens())
      .finally(() => setIsLoading(false));
  }, []);

  const handleAuthResponse = useCallback((response: AuthResponse) => {
    storeTokens(response.tokens);
    setUser(response.user);
  }, []);

  const login = useCallback(async (data: LoginRequest) => {
    const response = await authApi.login(data);
    handleAuthResponse(response);
  }, [handleAuthResponse]);

  const register = useCallback(async (data: RegisterRequest) => {
    const response = await authApi.register(data);
    handleAuthResponse(response);
  }, [handleAuthResponse]);

  const loginWithGoogle = useCallback(async (idToken: string) => {
    const response = await authApi.googleAuth(idToken);
    handleAuthResponse(response);
  }, [handleAuthResponse]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore errors on logout
    }
    clearTokens();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        loginWithGoogle,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

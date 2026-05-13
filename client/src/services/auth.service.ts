import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, catchError, map, of } from 'rxjs';

import { environment } from '../environments/environment';

interface LoginResponse {
  success: boolean;
  data: { access_token: string; token_type: string; user?: AuthUser } | null;
  error: { code: string; message: string } | null;
}

interface RegisterResponse {
  success: boolean;
  data: ({ access_token: string; token_type: string } & AuthUser) | null;
  error: { code: string; message: string } | null;
}

export interface AuthUser {
  user_id: string;
  email: string;
  name: string | null;
  username: string | null;
  school: string | null;
  role: string;
}

interface JwtClaims {
  sub: string;
  role: string;
  email?: string;
  name?: string;
  exp?: number;
}

export interface LoginOutcome {
  success: boolean;
  errorMessage?: string;
}

export interface RegisterRequest {
  name: string;
  email: string;
  username?: string | null;
  school?: string | null;
  password: string;
}

export interface RegisterOutcome {
  success: boolean;
  errorMessage?: string;
}

const TOKEN_STORAGE_KEY = 'mapleAccessToken';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);

  private readonly loginUrl = `${environment.apiBaseUrl}/api/v1/code-eval/auth/login`;
  private readonly registerUrl = `${environment.apiBaseUrl}/api/v1/code-eval/auth/register`;

  setToken(token: string): void {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  }

  getToken(): string | null {
    return localStorage.getItem(TOKEN_STORAGE_KEY) ?? environment.devToken ?? null;
  }

  clear(): void {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }

  isAuthenticated(): boolean {
    const token = this.getToken();
    return !!token && token.length > 0;
  }

  /**
   * Decode the JWT payload (no signature verification — backend is the
   * source of truth). Returns null if the token is missing or malformed.
   */
  getClaims(): JwtClaims | null {
    const token = this.getToken();
    if (!token) return null;
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    try {
      const payload = atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'));
      return JSON.parse(payload) as JwtClaims;
    } catch {
      return null;
    }
  }

  login(email: string, password: string): Observable<LoginOutcome> {
    const headers = new HttpHeaders({ 'Content-Type': 'application/json' });
    return this.http
      .post<LoginResponse>(this.loginUrl, { email, password }, { headers })
      .pipe(
        map((response) => {
          if (response.success && response.data?.access_token) {
            this.setToken(response.data.access_token);
            return { success: true };
          }
          return {
            success: false,
            errorMessage: response.error?.message ?? 'Sign-in failed.',
          };
        }),
        catchError((err) => {
          const code: string = err?.error?.error?.code ?? 'NETWORK_ERROR';
          const message: string =
            err?.error?.error?.message ??
            (code === 'AUTH_ERROR'
              ? 'Invalid email or password.'
              : 'Sign-in failed — check your connection and try again.');
          return of({ success: false, errorMessage: message });
        }),
      );
  }

  register(request: RegisterRequest): Observable<RegisterOutcome> {
    const headers = new HttpHeaders({ 'Content-Type': 'application/json' });
    return this.http.post<RegisterResponse>(this.registerUrl, request, { headers }).pipe(
      map((response) => {
        if (response.success && response.data?.access_token) {
          this.setToken(response.data.access_token);
          return { success: true };
        }
        return {
          success: false,
          errorMessage: response.error?.message ?? 'Account creation failed.',
        };
      }),
      catchError((err) => {
        const code: string = err?.error?.error?.code ?? 'NETWORK_ERROR';
        const message: string =
          err?.error?.error?.message ??
          (code === 'CONFLICT'
            ? 'An account with that email or username already exists.'
            : 'Account creation failed — check your connection and try again.');
        return of({ success: false, errorMessage: message });
      }),
    );
  }
}

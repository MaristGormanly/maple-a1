import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, of } from 'rxjs';

import { environment } from '../environments/environment';
import {
  AccountProfileResponse,
  DeleteResponse,
  GitHubSettingsResponse,
  PasswordUpdateResponse,
  StyleGuideReferencesResponse,
} from '../utils/api.types';

@Injectable({ providedIn: 'root' })
export class SettingsService {
  private http = inject(HttpClient);
  private readonly githubUrl = `${environment.apiBaseUrl}/api/v1/code-eval/settings/github`;
  private readonly accountUrl = `${environment.apiBaseUrl}/api/v1/code-eval/settings/account`;
  private readonly styleGuideReferencesUrl =
    `${environment.apiBaseUrl}/api/v1/code-eval/settings/style-guide-references`;

  getGitHubSettings(): Observable<GitHubSettingsResponse> {
    return this.http.get<GitHubSettingsResponse>(this.githubUrl).pipe(
      catchError((err) => of(this.toErrorResponse<GitHubSettingsResponse>(err))),
    );
  }

  getStyleGuideReferences(): Observable<StyleGuideReferencesResponse> {
    return this.http.get<StyleGuideReferencesResponse>(this.styleGuideReferencesUrl).pipe(
      catchError((err) => of(this.toErrorResponse<StyleGuideReferencesResponse>(err))),
    );
  }

  saveGitHubSettings(
    githubUsername: string | null,
    personalAccessToken: string,
  ): Observable<GitHubSettingsResponse> {
    return this.http
      .put<GitHubSettingsResponse>(this.githubUrl, {
        github_username: githubUsername,
        personal_access_token: personalAccessToken,
      })
      .pipe(catchError((err) => of(this.toErrorResponse<GitHubSettingsResponse>(err))));
  }

  clearGitHubSettings(): Observable<GitHubSettingsResponse> {
    return this.http
      .delete<GitHubSettingsResponse>(this.githubUrl)
      .pipe(catchError((err) => of(this.toErrorResponse<GitHubSettingsResponse>(err))));
  }

  getAccountProfile(): Observable<AccountProfileResponse> {
    return this.http
      .get<AccountProfileResponse>(this.accountUrl)
      .pipe(catchError((err) => of(this.toErrorResponse<AccountProfileResponse>(err))));
  }

  updateAccountProfile(profile: {
    name: string | null;
    email: string | null;
    username: string | null;
    school: string | null;
  }): Observable<AccountProfileResponse> {
    return this.http
      .patch<AccountProfileResponse>(this.accountUrl, profile)
      .pipe(catchError((err) => of(this.toErrorResponse<AccountProfileResponse>(err))));
  }

  updatePassword(
    currentPassword: string,
    newPassword: string,
  ): Observable<PasswordUpdateResponse> {
    return this.http
      .patch<PasswordUpdateResponse>(`${this.accountUrl}/password`, {
        current_password: currentPassword,
        new_password: newPassword,
      })
      .pipe(catchError((err) => of(this.toErrorResponse<PasswordUpdateResponse>(err))));
  }

  deleteAccount(confirmation: string): Observable<DeleteResponse> {
    return this.http
      .delete<DeleteResponse>(this.accountUrl, { body: { confirmation } })
      .pipe(catchError((err) => of(this.toErrorResponse<DeleteResponse>(err))));
  }

  private toErrorResponse<
    T extends
      | AccountProfileResponse
      | DeleteResponse
      | GitHubSettingsResponse
      | PasswordUpdateResponse
      | StyleGuideReferencesResponse,
  >(
    err: unknown,
  ): T {
    const maybeErr = err as {
      error?: { error?: { code?: string; message?: string } };
      message?: string;
    };
    return {
      success: false,
      data: null,
      error: {
        code: maybeErr?.error?.error?.code ?? 'NETWORK_ERROR',
        message: maybeErr?.error?.error?.message ?? maybeErr?.message ?? 'Unknown error',
      },
      metadata: {
        timestamp: new Date().toISOString(),
        module: 'a1',
        version: 'unknown',
      },
    } as T;
  }
}

import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, of } from 'rxjs';

import { environment } from '../environments/environment';
import { GitHubSettingsResponse } from '../utils/api.types';

@Injectable({ providedIn: 'root' })
export class SettingsService {
  private http = inject(HttpClient);
  private readonly githubUrl = `${environment.apiBaseUrl}/api/v1/code-eval/settings/github`;

  getGitHubSettings(): Observable<GitHubSettingsResponse> {
    return this.http.get<GitHubSettingsResponse>(this.githubUrl).pipe(
      catchError((err) => of(this.toErrorResponse(err))),
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
      .pipe(catchError((err) => of(this.toErrorResponse(err))));
  }

  clearGitHubSettings(): Observable<GitHubSettingsResponse> {
    return this.http
      .delete<GitHubSettingsResponse>(this.githubUrl)
      .pipe(catchError((err) => of(this.toErrorResponse(err))));
  }

  private toErrorResponse(err: unknown): GitHubSettingsResponse {
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
    };
  }
}

import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, of } from 'rxjs';

import { environment } from '../environments/environment';
import { RepositoryListResponse } from '../utils/api.types';

@Injectable({ providedIn: 'root' })
export class RepositoryService {
  private http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/api/v1/code-eval/repositories`;

  listRepositories(page = 1): Observable<RepositoryListResponse> {
    return this.http
      .get<RepositoryListResponse>(this.baseUrl, { params: { page } })
      .pipe(catchError((err) => of(this.toErrorResponse(err))));
  }

  private toErrorResponse(err: unknown): RepositoryListResponse {
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

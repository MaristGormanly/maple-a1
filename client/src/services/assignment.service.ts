import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, of } from 'rxjs';

import { environment } from '../environments/environment';
import { AssignmentListResponse, AssignmentDetailResponse, DeleteResponse } from '../utils/api.types';

export interface AssignmentCreateRequest {
  title: string;
  test_suite_repo_url?: string | null;
  rubric_id?: string | null;
  enable_lint_review: boolean;
  language_override?: string | null;
  test_discovery_mode: 'instructor_suite' | 'auto_discover';
}

export interface AssignmentData {
  assignment_id: string;
  title: string;
  instructor_id: string;
  test_suite_repo_url: string | null;
  rubric_id: string | null;
  enable_lint_review: boolean;
  language_override: string | null;
  test_discovery_mode: 'instructor_suite' | 'auto_discover';
}

export interface AssignmentResponse {
  success: boolean;
  data: AssignmentData | null;
  error: { code: string; message: string } | null;
  metadata: { timestamp: string; module: string; version: string };
}

@Injectable({ providedIn: 'root' })
export class AssignmentService {
  private http = inject(HttpClient);

  private readonly url = `${environment.apiBaseUrl}/api/v1/code-eval/assignments`;

  private readonly _errMeta = () => ({
    timestamp: new Date().toISOString(),
    module: 'a1',
    version: 'unknown',
  });

  create(request: AssignmentCreateRequest): Observable<AssignmentResponse> {
    return this.http.post<AssignmentResponse>(this.url, request).pipe(
      catchError((err) => {
        const message: string =
          err?.error?.error?.message ?? err?.message ?? 'Unknown error';
        const code: string = err?.error?.error?.code ?? 'NETWORK_ERROR';
        const response: AssignmentResponse = {
          success: false,
          data: null,
          error: { code, message },
          metadata: this._errMeta(),
        };
        return of(response);
      }),
    );
  }

  getAll(): Observable<AssignmentListResponse> {
    return this.http.get<AssignmentListResponse>(this.url).pipe(
      catchError((err) => {
        const message: string = err?.error?.error?.message ?? err?.message ?? 'Unknown error';
        const code: string = err?.error?.error?.code ?? 'NETWORK_ERROR';
        return of<AssignmentListResponse>({
          success: false,
          data: null,
          error: { code, message },
          metadata: this._errMeta(),
        });
      }),
    );
  }

  getById(id: string): Observable<AssignmentDetailResponse> {
    return this.http.get<AssignmentDetailResponse>(`${this.url}/${id}`).pipe(
      catchError((err) => {
        const message: string = err?.error?.error?.message ?? err?.message ?? 'Unknown error';
        const code: string = err?.error?.error?.code ?? 'NETWORK_ERROR';
        return of<AssignmentDetailResponse>({
          success: false,
          data: null,
          error: { code, message },
          metadata: this._errMeta(),
        });
      }),
    );
  }

  delete(id: string): Observable<DeleteResponse> {
    return this.http.delete<DeleteResponse>(`${this.url}/${id}`).pipe(
      catchError((err) => {
        const message: string = err?.error?.error?.message ?? err?.message ?? 'Unknown error';
        const code: string = err?.error?.error?.code ?? 'NETWORK_ERROR';
        return of<DeleteResponse>({
          success: false,
          data: null,
          error: { code, message },
          metadata: this._errMeta(),
        });
      }),
    );
  }
}

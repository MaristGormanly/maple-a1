import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, catchError, of } from 'rxjs';

import { environment } from '../environments/environment';
import { ReviewRequest, SubmissionResponse, SubmissionStatusResponse } from '../utils/api.types';

@Injectable({ providedIn: 'root' })
export class EvaluationService {
  private readonly url = `${environment.apiBaseUrl}/api/v1/code-eval/evaluate`;
  private readonly submissionsUrl = `${environment.apiBaseUrl}/api/v1/code-eval/submissions`;

  constructor(private http: HttpClient) {}

  // TODO: Replace devToken stub with a real token from the auth service once
  // POST /api/v1/code-eval/auth/login is implemented (Milestone 2).
  submitEvaluation(
    githubUrl: string,
    assignmentId: string,
    rubricFile: File
  ): Observable<SubmissionResponse> {
    const body = new FormData();
    body.append('github_url', githubUrl);
    body.append('assignment_id', assignmentId);
    body.append('rubric', rubricFile);

    // Do not set Content-Type manually — the browser sets multipart/form-data
    // with the correct boundary automatically when the body is FormData.
    const headers = new HttpHeaders({
      Authorization: `Bearer ${environment.devToken ?? ''}`,
    });

    return this.http.post<SubmissionResponse>(this.url, body, { headers }).pipe(
      catchError((err) => {
        const message: string =
          err?.error?.error?.message ?? err?.message ?? 'Unknown error';
        const code: string = err?.error?.error?.code ?? 'NETWORK_ERROR';
        const response: SubmissionResponse = {
          success: false,
          data: null,
          error: { code, message },
          metadata: {
            timestamp: new Date().toISOString(),
            module: 'a1',
            version: 'unknown',
          },
        };
        return of(response);
      })
    );
  }

  getSubmissionStatus(submissionId: string): Observable<SubmissionStatusResponse> {
    const headers = new HttpHeaders({
      Authorization: `Bearer ${environment.devToken ?? ''}`,
    });
    return this.http
      .get<SubmissionStatusResponse>(`${this.submissionsUrl}/${submissionId}`, { headers })
      .pipe(
        catchError((err) => {
          const message: string =
            err?.error?.error?.message ?? err?.message ?? 'Unknown error';
          const code: string = err?.error?.error?.code ?? 'NETWORK_ERROR';
          const response: SubmissionStatusResponse = {
            success: false,
            data: null,
            error: { code, message },
            metadata: {
              timestamp: new Date().toISOString(),
              module: 'a1',
              version: 'unknown',
            },
          };
          return of(response);
        })
      );
  }

  submitReview(submissionId: string, request: ReviewRequest): Observable<SubmissionStatusResponse> {
    const headers = new HttpHeaders({
      Authorization: `Bearer ${environment.devToken ?? ''}`,
      'Content-Type': 'application/json',
    });
    return this.http
      .post<SubmissionStatusResponse>(
        `${this.submissionsUrl}/${submissionId}/review`,
        request,
        { headers }
      )
      .pipe(
        catchError((err) => {
          const message: string =
            err?.error?.error?.message ?? err?.message ?? 'Unknown error';
          const code: string = err?.error?.error?.code ?? 'NETWORK_ERROR';
          const response: SubmissionStatusResponse = {
            success: false,
            data: null,
            error: { code, message },
            metadata: {
              timestamp: new Date().toISOString(),
              module: 'a1',
              version: 'unknown',
            },
          };
          return of(response);
        })
      );
  }
}

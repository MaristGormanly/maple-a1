import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, of } from 'rxjs';

import { environment } from '../environments/environment';
import { DeleteResponse, ReviewRequest, SubmissionListResponse, SubmissionResponse, SubmissionStatusResponse } from '../utils/api.types';

@Injectable({ providedIn: 'root' })
export class EvaluationService {
  private http = inject(HttpClient);

  private readonly url = `${environment.apiBaseUrl}/api/v1/code-eval/evaluate`;
  private readonly submissionsUrl = `${environment.apiBaseUrl}/api/v1/code-eval/submissions`;

  // The Authorization header is attached automatically by `authInterceptor`
  // (registered in app.config.ts) so individual methods do not build it.

  submitEvaluation(
    githubUrl: string,
    assignmentId: string,
    rubricFile: File,
  ): Observable<SubmissionResponse> {
    const body = new FormData();
    body.append('github_url', githubUrl);
    body.append('assignment_id', assignmentId);
    body.append('rubric', rubricFile);

    // Do not set Content-Type manually — the browser sets multipart/form-data
    // with the correct boundary automatically when the body is FormData.
    return this.http.post<SubmissionResponse>(this.url, body).pipe(
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
    return this.http
      .get<SubmissionStatusResponse>(`${this.submissionsUrl}/${submissionId}`)
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

  getSubmissions(): Observable<SubmissionListResponse> {
    return this.http
      .get<SubmissionListResponse>(this.submissionsUrl)
      .pipe(
        catchError((err) => {
          const message: string = err?.error?.error?.message ?? err?.message ?? 'Unknown error';
          const code: string = err?.error?.error?.code ?? 'NETWORK_ERROR';
          return of<SubmissionListResponse>({
            success: false,
            data: null,
            error: { code, message },
            metadata: { timestamp: new Date().toISOString(), module: 'a1', version: 'unknown' },
          });
        })
      );
  }

  deleteSubmission(id: string): Observable<DeleteResponse> {
    return this.http.delete<DeleteResponse>(`${this.submissionsUrl}/${id}`).pipe(
      catchError((err) => {
        const message: string = err?.error?.error?.message ?? err?.message ?? 'Unknown error';
        const code: string = err?.error?.error?.code ?? 'NETWORK_ERROR';
        return of<DeleteResponse>({
          success: false,
          data: null,
          error: { code, message },
          metadata: { timestamp: new Date().toISOString(), module: 'a1', version: 'unknown' },
        });
      }),
    );
  }

  submitReview(submissionId: string, request: ReviewRequest): Observable<SubmissionStatusResponse> {
    return this.http
      .post<SubmissionStatusResponse>(
        `${this.submissionsUrl}/${submissionId}/review`,
        request,
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

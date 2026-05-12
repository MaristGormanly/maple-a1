import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, of } from 'rxjs';

import { environment } from '../environments/environment';
import { DeleteResponse, RubricListResponse, RubricDetailResponse } from '../utils/api.types';

@Injectable({ providedIn: 'root' })
export class RubricService {
  private http = inject(HttpClient);

  readonly url = `${environment.apiBaseUrl}/api/v1/code-eval/rubrics`;

  private readonly _errMeta = () => ({
    timestamp: new Date().toISOString(),
    module: 'a1',
    version: 'unknown',
  });

  getAll(): Observable<RubricListResponse> {
    return this.http.get<RubricListResponse>(this.url).pipe(
      catchError((err) => {
        const message: string = err?.error?.error?.message ?? err?.message ?? 'Unknown error';
        const code: string = err?.error?.error?.code ?? 'NETWORK_ERROR';
        return of<RubricListResponse>({
          success: false,
          data: null,
          error: { code, message },
          metadata: this._errMeta(),
        });
      }),
    );
  }

  update(id: string, title: string, notes: string | null): Observable<RubricDetailResponse> {
    return this.http.put<RubricDetailResponse>(`${this.url}/${id}`, { title, notes }).pipe(
      catchError((err) => {
        const message: string = err?.error?.error?.message ?? err?.message ?? 'Unknown error';
        const code: string = err?.error?.error?.code ?? 'NETWORK_ERROR';
        return of<RubricDetailResponse>({
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

  uploadFile(rubricId: string, file: File): Observable<RubricDetailResponse> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<RubricDetailResponse>(`${this.url}/${rubricId}/file`, form).pipe(
      catchError((err) => {
        const message: string = err?.error?.error?.message ?? err?.message ?? 'Unknown error';
        const code: string = err?.error?.error?.code ?? 'NETWORK_ERROR';
        return of<RubricDetailResponse>({
          success: false,
          data: null,
          error: { code, message },
          metadata: this._errMeta(),
        });
      }),
    );
  }

  fetchFileBlob(rubricId: string): Observable<Blob> {
    return this.http.get(`${this.url}/${rubricId}/file`, { responseType: 'blob' });
  }

  isPdf(filename: string | null): boolean {
    return filename?.toLowerCase().endsWith('.pdf') ?? false;
  }
}

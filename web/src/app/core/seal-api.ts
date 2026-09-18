import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, throwError } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { SealJob, UploadResult } from './types';

/** A download the browser has in hand: the bytes plus the name to save them as. */
export interface SealedFile {
  blob: Blob;
  filename: string;
}

@Injectable({ providedIn: 'root' })
export class SealApi {
  private readonly http = inject(HttpClient);

  upload(file: File): Observable<UploadResult> {
    return this.http
      .post<UploadResult>('/api/upload', file, {
        headers: { 'Content-Type': 'application/pdf' },
      })
      .pipe(catchError(readableError));
  }

  seal(job: SealJob): Observable<SealedFile> {
    return this.http.post('/api/seal', job, { observe: 'response', responseType: 'blob' }).pipe(
      map((response) => ({
        blob: response.body as Blob,
        filename: filenameFrom(response.headers.get('Content-Disposition')),
      })),
      catchError(readableError),
    );
  }
}

function filenameFrom(disposition: string | null): string {
  const found = disposition?.match(/filename="([^"]+)"/);
  return found ? found[1] : 'sealed.pdf';
}

/**
 * The server answers errors as JSON, but a blob response type hands them over as
 * a Blob, so the message has to be read back out before it can be shown.
 */
function readableError(error: HttpErrorResponse): Observable<never> {
  if (error.error instanceof Blob) {
    return new Observable<never>((subscriber) => {
      error.error
        .text()
        .then((text: string) => {
          let message = text;
          try {
            message = JSON.parse(text).error ?? text;
          } catch {
            /* not JSON; show it as it came */
          }
          subscriber.error(new Error(message));
        })
        .catch(() => subscriber.error(new Error('The server could not be reached.')));
    });
  }
  const message =
    error.error?.error ?? (error.status === 0 ? 'The server is not running.' : error.message);
  return throwError(() => new Error(message));
}

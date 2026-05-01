import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { AuthService } from '../services/auth.service';

/**
 * Attaches `Authorization: Bearer <jwt>` to every outbound request whose
 * URL targets the MAPLE API. Skipped when no token is present (the auth
 * guard prevents this on protected routes; login itself does not need a
 * token).
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const token = auth.getToken();

  if (!token || token.length === 0) {
    return next(req);
  }

  // Don't double-attach if a header is already set (e.g. login flow).
  if (req.headers.has('Authorization')) {
    return next(req);
  }

  return next(
    req.clone({
      setHeaders: { Authorization: `Bearer ${token}` },
    }),
  );
};

import type { Environment } from './environment.model';

export const environment: Environment = {
  production: true,
  // Production API (TLS on Nginx). Must match DNS/Certbot for api.maple-a1.com; see docs/deployment.md.
  apiBaseUrl: 'https://api.maple-a1.com',
  // devToken is intentionally absent here. Adding it to this file is a deployment error.
  // Real authentication via POST /auth/login will be wired in M3.
};

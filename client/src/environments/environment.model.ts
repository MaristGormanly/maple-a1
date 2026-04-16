export interface Environment {
  production: boolean;
  apiBaseUrl: string;
  /**
   * Dev-only JWT stub used while the real auth service is not yet implemented.
   * Must be absent from production environment files.
   * Will be removed entirely when POST /auth/login is wired in M3.
   */
  devToken?: string;
}

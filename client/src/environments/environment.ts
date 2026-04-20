import type { Environment } from './environment.model';

export const environment: Environment = {
  production: false,
  apiBaseUrl: 'http://localhost:8000',
  // devToken is intentionally empty here. Override it in environment.development.ts
  // (gitignored) with a locally-signed JWT. To generate one, run from the server
  // virtualenv:
  //   python -c "from app.utils.security import create_access_token; print(create_access_token({'sub': 'dev', 'role': 'user'}))"
  // See client/src/environments/environment.development.ts.example for the file shape.
  devToken: '',
};

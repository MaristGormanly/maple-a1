export const environment = {
  production: false,
  apiBaseUrl: 'http://localhost:8000',
  // TODO: Replace with a real signed JWT before demoing.
  // The evaluate endpoint validates this as a JWT using the server's SECRET_KEY and ALGORITHM.
  // A plain string will be rejected with 401. To generate a valid dev token, run from the
  // server virtualenv:
  //   python -c "from app.utils.security import create_access_token; print(create_access_token({'sub': 'dev', 'role': 'user'}))"
  devToken: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZXYiLCJyb2xlIjoidXNlciIsImV4cCI6MTc3NzY2MjM3OX0.RTUQW8RdxA4bwp32VH201vUZjoOIeLqBmkXDSrUJOss',
};

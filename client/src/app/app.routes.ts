import { Routes } from '@angular/router';
import { ShellComponent } from '../components/shell/shell.component';
import { LoginPageComponent } from '../pages/login-page/login-page.component';
import { DashboardPageComponent } from '../pages/dashboard-page/dashboard-page.component';
import { SubmitPageComponent } from '../pages/submit-page/submit-page.component';
import { StatusPageComponent } from '../pages/status-page/status-page.component';
import { AssignmentPageComponent } from '../pages/assignment-page/assignment-page.component';
import { authGuard } from '../guards/auth.guard';

export const routes: Routes = [
  { path: 'login', component: LoginPageComponent },
  {
    path: '',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      { path: 'dashboard', component: DashboardPageComponent },
      { path: 'submit', component: SubmitPageComponent },
      { path: 'status/:id', component: StatusPageComponent },
      { path: 'assignment', component: AssignmentPageComponent },
    ],
  },
  { path: '**', redirectTo: 'dashboard' },
];

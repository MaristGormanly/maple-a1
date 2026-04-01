import { Routes } from '@angular/router';
import { SubmitPageComponent } from '../pages/submit-page/submit-page.component';
import { StatusPageComponent } from '../pages/status-page/status-page.component';

export const routes: Routes = [
  { path: '', redirectTo: 'submit', pathMatch: 'full' },
  { path: 'submit', component: SubmitPageComponent },
  { path: 'status/:id', component: StatusPageComponent },
  { path: '**', redirectTo: 'submit' },
];

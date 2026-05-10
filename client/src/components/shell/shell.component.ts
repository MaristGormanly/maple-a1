import { Component, inject } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive, Router } from '@angular/router';

import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './shell.component.html',
})
export class ShellComponent {
  private router = inject(Router);
  private auth = inject(AuthService);

  get currentUserEmail(): string {
    return this.auth.getClaims()?.sub ?? 'instructor@marist.edu';
  }

  get currentUserRole(): string {
    return this.auth.getClaims()?.role ?? 'Instructor';
  }

  get userInitials(): string {
    const local = this.currentUserEmail.split('@')[0];
    return local.slice(0, 2).toUpperCase();
  }

  logout(): void {
    this.auth.clear();
    this.router.navigate(['/login']);
  }
}

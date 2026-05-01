import { Component, inject } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login-page',
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './login-page.component.html',
})
export class LoginPageComponent {
  private router = inject(Router);
  private auth = inject(AuthService);

  showPassword = false;
  submitting = false;
  errorMessage: string | null = null;

  form = new FormGroup({
    email: new FormControl('', [Validators.required, Validators.email]),
    password: new FormControl('', [Validators.required, Validators.minLength(1)]),
  });

  onSubmit(event: Event): void {
    event.preventDefault();
    if (this.submitting) return;
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    const { email, password } = this.form.value;
    this.submitting = true;
    this.errorMessage = null;

    this.auth.login(email!, password!).subscribe((outcome) => {
      this.submitting = false;
      if (outcome.success) {
        this.router.navigate(['/dashboard']);
      } else {
        this.errorMessage = outcome.errorMessage ?? 'Sign-in failed.';
      }
    });
  }

  get showEmailErr(): boolean {
    const c = this.form.controls.email;
    return c.touched && c.invalid;
  }

  get showPwErr(): boolean {
    const c = this.form.controls.password;
    return c.touched && c.invalid;
  }
}

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
  showCreatePassword = false;
  createMode = false;
  submitting = false;
  errorMessage: string | null = null;

  form = new FormGroup({
    email: new FormControl('', [Validators.required, Validators.email]),
    password: new FormControl('', [Validators.required, Validators.minLength(1)]),
  });

  createForm = new FormGroup({
    name: new FormControl('', [Validators.required, Validators.maxLength(160)]),
    email: new FormControl('', [Validators.required, Validators.email]),
    username: new FormControl('', [
      Validators.minLength(3),
      Validators.maxLength(80),
      Validators.pattern(/^[A-Za-z0-9._-]*$/),
    ]),
    school: new FormControl('', [Validators.maxLength(160)]),
    password: new FormControl('', [Validators.required, Validators.minLength(8)]),
  });

  setMode(createMode: boolean): void {
    this.createMode = createMode;
    this.errorMessage = null;
  }

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

  onCreateAccount(event: Event): void {
    event.preventDefault();
    if (this.submitting) return;
    if (this.createForm.invalid) {
      this.createForm.markAllAsTouched();
      return;
    }

    const raw = this.createForm.getRawValue();
    this.submitting = true;
    this.errorMessage = null;

    this.auth
      .register({
        name: raw.name!.trim(),
        email: raw.email!.trim(),
        username: raw.username?.trim() || null,
        school: raw.school?.trim() || null,
        password: raw.password!,
      })
      .subscribe((outcome) => {
        this.submitting = false;
        if (outcome.success) {
          this.router.navigate(['/dashboard']);
        } else {
          this.errorMessage = outcome.errorMessage ?? 'Account creation failed.';
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

  get showCreateNameErr(): boolean {
    const c = this.createForm.controls.name;
    return c.touched && c.invalid;
  }

  get showCreateEmailErr(): boolean {
    const c = this.createForm.controls.email;
    return c.touched && c.invalid;
  }

  get showCreatePwErr(): boolean {
    const c = this.createForm.controls.password;
    return c.touched && c.invalid;
  }
}

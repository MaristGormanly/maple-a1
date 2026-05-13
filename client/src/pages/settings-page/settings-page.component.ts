import { DatePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';

import { ConfirmDialogComponent } from '../../components/confirm-dialog/confirm-dialog.component';
import { AuthService } from '../../services/auth.service';
import { SettingsService } from '../../services/settings.service';
import { AccountProfile, GitHubSettingsData, StyleGuideReference } from '../../utils/api.types';

type SettingsTab = 'github' | 'style-guides' | 'account';
const DELETE_CONFIRMATION = 'I want to delete my account';

@Component({
  selector: 'app-settings-page',
  standalone: true,
  imports: [DatePipe, ReactiveFormsModule, ConfirmDialogComponent],
  templateUrl: './settings-page.component.html',
})
export class SettingsPageComponent implements OnInit {
  private router = inject(Router);
  private auth = inject(AuthService);

  activeTab = signal<SettingsTab>('github');
  githubSettings = signal<GitHubSettingsData | null>(null);
  styleGuideReferences = signal<StyleGuideReference[]>([]);
  accountProfile = signal<AccountProfile | null>(null);

  form = new FormGroup({
    githubUsername: new FormControl('', [Validators.maxLength(120)]),
    personalAccessToken: new FormControl('', [Validators.required, Validators.maxLength(512)]),
  });

  accountForm = new FormGroup({
    name: new FormControl('', [Validators.required, Validators.maxLength(160)]),
    email: new FormControl('', [Validators.required, Validators.email, Validators.maxLength(255)]),
    username: new FormControl('', [
      Validators.minLength(3),
      Validators.maxLength(80),
      Validators.pattern(/^[A-Za-z0-9._-]*$/),
    ]),
    school: new FormControl('', [Validators.maxLength(160)]),
  });

  passwordForm = new FormGroup({
    currentPassword: new FormControl('', [Validators.required]),
    newPassword: new FormControl('', [Validators.required, Validators.minLength(8)]),
  });

  deleteAccountForm = new FormGroup({
    confirmation: new FormControl('', [Validators.required]),
  });

  loading = signal(true);
  referencesLoading = signal(true);
  accountLoading = signal(true);
  saving = signal(false);
  savingAccount = signal(false);
  savingPassword = signal(false);
  clearing = signal(false);
  deletingAccount = signal(false);
  showDeleteDialog = signal(false);
  errorMessage = signal<string | null>(null);
  successMessage = signal<string | null>(null);
  successBody = signal<string | null>(null);

  constructor(private settingsService: SettingsService) {}

  ngOnInit(): void {
    this.loadGitHubSettings();
    this.loadStyleGuideReferences();
    this.loadAccountProfile();
  }

  selectTab(tab: SettingsTab): void {
    this.activeTab.set(tab);
  }

  loadGitHubSettings(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.successBody.set(null);
    this.settingsService
      .getGitHubSettings()
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe((response) => {
        if (response.success && response.data) {
          this.applyGitHubSettings(response.data);
        } else {
          this.errorMessage.set(response.error?.message ?? 'Unable to load GitHub settings.');
        }
      });
  }

  loadStyleGuideReferences(): void {
    this.referencesLoading.set(true);
    this.settingsService
      .getStyleGuideReferences()
      .pipe(finalize(() => this.referencesLoading.set(false)))
      .subscribe((response) => {
        if (response.success && response.data) {
          this.styleGuideReferences.set(response.data.references);
        } else {
          this.errorMessage.set(response.error?.message ?? 'Unable to load style guide references.');
          this.styleGuideReferences.set([]);
        }
      });
  }

  saveGitHubSettings(): void {
    if (this.githubSettings()?.connected) {
      this.errorMessage.set('Delete the existing GitHub key before saving a new one.');
      return;
    }

    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    const raw = this.form.getRawValue();
    this.saving.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.successBody.set(null);
    this.form.disable({ emitEvent: false });

    this.settingsService
      .saveGitHubSettings(raw.githubUsername?.trim() || null, raw.personalAccessToken ?? '')
      .pipe(
        finalize(() => {
          this.saving.set(false);
          this.syncFormLockState();
        }),
      )
      .subscribe((response) => {
        if (response.success && response.data) {
          this.applyGitHubSettings(response.data);
          this.successMessage.set('GitHub connection saved.');
          this.successBody.set('The token itself is encrypted server-side and is never displayed here.');
        } else {
          this.errorMessage.set(response.error?.message ?? 'Unable to save GitHub settings.');
        }
      });
  }

  openDeleteDialog(): void {
    if (!this.githubSettings()?.connected) return;
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.successBody.set(null);
    this.showDeleteDialog.set(true);
  }

  cancelDeleteDialog(): void {
    this.showDeleteDialog.set(false);
  }

  clearGitHubSettings(): void {
    if (!this.githubSettings()?.connected) return;

    this.clearing.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.successBody.set(null);

    this.settingsService
      .clearGitHubSettings()
      .pipe(finalize(() => this.clearing.set(false)))
      .subscribe((response) => {
        if (response.success && response.data) {
          this.showDeleteDialog.set(false);
          this.applyGitHubSettings(response.data);
          this.successMessage.set('GitHub key deleted.');
          this.successBody.set('A new token is required before evaluations can access private repositories.');
        } else {
          this.errorMessage.set(response.error?.message ?? 'Unable to delete GitHub key.');
        }
      });
  }

  loadAccountProfile(): void {
    this.accountLoading.set(true);
    this.settingsService
      .getAccountProfile()
      .pipe(finalize(() => this.accountLoading.set(false)))
      .subscribe((response) => {
        if (response.success && response.data) {
          this.applyAccountProfile(response.data);
        } else {
          this.errorMessage.set(response.error?.message ?? 'Unable to load account information.');
        }
      });
  }

  saveAccountProfile(): void {
    if (this.accountForm.invalid) {
      this.accountForm.markAllAsTouched();
      return;
    }

    const raw = this.accountForm.getRawValue();
    this.savingAccount.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.successBody.set(null);

    this.settingsService
      .updateAccountProfile({
        name: raw.name?.trim() || null,
        email: raw.email?.trim() || null,
        username: raw.username?.trim() || null,
        school: raw.school?.trim() || null,
      })
      .pipe(finalize(() => this.savingAccount.set(false)))
      .subscribe((response) => {
        if (response.success && response.data) {
          this.applyAccountProfile(response.data);
          this.successMessage.set('Account information saved.');
          this.successBody.set('Your profile changes are now active.');
        } else {
          this.errorMessage.set(response.error?.message ?? 'Unable to save account information.');
        }
      });
  }

  updatePassword(): void {
    if (this.passwordForm.invalid) {
      this.passwordForm.markAllAsTouched();
      return;
    }

    const raw = this.passwordForm.getRawValue();
    this.savingPassword.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.successBody.set(null);

    this.settingsService
      .updatePassword(raw.currentPassword ?? '', raw.newPassword ?? '')
      .pipe(finalize(() => this.savingPassword.set(false)))
      .subscribe((response) => {
        if (response.success && response.data?.updated) {
          this.passwordForm.reset();
          this.successMessage.set('Password updated.');
          this.successBody.set('Use the new password the next time you sign in.');
        } else {
          this.errorMessage.set(response.error?.message ?? 'Unable to update password.');
        }
      });
  }

  deleteAccount(): void {
    const confirmation = this.deleteAccountForm.controls.confirmation.value ?? '';
    if (confirmation !== DELETE_CONFIRMATION) {
      this.deleteAccountForm.markAllAsTouched();
      this.errorMessage.set(`Type "${DELETE_CONFIRMATION}" before deleting your account.`);
      return;
    }

    this.deletingAccount.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);
    this.successBody.set(null);

    this.settingsService
      .deleteAccount(confirmation)
      .pipe(finalize(() => this.deletingAccount.set(false)))
      .subscribe((response) => {
        if (response.success) {
          this.auth.clear();
          this.router.navigate(['/login']);
        } else {
          this.errorMessage.set(response.error?.message ?? 'Unable to delete account.');
        }
      });
  }

  get deleteConfirmation(): string {
    return DELETE_CONFIRMATION;
  }

  get deleteAccountReady(): boolean {
    return this.deleteAccountForm.controls.confirmation.value === DELETE_CONFIRMATION;
  }

  get showUsernameErr(): boolean {
    const c = this.form.controls.githubUsername;
    return c.touched && c.invalid;
  }

  get showTokenErr(): boolean {
    const c = this.form.controls.personalAccessToken;
    return c.touched && c.invalid;
  }

  private applyGitHubSettings(settings: GitHubSettingsData): void {
    this.githubSettings.set(settings);
    this.form.reset({
      githubUsername: settings.github_username ?? '',
      personalAccessToken: '',
    });
    this.syncFormLockState();
  }

  private applyAccountProfile(profile: AccountProfile): void {
    this.accountProfile.set(profile);
    this.accountForm.reset({
      name: profile.name ?? '',
      email: profile.email,
      username: profile.username ?? '',
      school: profile.school ?? '',
    });
  }

  private syncFormLockState(): void {
    if (this.githubSettings()?.connected) {
      this.form.controls.githubUsername.disable({ emitEvent: false });
      this.form.controls.personalAccessToken.disable({ emitEvent: false });
    } else {
      this.form.enable({ emitEvent: false });
    }
  }
}

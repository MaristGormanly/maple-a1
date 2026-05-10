import { DatePipe } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize } from 'rxjs';

import { ConfirmDialogComponent } from '../../components/confirm-dialog/confirm-dialog.component';
import { SettingsService } from '../../services/settings.service';
import { GitHubSettingsData } from '../../utils/api.types';

type SettingsTab = 'github';

@Component({
  selector: 'app-settings-page',
  standalone: true,
  imports: [DatePipe, ReactiveFormsModule, ConfirmDialogComponent],
  templateUrl: './settings-page.component.html',
})
export class SettingsPageComponent implements OnInit {
  activeTab = signal<SettingsTab>('github');
  githubSettings = signal<GitHubSettingsData | null>(null);

  form = new FormGroup({
    githubUsername: new FormControl('', [Validators.maxLength(120)]),
    personalAccessToken: new FormControl('', [Validators.required, Validators.maxLength(512)]),
  });

  loading = signal(true);
  saving = signal(false);
  clearing = signal(false);
  showDeleteDialog = signal(false);
  errorMessage = signal<string | null>(null);
  successMessage = signal<string | null>(null);

  constructor(private settingsService: SettingsService) {}

  ngOnInit(): void {
    this.loadGitHubSettings();
  }

  selectTab(tab: SettingsTab): void {
    this.activeTab.set(tab);
  }

  loadGitHubSettings(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
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
        } else {
          this.errorMessage.set(response.error?.message ?? 'Unable to save GitHub settings.');
        }
      });
  }

  openDeleteDialog(): void {
    if (!this.githubSettings()?.connected) return;
    this.errorMessage.set(null);
    this.successMessage.set(null);
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

    this.settingsService
      .clearGitHubSettings()
      .pipe(finalize(() => this.clearing.set(false)))
      .subscribe((response) => {
        if (response.success && response.data) {
          this.showDeleteDialog.set(false);
          this.applyGitHubSettings(response.data);
          this.successMessage.set('GitHub key deleted.');
        } else {
          this.errorMessage.set(response.error?.message ?? 'Unable to delete GitHub key.');
        }
      });
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

  private syncFormLockState(): void {
    if (this.githubSettings()?.connected) {
      this.form.controls.githubUsername.disable({ emitEvent: false });
      this.form.controls.personalAccessToken.disable({ emitEvent: false });
    } else {
      this.form.enable({ emitEvent: false });
    }
  }
}

import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { of } from 'rxjs';

import { SettingsPageComponent } from './settings-page.component';
import { AuthService } from '../../services/auth.service';
import { SettingsService } from '../../services/settings.service';
import {
  AccountProfileResponse,
  DeleteResponse,
  GitHubSettingsResponse,
  PasswordUpdateResponse,
  StyleGuideReferencesResponse,
} from '../../utils/api.types';

const METADATA = { timestamp: '2026-05-09T00:00:00Z', module: 'a1', version: '1.0.0' };

function githubResponse(
  connected: boolean,
  githubUsername: string | null = connected ? 'instructor' : null,
): GitHubSettingsResponse {
  return {
    success: true,
    error: null,
    metadata: METADATA,
    data: {
      connected,
      github_username: githubUsername,
      last_updated_at: connected ? '2026-05-09T12:00:00Z' : null,
    },
  };
}

function styleGuideReferencesResponse(
  references: NonNullable<StyleGuideReferencesResponse['data']>['references'] = [
    {
      title: 'PEP 8 — Style Guide for Python Code',
      document_url: 'https://peps.python.org/pep-0008/',
      language: 'python',
      version: '2024-06-01',
      date_created: '2026-05-12T14:30:00Z',
    },
  ],
): StyleGuideReferencesResponse {
  return {
    success: true,
    error: null,
    metadata: METADATA,
    data: { references },
  };
}

function accountResponse(): AccountProfileResponse {
  return {
    success: true,
    error: null,
    metadata: METADATA,
    data: {
      user_id: 'user-1',
      name: 'Elena Marsh',
      email: 'elena@marist.edu',
      username: 'emarsh',
      school: 'Marist',
      role: 'Instructor',
      created_at: '2026-05-13T12:00:00Z',
      updated_at: null,
    },
  };
}

describe('SettingsPageComponent', () => {
  let settingsService: {
    getGitHubSettings: ReturnType<typeof vi.fn>;
    getStyleGuideReferences: ReturnType<typeof vi.fn>;
    saveGitHubSettings: ReturnType<typeof vi.fn>;
    clearGitHubSettings: ReturnType<typeof vi.fn>;
    getAccountProfile: ReturnType<typeof vi.fn>;
    updateAccountProfile: ReturnType<typeof vi.fn>;
    updatePassword: ReturnType<typeof vi.fn>;
    deleteAccount: ReturnType<typeof vi.fn>;
  };
  let router: { navigate: ReturnType<typeof vi.fn> };
  let auth: { clear: ReturnType<typeof vi.fn> };

  beforeEach(async () => {
    settingsService = {
      getGitHubSettings: vi.fn(),
      getStyleGuideReferences: vi.fn(),
      saveGitHubSettings: vi.fn(),
      clearGitHubSettings: vi.fn(),
      getAccountProfile: vi.fn(),
      updateAccountProfile: vi.fn(),
      updatePassword: vi.fn(),
      deleteAccount: vi.fn(),
    };
    router = { navigate: vi.fn() };
    auth = { clear: vi.fn() };

    await TestBed.configureTestingModule({
      imports: [SettingsPageComponent],
      providers: [
        { provide: SettingsService, useValue: settingsService },
        { provide: AuthService, useValue: auth },
        { provide: Router, useValue: router },
      ],
    }).compileComponents();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function setup(
    initialResponse: GitHubSettingsResponse,
    referencesResponse: StyleGuideReferencesResponse = styleGuideReferencesResponse(),
  ) {
    settingsService.getGitHubSettings.mockReturnValue(of(initialResponse));
    settingsService.getStyleGuideReferences.mockReturnValue(of(referencesResponse));
    settingsService.getAccountProfile.mockReturnValue(of(accountResponse()));
    const fixture = TestBed.createComponent(SettingsPageComponent);
    fixture.detectChanges();
    return { fixture, component: fixture.componentInstance };
  }

  it('renders connected state as a locked saved key', () => {
    const { fixture, component } = setup(githubResponse(true, 'octocat'));
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    const username = host.querySelector<HTMLInputElement>('#githubUsername');

    expect(username?.value).toBe('octocat');
    expect(username?.disabled).toBe(true);
    expect(host.querySelector('#personalAccessToken')).toBeNull();
    expect(host.textContent).toContain('Personal access token saved and encrypted in the backend.');
    expect(host.textContent).toContain('Delete key');
    expect(host.textContent).not.toContain('Save connection');
    expect(component.form.controls.personalAccessToken.disabled).toBe(true);
  });

  it('renders not connected state as editable save form', () => {
    const { fixture, component } = setup(githubResponse(false));
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    const username = host.querySelector<HTMLInputElement>('#githubUsername');

    expect(username?.disabled).toBe(false);
    expect(host.querySelector('#personalAccessToken')).not.toBeNull();
    expect(host.textContent).toContain('Save connection');
    expect(host.textContent).not.toContain('Delete key');
    expect(component.form.enabled).toBe(true);
  });

  it('saving a token updates the page into connected state', () => {
    const { fixture, component } = setup(githubResponse(false));
    settingsService.saveGitHubSettings.mockReturnValue(of(githubResponse(true, 'octocat')));

    component.form.controls.githubUsername.setValue('octocat');
    component.form.controls.personalAccessToken.setValue('github_pat_secret');
    component.saveGitHubSettings();
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    expect(settingsService.saveGitHubSettings).toHaveBeenCalledWith('octocat', 'github_pat_secret');
    expect(component.githubSettings()?.connected).toBe(true);
    expect(host.querySelector('#personalAccessToken')).toBeNull();
    expect(host.textContent).toContain('Delete key');
    expect(host.textContent).toContain('GitHub connection saved.');
  });

  it('delete confirmation clears the connection and returns to save form', () => {
    const { fixture, component } = setup(githubResponse(true, 'octocat'));
    settingsService.clearGitHubSettings.mockReturnValue(of(githubResponse(false)));

    component.openDeleteDialog();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Delete GitHub key');

    component.clearGitHubSettings();
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    expect(settingsService.clearGitHubSettings).toHaveBeenCalled();
    expect(component.githubSettings()?.connected).toBe(false);
    expect(host.querySelector('#personalAccessToken')).not.toBeNull();
    expect(host.textContent).toContain('Save connection');
    expect(host.textContent).not.toContain('Delete GitHub key');
    expect(host.textContent).toContain('GitHub key deleted.');
  });

  it('renders style guide references in the adjacent settings tab', () => {
    const { fixture, component } = setup(githubResponse(true, 'octocat'));

    component.selectTab('style-guides');
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    const link = host.querySelector<HTMLAnchorElement>('a[href="https://peps.python.org/pep-0008/"]');

    expect(host.textContent).toContain('Style Guide References');
    expect(host.textContent).toContain('PEP 8 — Style Guide for Python Code');
    expect(host.textContent).toContain('python');
    expect(host.textContent).toContain('2024-06-01');
    expect(link?.textContent).toContain('Open');
    expect(link?.target).toBe('_blank');
  });

  it('renders an empty style guide references state', () => {
    const { fixture, component } = setup(
      githubResponse(true, 'octocat'),
      styleGuideReferencesResponse([]),
    );

    component.selectTab('style-guides');
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    expect(host.textContent).toContain('No references indexed');
    expect(host.textContent).toContain('Run the style guide ingester before using RAG-backed style review.');
  });

  it('renders and saves account information in the account tab', () => {
    const { fixture, component } = setup(githubResponse(true, 'octocat'));
    settingsService.updateAccountProfile.mockReturnValue(of({
      ...accountResponse(),
      data: {
        ...accountResponse().data!,
        name: 'Elena M.',
        username: 'elenam',
        school: 'School of CS',
      },
    } satisfies AccountProfileResponse));

    component.selectTab('account');
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    expect(host.textContent).toContain('Account Information');
    expect(host.querySelector<HTMLInputElement>('#accountName')?.value).toBe('Elena Marsh');

    component.accountForm.controls.name.setValue('Elena M.');
    component.accountForm.controls.username.setValue('elenam');
    component.accountForm.controls.school.setValue('School of CS');
    component.saveAccountProfile();
    fixture.detectChanges();

    expect(settingsService.updateAccountProfile).toHaveBeenCalledWith({
      name: 'Elena M.',
      email: 'elena@marist.edu',
      username: 'elenam',
      school: 'School of CS',
    });
    expect(component.accountProfile()?.name).toBe('Elena M.');
    expect(host.textContent).toContain('Account information saved.');
  });

  it('updates password without displaying stored password', () => {
    const { fixture, component } = setup(githubResponse(true, 'octocat'));
    settingsService.updatePassword.mockReturnValue(of({
      success: true,
      data: { updated: true },
      error: null,
      metadata: METADATA,
    } satisfies PasswordUpdateResponse));

    component.selectTab('account');
    component.passwordForm.controls.currentPassword.setValue('oldpassword');
    component.passwordForm.controls.newPassword.setValue('newpassword');
    component.updatePassword();
    fixture.detectChanges();

    const host = fixture.nativeElement as HTMLElement;
    expect(settingsService.updatePassword).toHaveBeenCalledWith('oldpassword', 'newpassword');
    expect(host.textContent).toContain('Password updated.');
    expect(host.textContent).not.toContain('oldpassword');
    expect(host.textContent).not.toContain('newpassword');
  });

  it('requires exact confirmation before deleting the account and logs out on success', () => {
    const { fixture, component } = setup(githubResponse(true, 'octocat'));
    settingsService.deleteAccount.mockReturnValue(of({
      success: true,
      data: { deleted: 'user-1' },
      error: null,
      metadata: METADATA,
    } satisfies DeleteResponse));

    component.selectTab('account');
    fixture.detectChanges();

    expect(component.deleteAccountReady).toBe(false);
    component.deleteAccountForm.controls.confirmation.setValue('I want to delete my account');
    component.deleteAccount();

    expect(settingsService.deleteAccount).toHaveBeenCalledWith('I want to delete my account');
    expect(auth.clear).toHaveBeenCalled();
    expect(router.navigate).toHaveBeenCalledWith(['/login']);
  });
});

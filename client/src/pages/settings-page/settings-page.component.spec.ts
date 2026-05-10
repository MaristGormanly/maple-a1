import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { SettingsPageComponent } from './settings-page.component';
import { SettingsService } from '../../services/settings.service';
import { GitHubSettingsResponse } from '../../utils/api.types';

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

describe('SettingsPageComponent', () => {
  let settingsService: {
    getGitHubSettings: ReturnType<typeof vi.fn>;
    saveGitHubSettings: ReturnType<typeof vi.fn>;
    clearGitHubSettings: ReturnType<typeof vi.fn>;
  };

  beforeEach(async () => {
    settingsService = {
      getGitHubSettings: vi.fn(),
      saveGitHubSettings: vi.fn(),
      clearGitHubSettings: vi.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [SettingsPageComponent],
      providers: [{ provide: SettingsService, useValue: settingsService }],
    }).compileComponents();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function setup(initialResponse: GitHubSettingsResponse) {
    settingsService.getGitHubSettings.mockReturnValue(of(initialResponse));
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
});

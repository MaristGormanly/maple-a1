import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { RepositoryService } from '../../services/repository.service';
import { RepositoryItem, RepositoryListResponse } from '../../utils/api.types';

@Component({
  selector: 'app-repositories-page',
  standalone: true,
  imports: [DatePipe, RouterLink],
  templateUrl: './repositories-page.component.html',
})
export class RepositoriesPageComponent {
  private repositoryService = inject(RepositoryService);
  private router = inject(Router);

  readonly searchQuery = signal('');
  private readonly _response = signal<RepositoryListResponse | null>(null);
  private readonly _repos = signal<RepositoryItem[]>([]);

  readonly loading = computed(() => this._response() === null);
  readonly loadError = computed(() => {
    const r = this._response();
    return r && (!r.success || !r.data)
      ? { code: r.error?.code ?? '', message: r.error?.message ?? 'Failed to load repositories.' }
      : null;
  });

  readonly filtered = computed(() => {
    const needle = this.searchQuery().toLowerCase();
    if (!needle) return this._repos();
    return this._repos().filter(r =>
      [r.full_name, r.description ?? ''].join(' ').toLowerCase().includes(needle)
    );
  });

  constructor() {
    this.repositoryService.listRepositories().subscribe(res => {
      this._response.set(res);
      this._repos.set(res.data?.repositories ?? []);
    });
  }

  onSearch(event: Event): void {
    this.searchQuery.set((event.target as HTMLInputElement).value);
  }

  submitRepo(repo: RepositoryItem): void {
    this.router.navigate(['/submit'], { state: { prefillUrl: repo.html_url } });
  }
}

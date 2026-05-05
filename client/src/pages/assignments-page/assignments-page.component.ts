import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AssignmentService } from '../../services/assignment.service';
import { AssignmentData, AssignmentListResponse } from '../../utils/api.types';

@Component({
  selector: 'app-assignments-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './assignments-page.component.html',
})
export class AssignmentsPageComponent {
  private assignmentService = inject(AssignmentService);
  readonly router = inject(Router);

  readonly searchQuery = signal('');
  private readonly _response = signal<AssignmentListResponse | null>(null);

  readonly loading = computed(() => this._response() === null);
  readonly loadError = computed(() => {
    const r = this._response();
    return r && (!r.success || !r.data) ? (r.error?.message ?? 'Failed to load assignments.') : null;
  });
  readonly allAssignments = computed(() => this._response()?.data?.assignments ?? []);
  readonly filtered = computed(() => {
    const needle = this.searchQuery().toLowerCase();
    if (!needle) return this.allAssignments();
    return this.allAssignments().filter(a =>
      [a.title, a.test_suite_repo_url ?? '', a.language_override ?? '']
        .join(' ').toLowerCase().includes(needle));
  });

  constructor() {
    this.assignmentService.getAll().subscribe(res => this._response.set(res));
  }

  viewAssignment(a: AssignmentData): void {
    this.router.navigate(['/assignments', a.assignment_id]);
  }

  onSearch(event: Event): void {
    this.searchQuery.set((event.target as HTMLInputElement).value);
  }
}

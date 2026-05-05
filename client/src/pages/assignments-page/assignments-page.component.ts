import { Component, OnInit } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AssignmentService } from '../../services/assignment.service';
import { AssignmentData } from '../../utils/api.types';

@Component({
  selector: 'app-assignments-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './assignments-page.component.html',
})
export class AssignmentsPageComponent implements OnInit {
  allAssignments: AssignmentData[] = [];
  loading = true;
  loadError: string | null = null;
  searchQuery = '';

  constructor(private router: Router, private assignmentService: AssignmentService) {}

  ngOnInit(): void {
    this.assignmentService.getAll().subscribe((res) => {
      this.loading = false;
      if (!res.success || !res.data) {
        this.loadError = res.error?.message ?? 'Failed to load assignments.';
        return;
      }
      this.allAssignments = res.data.assignments;
    });
  }

  get filtered(): AssignmentData[] {
    if (!this.searchQuery) return this.allAssignments;
    const needle = this.searchQuery.toLowerCase();
    return this.allAssignments.filter((a) => {
      const haystack = [a.title, a.test_suite_repo_url ?? '', a.language_override ?? '']
        .join(' ')
        .toLowerCase();
      return haystack.includes(needle);
    });
  }

  viewAssignment(a: AssignmentData): void {
    this.router.navigate(['/assignments', a.assignment_id]);
  }
}

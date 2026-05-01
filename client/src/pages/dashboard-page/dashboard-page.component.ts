import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { SubmissionStatusData } from '../../utils/api.types';
import { badgeTone, displayStatus } from '../../utils/status-display.util';

interface Student {
  name: string;
  email: string;
  initials: string;
  tint: number;
}

interface Submission {
  id: string;
  student: Student;
  github: string;
  status: string;
  score: number | null;
  submitted: string;
}

const AVATAR_TINTS = [
  'oklch(0.6 0.12 265)',
  'oklch(0.6 0.12 155)',
  'oklch(0.62 0.14 55)',
  'oklch(0.58 0.14 25)',
  'oklch(0.55 0.12 315)',
  'oklch(0.6 0.12 195)',
  'oklch(0.55 0.13 85)',
  'oklch(0.58 0.14 355)',
];

const JORDAN_VEGA_STATUS: SubmissionStatusData = {
  submission_id: 'a3f1c82e-9b04-4d7e-8f12-6a7b9c4d5e2f',
  assignment_id: '11111111-2222-3333-4444-555555555555',
  student_id: 'b7e2c4a0-1234-5678-abcd-ef0123456789',
  github_repo_url: 'github.com/jvega-marist/cmpt220-hw4-bst',
  commit_hash: 'a4f8c2d19e3b',
  status: 'Awaiting Review',
  created_at: new Date(Date.now() - 12 * 60 * 1000).toISOString(),
  evaluation: {
    deterministic_score: 78,
    review_status: 'pending',
    metadata: {
      language: { language: 'python', version: '3.11', source: 'pyproject.toml', override_applied: false },
      test_summary: { framework: 'pytest', passed: 8, failed: 2, errors: 0, skipped: 0 },
    },
    ai_feedback: {
      flags: [],
      metadata: { style_guide_version: 'PEP 8 (2024)' },
      criteria_scores: [
        {
          criterion_name: 'BST Insert & Search',
          score: 90,
          level: 'Exemplary',
          justification: 'Both insert() and search() are implemented correctly and handle all tested cases including duplicate values and empty trees. Iterative search is efficient and avoids unnecessary recursion overhead.',
          confidence: 0.95,
        },
        {
          criterion_name: 'BST Delete',
          score: 65,
          level: 'Developing',
          justification: 'The two-child deletion case uses an incorrect successor: the code finds the in-order predecessor instead of the in-order successor, causing test_delete_root_two_children and test_delete_internal_node to fail. Single-child and leaf deletion are correct.',
          confidence: 0.91,
          recommendation: {
            file_path: 'bst.py',
            line_range: { start: 58, end: 63 },
            original_snippet: '        successor = node.left\n        while successor.right:\n            successor = successor.right',
            revised_snippet: '        successor = node.right\n        while successor.left:\n            successor = successor.left',
            diff: '--- a/bst.py\n+++ b/bst.py\n@@ -58,6 +58,6 @@\n         # find in-order successor\n-        successor = node.left\n-        while successor.right:\n-            successor = successor.right\n+        successor = node.right\n+        while successor.left:\n+            successor = successor.left',
            rationale: 'The in-order successor of a node is the leftmost node in its right subtree, not the rightmost node in its left subtree.',
          },
        },
        {
          criterion_name: 'Edge Case Handling',
          score: 70,
          level: 'Proficient',
          justification: 'Empty tree and single-node cases are handled for insert and search. Delete on an empty tree raises an unhandled AttributeError rather than returning gracefully, which caused one test failure.',
          confidence: 0.88,
          recommendation: {
            file_path: 'bst.py',
            line_range: { start: 44, end: 46 },
            original_snippet: '    def delete(self, val):\n        self.root = self._delete(self.root, val)',
            revised_snippet: '    def delete(self, val):\n        if self.root is None:\n            return\n        self.root = self._delete(self.root, val)',
            diff: '--- a/bst.py\n+++ b/bst.py\n@@ -44,4 +44,6 @@\n     def delete(self, val):\n-        self.root = self._delete(self.root, val)\n+        if self.root is None:\n+            return\n+        self.root = self._delete(self.root, val)',
            rationale: 'Without a None guard, calling delete() on an empty tree propagates into _delete() where self.root is None and triggers an AttributeError.',
          },
        },
        {
          criterion_name: 'Code Style & Readability',
          score: 80,
          level: 'Proficient',
          justification: 'Naming is consistent and follows PEP 8 conventions. Helper methods are well-separated. Two private methods are missing docstrings, and one function exceeds the 79-character line limit on three lines.',
          confidence: 0.82,
        },
      ],
      recommendations: [
        {
          file_path: 'bst.py',
          line_range: { start: 58, end: 63 },
          original_snippet: '        successor = node.left\n        while successor.right:\n            successor = successor.right',
          revised_snippet: '        successor = node.right\n        while successor.left:\n            successor = successor.left',
          diff: '--- a/bst.py\n+++ b/bst.py\n@@ -58,6 +58,6 @@\n         # find in-order successor\n-        successor = node.left\n-        while successor.right:\n-            successor = successor.right\n+        successor = node.right\n+        while successor.left:\n+            successor = successor.left',
          rationale: 'In-order successor must come from the right subtree, not the left.',
        },
        {
          file_path: 'bst.py',
          line_range: { start: 44, end: 46 },
          original_snippet: '    def delete(self, val):\n        self.root = self._delete(self.root, val)',
          revised_snippet: '    def delete(self, val):\n        if self.root is None:\n            return\n        self.root = self._delete(self.root, val)',
          diff: '--- a/bst.py\n+++ b/bst.py\n@@ -44,4 +44,6 @@\n     def delete(self, val):\n-        self.root = self._delete(self.root, val)\n+        if self.root is None:\n+            return\n+        self.root = self._delete(self.root, val)',
          rationale: 'Guard against delete() being called on an empty tree.',
        },
      ],
    },
  },
};

const FIXTURE_STATUS: Record<string, SubmissionStatusData> = {
  'a3f1c82e-9b04-4d7e-8f12-6a7b9c4d5e2f': JORDAN_VEGA_STATUS,
};

const SUBMISSIONS: Submission[] = [
  { id: 'a3f1c82e-9b04-4d7e-8f12-6a7b9c4d5e2f', student: { name: 'Jordan Vega', email: 'jvega@marist.edu', initials: 'JV', tint: 0 }, github: 'github.com/jvega-marist/cmpt220-hw4-bst', status: 'Awaiting Review', score: 78, submitted: '12 min ago' },
  { id: 'b4c2d935-0e17-4a8f-9d31-7c5e8a9b2d41', student: { name: 'Priya Sharma', email: 'psharma@marist.edu', initials: 'PS', tint: 1 }, github: 'github.com/priyas/hw4-trees', status: 'Completed', score: 94, submitted: '38 min ago' },
  { id: 'c5d3ea46-1f28-4b90-8e42-6d7f9a0b3c52', student: { name: 'Marcus Lee', email: 'mlee@marist.edu', initials: 'ML', tint: 2 }, github: 'github.com/marcuslee/cmpt220-hw4', status: 'Evaluating', score: null, submitted: '41 min ago' },
  { id: 'd6e4fb57-2039-4c01-9f53-7e8fab1c4d63', student: { name: 'Amina Okafor', email: 'aokafor@marist.edu', initials: 'AO', tint: 3 }, github: 'github.com/aminao/bst-hw4', status: 'Testing', score: null, submitted: '1 h ago' },
  { id: 'e7f50c68-314a-4d12-a064-8f9b0c2d5e74', student: { name: 'Ben Tanaka', email: 'btanaka@marist.edu', initials: 'BT', tint: 4 }, github: 'github.com/bentanaka/bst-assignment', status: 'Failed', score: null, submitted: '2 h ago' },
  { id: 'f8061d79-425b-4e23-b175-a0ac1d3e6f85', student: { name: 'Chloe Dubois', email: 'cdubois@marist.edu', initials: 'CD', tint: 5 }, github: 'github.com/chloed/cmpt220-hw4-bst', status: 'Completed', score: 71, submitted: '3 h ago' },
  { id: '091728a0-536c-4f34-c286-b1bd2e4f7096', student: { name: 'Noah Klein', email: 'nklein@marist.edu', initials: 'NK', tint: 6 }, github: 'github.com/noahk/hw4-bst', status: 'Completed', score: 88, submitted: '4 h ago' },
  { id: '1a2839b1-647d-4045-d397-c2ce3f508107', student: { name: 'Sofia Reyes', email: 'sreyes@marist.edu', initials: 'SR', tint: 7 }, github: 'github.com/sofiar/bst-python', status: 'Awaiting Review', score: 82, submitted: '5 h ago' },
  { id: '2b394ac2-758e-4156-e4a8-d3df40619218', student: { name: 'Ethan Brooks', email: 'ebrooks@marist.edu', initials: 'EB', tint: 0 }, github: 'github.com/ebrooks/cmpt220', status: 'Completed', score: 66, submitted: '6 h ago' },
];

@Component({
  selector: 'app-dashboard-page',
  standalone: true,
  imports: [],
  templateUrl: './dashboard-page.component.html',
})
export class DashboardPageComponent {
  view: 'table' | 'cards' = 'table';
  searchQuery = '';
  filter = 'all';
  allSubmissions = SUBMISSIONS;
  avatarTints = AVATAR_TINTS;
  // Visible to template until the dashboard list endpoint (D1) lands.
  sampleAssignmentId = '11111111-2222-3333-4444-555555555555';

  constructor(private router: Router) {}

  get filtered(): Submission[] {
    return this.allSubmissions.filter((r) => {
      if (this.filter !== 'all' && this.displayStatus(r.status) !== this.filter) return false;
      if (this.searchQuery) {
        const needle = this.searchQuery.toLowerCase();
        const haystack = [r.student.name, r.student.email, r.github, r.id].join(' ').toLowerCase();
        if (!haystack.includes(needle)) return false;
      }
      return true;
    });
  }

  avatarColor(tint: number): string {
    return this.avatarTints[tint % this.avatarTints.length];
  }

  displayStatus(raw: string): string {
    return displayStatus(raw);
  }

  badgeTone(status: string): string {
    return badgeTone(status);
  }

  viewStatus(r: Submission): void {
    this.router.navigate(['/status', r.id], {
      state: { statusData: FIXTURE_STATUS[r.id] ?? null, studentLabel: r.student.name },
    });
  }

  copyId(id: string): void {
    navigator.clipboard?.writeText(id);
  }
}

import { Component, Input } from '@angular/core';
import { NgClass } from '@angular/common';

import { CriterionScore } from '../../utils/api.types';

@Component({
  selector: 'app-criteria-scores',
  standalone: true,
  imports: [NgClass],
  templateUrl: './criteria-scores.component.html',
  styles: [`
    .criteria-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
      margin-top: 8px;
    }

    .criterion {
      border: 1px solid #ddd;
      border-radius: 6px;
      padding: 14px 16px;
      background: #fff;
    }

    .criterion--review {
      border-color: #f59e0b;
      background: #fffbeb;
    }

    .criterion-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 8px;
    }

    .criterion-name {
      font-weight: 600;
      font-size: 0.95rem;
    }

    .criterion-badges {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
    }

    .score {
      font-size: 1.1rem;
      font-weight: 700;
      min-width: 40px;
      text-align: right;
    }

    .level-badge {
      display: inline-block;
      padding: 2px 10px;
      border-radius: 12px;
      font-size: 0.78rem;
      font-weight: 600;
      white-space: nowrap;
    }

    .level--exemplary   { background: #d1fae5; color: #065f46; }
    .level--proficient  { background: #dbeafe; color: #1e40af; }
    .level--developing  { background: #fef9c3; color: #854d0e; }
    .level--beginning   { background: #fee2e2; color: #991b1b; }
    .level--review      { background: #fde68a; color: #92400e; }

    .review-flag {
      font-size: 0.75rem;
      font-weight: 600;
      color: #92400e;
      background: #fde68a;
      padding: 2px 8px;
      border-radius: 10px;
    }

    .justification {
      font-size: 0.88rem;
      color: #374151;
      line-height: 1.5;
      margin-bottom: 8px;
    }

    .confidence-row {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.8rem;
      color: #6b7280;
    }

    .confidence-bar-track {
      flex: 1;
      height: 5px;
      background: #e5e7eb;
      border-radius: 3px;
      overflow: hidden;
      max-width: 120px;
    }

    .confidence-bar-fill {
      height: 100%;
      background: #6b7280;
      border-radius: 3px;
    }

    .confidence-bar-fill--high   { background: #10b981; }
    .confidence-bar-fill--medium { background: #f59e0b; }
    .confidence-bar-fill--low    { background: #ef4444; }
  `],
})
export class CriteriaScoresComponent {
  // Criteria arrive in rubric order from the API (Pass 3 preserves rubric criterion sequence).
  @Input() criteriaScores: CriterionScore[] = [];

  levelClass(level: string): string {
    const map: Record<string, string> = {
      Exemplary: 'level--exemplary',
      Proficient: 'level--proficient',
      Developing: 'level--developing',
      Beginning: 'level--beginning',
      NEEDS_HUMAN_REVIEW: 'level--review',
    };
    return map[level] ?? '';
  }

  levelLabel(level: string): string {
    return level === 'NEEDS_HUMAN_REVIEW' ? 'Needs Review' : level;
  }

  confidencePct(confidence: number): number {
    return Math.round(confidence * 100);
  }

  confidenceBarClass(confidence: number): string {
    if (confidence >= 0.75) return 'confidence-bar-fill--high';
    if (confidence >= 0.5)  return 'confidence-bar-fill--medium';
    return 'confidence-bar-fill--low';
  }

  isNeedsReview(criterion: CriterionScore): boolean {
    return criterion.level === 'NEEDS_HUMAN_REVIEW';
  }
}

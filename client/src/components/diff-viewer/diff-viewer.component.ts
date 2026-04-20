import { Component, Input, OnChanges } from '@angular/core';
import { NgClass } from '@angular/common';

import { RecommendationObject } from '../../utils/api.types';

interface DiffLine {
  content: string;
  type: 'added' | 'removed' | 'hunk' | 'context';
}

interface FileGroup {
  filePath: string;
  items: Array<{ rec: RecommendationObject; parsedDiff: DiffLine[] }>;
}

@Component({
  selector: 'app-diff-viewer',
  standalone: true,
  imports: [NgClass],
  templateUrl: './diff-viewer.component.html',
  styles: [`
    .diff-section {
      margin-top: 16px;
    }

    .diff-section-heading {
      font-weight: 600;
      font-size: 0.95rem;
      margin-bottom: 8px;
    }

    .file-group {
      margin-bottom: 20px;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      overflow: hidden;
    }

    .file-header {
      display: flex;
      align-items: center;
      gap: 10px;
      background: #f3f4f6;
      padding: 8px 14px;
      border-bottom: 1px solid #d1d5db;
    }

    .file-path {
      font-family: monospace;
      font-size: 0.85rem;
      font-weight: 600;
      color: #1e40af;
    }

    .rec-block {
      border-top: 1px solid #e5e7eb;
    }

    .rec-block:first-child {
      border-top: none;
    }

    .rec-meta {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 6px 14px;
      background: #f9fafb;
      border-bottom: 1px solid #e5e7eb;
      font-size: 0.8rem;
      color: #6b7280;
    }

    .line-range {
      font-family: monospace;
      font-weight: 500;
    }

    .rationale {
      font-style: italic;
      color: #374151;
    }

    .diff-table {
      width: 100%;
      border-collapse: collapse;
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
      font-size: 0.82rem;
      line-height: 1.5;
    }

    .diff-table tr.line--added   { background: #dcfce7; }
    .diff-table tr.line--removed { background: #fee2e2; }
    .diff-table tr.line--hunk    { background: #dbeafe; color: #1e40af; }
    .diff-table tr.line--context { background: #fff; }

    .diff-gutter {
      width: 20px;
      text-align: center;
      font-size: 0.78rem;
      padding: 0 6px;
      user-select: none;
      color: #9ca3af;
      vertical-align: top;
    }

    .diff-gutter--added   { color: #16a34a; background: #bbf7d0; }
    .diff-gutter--removed { color: #dc2626; background: #fecaca; }
    .diff-gutter--hunk    { color: #1e40af; background: #bfdbfe; }

    .diff-content {
      padding: 1px 14px;
      white-space: pre;
      overflow-x: auto;
      vertical-align: top;
    }
  `],
})
export class DiffViewerComponent implements OnChanges {
  @Input() recommendations: RecommendationObject[] = [];

  fileGroups: FileGroup[] = [];

  ngOnChanges(): void {
    this.fileGroups = this.buildFileGroups(this.recommendations);
  }

  private buildFileGroups(recs: RecommendationObject[]): FileGroup[] {
    const map = new Map<string, FileGroup>();
    for (const rec of recs) {
      if (!map.has(rec.file_path)) {
        map.set(rec.file_path, { filePath: rec.file_path, items: [] });
      }
      map.get(rec.file_path)!.items.push({ rec, parsedDiff: this.parseDiff(rec.diff) });
    }
    // Stable order: preserve first-seen sequence
    return Array.from(map.values());
  }

  private parseDiff(raw: string): DiffLine[] {
    const result: DiffLine[] = [];
    for (const line of raw.split('\n')) {
      if (line.startsWith('--- ') || line.startsWith('+++ ')) {
        // Drop unified-diff file headers; file path shown in the card header
        continue;
      }
      if (line.startsWith('@@')) {
        result.push({ content: line, type: 'hunk' });
      } else if (line.startsWith('+')) {
        result.push({ content: line.slice(1), type: 'added' });
      } else if (line.startsWith('-')) {
        result.push({ content: line.slice(1), type: 'removed' });
      } else {
        // Context lines have a leading space; strip it
        result.push({ content: line.length > 0 ? line.slice(1) : '', type: 'context' });
      }
    }
    return result;
  }

  gutterSymbol(type: DiffLine['type']): string {
    return { added: '+', removed: '-', hunk: '⋯', context: ' ' }[type];
  }

  lineClass(type: DiffLine['type']): string {
    return `line--${type}`;
  }

  gutterClass(type: DiffLine['type']): string {
    return type !== 'context' ? `diff-gutter--${type}` : '';
  }
}

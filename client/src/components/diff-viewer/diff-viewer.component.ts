import { Component, Input, OnChanges } from '@angular/core';
import { RecommendationObject } from '../../utils/api.types';

interface DiffLine {
  content: string;
  type: 'add' | 'del' | 'ctx';
}

interface FileGroup {
  filePath: string;
  items: Array<{ rec: RecommendationObject; lines: DiffLine[]; addCount: number; delCount: number }>;
}

@Component({
  selector: 'app-diff-viewer',
  standalone: true,
  imports: [],
  templateUrl: './diff-viewer.component.html',
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
      const lines = this.parseDiff(rec.diff);
      map.get(rec.file_path)!.items.push({
        rec, lines,
        addCount: lines.filter(l => l.type === 'add').length,
        delCount: lines.filter(l => l.type === 'del').length,
      });
    }
    return Array.from(map.values());
  }

  private parseDiff(raw: string): DiffLine[] {
    const result: DiffLine[] = [];
    for (const line of raw.split('\n')) {
      if (line.startsWith('--- ') || line.startsWith('+++ ') || line.startsWith('@@')) continue;
      if (line.startsWith('+')) {
        result.push({ content: line.slice(1), type: 'add' });
      } else if (line.startsWith('-')) {
        result.push({ content: line.slice(1), type: 'del' });
      } else {
        result.push({ content: line.length > 0 ? line.slice(1) : '', type: 'ctx' });
      }
    }
    return result;
  }

  totalHunks(): number {
    return this.recommendations.length;
  }

  gutterSymbol(type: DiffLine['type']): string {
    return { add: '+', del: '−', ctx: ' ' }[type];
  }
}

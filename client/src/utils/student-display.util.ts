import { SubmissionSummary } from './api.types';

export const AVATAR_TINTS = [
  'oklch(0.6 0.12 265)',
  'oklch(0.6 0.12 155)',
  'oklch(0.62 0.14 55)',
  'oklch(0.58 0.14 25)',
  'oklch(0.55 0.12 315)',
  'oklch(0.6 0.12 195)',
  'oklch(0.55 0.13 85)',
  'oklch(0.58 0.14 355)',
];

export interface StudentInfo {
  name: string;
  email: string;
  initials: string;
  tint: number;
}

export function tintIndex(studentId: string): number {
  let sum = 0;
  for (let i = 0; i < studentId.length; i++) sum += studentId.charCodeAt(i);
  return sum % AVATAR_TINTS.length;
}

export function deriveStudent(summary: SubmissionSummary): StudentInfo {
  const email = summary.student_email ?? summary.student_id;
  const prefix = email.split('@')[0];
  const name = prefix
    .replace(/[._-]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
  const parts = name.trim().split(' ').filter(Boolean);
  const initials =
    parts.length >= 2
      ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
      : name.slice(0, 2).toUpperCase();
  return { name, email: summary.student_email ?? '', initials, tint: tintIndex(summary.student_id) };
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

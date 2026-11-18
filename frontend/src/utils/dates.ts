import { format, formatDistanceToNow, parseISO } from 'date-fns';

export function formatDate(iso: string): string {
  try {
    return format(parseISO(iso), 'dd MMM yyyy HH:mm') + ' UTC';
  } catch {
    return iso;
  }
}

export function formatRelative(iso: string): string {
  try {
    return formatDistanceToNow(parseISO(iso), { addSuffix: true });
  } catch {
    return iso;
  }
}

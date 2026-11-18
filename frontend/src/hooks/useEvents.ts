import { useQuery } from '@tanstack/react-query';
import { getEvents } from '../api/events';

export function useEvents(limit: number, offset: number) {
  return useQuery({
    queryKey: ['events', limit, offset],
    queryFn: () => getEvents(limit, offset),
  });
}

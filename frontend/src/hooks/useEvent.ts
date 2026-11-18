import { useQuery } from '@tanstack/react-query';
import { getEvent } from '../api/events';
import type { EventDetailResponse } from '../types';

export function useEvent(id: string) {
  return useQuery({
    queryKey: ['event', id],
    queryFn: () => getEvent(id),
    refetchInterval: (query) => {
      const data = query.state.data as EventDetailResponse | undefined;
      if (!data) return 5000;
      const status = data.event?.status;
      if (status === 'assessed' || status === 'failed') return false;
      return 5000;
    },
  });
}

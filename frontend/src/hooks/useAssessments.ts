import { useQuery } from '@tanstack/react-query';
import { getAssessments } from '../api/dashboard';

export function useAssessments(limit: number, offset: number, clientId?: string) {
  return useQuery({
    queryKey: ['assessments', limit, offset, clientId],
    queryFn: () => getAssessments(limit, offset, clientId),
  });
}

import { Card, Text, Title, Stack } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

interface HealthCheck {
  status: string;
  version: string;
  started_at: string;
  uptime_seconds: number;
}

async function fetchHealth(): Promise<HealthCheck> {
  const response = await fetch('/api/health');
  if (!response.ok) {
    throw new Error('Health check failed');
  }
  return response.json();
}

export function Dashboard() {
  const { data, error, isLoading } = useQuery<HealthCheck>({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  if (isLoading) {
    return <Text>Loading...</Text>;
  }

  if (error) {
    return <Text color="red">Error: {error.toString()}</Text>;
  }

  if (!data) {
    return <Text>No data available</Text>;
  }

  return (
    <Stack>
      <Title order={2}>System Status</Title>
      <Card shadow="sm" p="lg">
        <Stack>
          <Text>Status: {data.status}</Text>
          <Text>Version: {data.version}</Text>
          <Text>Started: {new Date(data.started_at).toLocaleString()}</Text>
          <Text>Uptime: {Math.floor(data.uptime_seconds / 60)} minutes</Text>
        </Stack>
      </Card>
    </Stack>
  );
} 
import { Box, Flex, Text } from '@chakra-ui/react';
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

export function StatusBar() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 5000,
  });

  const bgColor = 'white';
  const borderColor = 'gray.200';

  return (
    <Box
      position="fixed"
      bottom={0}
      left={0}
      right={0}
      bg={bgColor}
      borderTop="1px"
      borderColor={borderColor}
      p={2}
      zIndex={1000}
    >
      <Flex align="center" gap={2}>
        <Box
          w={2}
          h={2}
          borderRadius="full"
          bg={isLoading ? 'yellow.400' : isError ? 'red.500' : 'green.500'}
        />
        <Text color={isLoading ? 'gray.500' : isError ? 'red.500' : 'green.500'}>
          {isLoading
            ? 'Checking system status...'
            : isError
            ? 'Health check failed'
            : `System healthy (v${data?.version})`}
        </Text>
      </Flex>
    </Box>
  );
} 
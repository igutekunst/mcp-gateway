import { Box, Flex, Text } from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';
import { API_BASE_URL } from '../config';

interface HealthResponse {
  status: string;
}

async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`);
  if (!response.ok) {
    throw new Error('Health check failed');
  }
  return response.json();
}

export function StatusBar() {
  const { isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: checkHealth,
    refetchInterval: 5000,
  });

  return (
    <Box
      position="fixed"
      bottom={0}
      left={0}
      right={0}
      borderTop="1px"
      borderColor="gray.200"
      p={2}
      bg="white"
    >
      <Flex align="center" gap={2}>
        <Box
          w={2}
          h={2}
          borderRadius="full"
          bg={isLoading ? 'yellow.400' : isError ? 'red.500' : 'green.500'}
        />
        <Text color={isLoading ? 'gray.500' : isError ? 'red.500' : 'green.500'}>
          {isLoading ? 'Checking system status...'
            : isError ? 'Health check failed'
            : 'System healthy'}
        </Text>
      </Flex>
    </Box>
  );
} 
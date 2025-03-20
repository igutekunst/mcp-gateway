import { Box, Flex, Text } from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';

const fetchHealth = async () => {
  const response = await fetch('/api/health');
  if (!response.ok) {
    throw new Error('Health check failed');
  }
  return response.json();
};

export function StatusBar() {
  const { isError, isLoading } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
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
      p={3}
      bg="white"
      zIndex={1000}
    >
      <Flex justify="flex-end" align="center" gap={2}>
        <Text
          fontSize="sm"
          color={isLoading ? 'gray.500' : isError ? 'red.500' : 'green.500'}
        >
          {isLoading ? "Checking system status..." : isError ? "Health check failed" : "System healthy"}
        </Text>
        <Box
          w="8px"
          h="8px"
          borderRadius="full"
          bg={isLoading ? 'yellow.400' : isError ? 'red.500' : 'green.500'}
        />
      </Flex>
    </Box>
  );
} 
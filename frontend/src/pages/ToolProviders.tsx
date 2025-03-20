import { Box, Heading, Table, Thead, Tbody, Tr, Th, Td, Button, Badge, HStack, Text, Tooltip, Circle } from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';
import { format, formatDistanceToNow, parseISO } from 'date-fns';
import { listApps, listApiKeys, type App, type ApiKey } from '../api/auth';
import { useState, useEffect } from 'react';

interface ToolProviderWithKey extends App {
  apiKey?: ApiKey;
}

async function fetchToolProviders(): Promise<ToolProviderWithKey[]> {
  const [apps, keys] = await Promise.all([
    listApps('tool_provider'),
    listApiKeys(),
  ]);

  return apps.map(app => ({
    ...app,
    apiKey: keys.find(key => key.app_id === app.id),
  }));
}

function LastConnectedCell({ lastConnected }: { lastConnected: string | null }) {
  const [diffSeconds, setDiffSeconds] = useState<number>(0);

  useEffect(() => {
    if (!lastConnected) return;

    // Initial calculation
    const date = parseISO(lastConnected);
    const now = new Date();
    const nowUtc = new Date(now.getTime() + now.getTimezoneOffset() * 60000);
    setDiffSeconds(Math.floor((nowUtc.getTime() - date.getTime()) / 1000));

    // Update every 100ms for smooth countdown
    const interval = setInterval(() => {
      const now = new Date();
      const nowUtc = new Date(now.getTime() + now.getTimezoneOffset() * 60000);
      setDiffSeconds(Math.floor((nowUtc.getTime() - date.getTime()) / 1000));
    }, 100);

    return () => clearInterval(interval);
  }, [lastConnected]);

  if (!lastConnected) {
    return (
      <HStack spacing={2}>
        <Circle size="8px" bg="gray.500" />
        <Text color="gray.500">Never connected</Text>
      </HStack>
    );
  }

  const date = parseISO(lastConnected);
  let color = "green.500";
  let timeAgo = diffSeconds < 60 
    ? `${diffSeconds} seconds ago`
    : formatDistanceToNow(date, { addSuffix: true });
  let status = `last heartbeat ${timeAgo}`;
  
  if (diffSeconds > 15) {
    color = "yellow.500";
    status = `reconnecting - last heartbeat ${timeAgo}`;
  }
  if (diffSeconds > 30) {
    color = "red.500";
    status = `disconnected - last heartbeat ${timeAgo}`;
  }

  return (
    <Tooltip label={`${format(date, 'MMM d, yyyy HH:mm:ss')} UTC`}>
      <HStack spacing={2}>
        <Circle size="8px" bg={color} />
        <Text color={color}>
          {status}
        </Text>
      </HStack>
    </Tooltip>
  );
}

export function ToolProviders() {
  const { data: providers, isLoading, error } = useQuery({
    queryKey: ['toolProviders'],
    queryFn: fetchToolProviders,
    refetchInterval: 1000, // Refresh API data every second
  });

  if (isLoading) {
    return <Text>Loading...</Text>;
  }

  if (error) {
    return <Text color="red.500">Error loading tool providers</Text>;
  }

  return (
    <Box>
      <HStack justify="space-between" mb={6}>
        <Heading>Tool Providers</Heading>
        <Button colorScheme="blue">Register New Provider</Button>
      </HStack>

      <Table variant="simple">
        <Thead>
          <Tr>
            <Th>Name</Th>
            <Th>Description</Th>
            <Th>Status</Th>
            <Th>Created</Th>
            <Th>Last Connected</Th>
            <Th>API Key</Th>
            <Th>Actions</Th>
          </Tr>
        </Thead>
        <Tbody>
          {providers?.map((provider) => (
            <Tr key={provider.id}>
              <Td>{provider.name}</Td>
              <Td>{provider.description || '-'}</Td>
              <Td>
                <Badge
                  colorScheme={provider.is_active ? 'green' : 'gray'}
                >
                  {provider.is_active ? 'Active' : 'Inactive'}
                </Badge>
              </Td>
              <Td>{format(parseISO(provider.created_at), 'MMM d, yyyy')}</Td>
              <Td>
                <LastConnectedCell lastConnected={provider.last_connected} />
              </Td>
              <Td>
                {provider.apiKey ? (
                  <Badge colorScheme="green">Active</Badge>
                ) : (
                  <Badge colorScheme="yellow">No Key</Badge>
                )}
              </Td>
              <Td>
                <HStack spacing={2}>
                  <Button size="sm">Edit</Button>
                  <Button size="sm" colorScheme="red" variant="ghost">
                    Delete
                  </Button>
                </HStack>
              </Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  );
} 
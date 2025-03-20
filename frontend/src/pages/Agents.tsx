import { Box, Heading, Table, Thead, Tbody, Tr, Th, Td, Button, Badge, HStack } from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';

interface Agent {
  id: string;
  name: string;
  status: 'active' | 'inactive';
  lastSeen: string;
  apiKey: string;
}

// TODO: Replace with actual API call
async function fetchAgents(): Promise<Agent[]> {
  return [];
}

export function Agents() {
  const { data: agents } = useQuery({
    queryKey: ['agents'],
    queryFn: fetchAgents,
  });

  return (
    <Box>
      <HStack justify="space-between" mb={6}>
        <Heading>Agents</Heading>
        <Button colorScheme="blue">Register New Agent</Button>
      </HStack>

      <Table variant="simple">
        <Thead>
          <Tr>
            <Th>Name</Th>
            <Th>Status</Th>
            <Th>Last Seen</Th>
            <Th>API Key</Th>
            <Th>Actions</Th>
          </Tr>
        </Thead>
        <Tbody>
          {agents?.map((agent) => (
            <Tr key={agent.id}>
              <Td>{agent.name}</Td>
              <Td>
                <Badge
                  colorScheme={agent.status === 'active' ? 'green' : 'gray'}
                >
                  {agent.status}
                </Badge>
              </Td>
              <Td>{agent.lastSeen}</Td>
              <Td>
                <code>{agent.apiKey}</code>
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
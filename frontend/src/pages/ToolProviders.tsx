import { Box, Heading, Table, Thead, Tbody, Tr, Th, Td, Button, Badge, HStack } from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';

interface ToolProvider {
  id: string;
  name: string;
  status: 'active' | 'inactive';
  tools: string[];
  apiKey: string;
}

// TODO: Replace with actual API call
async function fetchToolProviders(): Promise<ToolProvider[]> {
  return [];
}

export function ToolProviders() {
  const { data: providers } = useQuery({
    queryKey: ['toolProviders'],
    queryFn: fetchToolProviders,
  });

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
            <Th>Status</Th>
            <Th>Tools</Th>
            <Th>API Key</Th>
            <Th>Actions</Th>
          </Tr>
        </Thead>
        <Tbody>
          {providers?.map((provider) => (
            <Tr key={provider.id}>
              <Td>{provider.name}</Td>
              <Td>
                <Badge
                  colorScheme={provider.status === 'active' ? 'green' : 'gray'}
                >
                  {provider.status}
                </Badge>
              </Td>
              <Td>{provider.tools.join(', ')}</Td>
              <Td>
                <code>{provider.apiKey}</code>
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
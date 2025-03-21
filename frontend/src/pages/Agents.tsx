import { Box, Heading, Table, Thead, Tbody, Tr, Th, Td, Button, Badge, HStack, Text, Tooltip, Tabs, TabList, TabPanels, TabPanel, Tab } from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';
import { format, formatDistanceToNow } from 'date-fns';
import { listApps, listApiKeys, type App, type ApiKey } from '../api/auth';
import { useState } from 'react';
import { LogViewer } from '../components/LogViewer';

interface AgentWithKey extends App {
  apiKey?: ApiKey;
}

async function fetchAgents(): Promise<AgentWithKey[]> {
  const [apps, keys] = await Promise.all([
    listApps('agent'),
    listApiKeys(),
  ]);

  return apps.map(app => ({
    ...app,
    apiKey: keys.find(key => key.app_id === app.id),
  }));
}

export function Agents() {
  const { data: agents, isLoading, error } = useQuery({
    queryKey: ['agents'],
    queryFn: fetchAgents,
  });

  const [selectedAgent, setSelectedAgent] = useState<AgentWithKey | null>(null);

  if (isLoading) {
    return <Text>Loading...</Text>;
  }

  if (error) {
    return <Text color="red.500">Error loading agents</Text>;
  }

  return (
    <Box>
      <HStack justify="space-between" mb={6}>
        <Heading>Agents</Heading>
        <Button colorScheme="blue">Register New Agent</Button>
      </HStack>

      <Tabs>
        <TabList>
          <Tab>Overview</Tab>
          {selectedAgent && (
            <Tab>Logs: {selectedAgent.name}</Tab>
          )}
        </TabList>

        <TabPanels>
          <TabPanel px={0}>
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
                {agents?.map((agent) => (
                  <Tr key={agent.id} onClick={() => setSelectedAgent(agent)} cursor="pointer" _hover={{ bg: 'gray.50' }}>
                    <Td>{agent.name}</Td>
                    <Td>{agent.description || '-'}</Td>
                    <Td>
                      <Badge
                        colorScheme={agent.is_active ? 'green' : 'gray'}
                      >
                        {agent.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </Td>
                    <Td>{format(new Date(agent.created_at), 'MMM d, yyyy')}</Td>
                    <Td>
                      {agent.last_connected ? (
                        <Tooltip label={format(new Date(agent.last_connected), 'MMM d, yyyy HH:mm:ss')}>
                          <Text>{formatDistanceToNow(new Date(agent.last_connected), { addSuffix: true })}</Text>
                        </Tooltip>
                      ) : (
                        'Never'
                      )}
                    </Td>
                    <Td>
                      {agent.apiKey ? (
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
          </TabPanel>

          {selectedAgent && (
            <TabPanel px={0}>
              <LogViewer 
                appId={selectedAgent.id} 
                refreshInterval={5000}
              />
            </TabPanel>
          )}
        </TabPanels>
      </Tabs>
    </Box>
  );
} 
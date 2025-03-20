import { Box, Heading, SimpleGrid, Stat, StatLabel, StatNumber, Card, CardBody } from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';

interface SystemStats {
  toolProviders: number;
  agents: number;
  activeConnections: number;
}

// TODO: Replace with actual API call
async function fetchSystemStats(): Promise<SystemStats> {
  return {
    toolProviders: 0,
    agents: 0,
    activeConnections: 0,
  };
}

export function Overview() {
  const { data: stats } = useQuery({
    queryKey: ['systemStats'],
    queryFn: fetchSystemStats,
    refetchInterval: 5000,
  });

  return (
    <Box>
      <Heading mb={6}>System Overview</Heading>
      
      <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
        <Card>
          <CardBody>
            <Stat>
              <StatLabel>Tool Providers</StatLabel>
              <StatNumber>{stats?.toolProviders ?? 0}</StatNumber>
            </Stat>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <Stat>
              <StatLabel>Agents</StatLabel>
              <StatNumber>{stats?.agents ?? 0}</StatNumber>
            </Stat>
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <Stat>
              <StatLabel>Active Connections</StatLabel>
              <StatNumber>{stats?.activeConnections ?? 0}</StatNumber>
            </Stat>
          </CardBody>
        </Card>
      </SimpleGrid>
    </Box>
  );
} 
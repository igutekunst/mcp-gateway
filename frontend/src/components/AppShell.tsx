import { Box, Flex, Text, Stack, Button } from '@chakra-ui/react';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { StatusBar } from './StatusBar';

interface NavButtonProps {
  to: string;
  children: React.ReactNode;
}

function NavButton({ to, children }: NavButtonProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const isActive = location.pathname === to || (to !== '/' && location.pathname.startsWith(to));

  return (
    <Button
      variant="ghost"
      w="full"
      justifyContent="flex-start"
      bg={isActive ? 'gray.100' : 'transparent'}
      onClick={() => navigate(to)}
      _hover={{
        bg: 'gray.50',
      }}
    >
      {children}
    </Button>
  );
}

export function AppShell() {
  return (
    <Flex h="100vh">
      <Box
        as="nav"
        w="240px"
        bg="white"
        borderRight="1px"
        borderColor="gray.200"
        p={4}
      >
        <Stack spacing={1}>
          <NavButton to="/">Overview</NavButton>
          <NavButton to="/tool-providers">Tool Providers</NavButton>
          <NavButton to="/agents">Agents</NavButton>
          <Box pt={4}>
            <Text fontSize="sm" color="gray.500" fontWeight="medium" mb={2}>
              System
            </Text>
            <Stack spacing={1}>
              <NavButton to="/monitoring">Monitoring</NavButton>
              <NavButton to="/debug">Debug</NavButton>
              <NavButton to="/settings">Settings</NavButton>
              <NavButton to="/help">Help</NavButton>
            </Stack>
          </Box>
        </Stack>
      </Box>

      <Flex flex={1} direction="column">
        <Box
          as="header"
          bg="white"
          borderBottom="1px"
          borderColor="gray.200"
          p={4}
        >
          <Text fontSize="xl" fontWeight="bold">
            MCP Gateway
          </Text>
        </Box>

        <Box flex={1} p={4} position="relative" bg="gray.50">
          <Outlet />
          <StatusBar />
        </Box>
      </Flex>
    </Flex>
  );
} 
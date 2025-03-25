import { Box, Flex, Text, Stack, Button, HStack, Divider, IconButton, Tooltip } from '@chakra-ui/react';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { StatusBar } from './StatusBar';
import { useAuth } from '../contexts/AuthContext';
import { FiLogOut } from 'react-icons/fi';

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
  const { logout } = useAuth();
  
  const handleLogout = async () => {
    await logout();
  };

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
          
          <Divider my={4} />
          
          <Button
            variant="ghost"
            w="full"
            justifyContent="flex-start"
            leftIcon={<FiLogOut />}
            onClick={handleLogout}
            colorScheme="red"
            size="sm"
          >
            Logout
          </Button>
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
          <Flex justify="space-between" align="center">
            <Text fontSize="xl" fontWeight="bold">
              MCP Gateway
            </Text>
            <Tooltip label="Logout">
              <IconButton
                icon={<FiLogOut />}
                aria-label="Logout"
                variant="ghost"
                onClick={handleLogout}
                size="sm"
              />
            </Tooltip>
          </Flex>
        </Box>

        <Box flex={1} p={4} position="relative" bg="gray.50">
          <Outlet />
          <StatusBar />
        </Box>
      </Flex>
    </Flex>
  );
} 
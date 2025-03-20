import { AppShell as MantineAppShell, Title, Box } from '@mantine/core';
import { Link } from 'react-router-dom';

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <MantineAppShell
      padding="md"
      navbar={{
        width: { base: 300 },
        breakpoint: 'sm',
      }}
      header={{
        height: 60,
      }}
    >
      <Box p="xs">
        <Title order={1}>MCP Gateway</Title>
      </Box>
      <Box p="xs">
        <Link to="/" style={{ textDecoration: 'none', color: 'inherit' }}>
          <Title order={3} mb="md">Dashboard</Title>
        </Link>
        <Link to="/apps" style={{ textDecoration: 'none', color: 'inherit' }}>
          <Title order={3} mb="md">Apps</Title>
        </Link>
        <Link to="/keys" style={{ textDecoration: 'none', color: 'inherit' }}>
          <Title order={3}>API Keys</Title>
        </Link>
      </Box>
      <Box p="md">
        {children}
      </Box>
    </MantineAppShell>
  );
} 
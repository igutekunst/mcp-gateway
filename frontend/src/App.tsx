import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { Dashboard } from './pages/Dashboard';
import { Apps } from './pages/Apps';
import { Keys } from './pages/Keys';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <MantineProvider>
        <Router>
          <AppShell>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/apps" element={<Apps />} />
              <Route path="/keys" element={<Keys />} />
            </Routes>
          </AppShell>
        </Router>
      </MantineProvider>
    </QueryClientProvider>
  );
}

export default App;

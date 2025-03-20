import { ChakraProvider } from '@chakra-ui/react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { AppShell } from './components/AppShell';
import { Overview } from './pages/Overview';
import { ToolProviders } from './pages/ToolProviders';
import { Agents } from './pages/Agents';

// Placeholder components for system pages
const Monitoring = () => <div>Monitoring</div>;
const Debug = () => <div>Debug</div>;
const Settings = () => <div>Settings</div>;
const Help = () => <div>Help</div>;

const queryClient = new QueryClient();

export function App() {
  return (
    <Router>
      <QueryClientProvider client={queryClient}>
        <ChakraProvider>
          <Routes>
            <Route path="/*" element={<AppShell />}>
              <Route index element={<Overview />} />
              <Route path="tool-providers" element={<ToolProviders />} />
              <Route path="agents" element={<Agents />} />
              <Route path="monitoring" element={<Monitoring />} />
              <Route path="debug" element={<Debug />} />
              <Route path="settings" element={<Settings />} />
              <Route path="help" element={<Help />} />
            </Route>
          </Routes>
        </ChakraProvider>
      </QueryClientProvider>
    </Router>
  );
}

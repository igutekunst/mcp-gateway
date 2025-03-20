import { ChakraProvider } from '@chakra-ui/react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { AppShell } from './components/AppShell';
import { Dashboard } from './pages/Dashboard';
import { Apps } from './pages/Apps';
import { Keys } from './pages/Keys';

const queryClient = new QueryClient();

export function App() {
  return (
    <Router>
      <QueryClientProvider client={queryClient}>
        <ChakraProvider>
          <Routes>
            <Route path="/*" element={<AppShell />}>
              <Route index element={<Dashboard />} />
              <Route path="apps" element={<Apps />} />
              <Route path="keys" element={<Keys />} />
            </Route>
          </Routes>
        </ChakraProvider>
      </QueryClientProvider>
    </Router>
  );
}

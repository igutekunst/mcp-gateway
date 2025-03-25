import React, { useState } from 'react';
import {
  Box,
  Button,
  Flex,
  FormControl,
  FormLabel,
  Input,
  VStack,
  Heading,
  Text,
  Alert,
  AlertIcon,
  Card,
  CardBody,
  CardHeader,
  FormErrorMessage,
  InputGroup,
  InputRightElement,
} from '@chakra-ui/react';
import { useAuth } from '../contexts/AuthContext';

export function Login() {
  const { login, isLoading, error } = useAuth();
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password.trim()) return;
    
    setIsSubmitting(true);
    try {
      await login(password);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleTogglePassword = () => {
    setShowPassword(!showPassword);
  };

  return (
    <Flex 
      minHeight="100vh" 
      width="100%" 
      align="center" 
      justify="center" 
      bg="gray.50"
      margin="0"
      padding="0"
    >
      <Box width="100%" maxWidth="400px" mx="auto" px={4}>
        <Card boxShadow="lg">
          <CardHeader pb={2}>
            <Heading size="lg" textAlign="center">MCP Gateway</Heading>
            <Text mt={2} color="gray.600" textAlign="center">Admin Login</Text>
          </CardHeader>
          <CardBody>
            <form onSubmit={handleSubmit}>
              <VStack spacing={4}>
                {error && (
                  <Alert status="error" borderRadius="md">
                    <AlertIcon />
                    {error}
                  </Alert>
                )}
                
                <FormControl isRequired isInvalid={!!error}>
                  <FormLabel>Admin Password</FormLabel>
                  <InputGroup>
                    <Input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your admin password"
                      autoFocus
                    />
                    <InputRightElement width="4.5rem">
                      <Button
                        h="1.75rem"
                        size="sm"
                        onClick={handleTogglePassword}
                      >
                        {showPassword ? 'Hide' : 'Show'}
                      </Button>
                    </InputRightElement>
                  </InputGroup>
                  {error && <FormErrorMessage>Invalid password</FormErrorMessage>}
                </FormControl>
                
                <Button
                  type="submit"
                  colorScheme="blue"
                  size="md"
                  width="full"
                  isLoading={isLoading || isSubmitting}
                  loadingText="Logging in"
                >
                  Login
                </Button>
              </VStack>
            </form>
          </CardBody>
        </Card>
      </Box>
    </Flex>
  );
} 
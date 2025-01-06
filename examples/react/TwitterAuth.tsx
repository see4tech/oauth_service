import React, { useState } from 'react';
import { Button } from '@mui/material';
import { TwitterPopupHandler } from './TwitterPopupHandler';

interface TwitterAuthProps {
  userId: string;
  apiKey: string;
}

export const TwitterAuth: React.FC<TwitterAuthProps> = ({ userId, apiKey }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // The frontend callback URL (where the popup will communicate with the parent window)
  const frontendCallbackUrl = `${window.location.origin}/auth/callback/twitter`;
  // The backend redirect URI (where Twitter will redirect to)
  const backendRedirectUri = `https://dukat.see4.tech/oauth/twitter/callback`;

  const handleOAuth2Login = async () => {
    try {
      setIsLoading(true);
      setError(null);
      console.log('Starting OAuth 2.0 flow...', {
        userId,
        redirectUri: backendRedirectUri,
        frontendCallback: frontendCallbackUrl
      });
      
      const response = await TwitterPopupHandler.initializeAuth(
        userId, 
        backendRedirectUri,
        false,
        frontendCallbackUrl,
        apiKey
      );
      
      // Open OAuth 2.0 window
      const authWindow = TwitterPopupHandler.openAuthWindow(
        response.authorization_url,
        false
      );
      
      console.log('OAuth 2.0 window opened with URL:', response.authorization_url);
    } catch (error) {
      console.error('Error starting OAuth 2.0 flow:', error);
      setError('Failed to start OAuth 2.0 flow. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleOAuth1Login = async () => {
    try {
      setIsLoading(true);
      setError(null);
      console.log('Starting OAuth 1.0a flow...', {
        userId,
        redirectUri: backendRedirectUri,
        frontendCallback: frontendCallbackUrl
      });
      
      const response = await TwitterPopupHandler.initializeAuth(
        userId,
        backendRedirectUri,
        true,
        frontendCallbackUrl,
        apiKey
      );
      
      // Open OAuth 1.0a window
      const authWindow = TwitterPopupHandler.openAuthWindow(
        response.authorization_url,
        true
      );
      
      console.log('OAuth 1.0a window opened with URL:', response.authorization_url);
    } catch (error) {
      console.error('Error starting OAuth 1.0a flow:', error);
      setError('Failed to start OAuth 1.0a flow. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  if (error) {
    return (
      <div style={{ color: 'red', textAlign: 'center', marginBottom: '16px' }}>
        {error}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', gap: '16px', flexDirection: 'column', alignItems: 'center' }}>
      <Button
        variant="contained"
        color="primary"
        onClick={handleOAuth2Login}
        disabled={isLoading}
      >
        {isLoading ? 'Connecting...' : 'Connect Twitter (OAuth 2.0)'}
      </Button>
      
      <Button
        variant="contained"
        color="secondary"
        onClick={handleOAuth1Login}
        disabled={isLoading}
      >
        {isLoading ? 'Connecting...' : 'Connect Twitter Media Upload (OAuth 1.0a)'}
      </Button>
    </div>
  );
};

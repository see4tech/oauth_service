import React from 'react';
import { Button } from '@mui/material';
import { TwitterPopupHandler } from './TwitterPopupHandler';

interface TwitterAuthProps {
  userId: string;
}

export const TwitterAuth: React.FC<TwitterAuthProps> = ({ userId }) => {
  // The frontend callback URL (where the popup will communicate with the parent window)
  const frontendCallbackUrl = `${window.location.origin}/auth/callback/twitter`;
  // The backend redirect URI (where Twitter will redirect to)
  const backendRedirectUri = `https://dukat.see4.tech/oauth/twitter/callback`;

  const handleOAuth2Login = async () => {
    try {
      console.log('Starting OAuth 2.0 flow...', {
        userId,
        redirectUri: backendRedirectUri,
        frontendCallback: frontendCallbackUrl
      });
      
      const response = await TwitterPopupHandler.initializeAuth(
        userId, 
        backendRedirectUri,
        false,
        frontendCallbackUrl
      );
      
      // Open OAuth 2.0 window
      const authWindow = window.open(
        response.authorization_url,
        'Twitter OAuth 2.0',
        'width=600,height=600'
      );
      
      console.log('OAuth 2.0 window opened with URL:', response.authorization_url);
    } catch (error) {
      console.error('Error starting OAuth 2.0 flow:', error);
    }
  };

  const handleOAuth1Login = async () => {
    try {
      console.log('Starting OAuth 1.0a flow...', {
        userId,
        redirectUri: backendRedirectUri,
        frontendCallback: frontendCallbackUrl
      });
      
      const response = await TwitterPopupHandler.initializeAuth(
        userId,
        backendRedirectUri,
        true,
        frontendCallbackUrl
      );
      
      // Open OAuth 1.0a window
      const authWindow = window.open(
        response.authorization_url,
        'Twitter OAuth 1.0a',
        'width=600,height=600'
      );
      
      console.log('OAuth 1.0a window opened with URL:', response.authorization_url);
    } catch (error) {
      console.error('Error starting OAuth 1.0a flow:', error);
    }
  };

  return (
    <div style={{ display: 'flex', gap: '16px', flexDirection: 'column', alignItems: 'center' }}>
      <Button
        variant="contained"
        color="primary"
        onClick={handleOAuth2Login}
      >
        Connect Twitter (OAuth 2.0)
      </Button>
      
      <Button
        variant="contained"
        color="secondary"
        onClick={handleOAuth1Login}
      >
        Connect Twitter Media Upload (OAuth 1.0a)
      </Button>
    </div>
  );
};

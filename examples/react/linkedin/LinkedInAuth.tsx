import { useState, useCallback, useEffect } from "react";
import { TwitterPopupHandler } from "./TwitterPopupHandler"; // Rename this to OAuthPopupHandler
import { LinkedInTokenExchange } from "./LinkedInTokenExchange";

const LinkedInAuth = ({ redirectUri, onSuccess, onError, isConnected = false }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [authWindow, setAuthWindow] = useState<Window | null>(null);
  const [localIsConnected, setLocalIsConnected] = useState(isConnected);

  useEffect(() => {
    const messageHandler = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) {
        console.warn('[Parent] Received message from unauthorized origin:', event.origin);
        return;
      }

      if (event.data.type === 'LINKEDIN_AUTH_CALLBACK') {
        // Close the window using our handler
        OAuthPopupHandler.closeAuthWindow(authWindow);
        setAuthWindow(null);
        setIsLoading(false);
        
        if (event.data.error) {
          onError?.(new Error(event.data.error));
        } else {
          onSuccess?.(event.data);
        }
      } else if (event.data.type === 'OAUTH_WINDOW_CLOSED') {
        // Handle manual window close
        setAuthWindow(null);
        setIsLoading(false);
      }
    };

    window.addEventListener('message', messageHandler);
    return () => {
      // Clean up: close window and remove listener
      OAuthPopupHandler.closeAuthWindow(authWindow);
      window.removeEventListener('message', messageHandler);
    };
  }, [authWindow, onSuccess, onError]);

  const handleLogin = async () => {
    if (isLoading) return;

    try {
      setIsLoading(true);
      const authData = await TwitterPopupHandler.initializeAuth(userId, redirectUri, false);
      
      if (authData.authorization_url) {
        const newWindow = TwitterPopupHandler.openAuthWindow(authData.authorization_url, false);
        if (!newWindow) {
          throw new Error('Could not open OAuth window');
        }
        setAuthWindow(newWindow);
      } else {
        throw new Error('No authorization URL received');
      }
    } catch (error) {
      console.error('[Parent] LinkedIn OAuth error:', error);
      onError(error as Error);
      setIsLoading(false);
    }
  };

  return (
    // ... rest of the component
  );
};

export default LinkedInAuth; 
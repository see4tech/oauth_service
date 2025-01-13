import { useState, useCallback, useRef, useEffect } from 'react';
import { TwitterPopupHandler } from '../TwitterPopupHandler';
import { TwitterTokenExchange } from '../TwitterTokenExchange';
import { toast } from "sonner";
import { validateConnection } from "@/utils/validateConnection";

export const useTwitterAuth = (
  redirectUri: string,
  onSuccess: (tokens: any) => void,
  onError: (error: Error) => void,
  isConnectedOAuth1 = false,
  isConnectedOAuth2 = false
) => {
  const [isLoading, setIsLoading] = useState(false);
  const [localIsConnectedOAuth1, setLocalIsConnectedOAuth1] = useState(isConnectedOAuth1);
  const [localIsConnectedOAuth2, setLocalIsConnectedOAuth2] = useState(isConnectedOAuth2);
  const [currentFlow, setCurrentFlow] = useState<'oauth1' | 'oauth2' | null>(null);
  const authWindow = useRef<Window | null>(null);
  const validationIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const pendingConnectionRef = useRef<boolean>(false);

  useEffect(() => {
    setLocalIsConnectedOAuth1(isConnectedOAuth1);
    setLocalIsConnectedOAuth2(isConnectedOAuth2);
  }, [isConnectedOAuth1, isConnectedOAuth2]);

  const clearValidationInterval = useCallback(() => {
    if (validationIntervalRef.current) {
      clearInterval(validationIntervalRef.current);
      validationIntervalRef.current = null;
    }
  }, []);

  const cleanup = useCallback(() => {
    clearValidationInterval();
    if (authWindow.current && !authWindow.current.closed) {
      authWindow.current.close();
    }
    authWindow.current = null;
    setIsLoading(false);
    setCurrentFlow(null);
  }, [clearValidationInterval]);

  useEffect(() => {
    const checkPopupAndUpdateStatus = setInterval(() => {
      if (authWindow.current?.closed && pendingConnectionRef.current) {
        console.log('[Twitter] Popup closed, checking final connection status');
        const userString = localStorage.getItem('user');
        if (userString) {
          const user = JSON.parse(userString);
          validateConnection(user.id.toString(), currentFlow === 'oauth1' ? 'twitter-oauth1' : 'twitter-oauth2')
            .then(isConnected => {
              if (isConnected) {
                if (currentFlow === 'oauth1') {
                  setLocalIsConnectedOAuth1(true);
                  const updatedUser = { ...user, twitter_oauth1_conectado: true };
                  localStorage.setItem('user', JSON.stringify(updatedUser));
                } else {
                  setLocalIsConnectedOAuth2(true);
                  const updatedUser = { ...user, twitter_oauth2_conectado: true };
                  localStorage.setItem('user', JSON.stringify(updatedUser));
                }
                toast.success(`Twitter ${currentFlow === 'oauth1' ? 'OAuth 1.0a' : 'OAuth 2.0'} connection confirmed`);
              }
              pendingConnectionRef.current = false;
              cleanup();
            });
        }
        clearInterval(checkPopupAndUpdateStatus);
      }
    }, 500);

    return () => clearInterval(checkPopupAndUpdateStatus);
  }, [currentFlow, cleanup]);

  const handleLogin = async (useOAuth1: boolean = false) => {
    const userString = localStorage.getItem('user');
    if (!userString) {
      console.error('[Twitter] No user found in localStorage');
      onError(new Error('No user found'));
      return;
    }

    const user = JSON.parse(userString);
    const userId = user.id;

    if (isLoading) return;

    try {
      setIsLoading(true);
      setCurrentFlow(useOAuth1 ? 'oauth1' : 'oauth2');
      pendingConnectionRef.current = false;
      console.log(`[Twitter] Initiating ${useOAuth1 ? 'OAuth 1.0a' : 'OAuth 2.0'} auth with user ID:`, userId);

      const authData = await TwitterPopupHandler.initializeAuth(Number(userId), redirectUri, useOAuth1);
      
      if (authData.authorization_url) {
        clearValidationInterval();
        
        const newWindow = TwitterPopupHandler.openAuthWindow(authData.authorization_url, useOAuth1);
        if (!newWindow) {
          throw new Error('Could not open OAuth window');
        }
        
        authWindow.current = newWindow;
        pendingConnectionRef.current = true;
      } else {
        throw new Error('No authorization URL received');
      }
    } catch (error) {
      console.error('[Twitter] Auth error:', error);
      onError(error as Error);
      cleanup();
    }
  };

  return {
    isLoading,
    localIsConnectedOAuth1,
    localIsConnectedOAuth2,
    handleLogin,
    currentFlow
  };
};
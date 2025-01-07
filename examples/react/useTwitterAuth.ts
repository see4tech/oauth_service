import { useState, useCallback } from 'react';
import { toast } from 'sonner';
import { TwitterPopupHandler } from '../TwitterPopupHandler';
import { TwitterTokenExchange } from '../TwitterTokenExchange';

export const useTwitterAuth = (
  redirectUri: string,
  onSuccess: (tokens: any) => void,
  onError: (error: Error) => void
) => {
  const [isLoading, setIsLoading] = useState(false);
  const [authWindow, setAuthWindow] = useState<Window | null>(null);
  const [oauth1Pending, setOauth1Pending] = useState(false);

  const closeAuthWindow = useCallback(async (window: Window | null) => {
    console.log('[Parent] Attempting to close auth window');
    if (!window || window.closed) {
      console.log('[Parent] Window already closed or null');
      return;
    }

    return new Promise<void>((resolve) => {
      const checkClosed = setInterval(() => {
        if (window.closed) {
          console.log('[Parent] Window confirmed closed');
          clearInterval(checkClosed);
          resolve();
        }
      }, 100);

      window.close();
      console.log('[Parent] Close command sent to window');

      // Fallback: resolve after 2 seconds even if window hasn't closed
      setTimeout(() => {
        clearInterval(checkClosed);
        if (!window.closed) {
          console.log('[Parent] Force closing window after timeout');
          window.close();
        }
        resolve();
      }, 2000);
    });
  }, []);

  const handleCallback = useCallback(async (
    code: string, 
    state: string, 
    isOAuth1: boolean = false,
    oauth1Verifier?: string
  ) => {
    try {
      setIsLoading(true);
      console.log('[Parent] Starting token exchange:', { 
        isOAuth1, 
        code: code.slice(0, 10) + '...', 
        hasVerifier: !!oauth1Verifier 
      });
      
      const tokens = await TwitterTokenExchange.exchangeCodeForToken(
        code, 
        state, 
        redirectUri, 
        isOAuth1, 
        oauth1Verifier
      );

      console.log('[Parent] Token exchange response:', {
        hasOAuth1Url: !!tokens.oauth1_url,
        tokenKeys: Object.keys(tokens)
      });
      
      if (!isOAuth1 && tokens.oauth1_url) {
        console.log('[Parent] Initiating OAuth 1.0a flow');
        setOauth1Pending(true);
        
        sessionStorage.setItem('twitter_oauth1_url', tokens.oauth1_url);
        
        // Close OAuth 2.0 window and wait for confirmation
        if (authWindow && !authWindow.closed) {
          console.log('[Parent] Closing OAuth 2.0 window before opening OAuth 1.0a');
          await closeAuthWindow(authWindow);
          setAuthWindow(null);
        }
        
        // Short delay to ensure clean window state
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // Open OAuth 1.0a window
        console.log('[Parent] Opening OAuth 1.0a window');
        const oauth1Window = TwitterPopupHandler.openAuthWindow(tokens.oauth1_url, true);
        if (oauth1Window) {
          setAuthWindow(oauth1Window);
          oauth1Window.focus();
        } else {
          throw new Error('Failed to open OAuth 1.0a window');
        }
        
        return;
      }
      
      if (isOAuth1 || !tokens.oauth1_url) {
        console.log('[Parent] Auth flow complete, calling onSuccess');
        onSuccess(tokens);
        
        if (authWindow && !authWindow.closed) {
          await closeAuthWindow(authWindow);
          setAuthWindow(null);
        }
      }
    } catch (error) {
      console.error('[Parent] Token exchange error:', error);
      onError(error as Error);
      
      if (isOAuth1) {
        const storedOAuth1Url = sessionStorage.getItem('twitter_oauth1_url');
        if (storedOAuth1Url) {
          toast.error('OAuth 1.0a failed. Click "Reconnect X" to try again.');
        }
      }
    } finally {
      setIsLoading(false);
      if (isOAuth1) {
        setOauth1Pending(false);
      }
    }
  }, [authWindow, closeAuthWindow, onSuccess, onError, redirectUri]);

  const handleLogin = async () => {
    const userString = localStorage.getItem('user');
    if (!userString) {
      const error = new Error('No user found');
      onError(error);
      toast.error(error.message);
      return;
    }

    const user = JSON.parse(userString);
    const userId = user?.id?.toString();

    if (!userId) {
      const error = new Error('No user ID found');
      onError(error);
      toast.error(error.message);
      return;
    }

    try {
      setIsLoading(true);
      const twitterCallbackUrl = redirectUri.replace('/linkedin/', '/twitter/');
      const authData = await TwitterPopupHandler.initializeAuth(userId, twitterCallbackUrl);
      console.log('[Parent] Auth initialization successful:', authData);
      
      if (authData.authorization_url) {
        sessionStorage.setItem('twitter_auth_state', authData.state);
        
        if (authData.additional_params?.oauth1_url) {
          sessionStorage.setItem('twitter_oauth1_url', authData.additional_params.oauth1_url);
        }
        
        const newWindow = TwitterPopupHandler.openAuthWindow(authData.authorization_url, false);
        if (!newWindow) {
          throw new Error('Could not open authentication window');
        }
        setAuthWindow(newWindow);
        newWindow.focus();
      } else {
        throw new Error('No authorization URL received');
      }
    } catch (error) {
      console.error('[Parent] Twitter auth error:', error);
      onError(error as Error);
      toast.error((error as Error).message);
      setIsLoading(false);
    }
  };

  return {
    isLoading,
    oauth1Pending,
    handleLogin,
    handleCallback
  };
};
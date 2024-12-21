import { Button } from "@/components/ui/button";
import { Loader2, Twitter } from "lucide-react";
import { useState, useCallback, useEffect } from "react";
import { toast } from "sonner";
import { TwitterPopupHandler } from "./TwitterPopupHandler";
import { TwitterTokenExchange } from "./TwitterTokenExchange";

interface TwitterAuthProps {
  redirectUri: string;
  onSuccess: (tokens: any) => void;
  onError: (error: Error) => void;
}

const TwitterAuth: React.FC<TwitterAuthProps> = ({
  redirectUri,
  onSuccess,
  onError
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [authWindow, setAuthWindow] = useState<Window | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Check authentication status on mount and after token changes
  useEffect(() => {
    const checkAuth = async () => {
      const isAuthed = TwitterTokenExchange.isAuthenticated();
      setIsAuthenticated(isAuthed);
      
      if (isAuthed) {
        // Try to get a valid token (this will refresh if needed)
        const token = await TwitterTokenExchange.getValidToken();
        if (!token) {
          // Token refresh failed or no refresh token available
          setIsAuthenticated(false);
          TwitterTokenExchange.clearTokens();
        }
      }
    };

    checkAuth();
  }, []);

  const handleCallback = useCallback(async (code: string, state: string, isOAuth1: boolean = false, oauth1Verifier?: string) => {
    try {
      setIsLoading(true);
      console.log('Starting Twitter authorization process...', { isOAuth1 });
      
      const result = await TwitterTokenExchange.exchangeCodeForToken(
        code, 
        state, 
        redirectUri,
        isOAuth1,
        oauth1Verifier
      );
      console.log('Twitter authorization successful');
      
      setIsAuthenticated(true);
      onSuccess(result);

      if (authWindow && !authWindow.closed) {
        console.log('Closing Twitter auth window');
        authWindow.close();
        setAuthWindow(null);
      }

      toast.success('Successfully connected your Twitter account');
    } catch (error) {
      console.error('Twitter authorization error:', error);
      setIsAuthenticated(false);
      TwitterTokenExchange.clearTokens();
      onError(error as Error);
      toast.error(getErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, [onSuccess, onError, redirectUri, authWindow]);

  useEffect(() => {
    const messageHandler = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) {
        console.warn('Received message from unauthorized origin:', event.origin);
        return;
      }

      const { type, code, state, oauth_verifier, error, isOAuth1 } = event.data;
      console.log('Received auth callback:', { 
        type, 
        code: code?.slice(0, 5) + '...', 
        state: state?.slice(0, 5) + '...',
        isOAuth1
      });
      
      if (type === 'TWITTER_AUTH_CALLBACK') {
        if (error) {
          const errorMessage = error === 'access_denied' 
            ? 'Twitter authorization was cancelled'
            : `Twitter authorization failed: ${error}`;
          
          onError(new Error(errorMessage));
          toast.error(errorMessage);
          
          if (authWindow && !authWindow.closed) {
            authWindow.close();
            setAuthWindow(null);
          }
        } else if ((code && state) || oauth_verifier) {
          handleCallback(code, state, isOAuth1, oauth_verifier);
        }
      }
    };

    window.addEventListener('message', messageHandler);
    return () => window.removeEventListener('message', messageHandler);
  }, [handleCallback, onError, authWindow]);

  useEffect(() => {
    if (!authWindow) return;

    const checkWindow = setInterval(() => {
      if (authWindow.closed) {
        console.log('Auth window was closed by user');
        setAuthWindow(null);
        setIsLoading(false);
        clearInterval(checkWindow);
        toast.error('Authentication was cancelled');
      }
    }, 500);

    return () => clearInterval(checkWindow);
  }, [authWindow]);

  const getErrorMessage = (error: any): string => {
    const message = error?.message || 'An unknown error occurred';
    
    if (message.includes('popup')) {
      return 'Please allow popups to connect your Twitter account';
    }
    if (message.includes('network')) {
      return 'Network error. Please check your connection and try again';
    }
    if (message.includes('timeout')) {
      return 'The request timed out. Please try again';
    }
    
    return message;
  };

  const handleDisconnect = async () => {
    try {
      setIsLoading(true);
      TwitterTokenExchange.clearTokens();
      setIsAuthenticated(false);
      toast.success('Successfully disconnected Twitter account');
    } catch (error) {
      console.error('Error disconnecting Twitter:', error);
      toast.error('Failed to disconnect Twitter account');
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogin = async () => {
    const userString = localStorage.getItem('user');
    if (!userString) {
      toast.error('Please log in to connect your Twitter account');
      return;
    }

    const user = JSON.parse(userString);
    const userId = user?.id?.toString();

    if (!userId) {
      toast.error('User ID not found. Please log in again');
      return;
    }

    try {
      setIsLoading(true);
      console.log('Initializing Twitter authorization...');
      
      const authData = await TwitterPopupHandler.initializeAuth(userId, redirectUri);
      console.log('Authorization URLs received');
      
      // Store state for OAuth 2.0
      if (authData.state) {
        sessionStorage.setItem('twitter_auth_state', authData.state);
      }

      // First complete OAuth 2.0 flow
      const oauth2Url = authData.authorization_url;
      if (oauth2Url) {
        const oauth2Window = TwitterPopupHandler.openAuthWindow(oauth2Url, false);
        if (!oauth2Window) {
          throw new Error('popup_blocked');
        }
        oauth2Window.focus();
        
        // Wait for OAuth 2.0 to complete
        await new Promise<void>((resolve, reject) => {
          const messageHandler = (event: MessageEvent) => {
            if (event.origin !== window.location.origin) return;
            if (event.data.type === 'TWITTER_AUTH_CALLBACK') {
              window.removeEventListener('message', messageHandler);
              if (event.data.error) {
                reject(new Error(event.data.error));
              } else {
                resolve();
              }
            }
          };
          window.addEventListener('message', messageHandler);
        });

        // Then complete OAuth 1.0a flow if available
        const oauth1Url = authData.additional_params?.oauth1_url;
        if (oauth1Url) {
          const oauth1Window = TwitterPopupHandler.openAuthWindow(oauth1Url, true);
          if (!oauth1Window) {
            throw new Error('popup_blocked');
          }
          oauth1Window.focus();
        }
      } else {
        throw new Error('No authorization URL received from server');
      }
    } catch (error: any) {
      console.error('Twitter auth initialization error:', error);
      onError(error as Error);
      toast.error(getErrorMessage(error));
      setIsLoading(false);
    }
  };

  return (
    <Button
      onClick={isAuthenticated ? handleDisconnect : handleLogin}
      disabled={isLoading}
      className="w-full"
      variant={isAuthenticated ? "destructive" : "outline"}
    >
      {isLoading ? (
        <>
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          {isAuthenticated ? 'Disconnecting...' : 'Connecting to Twitter...'}
        </>
      ) : (
        <>
          <Twitter className="mr-2 h-4 w-4" />
          {isAuthenticated ? 'Disconnect Twitter' : 'Connect Twitter'}
        </>
      )}
    </Button>
  );
};

export default TwitterAuth;

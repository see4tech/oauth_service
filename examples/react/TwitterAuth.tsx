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
      
      onSuccess(result);

      if (authWindow && !authWindow.closed) {
        console.log('Closing Twitter auth window');
        authWindow.close();
        setAuthWindow(null);
      }

      toast.success('Successfully connected your Twitter account');
    } catch (error) {
      console.error('Twitter authorization error:', error);
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

      // Open OAuth 2.0 window by default, fallback to OAuth 1.0a if needed
      const authUrl = authData.authorization_url || authData.additional_params?.oauth1_url;
      const isOAuth1 = !authData.authorization_url;
      
      if (authUrl) {
        const newWindow = TwitterPopupHandler.openAuthWindow(authUrl, isOAuth1);
        if (!newWindow) {
          throw new Error('popup_blocked');
        }
        setAuthWindow(newWindow);
        
        // Focus the popup window
        newWindow.focus();
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
      onClick={handleLogin}
      disabled={isLoading}
      className="w-full"
      variant="outline"
    >
      {isLoading ? (
        <>
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Connecting to Twitter...
        </>
      ) : (
        <>
          <Twitter className="mr-2 h-4 w-4" />
          Connect Twitter
        </>
      )}
    </Button>
  );
};

export default TwitterAuth;

import { Button } from "@/components/ui/button";
import { Loader2, Instagram } from "lucide-react";
import { useState, useCallback, useEffect } from "react";
import { toast } from "sonner";
import { InstagramPopupHandler } from "./InstagramPopupHandler";
import { InstagramTokenExchange } from "./InstagramTokenExchange";

interface InstagramAuthProps {
  redirectUri: string;
  onSuccess: (tokens: any) => void;
  onError: (error: Error) => void;
}

const InstagramAuth: React.FC<InstagramAuthProps> = ({
  redirectUri,
  onSuccess,
  onError
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [authWindow, setAuthWindow] = useState<Window | null>(null);

  const handleCallback = useCallback(async (code: string, state: string) => {
    try {
      setIsLoading(true);
      console.log('Starting Instagram authorization process...');
      
      const result = await InstagramTokenExchange.exchangeCodeForToken(code, state, redirectUri);
      console.log('Instagram authorization successful');
      
      onSuccess(result);

      if (authWindow && !authWindow.closed) {
        console.log('Closing Instagram auth window');
        authWindow.close();
        setAuthWindow(null);
      }

      toast.success('Successfully connected your Instagram account');
    } catch (error) {
      console.error('Instagram authorization error:', error);
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

      const { type, code, state, error } = event.data;
      console.log('Received auth callback:', { type, code: code?.slice(0, 5) + '...', state: state?.slice(0, 5) + '...' });
      
      if (type === 'INSTAGRAM_AUTH_CALLBACK') {
        if (error) {
          const errorMessage = error === 'access_denied' 
            ? 'Instagram authorization was cancelled'
            : `Instagram authorization failed: ${error}`;
          
          onError(new Error(errorMessage));
          toast.error(errorMessage);
          
          if (authWindow && !authWindow.closed) {
            authWindow.close();
            setAuthWindow(null);
          }
        } else if (code && state) {
          handleCallback(code, state);
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
      return 'Please allow popups to connect your Instagram account';
    }
    if (message.includes('network')) {
      return 'Network error. Please check your connection and try again';
    }
    if (message.includes('timeout')) {
      return 'The request timed out. Please try again';
    }
    if (message.includes('business')) {
      return 'This Instagram account needs to be a Business or Creator account';
    }
    
    return message;
  };

  const handleLogin = async () => {
    const userString = localStorage.getItem('user');
    if (!userString) {
      toast.error('Please log in to connect your Instagram account');
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
      console.log('Initializing Instagram authorization...');
      
      const authData = await InstagramPopupHandler.initializeAuth(userId, redirectUri);
      console.log('Authorization URL received');
      
      if (authData.authorization_url) {
        sessionStorage.setItem('instagram_auth_state', authData.state);
        
        const newWindow = InstagramPopupHandler.openAuthWindow(authData.authorization_url);
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
      console.error('Instagram auth initialization error:', error);
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
          Connecting to Instagram...
        </>
      ) : (
        <>
          <Instagram className="mr-2 h-4 w-4" />
          Connect Instagram
        </>
      )}
    </Button>
  );
};

export default InstagramAuth;

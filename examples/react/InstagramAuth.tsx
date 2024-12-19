import { Button } from "@/components/ui/button";
import { Loader2, Instagram } from "lucide-react";
import { useState, useCallback, useEffect } from "react";
import { toast } from "sonner";

interface InstagramAuthProps {
  redirectUri: string;
  onSuccess: (tokens: any) => void;
  onError: (error: Error) => void;
}

class InstagramAuthHandler {
  static async initializeAuth(userId: string, redirectUri: string): Promise<any> {
    const response = await fetch('http://localhost:8000/oauth/instagram/init', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: userId,
        redirect_uri: redirectUri,
        frontend_callback_url: `${window.location.origin}/oauth/instagram/callback`
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || 'Failed to initialize Instagram auth');
    }

    return response.json();
  }

  static async exchangeCodeForToken(code: string, state: string, redirectUri: string): Promise<any> {
    console.log('Exchanging code for token:', { code, state });
    
    const response = await fetch('http://localhost:8000/oauth/instagram/token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        code,
        state,
        redirect_uri: redirectUri
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      console.error('Token exchange error:', error);
      throw new Error(error.message || 'Failed to exchange code for token');
    }

    const data = await response.json();
    console.log('Token exchange successful:', data);
    return data;
  }

  static openAuthWindow(url: string): Window | null {
    const width = 600;
    const height = 700;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;

    return window.open(
      url,
      'Instagram Auth',
      `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no,location=no`
    );
  }
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
      
      // Verify state matches what we stored
      const storedState = sessionStorage.getItem('instagram_auth_state');
      if (state !== storedState) {
        throw new Error('Security validation failed. Please try again.');
      }

      const result = await InstagramAuthHandler.exchangeCodeForToken(code, state, redirectUri);
      console.log('Instagram authorization successful');

      // Clear stored state
      sessionStorage.removeItem('instagram_auth_state');
      
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
      
      const authData = await InstagramAuthHandler.initializeAuth(userId, redirectUri);
      console.log('Authorization URL received');
      
      if (authData.authorization_url) {
        sessionStorage.setItem('instagram_auth_state', authData.state);
        
        const newWindow = InstagramAuthHandler.openAuthWindow(authData.authorization_url);
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

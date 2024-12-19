import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { useState, useCallback, useEffect } from "react";
import { toast } from "sonner";
import { LinkedInPopupHandler } from "./LinkedInPopupHandler";
import { LinkedInTokenExchange } from "./LinkedInTokenExchange";

const LinkedInAuth = ({ redirectUri, onSuccess, onError }: {
  redirectUri: string;
  onSuccess: (tokens: any) => void;
  onError: (error: Error) => void;
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [authWindow, setAuthWindow] = useState<Window | null>(null);

  const handleCallback = useCallback(async (code: string, state: string) => {
    try {
      setIsLoading(true);
      console.log('Starting token exchange with code:', code);
      
      const tokens = await LinkedInTokenExchange.exchangeCodeForToken(code, state, redirectUri);
      console.log('LinkedIn tokens received:', tokens);
      
      onSuccess(tokens);

      if (authWindow && !authWindow.closed) {
        console.log('Closing auth window');
        authWindow.close();
        setAuthWindow(null);
      }
    } catch (error) {
      console.error('LinkedIn token exchange error:', error);
      onError(error as Error);
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
      console.log('Received postMessage:', event.data);
      
      if (type === 'LINKEDIN_AUTH_CALLBACK') {
        if (error) {
          onError(new Error(error));
          toast.error(error);
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
      }
    }, 500);

    return () => clearInterval(checkWindow);
  }, [authWindow]);

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
      const authData = await LinkedInPopupHandler.initializeAuth(userId, redirectUri);
      console.log('Auth initialization successful:', authData);
      
      if (authData.authorization_url) {
        sessionStorage.setItem('linkedin_auth_state', authData.state);
        const newWindow = LinkedInPopupHandler.openAuthWindow(authData.authorization_url);
        if (!newWindow) {
          throw new Error('Could not open authentication window');
        }
        setAuthWindow(newWindow);
      } else {
        throw new Error('No authorization URL received');
      }
    } catch (error) {
      console.error('LinkedIn auth error:', error);
      onError(error as Error);
      toast.error((error as Error).message);
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
          Conectando...
        </>
      ) : (
        'Conectar LinkedIn'
      )}
    </Button>
  );
};

export default LinkedInAuth;
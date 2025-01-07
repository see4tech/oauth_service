import { useState, useCallback, useEffect, useRef } from "react";
import { LinkedInPopupHandler } from "./LinkedInPopupHandler";
import { LinkedInTokenExchange } from "./LinkedInTokenExchange";
import { toast } from "sonner";

interface LinkedInAuthProps {
  redirectUri: string;
  onSuccess: (tokens: any) => void;
  onError?: (error: Error) => void;
  isConnected?: boolean;
}

const LinkedInAuth = ({ redirectUri, onSuccess, onError, isConnected = false }: LinkedInAuthProps) => {
  const [isLoading, setIsLoading] = useState(false);
  const [localIsConnected, setLocalIsConnected] = useState(isConnected);
  const authWindowRef = useRef<Window | null>(null);
  const checkWindowIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    setLocalIsConnected(isConnected);
  }, [isConnected]);

  const clearWindowCheck = () => {
    if (checkWindowIntervalRef.current) {
      window.clearInterval(checkWindowIntervalRef.current);
      checkWindowIntervalRef.current = null;
    }
  };

  const cleanup = useCallback(() => {
    clearWindowCheck();
    LinkedInPopupHandler.closeAuthWindow(authWindowRef.current);
    authWindowRef.current = null;
    setIsLoading(false);
  }, []);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) {
        console.warn('Received message from unauthorized origin:', event.origin);
        return;
      }

      if (event.data?.type === 'LINKEDIN_AUTH_CALLBACK') {
        console.log('Received LinkedIn callback:', event.data);
        
        if (event.data.success) {
          console.log('LinkedIn auth successful');
          setLocalIsConnected(true);
          onSuccess(event.data);
          toast.success('LinkedIn authorization successful');
        } else if (event.data.error) {
          console.error('LinkedIn auth error:', event.data.error);
          onError?.(new Error(event.data.error));
          toast.error('LinkedIn authorization failed');
        }
        
        cleanup();
      }
    };

    window.addEventListener('message', handleMessage);
    return () => {
      window.removeEventListener('message', handleMessage);
      cleanup();
    };
  }, [onSuccess, onError, cleanup]);

  const handleLogin = async () => {
    const userString = localStorage.getItem('user');
    if (!userString) {
      console.error('No user found in localStorage');
      onError?.(new Error('No user found'));
      return;
    }

    const user = JSON.parse(userString);
    const userId = user.id;

    if (isLoading) return;

    try {
      setIsLoading(true);
      console.log('Initiating LinkedIn auth with user ID:', userId);

      const authData = await LinkedInPopupHandler.initializeAuth(userId, redirectUri);
      
      if (authData.authorization_url) {
        // Close any existing window
        cleanup();
        
        // Open new window
        const newWindow = LinkedInPopupHandler.openAuthWindow(authData.authorization_url);
        if (!newWindow) {
          throw new Error('Could not open OAuth window');
        }
        
        authWindowRef.current = newWindow;
        
        // Start checking if window is closed
        checkWindowIntervalRef.current = window.setInterval(() => {
          if (authWindowRef.current?.closed) {
            cleanup();
          }
        }, 1000);
      } else {
        throw new Error('No authorization URL received');
      }
    } catch (error) {
      console.error('LinkedIn auth error:', error);
      onError?.(error as Error);
      cleanup();
    }
  };

  return (
    <button
      onClick={handleLogin}
      disabled={isLoading}
      className={`w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white 
        ${isLoading ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'}
        ${localIsConnected ? 'bg-green-600 hover:bg-green-700' : ''}`}
    >
      {isLoading ? 'Conectando...' : (localIsConnected ? 'Reconectar LinkedIn' : 'Conectar LinkedIn')}
    </button>
  );
};

export default LinkedInAuth;
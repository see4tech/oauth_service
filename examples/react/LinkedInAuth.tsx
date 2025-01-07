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

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      console.log('Received message:', event.data);
      
      if (event.data?.type === 'LINKEDIN_AUTH_CALLBACK') {
        // Always try to close the window
        if (authWindowRef.current) {
          authWindowRef.current.close();
          authWindowRef.current = null;
        }
        
        setIsLoading(false);

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
      }
    };

    window.addEventListener('message', handleMessage);
    return () => {
      window.removeEventListener('message', handleMessage);
      // Cleanup on unmount
      if (authWindowRef.current) {
        authWindowRef.current.close();
        authWindowRef.current = null;
      }
    };
  }, [onSuccess, onError]);

  const handleLogin = async () => {
    try {
      const userString = localStorage.getItem('user');
      if (!userString) {
        throw new Error('No user found');
      }

      const user = JSON.parse(userString);
      const userId = user.id;

      if (isLoading) return;
      setIsLoading(true);

      const authData = await LinkedInPopupHandler.initializeAuth(userId, redirectUri);
      
      if (!authData.authorization_url) {
        throw new Error('No authorization URL received');
      }

      // Close any existing window
      if (authWindowRef.current) {
        authWindowRef.current.close();
      }

      // Open new window
      const newWindow = window.open(
        authData.authorization_url,
        'LinkedIn Auth',
        'width=600,height=600'
      );

      if (!newWindow) {
        throw new Error('Could not open OAuth window');
      }

      authWindowRef.current = newWindow;

      // Check if window is closed manually
      const checkWindow = setInterval(() => {
        if (newWindow.closed) {
          clearInterval(checkWindow);
          setIsLoading(false);
          authWindowRef.current = null;
        }
      }, 1000);

    } catch (error) {
      console.error('LinkedIn auth error:', error);
      onError?.(error as Error);
      setIsLoading(false);
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
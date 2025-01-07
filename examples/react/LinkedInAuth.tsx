import { useState, useCallback, useEffect } from "react";
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
  const [authWindow, setAuthWindow] = useState<Window | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [localIsConnected, setLocalIsConnected] = useState(isConnected);
  const [authCompleted, setAuthCompleted] = useState(false);

  useEffect(() => {
    setLocalIsConnected(isConnected);
  }, [isConnected]);

  useEffect(() => {
    const messageHandler = async (event: MessageEvent) => {
      if (event.origin !== window.location.origin) {
        console.warn('[Parent] Received message from unauthorized origin:', event.origin);
        return;
      }

      console.log('Received message:', event.data);

      if (event.data.type === 'LINKEDIN_AUTH_CALLBACK') {
        // Close the window first
        if (authWindow && !authWindow.closed) {
          console.log('Closing auth window');
          authWindow.close();
        }
        setAuthWindow(null);
        setIsLoading(false);

        if (event.data.success && event.data.platform === 'linkedin') {
          console.log('LinkedIn auth successful');
          setAuthCompleted(true);
          setLocalIsConnected(true);
          onSuccess(event.data);
          toast.success('LinkedIn authorization successful');
        } else if (event.data.error) {
          console.error('LinkedIn auth error:', event.data.error);
          onError?.(new Error(event.data.error));
          toast.error('LinkedIn authorization failed');
        }
      } else if (event.data.type === 'OAUTH_WINDOW_CLOSED') {
        // Handle manual window close
        setAuthWindow(null);
        setIsLoading(false);
        if (!authCompleted) {
          console.log('Authentication window was closed by user');
        }
      }
    };

    window.addEventListener('message', messageHandler);
    return () => {
      window.removeEventListener('message', messageHandler);
      if (authWindow && !authWindow.closed) {
        console.log('Cleaning up auth window');
        authWindow.close();
      }
    };
  }, [authWindow, onSuccess, onError, authCompleted]);

  useEffect(() => {
    if (!authCompleted || countdown === null) return;
    
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
    
    if (countdown === 0 && authWindow) {
      console.log('Countdown finished, closing window');
      authWindow.close();
      setAuthWindow(null);
      setIsLoading(false);
      setCountdown(null);
      setAuthCompleted(false);
    }
  }, [countdown, authWindow, authCompleted]);

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
      console.log('Initiating LinkedIn auth with user ID:', userId);
      setIsLoading(true);

      const authData = await LinkedInPopupHandler.initializeAuth(userId, redirectUri);
      console.log('LinkedIn auth response:', authData);
      
      if (authData.authorization_url) {
        console.log('Auth initialization successful:', authData);
        
        const newWindow = LinkedInPopupHandler.openAuthWindow(authData.authorization_url);
        if (!newWindow) {
          throw new Error('Could not open OAuth window');
        }
        setAuthWindow(newWindow);
      } else {
        throw new Error('No authorization URL received');
      }
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
      {isLoading ? (
        <>
          <span className="mr-2">Conectando...</span>
          {countdown !== null && <span>({countdown}s)</span>}
        </>
      ) : (
        <>
          {localIsConnected ? 'Reconectar LinkedIn' : 'Conectar LinkedIn'}
        </>
      )}
    </button>
  );
};

export default LinkedInAuth;

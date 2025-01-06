import { Button } from "@/components/ui/button";
import { Loader2, Twitter } from "lucide-react";
import { useState, useCallback, useEffect } from "react";
import { toast } from "sonner";
import { TwitterPopupHandler } from "./TwitterPopupHandler";
import { TwitterTokenExchange } from "./TwitterTokenExchange";

const TwitterAuth = ({ redirectUri, onSuccess, onError, isConnected = false }: {
  redirectUri: string;
  onSuccess: (tokens: any) => void;
  onError: (error: Error) => void;
  isConnected?: boolean;
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [authWindow, setAuthWindow] = useState<Window | null>(null);
  const [localIsConnected, setLocalIsConnected] = useState(isConnected);
  const [oauth1Pending, setOauth1Pending] = useState(false);
  const [currentFlow, setCurrentFlow] = useState<'oauth1' | 'oauth2' | null>(null);

  useEffect(() => {
    setLocalIsConnected(isConnected);
  }, [isConnected]);

  const handleCallback = useCallback(async (code: string, state: string, isOAuth1: boolean = false, oauth1Verifier?: string) => {
    if (currentFlow !== (isOAuth1 ? 'oauth1' : 'oauth2')) {
      console.log('[Parent] Ignoring callback for different flow type');
      return;
    }

    try {
      setIsLoading(true);
      console.log('[Parent] Starting token exchange:', { 
        isOAuth1, 
        code: code.slice(0, 10) + '...', 
        hasVerifier: !!oauth1Verifier,
        currentFlow
      });
      
      const tokens = await TwitterTokenExchange.exchangeCodeForToken(code, state, redirectUri, isOAuth1, oauth1Verifier);
      console.log('[Parent] Twitter tokens received:', { 
        type: isOAuth1 ? 'OAuth1.0a' : 'OAuth2.0', 
        tokenKeys: Object.keys(tokens)
      });
      
      onSuccess(tokens);
      setLocalIsConnected(true);
      
      if (authWindow && !authWindow.closed) {
        try {
          authWindow.postMessage({ type: 'CLOSE_OAUTH_WINDOW' }, window.location.origin);
        } catch (error) {
          console.error('[Parent] Error posting close message:', error);
          if (!authWindow.closed) {
            authWindow.close();
          }
        }
      }
    } catch (error) {
      console.error('[Parent] Twitter token exchange error:', error);
      onError(error as Error);
      toast.error((error as Error).message);
    } finally {
      setIsLoading(false);
      if (isOAuth1) {
        setOauth1Pending(false);
      }
      setCurrentFlow(null);
    }
  }, [onSuccess, onError, redirectUri, authWindow, currentFlow]);

  useEffect(() => {
    const messageHandler = (event: MessageEvent) => {
        if (event.origin !== window.location.origin) {
            console.warn('[Parent] Received message from unauthorized origin:', event.origin);
            return;
        }

        if (event.data.type === 'TWITTER_AUTH_CALLBACK') {
            // Close the window using our handler
            TwitterPopupHandler.closeAuthWindow(authWindow);
            setAuthWindow(null);
            setIsLoading(false);
            
            if (event.data.error) {
                onError?.(new Error(event.data.error));
            } else {
                onSuccess?.(event.data);
            }
        } else if (event.data.type === 'TWITTER_AUTH_WINDOW_CLOSED') {
            // Handle manual window close
            setAuthWindow(null);
            setIsLoading(false);
            setCurrentFlow(null);
        }
    };

    window.addEventListener('message', messageHandler);
    return () => {
        // Clean up: close window and remove listener
        TwitterPopupHandler.closeAuthWindow(authWindow);
        window.removeEventListener('message', messageHandler);
    };
  }, [authWindow, onSuccess, onError]);

  const handleOAuth2Login = async () => {
    if (isLoading) return;
    
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
      setCurrentFlow('oauth2');
      const twitterCallbackUrl = redirectUri.replace('/linkedin/', '/twitter/');
      const authData = await TwitterPopupHandler.initializeAuth(Number(userId), twitterCallbackUrl, false);
      console.log('[Parent] OAuth 2.0 initialization successful:', authData);
      
      if (authData.authorization_url) {
        sessionStorage.setItem('twitter_auth_state', authData.state);
        const newWindow = TwitterPopupHandler.openAuthWindow(authData.authorization_url, false);
        if (!newWindow) {
          throw new Error('Could not open OAuth 2.0 window');
        }
        setAuthWindow(newWindow);
      } else {
        throw new Error('No OAuth 2.0 authorization URL received');
      }
    } catch (error) {
      console.error('[Parent] Twitter OAuth 2.0 error:', error);
      onError(error as Error);
      toast.error((error as Error).message);
      setIsLoading(false);
      setCurrentFlow(null);
    }
  };

  const handleOAuth1Login = async () => {
    if (isLoading) return;
    
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
      setOauth1Pending(true);
      setCurrentFlow('oauth1');
      const twitterCallbackUrl = redirectUri.replace('/linkedin/', '/twitter/');
      const authData = await TwitterPopupHandler.initializeAuth(Number(userId), twitterCallbackUrl, true);
      console.log('[Parent] OAuth 1.0a initialization successful:', authData);
      
      // Check for authorization_url in the response for OAuth 1.0a flow
      if (authData.authorization_url) {
        const newWindow = TwitterPopupHandler.openAuthWindow(authData.authorization_url, true);
        if (!newWindow) {
          throw new Error('Could not open OAuth 1.0a window');
        }
        setAuthWindow(newWindow);
      } else {
        throw new Error('No OAuth 1.0a authorization URL received');
      }
    } catch (error) {
      console.error('[Parent] Twitter OAuth 1.0a error:', error);
      onError(error as Error);
      toast.error((error as Error).message);
      setIsLoading(false);
      setOauth1Pending(false);
      setCurrentFlow(null);
    }
  };

  return (
    <div className="space-y-2">
      <Button
        onClick={handleOAuth2Login}
        disabled={isLoading}
        className="w-full mb-2"
        variant={localIsConnected ? "outline" : "default"}
      >
        {isLoading && currentFlow === 'oauth2' ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Conectando OAuth 2.0...
          </>
        ) : (
          <>
            <Twitter className="mr-2 h-4 w-4" />
            {localIsConnected ? 'Reconectar Twitter OAuth 2.0' : 'Conectar Twitter OAuth 2.0'}
          </>
        )}
      </Button>

      <Button
        onClick={handleOAuth1Login}
        disabled={isLoading}
        className="w-full"
        variant={localIsConnected ? "outline" : "default"}
      >
        {isLoading && currentFlow === 'oauth1' ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Conectando OAuth 1.0a...
          </>
        ) : (
          <>
            <Twitter className="mr-2 h-4 w-4" />
            {localIsConnected ? 'Reconectar Twitter OAuth 1.0a' : 'Conectar Twitter OAuth 1.0a'}
          </>
        )}
      </Button>

      {localIsConnected && !isLoading && (
        <p className="text-sm text-green-600 flex items-center justify-center">
          ✓ Twitter conectado
        </p>
      )}
    </div>
  );
};

export default TwitterAuth;
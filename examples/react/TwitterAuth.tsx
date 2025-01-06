import { Button } from "@/components/ui/button";
import { Loader2, Twitter, RefreshCw } from "lucide-react";
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
  

  useEffect(() => {
    setLocalIsConnected(isConnected);
  }, [isConnected]);

  const handleCallback = useCallback(async (code: string, state: string, isOAuth1: boolean = false, oauth1Verifier?: string) => {
    try {
      setIsLoading(true);
      console.log('[Parent] Starting token exchange:', { isOAuth1, code: code.slice(0, 10) + '...', hasVerifier: !!oauth1Verifier });
      
      const tokens = await TwitterTokenExchange.exchangeCodeForToken(code, state, redirectUri, isOAuth1, oauth1Verifier);
      console.log('[Parent] Twitter tokens received:', { 
        type: isOAuth1 ? 'OAuth1.0a' : 'OAuth2.0', 
        tokenKeys: Object.keys(tokens)
      });
      
      onSuccess(tokens);
      setLocalIsConnected(true);
      
      // Display success message in the window
      if (authWindow && !authWindow.closed) {
        try {
          authWindow.document.write(`
            <!DOCTYPE html>
            <html>
              <head>
                <title>Twitter OAuth</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                  body {
                    font-family: system-ui, -apple-system, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background-color: #f5f5f5;
                  }
                  .container {
                    text-align: center;
                    padding: 2rem;
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                  }
                  .success {
                    color: #10b981;
                    margin-bottom: 1rem;
                  }
                  .button {
                    background-color: #6b7280;
                    color: white;
                    padding: 12px 24px;
                    border-radius: 6px;
                    border: none;
                    cursor: pointer;
                    font-weight: 500;
                  }
                  .button:hover {
                    background-color: #4b5563;
                  }
                </style>
              </head>
              <body>
                <div class="container">
                  <h2 class="success">✓ Twitter Connected Successfully</h2>
                  <p>You can now close this window.</p>
                  <button onclick="window.opener.postMessage({type: 'CLOSE_OAUTH_WINDOW'}, window.location.origin)" class="button">Close Window</button>
                </div>
              </body>
            </html>
          `);
        } catch (error) {
          // If we can't modify the window content, just show a toast
          toast.success('Twitter connected successfully. You can close the popup window.');
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
    }
  }, [onSuccess, onError, redirectUri, authWindow]);

  useEffect(() => {
    const messageHandler = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) {
        console.warn('[Parent] Received message from unauthorized origin:', event.origin);
        return;
      }

      console.log('[Parent] Received postMessage:', {
        type: event.data.type,
        hasCode: !!event.data.code,
        hasState: !!event.data.state,
        hasVerifier: !!event.data.oauth_verifier,
        hasToken: !!event.data.oauth_token,
        data: event.data
      });
      
      if (event.data.type === 'TWITTER_AUTH_CALLBACK') {
        if (event.data.success) {
          console.log('[Parent] Twitter OAuth successful, proceeding with token exchange');
          if (event.data.oauth_verifier) {
            // Handle OAuth 1.0a callback
            console.log('[Parent] Processing OAuth 1.0a callback');
            handleCallback(event.data.oauth_token, '', true, event.data.oauth_verifier);
          } else if (event.data.code && event.data.state) {
            // Handle OAuth 2.0 callback
            console.log('[Parent] Processing OAuth 2.0 callback');
            handleCallback(event.data.code, event.data.state);
          }
        } else {
          console.error('[Parent] Twitter OAuth failed:', event.data.error);
          onError(new Error(event.data.error || 'Authentication failed'));
          if (authWindow && !authWindow.closed) {
            window.postMessage({ type: 'CLOSE_OAUTH_WINDOW' }, window.location.origin);
            setAuthWindow(null);
          }
          toast.error(`Twitter authentication failed: ${event.data.error || 'Unknown error'}`);
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
        console.log('[Parent] Auth window was closed by user');
        setAuthWindow(null);
        setIsLoading(false);
        setOauth1Pending(false);
        clearInterval(checkWindow);
      }
    }, 1000);

    return () => clearInterval(checkWindow);
  }, [authWindow]);

  const handleOAuth2Login = async () => {
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
      const authData = await TwitterPopupHandler.initializeAuth(userId, twitterCallbackUrl, false);
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
    }
  };

  const handleOAuth1Login = async () => {
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
      const twitterCallbackUrl = redirectUri.replace('/linkedin/', '/twitter/');
      const authData = await TwitterPopupHandler.initializeAuth(userId, twitterCallbackUrl, true);
      console.log('[Parent] OAuth 1.0a initialization successful:', authData);
      
      if (authData.oauth1_url) {
        const newWindow = TwitterPopupHandler.openAuthWindow(authData.oauth1_url, true);
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
        {isLoading && !oauth1Pending ? (
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
        {isLoading && oauth1Pending ? (
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

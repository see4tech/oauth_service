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
        hasOAuth1Url: !!tokens.oauth1_url,
        tokenKeys: Object.keys(tokens),
        oauth1Url: tokens.oauth1_url,
        tokens 
      });
      
      // If we received OAuth 1.0a URL in the response and we're not already in OAuth 1.0a flow
      if (!isOAuth1 && tokens.oauth1_url && authWindow && !authWindow.closed) {
        console.log('[Parent] Initiating OAuth 1.0a flow with URL:', tokens.oauth1_url);
        setOauth1Pending(true);
        
        // Store the OAuth 1.0a URL in case we need to retry
        sessionStorage.setItem('twitter_oauth1_url', tokens.oauth1_url);
        
        // Display a message in the window
        try {
          // Prevent the window from closing
          authWindow.onbeforeunload = (e) => {
            e.preventDefault();
            e.returnValue = '';
          };
          
          authWindow.document.write(`
            <!DOCTYPE html>
            <html>
              <head>
                <title>Twitter OAuth</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
          authWindow.document.body.innerHTML = `
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; font-family: system-ui, -apple-system, sans-serif;">
              <h2 style="margin-bottom: 20px;">OAuth 2.0 Authorization Complete</h2>
              <p style="margin-bottom: 20px;">Please click the button below to complete Twitter OAuth 1.0a authorization.</p>
              <a href="${tokens.oauth1_url}" 
                 style="background-color: #1da1f2; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 500;">
                Continue with Twitter OAuth 1.0a
              </a>
            </div>
          `;
        } catch (error) {
          // If we can't modify the window content (e.g., due to CORS), navigate directly
          console.log('[Parent] Redirecting to OAuth 1.0a URL');
          authWindow.location.href = tokens.oauth1_url;
        }
        
        return;
      }
      
      // Only call onSuccess and update UI after both flows are complete
      if (isOAuth1 || !tokens.oauth1_url) {
        console.log('[Parent] Both OAuth flows complete, calling onSuccess');
        onSuccess(tokens);
        setLocalIsConnected(true);
        
        // Display success message in the window
        if (authWindow && !authWindow.closed) {
          try {
            authWindow.document.body.innerHTML = `
              <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; font-family: system-ui, -apple-system, sans-serif;">
                <h2 style="margin-bottom: 20px; color: #10b981;">✓ Twitter Connected Successfully</h2>
                <p style="margin-bottom: 20px;">You can now close this window.</p>
                <button onclick="window.close()" 
                        style="background-color: #6b7280; color: white; padding: 12px 24px; border-radius: 6px; border: none; cursor: pointer; font-weight: 500;">
                  Close Window
                </button>
              </div>
            `;
          } catch (error) {
            // If we can't modify the window content, just show a toast
            toast.success('Twitter connected successfully. You can close the popup window.');
          }
        }
      }

    } catch (error) {
      console.error('[Parent] Twitter token exchange error:', error);
      onError(error as Error);
      toast.error((error as Error).message);
      
      // If this was an OAuth 1.0a error, we might want to retry
      if (isOAuth1) {
        const storedOAuth1Url = sessionStorage.getItem('twitter_oauth1_url');
        if (storedOAuth1Url) {
          toast.error('OAuth 1.0a failed. Click "Reconectar Twitter" to try again.');
        }
      }
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
            authWindow.close();
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
      const twitterCallbackUrl = redirectUri.replace('/linkedin/', '/twitter/');
      const authData = await TwitterPopupHandler.initializeAuth(userId, twitterCallbackUrl);
      console.log('[Parent] Auth initialization successful:', authData);
      
      if (authData.authorization_url) {
        sessionStorage.setItem('twitter_auth_state', authData.state);
        
        // Store OAuth 1.0a URL for later use
        if (authData.additional_params?.oauth1_url) {
          sessionStorage.setItem('twitter_oauth1_url', authData.additional_params.oauth1_url);
        }
        
        const newWindow = TwitterPopupHandler.openAuthWindow(authData.authorization_url);
        if (!newWindow) {
          throw new Error('Could not open authentication window');
        }
        setAuthWindow(newWindow);
        
        // Don't set success state here - wait for the callback
      } else {
        throw new Error('No authorization URL received');
      }
    } catch (error) {
      console.error('[Parent] Twitter auth error:', error);
      onError(error as Error);
      toast.error((error as Error).message);
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-2">
      <Button
        onClick={handleLogin}
        disabled={isLoading}
        className="w-full"
        variant={localIsConnected ? "outline" : "default"}
      >
        {isLoading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            {oauth1Pending ? 'Completando OAuth 1.0a...' : 'Conectando...'}
          </>
        ) : (
          <>
            {localIsConnected ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4" />
                Reconectar Twitter
              </>
            ) : (
              <>
                <Twitter className="mr-2 h-4 w-4" />
                Conectar Twitter
              </>
            )}
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

export class TwitterPopupHandler {
  static async initializeAuth(userId: number, redirectUri: string, useOAuth1: boolean = false) {
    console.log(`[Parent] Initiating Twitter ${useOAuth1 ? 'OAuth 1.0a' : 'OAuth 2.0'} auth with user ID:`, userId);
    
    // Ensure clean URLs without trailing slashes
    const origin = window.location.origin.replace(/\/$/, '');
    const frontendCallbackUrl = `${origin}/auth/callback/twitter`;
    const baseOAuthUrl = import.meta.env.VITE_BASE_OAUTH_URL.replace(/\/$/, '');
    
    console.log('[Parent] Request details:', {
      endpoint: `${baseOAuthUrl}/oauth/twitter/init`,
      payload: {
        user_id: userId.toString(), // Convert userId to string
        redirect_uri: redirectUri,
        frontend_callback_url: frontendCallbackUrl,
        use_oauth1: useOAuth1
      },
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': 'VITE_API_KEY present: ' + !!import.meta.env.VITE_API_KEY
      }
    });

    const response = await fetch(`${baseOAuthUrl}/oauth/twitter/init`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': import.meta.env.VITE_API_KEY
      },
      body: JSON.stringify({
        user_id: userId.toString(), // Convert userId to string
        redirect_uri: redirectUri,
        frontend_callback_url: frontendCallbackUrl,
        use_oauth1: useOAuth1
      }),
    });

    if (!response.ok) {
      const errorData = await response.text();
      console.error('[Parent] Twitter auth response error:', errorData);
      throw new Error(`Failed to initialize Twitter authentication: ${errorData}`);
    }

    const data = await response.json();
    console.log('[Parent] Twitter auth response:', data);
    return data;
  }

  static openAuthWindow(url: string, isOAuth1: boolean = false): Window | null {
    console.log(`[Parent] Opening ${isOAuth1 ? 'OAuth 1.0a' : 'OAuth 2.0'} window with URL:`, url);
    
    const width = 600;
    const height = 700;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    const features = `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no,location=yes,status=yes,scrollbars=yes`;
    
    try {
      const windowName = isOAuth1 
        ? `Twitter Auth OAuth1 ${Date.now()}`  // Unique name for OAuth 1.0a
        : 'Twitter Auth OAuth2';               // Fixed name for OAuth 2.0
      
      console.log(`[Parent] Opening window with name:`, windowName);
      const authWindow = window.open(url, windowName, features);
      
      if (!authWindow) {
        console.error(`[Parent] Failed to open ${isOAuth1 ? 'OAuth 1.0a' : 'OAuth 2.0'} window`);
        return null;
      }

      // Add message listener for callback
      const messageHandler = (event: MessageEvent) => {
        if (event.origin !== window.location.origin) {
          console.warn('[Parent] Received message from unauthorized origin:', event.origin);
          return;
        }
        
        console.log('[Parent] Received message in handler:', event.data);
        
        if (event.data.type === 'TWITTER_AUTH_CALLBACK') {
          // Forward the message with OAuth type information
          window.postMessage({ ...event.data, isOAuth1 }, window.location.origin);
          
          // Clean up
          window.removeEventListener('message', messageHandler);
          window.removeEventListener('message', closeHandler);
          
          // Close the window after a short delay
          setTimeout(() => {
            if (authWindow && !authWindow.closed) {
              authWindow.close();
            }
          }, 100);
        }
      };

      // Add message listener for manual window close
      const closeHandler = (event: MessageEvent) => {
        if (event.origin !== window.location.origin) return;
        
        if (event.data.type === 'CLOSE_OAUTH_WINDOW') {
          console.log('[Parent] Received close window command');
          window.removeEventListener('message', messageHandler);
          window.removeEventListener('message', closeHandler);
          if (authWindow && !authWindow.closed) {
            authWindow.close();
          }
        }
      };

      window.addEventListener('message', messageHandler);
      window.addEventListener('message', closeHandler);
      
      // Focus the window
      authWindow.focus();
      
      return authWindow;
    } catch (error) {
      console.error(`[Parent] Error opening auth window:`, error);
      return null;
    }
  }
}
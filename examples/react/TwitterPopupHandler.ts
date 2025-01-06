export class TwitterPopupHandler {
  static async initializeAuth(userId: string, redirectUri: string) {
    console.log('[Parent] Initiating Twitter auth with user ID:', userId);
    
    const response = await fetch(`${import.meta.env.VITE_BASE_OAUTH_URL}/oauth/twitter/init`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': import.meta.env.VITE_API_KEY
      },
      body: JSON.stringify({
        user_id: userId,
        redirect_uri: redirectUri,
        frontend_callback_url: redirectUri,
        scopes: ['tweet.read', 'tweet.write', 'users.read']
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
      // For OAuth 1.0a, always open a new window with _blank target
      if (isOAuth1) {
        console.log(`[Parent] Opening new OAuth 1.0a window with URL:`, url);
        const authWindow = window.open(url, '_blank', features);
        
        if (!authWindow) {
          console.error('[Parent] Failed to open OAuth 1.0a window');
          return null;
        }
        
        // Add message listener for OAuth 1.0a callback
        const messageHandler = (event: MessageEvent) => {
          if (event.origin !== window.location.origin) {
            console.warn('[Parent] Received message from unauthorized origin:', event.origin);
            return;
          }
          
          console.log('[Parent] Received message in OAuth 1.0a handler:', event.data);
          
          if (event.data.type === 'TWITTER_AUTH_CALLBACK') {
            // Forward the message with OAuth type information
            window.postMessage({ ...event.data, isOAuth1: true }, window.location.origin);
            
            // Clean up
            window.removeEventListener('message', messageHandler);
            
            // Close the window
            authWindow.close();
          }
        };
        
        window.addEventListener('message', messageHandler);
        
        // Focus the window
        authWindow.focus();
        
        return authWindow;
      }
      
      // For OAuth 2.0, use a named window
      const windowName = 'Twitter Auth OAuth2';
      console.log(`[Parent] Opening OAuth 2.0 window with name:`, windowName);
      const authWindow = window.open(url, windowName, features);
      
      if (!authWindow) {
        console.error('[Parent] Failed to open OAuth 2.0 window');
        return null;
      }

      // Add message listener for OAuth 2.0 callback
      const messageHandler = (event: MessageEvent) => {
        if (event.origin !== window.location.origin) {
          console.warn('[Parent] Received message from unauthorized origin:', event.origin);
          return;
        }
        
        console.log('[Parent] Received message in OAuth 2.0 handler:', event.data);
        
        if (event.data.type === 'TWITTER_AUTH_CALLBACK') {
          // Forward the message with OAuth type information
          window.postMessage({ ...event.data, isOAuth1: false }, window.location.origin);
          
          // Clean up
          window.removeEventListener('message', messageHandler);
        }
      };

      window.addEventListener('message', messageHandler);
      
      // Focus the window
      authWindow.focus();
      
      return authWindow;
    } catch (error) {
      console.error(`[Parent] Error opening auth window:`, error);
      return null;
    }
  }
}
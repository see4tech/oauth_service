export class TwitterPopupHandler {
  static async initializeAuth(
    userId: string,
    redirectUri: string,
    useOAuth1: boolean,
    frontendCallbackUrl: string,
    apiKey: string
  ) {
    try {
      const response = await fetch('https://dukat.see4.tech/oauth/twitter/init', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': apiKey
        },
        body: JSON.stringify({
          user_id: userId,
          redirect_uri: redirectUri,
          frontend_callback_url: frontendCallbackUrl,
          use_oauth1: useOAuth1
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || 'Failed to initialize Twitter OAuth');
      }

      const data = await response.json();
      console.log(`Twitter OAuth ${useOAuth1 ? '1.0a' : '2.0'} initialization response:`, data);
      return data;
    } catch (error) {
      console.error('Error initializing Twitter OAuth:', error);
      throw error;
    }
  }

  static exchangeToken(
    code: string,
    state: string,
    redirectUri: string,
    apiKey: string,
    isOAuth1: boolean = false,
    oauth1Verifier?: string
  ) {
    return fetch('https://dukat.see4.tech/oauth/twitter/callback', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey
      },
      body: JSON.stringify({
        code,
        state,
        redirect_uri: redirectUri,
        oauth1_verifier: oauth1Verifier
      })
    }).then(response => {
      if (!response.ok) {
        return response.json().then(error => {
          throw new Error(error.message || 'Failed to exchange token');
        });
      }
      return response.json();
    });
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
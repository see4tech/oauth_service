export class TwitterPopupHandler {
  static async initializeAuth(userId: number, redirectUri: string, useOAuth1: boolean = false) {
    console.log(`[Parent] Initiating Twitter ${useOAuth1 ? 'OAuth 1.0a' : 'OAuth 2.0'} auth with user ID:`, userId);
    
    // Ensure clean URLs without trailing slashes
    const origin = window.location.origin.replace(/\/$/, '');
    const baseOAuthUrl = import.meta.env.VITE_BASE_OAUTH_URL.replace(/\/$/, '');
    const frontendCallbackUrl = `${origin}/oauth/twitter/callback/${useOAuth1 ? '1' : '2'}`;
    
    // For OAuth 1.0a, include user information in the callback URL
    const callbackUrl = useOAuth1 
      ? `${frontendCallbackUrl}?user_id=${userId}&frontend_callback_url=${encodeURIComponent(frontendCallbackUrl)}`
      : frontendCallbackUrl;
    
    console.log('[Parent] Request details:', {
      endpoint: `${baseOAuthUrl}/oauth/twitter/init`,
      payload: {
        user_id: userId.toString(), // Convert userId to string
        redirect_uri: redirectUri,
        frontend_callback_url: callbackUrl,
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
        frontend_callback_url: callbackUrl,
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

  static openAuthWindow(url: string, isOAuth1: boolean): Window | null {
    const width = 600;
    const height = 800;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;

    console.log('[Parent] Opening auth window with URL:', url);
    
    try {
      const popup = window.open(
        url,
        'Twitter Auth',
        `width=${width},height=${height},left=${left},top=${top},` +
        'toolbar=no,menubar=no,scrollbars=yes,resizable=yes,status=no'
      );

      if (popup) {
        console.log('[Parent] Auth window opened successfully');
        
        // Start monitoring the popup
        const checkClosed = setInterval(() => {
          if (popup.closed) {
            console.log('[Parent] Auth window was closed manually');
            clearInterval(checkClosed);
            // Notify the parent that the window was closed manually
            window.postMessage({
              type: 'TWITTER_AUTH_WINDOW_CLOSED',
              manual: true
            }, window.location.origin);
          }
        }, 500);

        // Store the interval ID to clear it later
        (popup as any).__checkClosedInterval = checkClosed;
      } else {
        console.error('[Parent] Failed to open auth window');
      }

      return popup;
    } catch (error) {
      console.error('[Parent] Error opening window:', error);
      return null;
    }
  }

  static closeAuthWindow(window: Window | null) {
    if (!window) {
      console.log('[Parent] No window to close');
      return;
    }

    console.log('[Parent] Attempting to close auth window');
    
    try {
      // Clear the check interval if it exists
      if ((window as any).__checkClosedInterval) {
        clearInterval((window as any).__checkClosedInterval);
      }
      
      // Only try to close if the window is from the same origin or if we have permission
      if (!window.closed) {
        window.close();
      }
    } catch (error) {
      console.error('[Parent] Error closing window:', error);
      // If we can't close it directly, we can try to post a message to it
      try {
        window.postMessage({ type: 'CLOSE_WINDOW' }, '*');
      } catch (e) {
        console.error('[Parent] Error posting close message:', e);
      }
    }
  }
}
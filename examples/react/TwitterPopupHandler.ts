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

  static openAuthWindow(url: string, isOAuth1: boolean = false): Window | null {
    const width = 600;
    const height = 700;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    const features = `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no,location=no`;
    
    const authWindow = window.open(url, `Twitter ${isOAuth1 ? 'OAuth 1.0a' : 'OAuth 2.0'} Auth`, features);
    
    if (authWindow) {
      // Add message listener to the parent window
      window.addEventListener('message', (event) => {
        if (event.origin !== window.location.origin) {
          return;
        }
        
        if (event.data.type === 'TWITTER_AUTH_CALLBACK') {
          window.postMessage(event.data, window.location.origin);
        }
      });
    }
    
    return authWindow;
  }
}
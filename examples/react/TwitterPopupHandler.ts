export class TwitterPopupHandler {
  static async initializeAuth(userId: string, redirectUri: string) {
    console.log('Initiating Twitter auth with user ID:', userId);
    
    const response = await fetch(`${import.meta.env.VITE_BASE_OAUTH_URL}/oauth/twitter/init`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': import.meta.env.VITE_API_KEY
      },
      body: JSON.stringify({
        user_id: userId,
        redirect_uri: redirectUri,
        frontend_callback_url: window.location.origin,
        scopes: ['tweet.read', 'tweet.write', 'users.read']
      }),
    });

    if (!response.ok) {
      const errorData = await response.text();
      console.error('Twitter auth response error:', errorData);
      throw new Error('Error initiating Twitter authentication');
    }

    const data = await response.json();
    console.log('Twitter auth response:', {
      oauth2_url: data.authorization_url,
      oauth1_url: data.additional_params?.oauth1_url,
      state: data.state
    });
    return data;
  }

  static openAuthWindow(url: string, isOAuth1: boolean = false): Window | null {
    const width = 600;
    const height = 700;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    const features = `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no`;
    
    const authWindow = window.open(url, 'Twitter Auth', features);
    
    // Add message listener to the parent window
    window.addEventListener('message', (event) => {
      if (event.origin !== window.location.origin) {
        return;
      }
      
      // Handle both OAuth 1.0a and 2.0 callbacks
      if (event.data.type === 'TWITTER_AUTH_CALLBACK') {
        window.postMessage({
          ...event.data,
          isOAuth1
        }, window.location.origin);
      }
    });
    
    return authWindow;
  }
} 
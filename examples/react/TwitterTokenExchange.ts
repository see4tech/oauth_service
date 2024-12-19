export class TwitterTokenExchange {
  static async exchangeCodeForToken(
    code: string, 
    state: string, 
    redirectUri: string,
    isOAuth1: boolean = false,
    oauth1Verifier?: string
  ) {
    if (!isOAuth1) {
      // OAuth 2.0 flow
      const savedState = sessionStorage.getItem('twitter_auth_state');
      console.log('Comparing states:', { received: state, saved: savedState });
      
      if (state !== savedState) {
        throw new Error('State mismatch in OAuth callback');
      }
    }

    console.log('Making token exchange request to:', `${import.meta.env.VITE_BASE_OAUTH_URL}/oauth/twitter/token`);
    const response = await fetch(`${import.meta.env.VITE_BASE_OAUTH_URL}/oauth/twitter/token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': import.meta.env.VITE_API_KEY
      },
      body: JSON.stringify({
        code,
        state,
        redirect_uri: redirectUri,
        ...(isOAuth1 && { oauth1_verifier: oauth1Verifier })
      }),
    });

    if (!response.ok) {
      const errorData = await response.text();
      console.error('Token exchange failed:', {
        status: response.status,
        statusText: response.statusText,
        error: errorData
      });
      throw new Error(errorData || 'Error exchanging code for tokens');
    }

    const data = await response.json();
    // Store tokens with platform prefix to avoid conflicts
    localStorage.setItem('twitter_tokens', JSON.stringify({
      ...data,
      timestamp: Date.now()
    }));
    console.log('Twitter tokens stored in localStorage');
    
    return data;
  }

  static async refreshToken(refreshToken: string) {
    console.log('Refreshing Twitter token');
    
    const response = await fetch(`${import.meta.env.VITE_BASE_OAUTH_URL}/oauth/twitter/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': import.meta.env.VITE_API_KEY
      },
      body: JSON.stringify({
        refresh_token: refreshToken
      }),
    });

    if (!response.ok) {
      const errorData = await response.text();
      console.error('Token refresh failed:', {
        status: response.status,
        statusText: response.statusText,
        error: errorData
      });
      throw new Error(errorData || 'Error refreshing token');
    }

    const data = await response.json();
    const currentTokens = JSON.parse(localStorage.getItem('twitter_tokens') || '{}');
    
    // Update stored tokens
    localStorage.setItem('twitter_tokens', JSON.stringify({
      ...currentTokens,
      ...data,
      timestamp: Date.now()
    }));
    
    return data;
  }
} 
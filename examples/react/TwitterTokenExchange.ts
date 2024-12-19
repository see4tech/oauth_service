export class TwitterTokenExchange {
  private static readonly TOKEN_EXPIRY_BUFFER = 300; // 5 minutes buffer before expiry

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
    await this.storeTokens(data);
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
    await this.storeTokens(data);
    
    return data;
  }

  private static async storeTokens(tokens: any) {
    const storageData = {
      ...tokens,
      timestamp: Date.now(),
      expires_at: tokens.expires_in ? Date.now() + (tokens.expires_in * 1000) : null
    };
    
    localStorage.setItem('twitter_tokens', JSON.stringify(storageData));
  }

  static async getValidToken(): Promise<string | null> {
    try {
      const storedData = localStorage.getItem('twitter_tokens');
      if (!storedData) return null;

      const tokens = JSON.parse(storedData);
      
      // For OAuth 1.0a tokens (they don't expire)
      if (tokens.oauth1) {
        return tokens.oauth1.access_token;
      }

      // For OAuth 2.0 tokens
      if (!tokens.oauth2) return null;

      const now = Date.now();
      const expiresAt = tokens.expires_at;
      
      // Check if token is expired or will expire soon
      if (expiresAt && (expiresAt - now) < (this.TOKEN_EXPIRY_BUFFER * 1000)) {
        // Token is expired or will expire soon, try to refresh
        if (tokens.oauth2.refresh_token) {
          console.log('Token expired or expiring soon, refreshing...');
          const newTokens = await this.refreshToken(tokens.oauth2.refresh_token);
          return newTokens.oauth2.access_token;
        } else {
          console.log('No refresh token available');
          return null;
        }
      }

      return tokens.oauth2.access_token;
    } catch (error) {
      console.error('Error getting valid token:', error);
      return null;
    }
  }

  static isAuthenticated(): boolean {
    try {
      const storedData = localStorage.getItem('twitter_tokens');
      if (!storedData) return false;

      const tokens = JSON.parse(storedData);
      
      // Check for OAuth 1.0a tokens
      if (tokens.oauth1?.access_token) return true;

      // Check for OAuth 2.0 tokens
      if (!tokens.oauth2?.access_token) return false;

      const now = Date.now();
      const expiresAt = tokens.expires_at;
      
      // Consider authenticated if token exists and is not expired
      return expiresAt ? now < expiresAt : false;
    } catch (error) {
      console.error('Error checking authentication status:', error);
      return false;
    }
  }

  static clearTokens() {
    localStorage.removeItem('twitter_tokens');
    sessionStorage.removeItem('twitter_auth_state');
  }
} 
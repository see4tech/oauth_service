interface TwitterTokens {
  oauth1?: {
    access_token: string;
    access_token_secret: string;
  };
  oauth2?: {
    access_token: string;
    token_type: string;
    expires_in: number;
    refresh_token: string;
    scope: string;
  };
}

export class TwitterTokenExchange {
  static async exchangeCodeForToken(
    code: string, 
    state: string, 
    redirectUri: string, 
    isOAuth1: boolean = false,
    oauth1Verifier?: string
  ) {
    if (!isOAuth1) {
      const savedState = sessionStorage.getItem('twitter_auth_state');
      console.log('[Parent] Comparing states:', { received: state, saved: savedState });
      
      if (state !== savedState) {
        throw new Error('State mismatch in OAuth callback');
      }
    }

    console.log('[Parent] Making token exchange request:', {
      url: `${import.meta.env.VITE_BASE_OAUTH_URL}/oauth/twitter/token`,
      isOAuth1,
      hasVerifier: !!oauth1Verifier
    });

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
        is_oauth1: isOAuth1,
        oauth1_verifier: oauth1Verifier
      }),
    });

    if (!response.ok) {
      const errorData = await response.text();
      console.error('[Parent] Token exchange failed:', {
        status: response.status,
        statusText: response.statusText,
        error: errorData
      });
      throw new Error(errorData || 'Error exchanging code for tokens');
    }

    const data = await response.json();
    console.log('[Parent] Token exchange response:', {
      success: data.success,
      hasAuthUrl: !!data.authorization_url,
      authUrl: data.authorization_url,
      tokenKeys: Object.keys(data)
    });
    
    if (data.success) {
      let storedTokens: TwitterTokens = {};
      try {
        const existingTokens = localStorage.getItem('twitter_access_token');
        console.log('[Parent] Existing stored tokens:', existingTokens ? JSON.parse(existingTokens) : 'None');
        if (existingTokens) {
          storedTokens = JSON.parse(existingTokens);
        }
      } catch (error) {
        console.error('[Parent] Error reading stored tokens:', error);
      }

      if (!isOAuth1) {
        storedTokens = {
          ...storedTokens,
          oauth2: {
            access_token: data.access_token,
            token_type: data.token_type,
            expires_in: data.expires_in,
            refresh_token: data.refresh_token,
            scope: data.scope
          }
        };
        console.log('[Parent] Twitter OAuth 2.0 tokens stored:', {
          hasAccessToken: !!data.access_token,
          hasRefreshToken: !!data.refresh_token
        });

        if (data.authorization_url) {
          console.log('[Parent] Redirecting to OAuth1 URL in the same window');
          // Instead of opening a new window, redirect the current one
          const currentWindow = window.opener || window;
          currentWindow.location.href = data.authorization_url;
        }
      } else {
        storedTokens = {
          ...storedTokens,
          oauth1: {
            access_token: data.access_token,
            access_token_secret: data.access_token_secret
          }
        };
        console.log('[Parent] Twitter OAuth 1.0a tokens stored:', {
          hasAccessToken: !!data.access_token,
          hasAccessTokenSecret: !!data.access_token_secret
        });
      }

      localStorage.setItem('twitter_access_token', JSON.stringify(storedTokens));
      console.log('[Parent] Final stored token state:', {
        hasOAuth1: !!storedTokens.oauth1,
        hasOAuth2: !!storedTokens.oauth2,
        oauth1Keys: storedTokens.oauth1 ? Object.keys(storedTokens.oauth1) : [],
        oauth2Keys: storedTokens.oauth2 ? Object.keys(storedTokens.oauth2) : []
      });
    } else {
      console.error('[Parent] Twitter authentication failed:', data.error);
      throw new Error(data.error || 'Failed to authenticate with Twitter');
    }
    
    return data;
  }
}
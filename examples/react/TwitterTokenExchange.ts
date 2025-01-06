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
      hasOAuth1Url: !!data.oauth1_url,
      oauth1Url: data.oauth1_url,
      tokenKeys: Object.keys(data)
    });
    
    if (data.success) {
      // Get existing tokens if any
      let storedTokens = {};
      try {
        const existingTokens = localStorage.getItem('twitter_access_token');
        if (existingTokens) {
          storedTokens = JSON.parse(existingTokens);
        }
      } catch (error) {
        console.warn('[Parent] Error reading stored tokens:', error);
      }

      if (!isOAuth1) {
        // Store OAuth 2.0 tokens
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
        console.log('[Parent] Twitter OAuth 2.0 tokens stored');
      } else {
        // Store OAuth 1.0a tokens
        storedTokens = {
          ...storedTokens,
          oauth1: {
            access_token: data.access_token,
            access_token_secret: data.access_token_secret
          }
        };
        console.log('[Parent] Twitter OAuth 1.0a tokens stored');
      }

      // Save combined tokens
      localStorage.setItem('twitter_access_token', JSON.stringify(storedTokens));
      console.log('[Parent] Combined tokens stored:', Object.keys(storedTokens));
    } else {
      console.error('[Parent] Twitter authentication failed:', data.error);
      throw new Error(data.error || 'Failed to authenticate with Twitter');
    }
    
    return data;
  }
}
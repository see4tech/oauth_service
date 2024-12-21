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

    console.log('Making token exchange request:', {
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
      console.error('Token exchange failed:', {
        status: response.status,
        statusText: response.statusText,
        error: errorData
      });
      throw new Error(errorData || 'Error exchanging code for tokens');
    }

    const data = await response.json();
    
    if (data.success) {
      if (!isOAuth1) {
        localStorage.setItem('twitter_access_token', JSON.stringify(data));
        console.log('Twitter OAuth 2.0 tokens stored');
      } else {
        console.log('Twitter OAuth 1.0a tokens received');
      }
    } else {
      console.error('Twitter authentication failed:', data.error);
      throw new Error(data.error || 'Failed to authenticate with Twitter');
    }
    
    return data;
  }
}
export class InstagramTokenExchange {
  static async exchangeCodeForToken(code: string, state: string, redirectUri: string) {
    const savedState = sessionStorage.getItem('instagram_auth_state');
    console.log('Comparing states:', { received: state, saved: savedState });
    
    if (state !== savedState) {
      throw new Error('State mismatch in OAuth callback');
    }

    console.log('Making token exchange request to:', `${import.meta.env.VITE_BASE_OAUTH_URL}/oauth/instagram/token`);
    const response = await fetch(`${import.meta.env.VITE_BASE_OAUTH_URL}/oauth/instagram/token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': import.meta.env.VITE_API_KEY
      },
      body: JSON.stringify({
        code,
        state,
        redirect_uri: redirectUri,
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
    localStorage.setItem('instagram_access_token', JSON.stringify(data));
    console.log('Instagram tokens stored in localStorage');
    
    return data;
  }
} 
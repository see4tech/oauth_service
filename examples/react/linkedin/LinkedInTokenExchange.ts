export class LinkedInTokenExchange {
  static async exchangeCodeForToken(code: string, state: string, redirectUri: string) {
    const savedState = sessionStorage.getItem('linkedin_auth_state');
    
    if (state !== savedState) {
      throw new Error('State mismatch in OAuth callback');
    }

    const response = await fetch(`${import.meta.env.VITE_BASE_OAUTH_URL}/oauth/linkedin/token`, {
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
      throw new Error(errorData || 'Error exchanging code for tokens');
    }

    const data = await response.json();
    
    if (data.success) {
      localStorage.setItem('linkedin_access_token', JSON.stringify(data));
    } else {
      throw new Error(data.error || 'Failed to authenticate with LinkedIn');
    }
    
    return data;
  }
}
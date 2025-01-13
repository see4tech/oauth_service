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
    console.log('[Parent] Starting token exchange:', {
      isOAuth1,
      code: code.slice(0, 10) + '...',
      hasVerifier: !!oauth1Verifier
    });

    const baseOAuthUrl = import.meta.env.VITE_BASE_OAUTH_URL.replace(/\/$/, '');
    const origin = window.location.origin.replace(/\/$/, '');
    const frontendCallbackUrl = `${origin}/oauth/twitter/callback/${isOAuth1 ? '1' : '2'}`;

    const response = await fetch(`${baseOAuthUrl}/oauth/twitter/callback/${isOAuth1 ? '1' : '2'}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': import.meta.env.VITE_API_KEY
      },
      body: JSON.stringify({
        code: code,
        state: state,
        redirect_uri: redirectUri,
        frontend_callback_url: frontendCallbackUrl,
        oauth1_verifier: oauth1Verifier,
        use_oauth1: isOAuth1
      }),
    });

    if (!response.ok) {
      const errorData = await response.text();
      console.error('[Parent] Token exchange error:', errorData);
      throw new Error(`Failed to exchange token: ${errorData}`);
    }

    const data = await response.json();
    console.log('[Parent] Token exchange response:', {
      hasOAuth1: !!data.oauth1,
      hasOAuth2: !!data.oauth2,
      tokenKeys: Object.keys(data)
    });

    return data;
  }
}
export class OAuthPopupHandler {
  static async initializeAuth(userId: number, redirectUri: string, platform: string) {
    console.log(`[Parent] Initiating ${platform} OAuth with user ID:`, userId);
    
    const origin = window.location.origin.replace(/\/$/, '');
    const baseOAuthUrl = import.meta.env.VITE_BASE_OAUTH_URL.replace(/\/$/, '');
    const frontendCallbackUrl = `${origin}/oauth/${platform}/callback/2`;
    
    const response = await fetch(`${baseOAuthUrl}/oauth/${platform}/init`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': import.meta.env.VITE_API_KEY
      },
      body: JSON.stringify({
        user_id: userId.toString(),
        redirect_uri: redirectUri,
        frontend_callback_url: frontendCallbackUrl
      }),
    });

    if (!response.ok) {
      const errorData = await response.text();
      throw new Error(`Failed to initialize ${platform} authentication: ${errorData}`);
    }

    return await response.json();
  }

  static openAuthWindow(url: string, platform: string): Window | null {
    const width = 600;
    const height = 800;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;

    const popup = window.open(
      url,
      `${platform} Auth`,
      `width=${width},height=${height},left=${left},top=${top},` +
      'toolbar=no,menubar=no,scrollbars=yes,resizable=yes,status=no'
    );

    if (popup) {
      const checkClosed = setInterval(() => {
        if (popup.closed) {
          clearInterval(checkClosed);
          window.postMessage({
            type: 'OAUTH_WINDOW_CLOSED',
            platform,
            manual: true
          }, window.location.origin);
        }
      }, 500);

      (popup as any).__checkClosedInterval = checkClosed;
    }

    return popup;
  }

  static closeAuthWindow(window: Window | null) {
    if (window) {
      if ((window as any).__checkClosedInterval) {
        clearInterval((window as any).__checkClosedInterval);
      }
      
      try {
        window.close();
      } catch (e) {
        console.error('Failed to close auth window:', e);
      }
    }
  }
} 
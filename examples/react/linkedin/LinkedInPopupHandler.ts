export class LinkedInPopupHandler {
  static async initializeAuth(userId: string | number, redirectUri: string) {
    console.log('Initiating LinkedIn auth with user ID:', userId);
    
    const response = await fetch(`${import.meta.env.VITE_BASE_OAUTH_URL}/oauth/linkedin/init`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': import.meta.env.VITE_API_KEY
      },
      body: JSON.stringify({
        user_id: String(userId),
        redirect_uri: redirectUri,
        frontend_callback_url: redirectUri,
        scopes: ['openid', 'profile', 'w_member_social']
      }),
    });

    if (!response.ok) {
      const errorData = await response.text();
      console.error('LinkedIn auth response error:', errorData);
      throw new Error('Error initiating LinkedIn authentication');
    }

    const data = await response.json();
    console.log('LinkedIn auth response:', data);
    return data;
  }

  static openAuthWindow(url: string): Window | null {
    const width = 600;
    const height = 700;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    const features = `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no`;
    
    try {
      const popup = window.open(url, '_blank', features);
      
      // Force focus on the popup
      if (popup) {
        popup.focus();
      }
      
      return popup;
    } catch (error) {
      console.error('Error opening popup:', error);
      return null;
    }
  }

  static closeAuthWindow(window: Window | null) {
    if (!window) return;
    
    try {
      if (!window.closed) {
        window.close();
      }
    } catch (error) {
      console.error('Error closing window:', error);
    }
  }
}
export class LinkedInPopupHandler {
  static async initializeAuth(userId: string, redirectUri: string) {
    console.log('Initiating LinkedIn auth with user ID:', userId);
    
    const response = await fetch(`${import.meta.env.VITE_BASE_OAUTH_URL}/oauth/linkedin/init`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': import.meta.env.VITE_API_KEY
      },
      body: JSON.stringify({
        user_id: userId,
        redirect_uri: redirectUri,
        frontend_callback_url: window.location.origin,
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
    
    const authWindow = window.open(url, 'LinkedIn Auth', features);
    
    // Add message listener to the parent window
    window.addEventListener('message', (event) => {
      if (event.origin !== window.location.origin) {
        return;
      }
      
      if (event.data.type === 'LINKEDIN_AUTH_CALLBACK') {
        window.postMessage(event.data, window.location.origin);
      }
    });
    
    return authWindow;
  }
}
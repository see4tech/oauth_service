export class InstagramPopupHandler {
  static async initializeAuth(userId: string, redirectUri: string) {
    console.log('Initiating Instagram auth with user ID:', userId);
    
    const response = await fetch(`${import.meta.env.VITE_BASE_OAUTH_URL}/oauth/instagram/init`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': import.meta.env.VITE_API_KEY
      },
      body: JSON.stringify({
        user_id: userId,
        redirect_uri: redirectUri,
        frontend_callback_url: `${window.location.origin}/oauth/instagram/callback`,
        scopes: ['instagram_basic', 'instagram_content_publish']
      }),
    });

    if (!response.ok) {
      const errorData = await response.text();
      console.error('Instagram auth response error:', errorData);
      throw new Error('Error initiating Instagram authentication');
    }

    const data = await response.json();
    console.log('Instagram auth response:', data);
    return data;
  }

  static openAuthWindow(url: string): Window | null {
    const width = 600;
    const height = 700;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    const features = `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no,location=no`;
    
    const authWindow = window.open(url, 'Instagram Auth', features);
    
    // Add message listener to the parent window
    window.addEventListener('message', (event) => {
      if (event.origin !== window.location.origin) {
        return;
      }
      
      if (event.data.type === 'INSTAGRAM_AUTH_CALLBACK') {
        window.postMessage(event.data, window.location.origin);
      }
    });
    
    return authWindow;
  }
} 
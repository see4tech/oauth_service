import { useEffect } from 'react';
import { useRouter } from 'next/router';

export default function OAuthCallback() {
  const router = useRouter();
  const { status, platform, error } = router.query;

  useEffect(() => {
    if (status && platform) {
      // Send message to parent window
      if (window.opener) {
        window.opener.postMessage({
          type: `${platform.toUpperCase()}_AUTH_CALLBACK`,
          success: status === 'success',
          error: error || null,
          platform: platform
        }, window.location.origin);
        
        // Close this window
        window.close();
      }
    }
  }, [status, platform, error]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <p>Completing authentication...</p>
    </div>
  );
} 
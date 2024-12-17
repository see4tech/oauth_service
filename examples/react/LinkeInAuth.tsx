import React, { useState, useEffect, useCallback } from 'react';
import { Button, Card } from '@/components/ui';
import { Linkedin } from 'lucide-react';

interface LinkedInAuthProps {
  clientId: string;
  redirectUri: string;
  onSuccess?: (tokens: any) => void;
  onError?: (error: Error) => void;
}

const LinkedInAuth: React.FC<LinkedInAuthProps> = ({
  clientId,
  redirectUri,
  onSuccess,
  onError
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Handle the OAuth callback
  const handleCallback = useCallback(async (code: string) => {
    try {
      setIsLoading(true);
      const response = await fetch('http://localhost:8000/oauth/linkedin/callback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          code,
          redirect_uri: redirectUri,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to exchange code for tokens');
      }

      const tokens = await response.json();
      onSuccess?.(tokens);
    } catch (err) {
      setError(err.message);
      onError?.(err);
    } finally {
      setIsLoading(false);
    }
  }, [redirectUri, onSuccess, onError]);

  // Initialize OAuth flow
  const handleLogin = async () => {
    try {
      setIsLoading(true);
      const response = await fetch('http://localhost:8000/oauth/linkedin/init', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          client_id: clientId,
          redirect_uri: redirectUri,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to initialize OAuth flow');
      }

      const { authorization_url } = await response.json();
      window.location.href = authorization_url;
    } catch (err) {
      setError(err.message);
      onError?.(err);
    } finally {
      setIsLoading(false);
    }
  };

  // Check for OAuth callback code
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    if (code) {
      handleCallback(code);
    }
  }, [handleCallback]);

  return (
    <Card className="w-full max-w-md p-6">
      <div className="flex flex-col space-y-4">
        <Button
          onClick={handleLogin}
          disabled={isLoading}
          className="w-full flex items-center justify-center space-x-2"
        >
          <Linkedin className="w-5 h-5" />
          <span>{isLoading ? 'Connecting...' : 'Connect LinkedIn'}</span>
        </Button>
        {error && (
          <div className="text-red-500 text-sm text-center">{error}</div>
        )}
      </div>
    </Card>
  );
};

export default LinkedInAuth;

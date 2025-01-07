<LinkedInAuth
    redirectUri={`${window.location.origin}/oauth/linkedin/callback`}
    onSuccess={(data) => {
        console.log('LinkedIn connection successful:', data);
        // Update UI or state to reflect successful connection
        setConnectedPlatforms(prev => ({...prev, linkedin: true}));
    }}
    onError={(error) => {
        console.error('LinkedIn connection error:', error);
        toast.error('Failed to connect LinkedIn');
    }}
    isConnected={connectedPlatforms.linkedin}
/> 
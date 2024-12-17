import React from 'react';
import TwitterAuth from './TwitterAuth';
import LinkedInAuth from './LinkedInAuth';
import FacebookAuth from './FacebookAuth';
import InstagramAuth from './InstagramAuth';

const OAuthDemo: React.FC = () => {
  const handleSuccess = (platform: string) => (tokens: any) => {
    console.log(`${platform} OAuth Success:`, tokens);
    // Store tokens or update application state
  };

  const handleError = (platform: string) => (error: Error) => {
    console.error(`${platform} OAuth Error:`, error);
    // Handle error appropriately
  };

  return (
    <div className="min-h-screen bg-gray-100 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-3xl font-extrabold text-gray-900 sm:text-4xl">
            OAuth Integration Demo
          </h2>
          <p className="mt-4 text-xl text-gray-600">
            Connect your social media accounts
          </p>
        </div>

        <div className="mt-12 grid gap-6 lg:grid-cols-2">
          <div>
            <TwitterAuth
              clientId={process.env.NEXT_PUBLIC_TWITTER_CLIENT_ID!}
              redirectUri={`${window.location.origin}/oauth/twitter/callback`}
              onSuccess={handleSuccess('Twitter')}
              onError={handleError('Twitter')}
            />
          </div>

          <div>
            <LinkedInAuth
              clientId={process.env
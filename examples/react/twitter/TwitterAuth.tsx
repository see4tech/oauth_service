import { useState, useCallback, useEffect } from "react";
import { Twitter, Loader2, RefreshCw } from "lucide-react";
import { useTwitterAuth } from "./hooks/useTwitterAuth";
import { AuthButton } from "./components/AuthButton";

interface TwitterAuthProps {
  redirectUri: string;
  onSuccess: (tokens: any) => void;
  onError: (error: Error) => void;
  isConnectedOAuth1?: boolean;
  isConnectedOAuth2?: boolean;
}

const TwitterAuth = ({
  redirectUri,
  onSuccess,
  onError,
  isConnectedOAuth1 = false,
  isConnectedOAuth2 = false
}: TwitterAuthProps) => {
  const { 
    isLoading, 
    localIsConnectedOAuth1,
    localIsConnectedOAuth2,
    handleLogin,
    currentFlow
  } = useTwitterAuth(
    redirectUri,
    onSuccess,
    onError,
    isConnectedOAuth1,
    isConnectedOAuth2
  );

  const handleOAuth1Login = () => {
    handleLogin(true);
  };

  const handleOAuth2Login = () => {
    handleLogin(false);
  };

  return (
    <div className="auth-button-container">
      <AuthButton
        onClick={handleOAuth1Login}
        isLoading={isLoading}
        currentFlow={currentFlow}
        flowType="oauth1"
        isConnected={localIsConnectedOAuth1}
      />
      <AuthButton
        onClick={handleOAuth2Login}
        isLoading={isLoading}
        currentFlow={currentFlow}
        flowType="oauth2"
        isConnected={localIsConnectedOAuth2}
      />
    </div>
  );
};

export default TwitterAuth;
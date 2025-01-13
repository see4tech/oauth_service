import { Loader2, X } from "lucide-react";

interface AuthButtonProps {
  onClick: () => void;
  isLoading: boolean;
  currentFlow: 'oauth1' | 'oauth2' | null;
  flowType: 'oauth1' | 'oauth2';
  isConnected: boolean;
}

export const AuthButton = ({
  onClick,
  isLoading,
  currentFlow,
  flowType,
  isConnected
}: AuthButtonProps) => {
  const isThisFlowLoading = isLoading && currentFlow === flowType;
  const label = flowType === 'oauth1' ? 'OAuth 1.0a' : 'OAuth 2.0';

  return (
    <button
      onClick={onClick}
      disabled={isLoading}
      data-connected={isConnected}
      className="social-auth-button"
    >
      {isThisFlowLoading ? (
        <>
          <Loader2 className="animate-spin" />
          <span>Conectando {label}...</span>
        </>
      ) : (
        <>
          <X />
          <span>{isConnected ? `Reconectar ${label}` : `Conectar ${label}`}</span>
        </>
      )}
    </button>
  );
};
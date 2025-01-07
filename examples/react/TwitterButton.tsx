import { Button } from "@/components/ui/button";
import { Loader2, Twitter, RefreshCw } from "lucide-react";

interface TwitterButtonProps {
  isLoading: boolean;
  oauth1Pending: boolean;
  localIsConnected: boolean;
  handleLogin: () => void;
}

export const TwitterButton = ({ 
  isLoading, 
  oauth1Pending, 
  localIsConnected, 
  handleLogin 
}: TwitterButtonProps) => {
  return (
    <Button
      onClick={handleLogin}
      disabled={isLoading}
      className="w-full"
      variant={localIsConnected ? "outline" : "default"}
    >
      {isLoading ? (
        <>
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          {oauth1Pending ? "Completando OAuth 1.0a..." : "Conectando..."}
        </>
      ) : (
        <>
          {localIsConnected ? (
            <>
              <RefreshCw className="mr-2 h-4 w-4" />
              Reconectar Twitter
            </>
          ) : (
            <>
              <Twitter className="mr-2 h-4 w-4" />
              Conectar Twitter
            </>
          )}
        </>
      )}
    </Button>
  );
};
import { useCallback } from 'react';
import { TwitterTokenExchange } from '../TwitterTokenExchange';

interface UseAuthCallbackProps {
  redirectUri: string;
  onSuccess: (tokens: any) => void;
  onError: (error: Error) => void;
  setIsLoading: (loading: boolean) => void;
  setOauth1Pending: (pending: boolean) => void;
  closePopupSafely: (window: Window | null) => void;
  popupWindow: Window | null;
}

export const useAuthCallback = ({
  redirectUri,
  onSuccess,
  onError,
  setIsLoading,
  setOauth1Pending,
  closePopupSafely,
  popupWindow
}: UseAuthCallbackProps) => {
  return useCallback(async (
    code: string,
    state: string,
    isOAuth1: boolean = false,
    oauth1Verifier?: string
  ) => {
    try {
      setIsLoading(true);
      console.log('[Parent] Starting token exchange:', {
        isOAuth1,
        code: code.slice(0, 10) + '...',
        hasVerifier: !!oauth1Verifier
      });

      const tokens = await TwitterTokenExchange.exchangeCodeForToken(
        code,
        state,
        redirectUri,
        isOAuth1,
        oauth1Verifier
      );

      console.log('[Parent] X tokens received:', {
        type: isOAuth1 ? 'OAuth1.0a' : 'OAuth2.0',
        tokenKeys: Object.keys(tokens)
      });

      onSuccess(tokens);

      try {
        closePopupSafely(popupWindow);
      } catch (error) {
        console.error('[Parent] Error closing popup:', error);
      }
    } catch (error) {
      console.error('[Parent] X token exchange error:', error);
      onError(error as Error);
    } finally {
      setIsLoading(false);
      if (isOAuth1) {
        setOauth1Pending(false);
      }
    }
  }, [redirectUri, onSuccess, onError, setIsLoading, setOauth1Pending, closePopupSafely, popupWindow]);
};
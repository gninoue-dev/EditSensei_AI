import { useState, useCallback } from 'react';
import { apiService } from '../services/api';
import { EditStyle, AIResponse } from '../types';

export function useAI() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResponse, setLastResponse] = useState<AIResponse | null>(null);

  const processCommand = useCallback(async (text: string, style?: EditStyle, context?: any) => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiService.sendCommand(text, style, context);
      setLastResponse(response);
      return response;
    } catch (err: any) {
      const errorMsg = err.message || 'Erreur traitement commande';
      setError(errorMsg);
      console.error(errorMsg);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const clearHistory = useCallback(async () => {
    try {
      await apiService.clearHistory();
    } catch (err) {
      console.error('Erreur clear history:', err);
    }
  }, []);

  return {
    loading,
    error,
    lastResponse,
    processCommand,
    clearHistory,
  };
}

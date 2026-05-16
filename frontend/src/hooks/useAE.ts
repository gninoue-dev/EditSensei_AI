import { useState, useCallback, useEffect } from 'react';
import { apiService } from '../services/api';
import { useWebSocket } from './useWebSocket';

export function useAE() {
  const [aeConnected, setAeConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const { lastMessage } = useWebSocket();

  // Écouter les changements de connexion AE
  useEffect(() => {
    if (lastMessage?.data?.ae_connected !== undefined) {
      setAeConnected(lastMessage.data.ae_connected);
    }
  }, [lastMessage]);

  // Vérifier le statut AE au chargement
  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = useCallback(async () => {
    try {
      const status = await apiService.getStatus();
      setAeConnected(status.ae_connected);
    } catch (error) {
      console.error('Erreur vérification AE:', error);
    }
  }, []);

  const applyPreset = useCallback(async (presetName: string, layer: string) => {
    setLoading(true);
    try {
      const result = await apiService.applyPreset(presetName, layer);
      return result;
    } catch (error) {
      console.error('Erreur appliquer preset:', error);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    aeConnected,
    loading,
    checkStatus,
    applyPreset,
  };
}

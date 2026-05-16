import React, { useEffect, useState } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { useAE } from '../hooks/useAE';
import { apiService } from '../services/api';

export function StatusBar() {
  const { connected: wsConnected } = useWebSocket();
  const { aeConnected } = useAE();
  const [aiReady, setAiReady] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<string>('');

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const health = await apiService.healthCheck();
        setAiReady(health.ai_enabled);
        setLastUpdate(new Date().toLocaleTimeString());
      } catch (error) {
        setAiReady(false);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 5000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-dark text-white px-6 py-3 flex justify-between items-center text-sm">
      <div className="flex gap-6">
        {/* WebSocket */}
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-500'}`}
          />
          <span>WebSocket: {wsConnected ? 'Connecté' : 'Déconnecté'}</span>
        </div>

        {/* After Effects */}
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${aeConnected ? 'bg-green-500' : 'bg-yellow-500'}`}
          />
          <span>After Effects: {aeConnected ? 'Connecté' : 'En attente...'}</span>
        </div>

        {/* IA */}
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${aiReady ? 'bg-green-500' : 'bg-red-500'}`}
          />
          <span>IA: {aiReady ? 'Prêt' : 'Non disponible'}</span>
        </div>
      </div>

      {/* Mise à jour */}
      {lastUpdate && (
        <span className="text-gray-400 text-xs">Mis à jour: {lastUpdate}</span>
      )}
    </div>
  );
}

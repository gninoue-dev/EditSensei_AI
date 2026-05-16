import { useEffect, useState, useCallback } from 'react';
import { wsService } from '../services/websocket';
import { WebSocketMessage } from '../types';

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);

  useEffect(() => {
    wsService.connect().catch(console.error);

    wsService.on('connected', () => setConnected(true));
    wsService.on('disconnected', () => setConnected(false));

    const handleMessage = (data: any) => {
      setLastMessage({
        type: 'message',
        data,
      });
    };

    wsService.on('command_result', handleMessage);
    wsService.on('ae_status', handleMessage);
    wsService.on('ae_command_executed', handleMessage);
    wsService.on('ae_error', handleMessage);

    return () => {
      wsService.disconnect();
    };
  }, []);

  const send = useCallback((message: WebSocketMessage) => {
    wsService.send(message);
  }, []);

  const sendCommand = useCallback((text: string, style?: string, layer?: string) => {
    wsService.sendCommand(text, style, layer);
  }, []);

  return {
    connected,
    lastMessage,
    send,
    sendCommand,
  };
}

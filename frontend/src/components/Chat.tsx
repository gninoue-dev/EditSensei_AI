import React, { useState, useRef, useEffect } from 'react';
import { ChatMessage as ChatMessageType, AECommand } from '../types';
import { useAI } from '../hooks/useAI';
import { CommandInput } from './CommandInput';

interface ChatProps {
  onCommandExecuted?: (commands: AECommand[]) => void;
}

export function Chat({ onCommandExecuted }: ChatProps) {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const { processCommand, loading } = useAI();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll vers le bas
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSendCommand = async (text: string, style?: any) => {
    // Ajouter le message utilisateur
    const userMessage: ChatMessageType = {
      role: 'user',
      content: text,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // Traiter la commande
    const result = await processCommand(text, style);

    if (result) {
      const assistantMessage: ChatMessageType = {
        role: 'assistant',
        content: result.message || 'Commande exécutée',
        timestamp: Date.now(),
        ae_actions: result.ae_commands,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      if (result.ae_commands && onCommandExecuted) {
        onCommandExecuted(result.ae_commands);
      }
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-lg">
      {/* En-tête */}
      <div className="px-6 py-4 border-b bg-gradient-to-r from-primary to-dark text-white rounded-t-lg">
        <h2 className="text-xl font-bold">ÉDITSENSEI AI</h2>
        <p className="text-sm opacity-90">Votre assistant d'édition IA</p>
      </div>

      {/* Zone messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-4 bg-light">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-center text-gray-500">
            <div>
              <p className="text-lg font-medium">Bienvenue dans ÉDITSENSEI</p>
              <p className="text-sm">Décrivez comment vous voulez modifier votre vidéo</p>
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-xs lg:max-w-md px-4 py-3 rounded-lg ${
                  msg.role === 'user'
                    ? 'bg-primary text-white rounded-br-none'
                    : 'bg-white text-dark border border-gray-200 rounded-bl-none'
                }`}
              >
                <p className="text-sm">{msg.content}</p>
                {msg.ae_actions && msg.ae_actions.length > 0 && (
                  <div className="mt-2 text-xs opacity-75">
                    {msg.ae_actions.length} action(s) appliquée(s)
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Input */}
      <div className="border-t p-6 bg-white rounded-b-lg">
        <CommandInput onSendCommand={handleSendCommand} loading={loading} />
      </div>
    </div>
  );
}

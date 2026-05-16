import React, { useState } from 'react';
import { EditStyle } from '../types';

interface CommandInputProps {
  onSendCommand: (text: string, style?: EditStyle) => void;
  loading?: boolean;
  disabled?: boolean;
}

const QUICK_COMMANDS = [
  { label: 'Plus agressif', style: 'aggressive' as EditStyle },
  { label: 'Plus smooth', style: 'smooth' as EditStyle },
  { label: 'Impact anime', style: 'anime' as EditStyle },
  { label: 'Gaming', style: 'gaming' as EditStyle },
];

export function CommandInput({ onSendCommand, loading, disabled }: CommandInputProps) {
  const [input, setInput] = useState('');
  const [selectedStyle, setSelectedStyle] = useState<EditStyle | null>(null);

  const handleSend = () => {
    if (input.trim()) {
      onSendCommand(input, selectedStyle || undefined);
      setInput('');
      setSelectedStyle(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !loading && !disabled) {
      handleSend();
    }
  };

  return (
    <div className="space-y-3">
      {/* Commandes rapides */}
      <div className="grid grid-cols-2 gap-2">
        {QUICK_COMMANDS.map((cmd) => (
          <button
            key={cmd.label}
            onClick={() => onSendCommand(cmd.label, cmd.style)}
            disabled={loading || disabled}
            className="px-3 py-2 bg-primary text-white rounded hover:bg-opacity-80 disabled:opacity-50 text-sm font-medium transition"
          >
            {cmd.label}
          </button>
        ))}
      </div>

      {/* Champ de saisie */}
      <div className="space-y-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Décrivez ce que vous voulez... Ex: 'Ajoute un glow et sync au beat'"
          disabled={loading || disabled}
          className="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary resize-none h-20 disabled:bg-gray-100"
        />

        {/* Sélecteur de style */}
        <div className="flex gap-2">
          <select
            value={selectedStyle || ''}
            onChange={(e) => setSelectedStyle((e.target.value as EditStyle) || null)}
            disabled={loading || disabled}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary disabled:bg-gray-100"
          >
            <option value="">Style (optionnel)</option>
            <option value="aggressive">Agressif</option>
            <option value="smooth">Smooth</option>
            <option value="anime">Anime</option>
            <option value="gaming">Gaming</option>
            <option value="cinematic">Cinématique</option>
          </select>

          <button
            onClick={handleSend}
            disabled={!input.trim() || loading || disabled}
            className="px-6 py-2 bg-primary text-white rounded-lg hover:bg-opacity-80 disabled:opacity-50 font-medium transition"
          >
            {loading ? '⏳' : '→'}
          </button>
        </div>
      </div>
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { AECommand } from '../types';

interface ConsoleProps {
  commands?: AECommand[];
}

export function Console({ commands = [] }: ConsoleProps) {
  const [logs, setLogs] = useState<string[]>([]);

  useEffect(() => {
    if (commands.length > 0) {
      setLogs((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] ${commands.length} commande(s) exécutée(s)`,
        ...commands.map((cmd) => `  → ${cmd.action}: ${cmd.property || cmd.layer || 'N/A'}`),
      ]);
    }
  }, [commands]);

  const clearLogs = () => setLogs([]);

  return (
    <div className="bg-dark text-white rounded-lg font-mono text-xs h-64 flex flex-col">
      <div className="flex justify-between items-center px-4 py-2 border-b border-gray-700">
        <span className="font-bold">Console</span>
        <button
          onClick={clearLogs}
          className="text-gray-400 hover:text-white text-xs px-2 py-1"
        >
          Clear
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-1 bg-black bg-opacity-50">
        {logs.length === 0 ? (
          <span className="text-gray-600">Prêt...</span>
        ) : (
          logs.map((log, idx) => <div key={idx}>{log}</div>)
        )}
      </div>
    </div>
  );
}

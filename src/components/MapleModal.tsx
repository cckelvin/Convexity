import React, { useState } from 'react';
import { X, Bot, ShieldCheck, FileCode, CheckCircle2, Play, Send } from 'lucide-react';
import { TerminalSession } from '../types';

interface MapleModalProps {
  session: TerminalSession;
  onToggleMaple: () => void;
  onRunCommand: (cmd: string) => void;
  onClose: () => void;
}

export const MapleModal: React.FC<MapleModalProps> = ({
  session,
  onToggleMaple,
  onRunCommand,
  onClose,
}) => {
  const [prompt, setPrompt] = useState('');

  const sampleWorkflows = [
    { name: 'Inspect Project Files', cmd: 'cat /home/user/projects/agent_task.py' },
    { name: 'Review Security Policies', cmd: 'cat /maple/rules/rules.md' },
    { name: 'Create Project Workflow', cmd: 'cat /maple/workflows/create-project.md' },
    { name: 'Train Model Workflow', cmd: 'cat /maple/workflows/train-model.md' },
  ];

  const handleAsk = () => {
    if (!prompt.trim()) return;
    onRunCommand(`maple ${prompt.trim()}`);
    setPrompt('');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-[#12161f] border border-neutral-800 rounded-xl w-full max-w-2xl flex flex-col shadow-2xl overflow-hidden font-mono text-xs sm:text-sm">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-800 bg-[#0d1117]">
          <div className="flex items-center gap-2 text-neutral-200 font-semibold">
            <Bot className="w-4 h-4 text-indigo-400" />
            <span>Maple AI Agent Control Center</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-4 overflow-y-auto max-h-[70vh]">
          {/* Status banner */}
          <div className="flex items-center justify-between p-3.5 rounded-lg bg-[#181d29] border border-indigo-900/50">
            <div className="flex items-center gap-3">
              <div
                className={`w-3 h-3 rounded-full ${
                  session.mapleLoaded ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]' : 'bg-neutral-500'
                }`}
              />
              <div>
                <div className="text-neutral-200 font-semibold">
                  Maple Status: {session.mapleLoaded ? 'ACTIVE' : 'INACTIVE'}
                </div>
                <div className="text-[11px] text-neutral-400">
                  {session.mapleLoaded
                    ? `Session ID: ${session.mapleSessionId || 'active-01'} | Security interceptor active`
                    : "Activate Maple to enable automated reasoning and safety checks."}
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={onToggleMaple}
              className={`px-3 py-1.5 rounded text-xs font-semibold transition ${
                session.mapleLoaded
                  ? 'bg-rose-900/60 hover:bg-rose-800 text-rose-200 border border-rose-700/60'
                  : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-sm'
              }`}
            >
              {session.mapleLoaded ? 'Deactivate' : 'Activate Maple'}
            </button>
          </div>

          {/* Quick Query Input */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-neutral-300">Ask Maple / Issue Directive:</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
                placeholder="e.g., 'inspect workspace' or 'verify safety boundaries'..."
                className="flex-1 px-3 py-2 bg-[#090d13] border border-neutral-700 rounded-md text-xs text-neutral-100 outline-none focus:border-indigo-500 transition"
              />
              <button
                type="button"
                onClick={handleAsk}
                className="px-3 py-2 rounded-md bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs flex items-center gap-1.5 transition"
              >
                <Send className="w-3.5 h-3.5" />
                Query
              </button>
            </div>
          </div>

          {/* Core Maple Features */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            <div className="p-3 rounded-lg bg-neutral-900/80 border border-neutral-800 space-y-1.5">
              <div className="flex items-center gap-2 text-indigo-300 font-semibold text-xs">
                <ShieldCheck className="w-4 h-4 text-indigo-400" />
                <span>Security Interception</span>
              </div>
              <p className="text-[11px] text-neutral-400 leading-relaxed">
                When Maple runs commands, dangerous patterns (recursive file deletions, raw partition writes, kill signals) are evaluated and require explicit human sign-off.
              </p>
            </div>

            <div className="p-3 rounded-lg bg-neutral-900/80 border border-neutral-800 space-y-1.5">
              <div className="flex items-center gap-2 text-sky-300 font-semibold text-xs">
                <FileCode className="w-4 h-4 text-sky-400" />
                <span>Agentic Workflows</span>
              </div>
              <p className="text-[11px] text-neutral-400 leading-relaxed">
                Automated multi-step tasks for project generation, dataset conversion to GGUF, library dependency verification, and model training.
              </p>
            </div>
          </div>

          {/* Quick Workflows */}
          <div className="space-y-2 pt-1">
            <div className="text-xs font-semibold text-neutral-300">Preset Workflows:</div>
            <div className="space-y-1.5">
              {sampleWorkflows.map((wf) => (
                <div
                  key={wf.name}
                  className="flex items-center justify-between p-2 rounded-md bg-neutral-900/60 border border-neutral-800 hover:border-neutral-700 transition"
                >
                  <div className="flex items-center gap-2 text-neutral-300 text-xs">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span>{wf.name}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      onRunCommand(wf.cmd);
                      onClose();
                    }}
                    className="flex items-center gap-1 px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-300 text-[11px] transition"
                  >
                    <Play className="w-3 h-3 text-sky-400" />
                    Run in Terminal
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

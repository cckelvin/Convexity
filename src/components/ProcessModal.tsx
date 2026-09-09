import React, { useState } from 'react';
import { X, Cpu, Play, Square, RefreshCw, AlertCircle } from 'lucide-react';
import { ProcessManager } from '../core/process';
import { ProcessItem } from '../types';

interface ProcessModalProps {
  processManager: ProcessManager;
  onClose: () => void;
}

export const ProcessModal: React.FC<ProcessModalProps> = ({ processManager, onClose }) => {
  const [includeAll, setIncludeAll] = useState(true);
  const [newCmd, setNewCmd] = useState('');
  const [, setTrigger] = useState(0);

  const reload = () => setTrigger((t) => t + 1);

  const processes = processManager.list(includeAll);

  const handleStart = () => {
    if (!newCmd.trim()) return;
    processManager.start(newCmd.trim(), 'human');
    setNewCmd('');
    reload();
  };

  const handleKill = (pid: number) => {
    processManager.kill(pid);
    reload();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-[#12161f] border border-neutral-800 rounded-xl w-full max-w-3xl flex flex-col shadow-2xl overflow-hidden font-mono text-xs sm:text-sm">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-800 bg-[#0d1117]">
          <div className="flex items-center gap-2 text-neutral-200 font-semibold">
            <Cpu className="w-4 h-4 text-emerald-400" />
            <span>Process & Job Manager</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 border-b border-neutral-800 bg-[#161b22]">
          <div className="flex items-center gap-2 flex-1 max-w-md">
            <input
              type="text"
              value={newCmd}
              onChange={(e) => setNewCmd(e.target.value)}
              placeholder="Run background job (e.g. 'python worker.py')..."
              className="flex-1 px-2.5 py-1.5 bg-[#0d1117] border border-neutral-700 rounded text-xs text-neutral-100 outline-none"
            />
            <button
              type="button"
              onClick={handleStart}
              className="flex items-center gap-1 px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs transition"
            >
              <Play className="w-3.5 h-3.5" />
              Spawn
            </button>
          </div>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-xs text-neutral-400 cursor-pointer">
              <input
                type="checkbox"
                checked={includeAll}
                onChange={(e) => setIncludeAll(e.target.checked)}
                className="rounded text-sky-500 bg-neutral-800 border-neutral-700"
              />
              Include terminated
            </label>
            <button
              type="button"
              onClick={reload}
              className="p-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-300 transition"
              title="Refresh list"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="p-4 overflow-y-auto max-h-[60vh]">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-neutral-800 text-[11px] text-neutral-400 uppercase tracking-wider">
                <th className="pb-2 font-semibold">PID</th>
                <th className="pb-2 font-semibold">State</th>
                <th className="pb-2 font-semibold">Source</th>
                <th className="pb-2 font-semibold">Command</th>
                <th className="pb-2 font-semibold text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800/60">
              {processes.map((proc: ProcessItem) => (
                <tr key={proc.pid} className="hover:bg-neutral-800/40 transition">
                  <td className="py-2.5 font-bold text-sky-400">{proc.pid}</td>
                  <td className="py-2.5">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${
                        proc.state === 'running'
                          ? 'bg-emerald-950/70 text-emerald-300 border border-emerald-800/80'
                          : 'bg-neutral-800 text-neutral-400'
                      }`}
                    >
                      {proc.state}
                    </span>
                  </td>
                  <td className="py-2.5 text-neutral-400">{proc.source}</td>
                  <td className="py-2.5 text-neutral-200 font-medium">{proc.command}</td>
                  <td className="py-2.5 text-right">
                    {proc.state === 'running' && proc.pid !== 1 ? (
                      <button
                        type="button"
                        onClick={() => handleKill(proc.pid)}
                        className="p-1 rounded text-rose-400 hover:text-rose-300 hover:bg-rose-950/40 transition inline-flex items-center gap-1"
                        title="Kill Process"
                      >
                        <Square className="w-3.5 h-3.5" />
                        <span className="text-[11px]">Kill</span>
                      </button>
                    ) : (
                      <span className="text-neutral-600 text-xs">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {processes.length === 0 && (
            <div className="py-8 text-center text-neutral-500">No active processes</div>
          )}
        </div>

        <div className="px-4 py-2.5 bg-[#0d1117] border-t border-neutral-800 text-neutral-400 text-xs flex items-center gap-2">
          <AlertCircle className="w-3.5 h-3.5 text-sky-400" />
          <span>PID 1 (init) and core system daemons are protected from unhandled termination.</span>
        </div>
      </div>
    </div>
  );
};

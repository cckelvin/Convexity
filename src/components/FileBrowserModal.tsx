import React, { useState } from 'react';
import { X, Folder, FileText, ChevronRight, CornerLeftUp, FilePlus, FolderPlus } from 'lucide-react';
import { VirtualFilesystem } from '../core/filesystem';

interface FileBrowserModalProps {
  fs: VirtualFilesystem;
  currentCwd: string;
  onClose: () => void;
  onNavigateToDir: (path: string) => void;
}

export const FileBrowserModal: React.FC<FileBrowserModalProps> = ({
  fs,
  currentCwd,
  onClose,
  onNavigateToDir,
}) => {
  const [activePath, setActivePath] = useState(currentCwd);
  const [selectedFile, setSelectedFile] = useState<{ path: string; content: string } | null>(null);
  const [newFileName, setNewFileName] = useState('');
  const [isCreatingFile, setIsCreatingFile] = useState(false);
  const [isCreatingDir, setIsCreatingDir] = useState(false);

  let items: string[] = [];
  try {
    items = fs.listDirectory(activePath, true, false);
  } catch {
    items = [];
  }

  const handleOpenItem = (itemName: string) => {
    const isDir = itemName.endsWith('/');
    const cleanName = itemName.replace(/\/$/, '');
    const fullPath = activePath === '/' ? `/${cleanName}` : `${activePath}/${cleanName}`;

    if (isDir) {
      setActivePath(fullPath);
      setSelectedFile(null);
    } else {
      try {
        const content = fs.readFile(fullPath);
        setSelectedFile({ path: fullPath, content });
      } catch (err: unknown) {
        setSelectedFile({ path: fullPath, content: `Error reading file: ${(err as Error).message}` });
      }
    }
  };

  const handleGoUp = () => {
    if (activePath === '/') return;
    const parts = activePath.split('/').filter(Boolean);
    parts.pop();
    setActivePath('/' + parts.join('/'));
    setSelectedFile(null);
  };

  const handleCreate = () => {
    if (!newFileName.trim()) return;
    const full = activePath === '/' ? `/${newFileName.trim()}` : `${activePath}/${newFileName.trim()}`;
    try {
      if (isCreatingFile) {
        fs.writeFile(full, '# New Convexity File\n');
        setSelectedFile({ path: full, content: '# New Convexity File\n' });
      } else if (isCreatingDir) {
        fs.makeDirectory(full, true);
      }
      setNewFileName('');
      setIsCreatingFile(false);
      setIsCreatingDir(false);
    } catch {
      // ignore
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-[#12161f] border border-neutral-800 rounded-xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden font-mono text-xs sm:text-sm">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-800 bg-[#0d1117]">
          <div className="flex items-center gap-2 text-neutral-200 font-semibold">
            <Folder className="w-4 h-4 text-sky-400" />
            <span>Convexity Virtual Filesystem</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Path bar */}
        <div className="flex items-center justify-between gap-2 px-4 py-2 border-b border-neutral-800/80 bg-[#161b22]">
          <div className="flex items-center gap-2 overflow-x-auto text-neutral-300">
            <button
              type="button"
              onClick={handleGoUp}
              disabled={activePath === '/'}
              className="p-1 rounded hover:bg-neutral-800 disabled:opacity-40 text-neutral-400 transition"
              title="Parent directory"
            >
              <CornerLeftUp className="w-4 h-4" />
            </button>
            <span className="text-neutral-500 font-bold">Path:</span>
            <span className="text-sky-300 font-semibold">{activePath}</span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => {
                onNavigateToDir(activePath);
                onClose();
              }}
              className="px-2.5 py-1 rounded bg-sky-950/60 hover:bg-sky-900 border border-sky-700/60 text-sky-300 text-xs transition"
            >
              Set CWD Here
            </button>
            <button
              type="button"
              onClick={() => {
                setIsCreatingFile(true);
                setIsCreatingDir(false);
              }}
              className="p-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-300 transition"
              title="New File"
            >
              <FilePlus className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => {
                setIsCreatingDir(true);
                setIsCreatingFile(false);
              }}
              className="p-1.5 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-300 transition"
              title="New Directory"
            >
              <FolderPlus className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Create inline form */}
        {(isCreatingFile || isCreatingDir) && (
          <div className="flex items-center gap-2 px-4 py-2 bg-neutral-900 border-b border-neutral-800">
            <span className="text-xs text-neutral-400">
              {isCreatingFile ? 'New file name:' : 'New directory name:'}
            </span>
            <input
              type="text"
              value={newFileName}
              onChange={(e) => setNewFileName(e.target.value)}
              placeholder={isCreatingFile ? 'test.py' : 'my_dir'}
              autoFocus
              className="px-2 py-1 bg-neutral-800 border border-neutral-700 rounded text-xs text-neutral-100 outline-none"
            />
            <button
              type="button"
              onClick={handleCreate}
              className="px-2 py-1 rounded bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold"
            >
              Create
            </button>
            <button
              type="button"
              onClick={() => {
                setIsCreatingFile(false);
                setIsCreatingDir(false);
              }}
              className="px-2 py-1 rounded bg-neutral-800 text-neutral-400 text-xs"
            >
              Cancel
            </button>
          </div>
        )}

        {/* Browser body */}
        <div className="flex-1 grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-neutral-800 overflow-hidden">
          {/* File list */}
          <div className="overflow-y-auto p-3 space-y-1 max-h-[50vh] md:max-h-full">
            {items.length === 0 ? (
              <div className="text-neutral-500 p-4 text-center">Empty directory</div>
            ) : (
              items.map((item) => {
                const isDir = item.endsWith('/');
                return (
                  <button
                    type="button"
                    key={item}
                    onClick={() => handleOpenItem(item)}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-md hover:bg-neutral-800/80 text-left transition group"
                  >
                    <div className="flex items-center gap-2.5">
                      {isDir ? (
                        <Folder className="w-4 h-4 text-amber-400 shrink-0" />
                      ) : (
                        <FileText className="w-4 h-4 text-sky-400 shrink-0" />
                      )}
                      <span className={`${isDir ? 'text-neutral-200 font-semibold' : 'text-neutral-300'}`}>
                        {item}
                      </span>
                    </div>
                    <ChevronRight className="w-3.5 h-3.5 text-neutral-600 group-hover:text-neutral-300 transition" />
                  </button>
                );
              })
            )}
          </div>

          {/* File content preview */}
          <div className="overflow-y-auto p-4 bg-[#090d13]">
            {selectedFile ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between border-b border-neutral-800 pb-2">
                  <span className="text-sky-400 font-semibold text-xs">{selectedFile.path}</span>
                  <span className="text-neutral-500 text-[11px]">
                    {new TextEncoder().encode(selectedFile.content).length} bytes
                  </span>
                </div>
                <pre className="text-xs text-neutral-300 whitespace-pre-wrap font-mono leading-relaxed select-text">
                  {selectedFile.content}
                </pre>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-neutral-500 text-xs">
                Select a file from the left to view its contents
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

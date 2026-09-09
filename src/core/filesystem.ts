import { FSNode, DirectoryNode, FileNode, FileStat } from '../types';

export class VirtualFilesystem {
  private root: DirectoryNode;

  constructor() {
    this.root = this.createDefaultTree();
  }

  private createDefaultTree(): DirectoryNode {
    const now = Date.now();
    return {
      name: '',
      type: 'dir',
      modified: now,
      permissions: 'rwxr-xr-x',
      children: {
        home: {
          name: 'home',
          type: 'dir',
          modified: now,
          permissions: 'rwxr-xr-x',
          children: {
            user: {
              name: 'user',
              type: 'dir',
              modified: now,
              permissions: 'rwxr-xr-x',
              children: {
                'welcome.txt': {
                  name: 'welcome.txt',
                  type: 'file',
                  modified: now,
                  size: 512,
                  permissions: 'rw-r--r--',
                  content: `CONVEXITY TERMINAL v1.2.0
========================
An AI-native operating environment for interactive development.

Quick Start:
  - Type 'help' to see available native built-in commands.
  - Run 'load maple' to activate the Maple AI copilot.
  - Explore documents in /docs and /maple using 'ls' and 'cat'.
  - Use 'ps' and 'jobs' to view simulated processes.
  - Test safety checks with commands like 'rm -rf /'.
`,
                },
                projects: {
                  name: 'projects',
                  type: 'dir',
                  modified: now,
                  permissions: 'rwxr-xr-x',
                  children: {
                    'agent_task.py': {
                      name: 'agent_task.py',
                      type: 'file',
                      modified: now,
                      size: 284,
                      permissions: 'rw-r--r--',
                      content: `"""
Convexity Agent Automation Example
"""
import sys

def main():
    print("Executing Convexity automated pipeline...")
    for step in ["Validation", "Model Inference", "Verification"]:
        print(f"  ✓ {step} completed successfully")
    print("Pipeline ready.")

if __name__ == '__main__':
    main()
`,
                    },
                    'notes.md': {
                      name: 'notes.md',
                      type: 'file',
                      modified: now,
                      size: 190,
                      permissions: 'rw-r--r--',
                      content: `# Project Notes
- AI terminal runtime initialized
- Built-in sandboxed file navigation
- Maple reasoning integration ready
`,
                    },
                  },
                },
              },
            },
          },
        },
        maple: {
          name: 'maple',
          type: 'dir',
          modified: now,
          permissions: 'rwxr-xr-x',
          children: {
            identity: {
              name: 'identity',
              type: 'dir',
              modified: now,
              permissions: 'rwxr-xr-x',
              children: {
                'identity.md': {
                  name: 'identity.md',
                  type: 'file',
                  modified: now,
                  size: 210,
                  permissions: 'rw-r--r--',
                  content: `# Maple Identity
Maple is an integrated AI agent inside Convexity designed to inspect, authorize, and assist developer terminal actions with rigorous security protocols.
`,
                },
              },
            },
            system: {
              name: 'system',
              type: 'dir',
              modified: now,
              permissions: 'rwxr-xr-x',
              children: {
                'maple-instructions.md': {
                  name: 'maple-instructions.md',
                  type: 'file',
                  modified: now,
                  size: 340,
                  permissions: 'rw-r--r--',
                  content: `# Maple System Instructions
1. Always analyze command danger prior to execution when source=maple.
2. Require human approval for destructive operations (rm, format, raw disk, killall).
3. Provide reasoning snapshots and structured outputs.
`,
                },
              },
            },
            rules: {
              name: 'rules',
              type: 'dir',
              modified: now,
              permissions: 'rwxr-xr-x',
              children: {
                'rules.md': {
                  name: 'rules.md',
                  type: 'file',
                  modified: now,
                  size: 180,
                  permissions: 'rw-r--r--',
                  content: `# Maple Security Rules
- Dangerous patterns trigger explicit confirmation dialogs.
- Sandboxed paths must resolve strictly within root boundaries.
`,
                },
              },
            },
            workflows: {
              name: 'workflows',
              type: 'dir',
              modified: now,
              permissions: 'rwxr-xr-x',
              children: {
                'create-project.md': {
                  name: 'create-project.md',
                  type: 'file',
                  modified: now,
                  size: 140,
                  permissions: 'rw-r--r--',
                  content: `# Workflow: Create Project
Initializes standard directory layout and template configuration for Convexity apps.
`,
                },
                'deploy-project.md': {
                  name: 'deploy-project.md',
                  type: 'file',
                  modified: now,
                  size: 155,
                  permissions: 'rw-r--r--',
                  content: `# Workflow: Deploy Project
Packages project artifacts, runs pre-flight security checks, and deploys to target cloud.
`,
                },
                'train-model.md': {
                  name: 'train-model.md',
                  type: 'file',
                  modified: now,
                  size: 160,
                  permissions: 'rw-r--r--',
                  content: `# Workflow: Train Model
Connects dataset streams to Maple fine-tuning pipelines with GGUF export support.
`,
                },
              },
            },
          },
        },
        docs: {
          name: 'docs',
          type: 'dir',
          modified: now,
          permissions: 'rwxr-xr-x',
          children: {
            'architecture.md': {
              name: 'architecture.md',
              type: 'file',
              modified: now,
              size: 420,
              permissions: 'rw-r--r--',
              content: `# Convexity Architecture
User / Maple -> Terminal -> TerminalRuntime -> Session -> Executor -> Virtual OS.
Each session maintains independent state:
- Current Working Directory (CWD)
- Custom Environment Variables
- Command History & Aliases
- Background Process Management
`,
            },
            'maple.md': {
              name: 'maple.md',
              type: 'file',
              modified: now,
              size: 260,
              permissions: 'rw-r--r--',
              content: `# Maple AI Documentation
Maple acts as the copilot and security gatekeeper. Load via 'load maple', unload via 'kill maple'.
`,
            },
            'workflows.md': {
              name: 'workflows.md',
              type: 'file',
              modified: now,
              size: 220,
              permissions: 'rw-r--r--',
              content: `# Workflows Guide
Convexity includes automated developer workflows for testing, packaging, model training, and deployment.
`,
            },
          },
        },
        libraries: {
          name: 'libraries',
          type: 'dir',
          modified: now,
          permissions: 'rwxr-xr-x',
          children: {
            'registry.json': {
              name: 'registry.json',
              type: 'file',
              modified: now,
              size: 320,
              permissions: 'rw-r--r--',
              content: JSON.stringify(
                {
                  version: '1.0.0',
                  libraries: [
                    { name: 'convexity-core', version: '1.2.0', description: 'Core runtime primitives' },
                    { name: 'maple-bridge', version: '1.0.1', description: 'Maple reasoning protocol' },
                    { name: 'flow-runner', version: '0.9.4', description: 'Asynchronous task graph execution' }
                  ]
                },
                null,
                2
              ),
            },
            'README.md': {
              name: 'README.md',
              type: 'file',
              modified: now,
              size: 150,
              permissions: 'rw-r--r--',
              content: `# Convexity Libraries
Registry of installed plugins, models, and execution extensions.
`,
            },
          },
        },
        tools: {
          name: 'tools',
          type: 'dir',
          modified: now,
          permissions: 'rwxr-xr-x',
          children: {
            'registry.json': {
              name: 'registry.json',
              type: 'file',
              modified: now,
              size: 280,
              permissions: 'rw-r--r--',
              content: JSON.stringify(
                {
                  version: '1.0.0',
                  tools: [
                    { name: 'hex-inspector', command: 'hexview', description: 'Binary inspection tool' },
                    { name: 'model-quantizer', command: 'quantize', description: 'Quantize neural models to GGUF' }
                  ]
                },
                null,
                2
              ),
            },
          },
        },
      },
    };
  }

  // Path resolution
  public resolvePath(cwd: string, pathStr: string): string {
    let clean = pathStr.trim();
    if (clean === '~' || clean.startsWith('~/')) {
      clean = clean.replace(/^~/, '/home/user');
    }

    if (!clean.startsWith('/')) {
      const base = cwd.endsWith('/') ? cwd.slice(0, -1) : cwd;
      clean = `${base}/${clean}`;
    }

    // Normalize . and ..
    const parts = clean.split('/').filter(Boolean);
    const resolved: string[] = [];

    for (const part of parts) {
      if (part === '.') continue;
      if (part === '..') {
        resolved.pop();
      } else {
        resolved.push(part);
      }
    }

    return '/' + resolved.join('/');
  }

  private getNode(pathStr: string): FSNode | null {
    const parts = pathStr.split('/').filter(Boolean);
    let current: FSNode = this.root;

    for (const part of parts) {
      if (current.type !== 'dir') return null;
      const nextNode: FSNode | undefined = current.children[part];
      if (!nextNode) return null;
      current = nextNode;
    }

    return current;
  }

  public exists(pathStr: string): boolean {
    return this.getNode(pathStr) !== null;
  }

  public isDirectory(pathStr: string): boolean {
    const node = this.getNode(pathStr);
    return node !== null && node.type === 'dir';
  }

  public isFile(pathStr: string): boolean {
    const node = this.getNode(pathStr);
    return node !== null && node.type === 'file';
  }

  public listDirectory(pathStr: string, showHidden = false, recursive = false): string[] {
    const node = this.getNode(pathStr);
    if (!node) throw new Error(`ls: directory not found: ${pathStr}`);
    if (node.type !== 'dir') throw new Error(`ls: not a directory: ${pathStr}`);

    const results: string[] = [];

    const traverse = (dir: DirectoryNode, prefix: string) => {
      for (const [name, child] of Object.entries(dir.children)) {
        if (!showHidden && name.startsWith('.')) continue;

        const displayName = child.type === 'dir' ? `${prefix}${name}/` : `${prefix}${name}`;
        results.push(displayName);

        if (recursive && child.type === 'dir') {
          traverse(child, `${prefix}${name}/`);
        }
      }
    };

    traverse(node, '');
    return results.sort();
  }

  public readFile(pathStr: string): string {
    const node = this.getNode(pathStr);
    if (!node) throw new Error(`cat: ${pathStr}: No such file or directory`);
    if (node.type === 'dir') throw new Error(`cat: ${pathStr}: Is a directory`);
    return node.content;
  }

  public writeFile(pathStr: string, content: string): void {
    const parts = pathStr.split('/').filter(Boolean);
    if (parts.length === 0) throw new Error('Cannot write to root directory');

    const fileName = parts.pop()!;
    const dirPath = '/' + parts.join('/');
    const parent = this.getNode(dirPath);

    if (!parent) {
      throw new Error(`Directory does not exist: ${dirPath}`);
    }
    if (parent.type !== 'dir') {
      throw new Error(`Not a directory: ${dirPath}`);
    }

    const existing = parent.children[fileName];
    if (existing && existing.type === 'dir') {
      throw new Error(`Cannot overwrite directory with file: ${fileName}`);
    }

    const now = Date.now();
    parent.children[fileName] = {
      name: fileName,
      type: 'file',
      content,
      size: new TextEncoder().encode(content).length,
      modified: now,
      permissions: 'rw-r--r--',
    };
  }

  public appendFile(pathStr: string, content: string): void {
    const existing = this.getNode(pathStr);
    if (existing) {
      if (existing.type === 'dir') throw new Error(`${pathStr} is a directory`);
      this.writeFile(pathStr, existing.content + '\n' + content);
    } else {
      this.writeFile(pathStr, content);
    }
  }

  public touchFile(pathStr: string): void {
    const existing = this.getNode(pathStr);
    if (existing) {
      existing.modified = Date.now();
      return;
    }
    this.writeFile(pathStr, '');
  }

  public makeDirectory(pathStr: string, parents = true): void {
    const parts = pathStr.split('/').filter(Boolean);
    if (parts.length === 0) return;

    let current: DirectoryNode = this.root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      let nextNode: FSNode | undefined = current.children[part];

      if (!nextNode) {
        if (!parents && i < parts.length - 1) {
          throw new Error(`Cannot create directory '${pathStr}': No such file or directory`);
        }
        const newDir: DirectoryNode = {
          name: part,
          type: 'dir',
          children: {},
          modified: Date.now(),
          permissions: 'rwxr-xr-x',
        };
        current.children[part] = newDir;
        nextNode = newDir;
      } else if (nextNode.type !== 'dir') {
        throw new Error(`File exists: ${part}`);
      }

      current = nextNode as DirectoryNode;
    }
  }

  public deletePath(pathStr: string, recursive = false): void {
    if (pathStr === '/' || pathStr === '') {
      throw new Error('rm: cannot remove root directory');
    }

    const parts = pathStr.split('/').filter(Boolean);
    const targetName = parts.pop()!;
    const parentPath = '/' + parts.join('/');
    const parent = this.getNode(parentPath);

    if (!parent || parent.type !== 'dir') {
      throw new Error(`rm: cannot remove '${pathStr}': No such file or directory`);
    }

    const target = parent.children[targetName];
    if (!target) {
      throw new Error(`rm: cannot remove '${pathStr}': No such file or directory`);
    }

    if (target.type === 'dir' && !recursive) {
      throw new Error(`rm: cannot remove '${pathStr}': Is a directory (use -r)`);
    }

    delete parent.children[targetName];
  }

  public copyPath(sourceStr: string, destStr: string): void {
    const sourceNode = this.getNode(sourceStr);
    if (!sourceNode) throw new Error(`cp: cannot stat '${sourceStr}': No such file or directory`);

    if (sourceNode.type === 'file') {
      let finalDest = destStr;
      if (this.isDirectory(destStr)) {
        const sourceName = sourceStr.split('/').filter(Boolean).pop()!;
        finalDest = this.resolvePath(destStr, sourceName);
      }
      this.writeFile(finalDest, sourceNode.content);
    } else {
      throw new Error('cp: directory recursive copy not implemented in sample');
    }
  }

  public movePath(sourceStr: string, destStr: string): void {
    this.copyPath(sourceStr, destStr);
    this.deletePath(sourceStr, true);
  }

  public searchFiles(startPath: string, pattern: string): string[] {
    const node = this.getNode(startPath);
    if (!node || node.type !== 'dir') return [];

    const results: string[] = [];
    const regex = new RegExp(
      '^' + pattern.replace(/\./g, '\\.').replace(/\*/g, '.*').replace(/\?/g, '.') + '$'
    );

    const traverse = (dir: DirectoryNode, currentPath: string) => {
      for (const [name, child] of Object.entries(dir.children)) {
        const full = `${currentPath}/${name}`;
        if (regex.test(name)) {
          results.push(full);
        }
        if (child.type === 'dir') {
          traverse(child, full);
        }
      }
    };

    traverse(node, startPath === '/' ? '' : startPath);
    return results;
  }

  public findText(startPath: string, query: string): Array<{ path: string; line: number; text: string }> {
    const node = this.getNode(startPath);
    if (!node) return [];

    const results: Array<{ path: string; line: number; text: string }> = [];

    const searchInFile = (file: FileNode, filePath: string) => {
      const lines = file.content.split('\n');
      lines.forEach((line, index) => {
        if (line.includes(query)) {
          results.push({
            path: filePath,
            line: index + 1,
            text: line.trim(),
          });
        }
      });
    };

    const traverse = (dir: DirectoryNode, currentPath: string) => {
      for (const [name, child] of Object.entries(dir.children)) {
        const full = `${currentPath}/${name}`;
        if (child.type === 'file') {
          searchInFile(child, full);
        } else {
          traverse(child, full);
        }
      }
    };

    if (node.type === 'file') {
      searchInFile(node, startPath);
    } else {
      traverse(node, startPath === '/' ? '' : startPath);
    }

    return results;
  }

  public getStat(pathStr: string): FileStat {
    const node = this.getNode(pathStr);
    if (!node) throw new Error(`stat: cannot stat '${pathStr}': No such file or directory`);

    const name = pathStr.split('/').filter(Boolean).pop() || '/';
    return {
      path: pathStr,
      name,
      type: node.type === 'dir' ? 'directory' : 'file',
      size: node.type === 'file' ? node.size : 4096,
      modified: new Date(node.modified).toISOString(),
      permissions: node.permissions || (node.type === 'dir' ? 'rwxr-xr-x' : 'rw-r--r--'),
      hidden: name.startsWith('.'),
    };
  }
}

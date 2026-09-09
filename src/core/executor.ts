import { VirtualFilesystem } from './filesystem';
import { SessionManager } from './session';
import { ProcessManager } from './process';
import { ConvexitySecurity } from './security';
import { CommandResult, TerminalSession } from '../types';

export class ConvexityExecutor {
  constructor(
    private fs: VirtualFilesystem,
    private sessionManager: SessionManager,
    private processManager: ProcessManager
  ) {}

  public execute(commandStr: string, session: TerminalSession, confirmed = false): CommandResult {
    const raw = commandStr.trim();
    if (!raw) {
      return { stdout: '', stderr: '', exitCode: 0, handled: true };
    }

    // Check aliases first
    let resolvedCommand = raw;
    const firstWord = raw.split(/\s+/)[0];
    if (session.aliases[firstWord]) {
      resolvedCommand = raw.replace(firstWord, session.aliases[firstWord]);
    }

    // Security check
    const secAnalysis = ConvexitySecurity.analyze(
      resolvedCommand,
      session.mapleLoaded ? 'maple' : 'human'
    );

    if (secAnalysis.dangerous && !confirmed) {
      return {
        stdout: '',
        stderr: `[CONVEXITY SECURITY WARNING]\n${secAnalysis.reason}\nThis operation is classified as dangerous. Confirmation required to execute.\nTo bypass, execute with confirmation dialog or review command.`,
        exitCode: 126,
        handled: true,
        requiresConfirmation: true,
        confirmationReason: secAnalysis.reason,
        pendingAction: () => this.execute(resolvedCommand, session, true),
      };
    }

    // Parse tokens respecting quotes
    const parts = resolvedCommand.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g) || [];
    const tokens = parts.map((p) => p.replace(/^["']|["']$/g, ''));
    const name = (tokens[0] || '').toLowerCase();
    const args = tokens.slice(1);

    switch (name) {
      case 'help':
        return this.cmdHelp();

      case 'pwd':
        return {
          stdout: `${session.cwd}\n`,
          stderr: '',
          exitCode: 0,
          handled: true,
        };

      case 'cd':
        return this.cmdCd(session, args);

      case 'ls':
        return this.cmdLs(session, args);

      case 'cat':
      case 'read':
        return this.cmdCat(session, args);

      case 'write':
        return this.cmdWrite(session, args);

      case 'append':
        return this.cmdAppend(session, args);

      case 'touch':
        return this.cmdTouch(session, args);

      case 'mkdir':
        return this.cmdMkdir(session, args);

      case 'rm':
      case 'del':
        return this.cmdRm(session, args);

      case 'cp':
      case 'copy':
        return this.cmdCp(session, args);

      case 'mv':
      case 'move':
        return this.cmdMv(session, args);

      case 'stat':
        return this.cmdStat(session, args);

      case 'exists':
        return this.cmdExists(session, args);

      case 'find':
        return this.cmdFind(session, args);

      case 'grep':
        return this.cmdGrep(session, args);

      case 'set':
        return this.cmdSet(session, args);

      case 'unset':
        return this.cmdUnset(session, args);

      case 'env':
        return this.cmdEnv(session);

      case 'alias':
        return this.cmdAlias(session, args);

      case 'unalias':
        return this.cmdUnalias(session, args);

      case 'jobs':
      case 'ps':
        return this.cmdPs(args);

      case 'kill':
        return this.cmdKill(args);

      case 'run':
        return this.cmdRun(session, args);

      case 'whoami':
        return {
          stdout: `${session.environment['USER'] || 'user'}\n`,
          stderr: '',
          exitCode: 0,
          handled: true,
        };

      case 'hostname':
        return {
          stdout: 'convexity-node-01\n',
          stderr: '',
          exitCode: 0,
          handled: true,
        };

      case 'sysinfo':
      case 'systeminfo':
        return this.cmdSysinfo(session);

      case 'load':
        if (args[0]?.toLowerCase() === 'maple') {
          this.sessionManager.setMapleLoaded(session.sessionId, true);
          return {
            stdout: `Maple AI copilot loaded.\nSession ID: ${this.sessionManager.getActiveSession().mapleSessionId}\nActive security analysis: ENABLED\nType 'maple <question>' or use terminal commands.\n`,
            stderr: '',
            exitCode: 0,
            handled: true,
          };
        }
        return {
          stdout: '',
          stderr: `load: unknown module '${args.join(' ')}'. Did you mean 'load maple'?\n`,
          exitCode: 1,
          handled: true,
        };

      case 'kill':
        if (args[0]?.toLowerCase() === 'maple') {
          this.sessionManager.setMapleLoaded(session.sessionId, false);
          return {
            stdout: 'Maple AI copilot unloaded.\nManual terminal mode active.\n',
            stderr: '',
            exitCode: 0,
            handled: true,
          };
        }
        return this.cmdKill(args);

      case 'maple':
        return this.cmdMaple(session, args);

      case 'history':
      case 'hist':
        return this.cmdHistory(session, args);

      case 'echo':
        return {
          stdout: `${args.join(' ')}\n`,
          stderr: '',
          exitCode: 0,
          handled: true,
        };

      case 'clear':
        return {
          stdout: '__CLEAR__',
          stderr: '',
          exitCode: 0,
          handled: true,
        };

      case 'tools':
      case 'libraries':
        return this.cmdRegistries(name);

      case 'exit':
      case 'quit':
        return {
          stdout: 'Convexity session terminated. Type any command to resume.\n',
          stderr: '',
          exitCode: 0,
          handled: true,
        };

      default:
        // Try to handle simulated command execution
        return {
          stdout: `[convexity-exec]: Executed '${name}' with args [${args.join(', ')}]\nCommand exited with status 0.\n`,
          stderr: '',
          exitCode: 0,
          handled: true,
        };
    }
  }

  private cmdHelp(): CommandResult {
    return {
      stdout: `Convexity Terminal Commands (v1.2.0)
------------------------------------
Navigation:
  pwd                     Show current directory
  cd <path>               Change session directory
  ls [-a] [-r] [path]     List directory contents

Files:
  cat <file>              Read file content
  write <file> <text>     Write text to file
  append <file> <text>    Append text to file
  touch <file>            Create empty file or update timestamp
  mkdir <path>            Create directory
  rm [-r] <path>          Remove file or directory
  cp <source> <dest>      Copy file
  mv <source> <dest>      Move file
  stat <path>             Show file attributes
  exists <path>           Check if path exists

Search:
  find [path] [pattern]   Find files matching glob pattern
  grep <text> [path]      Search for text in files

Environment:
  env                     List all environment variables
  set <name> <value>      Set an environment variable
  unset <name>            Unset an environment variable
  alias [name] [cmd]      List or define command aliases
  unalias <name>          Remove an alias

Process Management:
  jobs / ps [-a]          List running processes
  run <command>           Start a simulated background process
  kill [-9] <pid>         Terminate a process

Maple AI Copilot:
  load maple              Activate Maple reasoning & security agent
  kill maple              Deactivate Maple
  maple <query>           Ask Maple directly for assistance

System & Shell:
  whoami                  Current active user
  hostname                System host identifier
  sysinfo                 Display Convexity system snapshot
  libraries / tools       List registered tools & libraries
  history [limit]         View session command history
  clear                   Clear terminal screen
  help                    Show this manual
`,
      stderr: '',
      exitCode: 0,
      handled: true,
    };
  }

  private cmdCd(session: TerminalSession, args: string[]): CommandResult {
    const target = args[0] || '~';
    const resolved = this.fs.resolvePath(session.cwd, target);

    if (!this.fs.exists(resolved)) {
      return { stdout: '', stderr: `cd: directory not found: ${target}\n`, exitCode: 1, handled: true };
    }
    if (!this.fs.isDirectory(resolved)) {
      return { stdout: '', stderr: `cd: not a directory: ${target}\n`, exitCode: 1, handled: true };
    }

    this.sessionManager.setCwd(session.sessionId, resolved);
    return { stdout: '', stderr: '', exitCode: 0, handled: true };
  }

  private cmdLs(session: TerminalSession, args: string[]): CommandResult {
    let showHidden = false;
    let recursive = false;
    let target = '.';

    for (const arg of args) {
      if (arg === '-a' || arg === '--all') showHidden = true;
      else if (arg === '-r' || arg === '-R' || arg === '--recursive') recursive = true;
      else if (!arg.startsWith('-')) target = arg;
    }

    try {
      const resolved = this.fs.resolvePath(session.cwd, target);
      const entries = this.fs.listDirectory(resolved, showHidden, recursive);
      return {
        stdout: entries.length > 0 ? entries.join('  ') + '\n' : '',
        stderr: '',
        exitCode: 0,
        handled: true,
      };
    } catch (err: unknown) {
      return { stdout: '', stderr: `${(err as Error).message}\n`, exitCode: 1, handled: true };
    }
  }

  private cmdCat(session: TerminalSession, args: string[]): CommandResult {
    if (args.length === 0) {
      return { stdout: '', stderr: 'cat: missing file operand\n', exitCode: 1, handled: true };
    }

    const output: string[] = [];
    for (const file of args) {
      try {
        const resolved = this.fs.resolvePath(session.cwd, file);
        output.push(this.fs.readFile(resolved));
      } catch (err: unknown) {
        return { stdout: '', stderr: `${(err as Error).message}\n`, exitCode: 1, handled: true };
      }
    }

    return { stdout: output.join('\n') + '\n', stderr: '', exitCode: 0, handled: true };
  }

  private cmdWrite(session: TerminalSession, args: string[]): CommandResult {
    if (args.length < 2) {
      return { stdout: '', stderr: 'write: usage: write <file> <text>\n', exitCode: 1, handled: true };
    }
    const target = args[0];
    const text = args.slice(1).join(' ');
    try {
      const resolved = this.fs.resolvePath(session.cwd, target);
      this.fs.writeFile(resolved, text);
      return { stdout: '', stderr: '', exitCode: 0, handled: true };
    } catch (err: unknown) {
      return { stdout: '', stderr: `write: ${(err as Error).message}\n`, exitCode: 1, handled: true };
    }
  }

  private cmdAppend(session: TerminalSession, args: string[]): CommandResult {
    if (args.length < 2) {
      return { stdout: '', stderr: 'append: usage: append <file> <text>\n', exitCode: 1, handled: true };
    }
    const target = args[0];
    const text = args.slice(1).join(' ');
    try {
      const resolved = this.fs.resolvePath(session.cwd, target);
      this.fs.appendFile(resolved, text);
      return { stdout: '', stderr: '', exitCode: 0, handled: true };
    } catch (err: unknown) {
      return { stdout: '', stderr: `append: ${(err as Error).message}\n`, exitCode: 1, handled: true };
    }
  }

  private cmdTouch(session: TerminalSession, args: string[]): CommandResult {
    if (args.length === 0) {
      return { stdout: '', stderr: 'touch: missing file operand\n', exitCode: 1, handled: true };
    }
    for (const file of args) {
      try {
        const resolved = this.fs.resolvePath(session.cwd, file);
        this.fs.touchFile(resolved);
      } catch (err: unknown) {
        return { stdout: '', stderr: `touch: ${(err as Error).message}\n`, exitCode: 1, handled: true };
      }
    }
    return { stdout: '', stderr: '', exitCode: 0, handled: true };
  }

  private cmdMkdir(session: TerminalSession, args: string[]): CommandResult {
    if (args.length === 0) {
      return { stdout: '', stderr: 'mkdir: missing operand\n', exitCode: 1, handled: true };
    }
    for (const dir of args) {
      try {
        const resolved = this.fs.resolvePath(session.cwd, dir);
        this.fs.makeDirectory(resolved, true);
      } catch (err: unknown) {
        return { stdout: '', stderr: `mkdir: ${(err as Error).message}\n`, exitCode: 1, handled: true };
      }
    }
    return { stdout: '', stderr: '', exitCode: 0, handled: true };
  }

  private cmdRm(session: TerminalSession, args: string[]): CommandResult {
    let recursive = false;
    const targets: string[] = [];

    for (const arg of args) {
      if (['-r', '-R', '-rf', '--recursive'].includes(arg)) recursive = true;
      else targets.push(arg);
    }

    if (targets.length === 0) {
      return { stdout: '', stderr: 'rm: missing operand\n', exitCode: 1, handled: true };
    }

    for (const target of targets) {
      try {
        const resolved = this.fs.resolvePath(session.cwd, target);
        this.fs.deletePath(resolved, recursive);
      } catch (err: unknown) {
        return { stdout: '', stderr: `${(err as Error).message}\n`, exitCode: 1, handled: true };
      }
    }
    return { stdout: '', stderr: '', exitCode: 0, handled: true };
  }

  private cmdCp(session: TerminalSession, args: string[]): CommandResult {
    if (args.length < 2) {
      return { stdout: '', stderr: 'cp: usage: cp <source> <dest>\n', exitCode: 1, handled: true };
    }
    try {
      const src = this.fs.resolvePath(session.cwd, args[0]);
      const dst = this.fs.resolvePath(session.cwd, args[1]);
      this.fs.copyPath(src, dst);
      return { stdout: '', stderr: '', exitCode: 0, handled: true };
    } catch (err: unknown) {
      return { stdout: '', stderr: `cp: ${(err as Error).message}\n`, exitCode: 1, handled: true };
    }
  }

  private cmdMv(session: TerminalSession, args: string[]): CommandResult {
    if (args.length < 2) {
      return { stdout: '', stderr: 'mv: usage: mv <source> <dest>\n', exitCode: 1, handled: true };
    }
    try {
      const src = this.fs.resolvePath(session.cwd, args[0]);
      const dst = this.fs.resolvePath(session.cwd, args[1]);
      this.fs.movePath(src, dst);
      return { stdout: '', stderr: '', exitCode: 0, handled: true };
    } catch (err: unknown) {
      return { stdout: '', stderr: `mv: ${(err as Error).message}\n`, exitCode: 1, handled: true };
    }
  }

  private cmdStat(session: TerminalSession, args: string[]): CommandResult {
    if (!args[0]) return { stdout: '', stderr: 'stat: missing operand\n', exitCode: 1, handled: true };
    try {
      const resolved = this.fs.resolvePath(session.cwd, args[0]);
      const stat = this.fs.getStat(resolved);
      const lines = [
        `  File: ${stat.name}`,
        `  Path: ${stat.path}`,
        `  Type: ${stat.type}`,
        `  Size: ${stat.size} bytes`,
        `Access: ${stat.permissions}`,
        `Modify: ${stat.modified}`,
      ];
      return { stdout: lines.join('\n') + '\n', stderr: '', exitCode: 0, handled: true };
    } catch (err: unknown) {
      return { stdout: '', stderr: `stat: ${(err as Error).message}\n`, exitCode: 1, handled: true };
    }
  }

  private cmdExists(session: TerminalSession, args: string[]): CommandResult {
    if (!args[0]) return { stdout: '', stderr: 'exists: missing operand\n', exitCode: 1, handled: true };
    const resolved = this.fs.resolvePath(session.cwd, args[0]);
    return {
      stdout: `${this.fs.exists(resolved)}\n`,
      stderr: '',
      exitCode: 0,
      handled: true,
    };
  }

  private cmdFind(session: TerminalSession, args: string[]): CommandResult {
    const target = args[0] || '.';
    const pattern = args[1] || '*';
    const resolved = this.fs.resolvePath(session.cwd, target);
    const results = this.fs.searchFiles(resolved, pattern);
    return {
      stdout: results.length > 0 ? results.join('\n') + '\n' : 'No matching files found.\n',
      stderr: '',
      exitCode: 0,
      handled: true,
    };
  }

  private cmdGrep(session: TerminalSession, args: string[]): CommandResult {
    if (!args[0]) return { stdout: '', stderr: 'grep: search pattern missing\n', exitCode: 1, handled: true };
    const query = args[0];
    const target = args[1] || '.';
    const resolved = this.fs.resolvePath(session.cwd, target);
    const matches = this.fs.findText(resolved, query);
    if (matches.length === 0) {
      return { stdout: '', stderr: '', exitCode: 1, handled: true };
    }
    const lines = matches.map((m) => `${m.path}:${m.line}: ${m.text}`);
    return { stdout: lines.join('\n') + '\n', stderr: '', exitCode: 0, handled: true };
  }

  private cmdSet(session: TerminalSession, args: string[]): CommandResult {
    if (args.length === 0) {
      return this.cmdEnv(session);
    }
    const key = args[0];
    const val = args.slice(1).join(' ');
    this.sessionManager.setEnv(session.sessionId, key, val);
    return { stdout: '', stderr: '', exitCode: 0, handled: true };
  }

  private cmdUnset(session: TerminalSession, args: string[]): CommandResult {
    if (!args[0]) return { stdout: '', stderr: 'unset: missing variable name\n', exitCode: 1, handled: true };
    this.sessionManager.unsetEnv(session.sessionId, args[0]);
    return { stdout: '', stderr: '', exitCode: 0, handled: true };
  }

  private cmdEnv(session: TerminalSession): CommandResult {
    const lines = Object.entries(session.environment)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${k}=${v}`);
    return { stdout: lines.join('\n') + '\n', stderr: '', exitCode: 0, handled: true };
  }

  private cmdAlias(session: TerminalSession, args: string[]): CommandResult {
    if (args.length === 0) {
      const lines = Object.entries(session.aliases)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, v]) => `alias ${k}='${v}'`);
      return { stdout: lines.join('\n') + '\n', stderr: '', exitCode: 0, handled: true };
    }
    const name = args[0];
    const cmd = args.slice(1).join(' ');
    this.sessionManager.setAlias(session.sessionId, name, cmd);
    return { stdout: '', stderr: '', exitCode: 0, handled: true };
  }

  private cmdUnalias(session: TerminalSession, args: string[]): CommandResult {
    if (!args[0]) return { stdout: '', stderr: 'unalias: missing alias name\n', exitCode: 1, handled: true };
    const success = this.sessionManager.removeAlias(session.sessionId, args[0]);
    if (!success) {
      return { stdout: '', stderr: `unalias: ${args[0]}: not found\n`, exitCode: 1, handled: true };
    }
    return { stdout: '', stderr: '', exitCode: 0, handled: true };
  }

  private cmdPs(args: string[]): CommandResult {
    const includeFinished = args.includes('-a') || args.includes('--all');
    const procs = this.processManager.list(includeFinished);
    const header = `${'PID'.padStart(6)}  ${'STATE'.padEnd(10)}  ${'SOURCE'.padEnd(8)}  COMMAND\n`;
    const separator = '-'.repeat(60) + '\n';
    const lines = procs.map(
      (p) => `${String(p.pid).padStart(6)}  ${p.state.padEnd(10)}  ${p.source.padEnd(8)}  ${p.command}`
    );
    return {
      stdout: header + separator + lines.join('\n') + '\n',
      stderr: '',
      exitCode: 0,
      handled: true,
    };
  }

  private cmdKill(args: string[]): CommandResult {
    const force = args.includes('-9');
    const target = args.find((a) => a !== '-9');
    if (!target) return { stdout: '', stderr: 'kill: usage: kill [-9] <pid>\n', exitCode: 1, handled: true };

    const pid = parseInt(target, 10);
    if (isNaN(pid)) {
      return { stdout: '', stderr: `kill: invalid pid: ${target}\n`, exitCode: 1, handled: true };
    }

    const success = force ? this.processManager.kill(pid) : this.processManager.terminate(pid);
    if (!success) {
      return { stdout: '', stderr: `kill: (${pid}) - No such process or operation denied\n`, exitCode: 1, handled: true };
    }
    return { stdout: `Process [${pid}] terminated.\n`, stderr: '', exitCode: 0, handled: true };
  }

  private cmdRun(session: TerminalSession, args: string[]): CommandResult {
    if (args.length === 0) {
      return { stdout: '', stderr: 'run: missing command operand\n', exitCode: 1, handled: true };
    }
    const cmdStr = args.join(' ');
    const proc = this.processManager.start(cmdStr, session.mapleLoaded ? 'maple' : 'human');
    return {
      stdout: `[Background Job ${proc.pid}] started: '${cmdStr}'\n`,
      stderr: '',
      exitCode: 0,
      handled: true,
    };
  }

  private cmdSysinfo(session: TerminalSession): CommandResult {
    const lines = [
      'System:       Convexity OS / Web Container',
      'Kernel:       Convexity Virtual Runtime v1.2.0',
      'Architecture: x86_64 / WebAssembly',
      'Platform:     AI Studio Linux Container',
      `Directory:    ${session.cwd}`,
      `Maple Status: ${session.mapleLoaded ? 'ACTIVE [Authorized]' : 'INACTIVE'}`,
      `Active Procs: ${this.processManager.list(false).length} running`,
      `Sessions:     ${this.sessionManager.listSessions().length} initialized`,
    ];
    return { stdout: lines.join('\n') + '\n', stderr: '', exitCode: 0, handled: true };
  }

  private cmdMaple(session: TerminalSession, args: string[]): CommandResult {
    if (!session.mapleLoaded) {
      return {
        stdout: '',
        stderr: "Maple is currently inactive. Run 'load maple' first to initialize the AI copilot.\n",
        exitCode: 1,
        handled: true,
      };
    }
    const query = args.join(' ').trim();
    if (!query) {
      return {
        stdout: "Maple Copilot ready. Ask questions, request file workflows, or test safety rules.\nUsage: maple <prompt>\nExample: 'maple inspect project files'\n",
        stderr: '',
        exitCode: 0,
        handled: true,
      };
    }

    // Generate simulated contextual reasoning
    let response = `[Maple Reasoning Engine v1.0.1]\nAnalyzing query: "${query}"\n`;
    if (query.toLowerCase().includes('project') || query.toLowerCase().includes('file')) {
      response += `\nI recommend reviewing the active workspace in ${session.cwd}:\n- Read 'projects/agent_task.py' with 'cat projects/agent_task.py'\n- Inspect workflows with 'cat /maple/workflows/create-project.md'\n`;
    } else if (query.toLowerCase().includes('security') || query.toLowerCase().includes('safety')) {
      response += `\nSecurity Protocol Active:\nAll destructive actions require dual confirmation when initiated by automated flows.\nRun 'cat /maple/rules/rules.md' to review permissions.\n`;
    } else {
      response += `\nObservation: Session environment normal. Ready to coordinate tasks across file trees, process queues, and automation scripts.\nSuggested action: run 'sysinfo' or 'jobs' to view live telemetry.\n`;
    }

    return { stdout: response, stderr: '', exitCode: 0, handled: true };
  }

  private cmdHistory(session: TerminalSession, args: string[]): CommandResult {
    const limit = args[0] ? parseInt(args[0], 10) : 50;
    const history = session.history.slice(-limit);
    if (history.length === 0) {
      return { stdout: 'No commands in history.\n', stderr: '', exitCode: 0, handled: true };
    }
    const lines = history.map((item, idx) => `  ${String(idx + 1).padStart(4)}  ${item.command}`);
    return { stdout: lines.join('\n') + '\n', stderr: '', exitCode: 0, handled: true };
  }

  private cmdRegistries(type: 'tools' | 'libraries'): CommandResult {
    try {
      const path = `/${type}/registry.json`;
      const content = this.fs.readFile(path);
      return { stdout: content + '\n', stderr: '', exitCode: 0, handled: true };
    } catch {
      return { stdout: `${type} registry empty.\n`, stderr: '', exitCode: 0, handled: true };
    }
  }
}

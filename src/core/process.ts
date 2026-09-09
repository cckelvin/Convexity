import { ProcessItem } from '../types';

export class ProcessManager {
  private processes: Map<number, ProcessItem> = new Map();
  private nextPid = 100;

  constructor() {
    // Seed initial system daemon processes
    this.processes.set(1, {
      pid: 1,
      command: 'convexity-init',
      state: 'running',
      startedAt: Date.now() - 3600000,
      source: 'system',
    });
    this.processes.set(2, {
      pid: 2,
      command: 'convexity-runtime-daemon',
      state: 'running',
      startedAt: Date.now() - 3500000,
      source: 'system',
    });
  }

  public list(includeFinished = false): ProcessItem[] {
    const list = Array.from(this.processes.values());
    if (!includeFinished) {
      return list.filter((p) => p.state === 'running');
    }
    return list;
  }

  public start(command: string, source: 'human' | 'maple' | 'system' = 'human'): ProcessItem {
    const pid = this.nextPid++;
    const proc: ProcessItem = {
      pid,
      command,
      state: 'running',
      startedAt: Date.now(),
      source,
    };
    this.processes.set(pid, proc);
    return proc;
  }

  public terminate(pid: number): boolean {
    const proc = this.processes.get(pid);
    if (!proc || proc.state !== 'running') return false;
    if (pid === 1) return false; // Protected init
    proc.state = 'stopped';
    return true;
  }

  public kill(pid: number): boolean {
    const proc = this.processes.get(pid);
    if (!proc || proc.state !== 'running') return false;
    if (pid === 1) return false;
    proc.state = 'killed';
    return true;
  }

  public get(pid: number): ProcessItem | undefined {
    return this.processes.get(pid);
  }
}

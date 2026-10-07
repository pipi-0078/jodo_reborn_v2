/** Reduce work behind the entrance overlay; keep the normal refresh rate inside. */
export class FrameScheduler {
  private pending = 0;
  private wasInside = false;

  step(delta: number, inside: boolean, hidden: boolean): number | null {
    if (hidden) {
      this.pending = 0;
      return null;
    }
    const changed = inside !== this.wasInside;
    this.wasInside = inside;
    // Bound long stalls, but retain elapsed time across intentionally skipped frames.
    this.pending += Math.min(Math.max(delta, 0), 0.05);
    if (!inside && !changed && this.pending + 1e-6 < 0.1) return null;
    const elapsed = this.pending;
    this.pending = 0;
    return elapsed;
  }
}

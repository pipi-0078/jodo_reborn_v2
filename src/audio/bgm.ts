const QUIET_GAIN = 0.18;
const FADE_IN_SECONDS = 4;
const FADE_OUT_SECONDS = 2;

/** One streaming player. Entry gestures unlock playback; confirmed entry makes it audible. */
export class AmbientBgm {
  private readonly audio: HTMLAudioElement;
  private context: AudioContext | null = null;
  private source: MediaElementAudioSourceNode | null = null;
  private gain: GainNode | null = null;
  private connected = false;
  private active = false;
  private starting = false;
  private generation = 0;
  private pauseTimer: ReturnType<typeof setTimeout> | undefined;
  private envelope = { from: 0, to: 0, start: 0, end: 0 };

  constructor(url: string, private readonly onError?: () => void) {
    this.audio = new Audio(url);
    this.audio.loop = true; // 音源自体の冒頭・末尾のフェードを保って繰り返す。
    this.audio.preload = 'none';
    // Never fall back to full-volume playback if Web Audio is unavailable.
    this.audio.muted = true;
    this.audio.addEventListener('error', () => this.fail());
  }

  /** Call directly in the entry button's click handler, before any await. */
  prepare(): void {
    try {
      if (!this.connected) {
        const AudioContextClass = window.AudioContext ??
          (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
        if (!AudioContextClass) throw new Error('Web Audio is unavailable');
        this.context ??= new AudioContextClass();
        this.gain ??= this.context.createGain();
        this.gain.gain.value = 0;
        this.source ??= this.context.createMediaElementSource(this.audio);
        this.source.connect(this.gain);
        this.gain.connect(this.context.destination);
        this.connected = true;
        this.audio.muted = false;
      }
      if (this.audio.error) this.audio.load();
      this.start();
    } catch {
      this.fail();
    }
  }

  setActive(active: boolean): void {
    if (active && this.active) return;
    this.active = active;
    this.clearPauseTimer();
    if (!this.connected) return;

    if (active) {
      this.start();
    } else {
      this.fadeTo(0, FADE_OUT_SECONDS);
      this.pauseTimer = setTimeout(() => this.stopImmediately(), FADE_OUT_SECONDS * 1000);
    }
  }

  /** Page teardown cannot reliably wait for a fade or a timer. */
  stopImmediately(): void {
    this.active = false;
    this.generation++;
    this.starting = false;
    this.clearPauseTimer();
    this.fadeTo(0, 0);
    this.audio.pause();
  }

  private start(): void {
    if (this.starting || !this.context) return;
    this.starting = true;
    const generation = ++this.generation;
    // Both APIs must be invoked synchronously while prepare() has user activation.
    const invoke = (action: () => Promise<void>): Promise<void> => {
      try { return action(); } catch (error) { return Promise.reject(error); }
    };
    void Promise.all([
      invoke(() => this.context!.resume()),
      invoke(() => this.audio.play()),
    ]).then(() => {
      if (generation !== this.generation) return;
      this.starting = false;
      if (this.active) {
        this.fadeTo(QUIET_GAIN, FADE_IN_SECONDS);
      } else if (this.pauseTimer === undefined) {
        // Entry may have failed or playback may finish preparing before pointer lock.
        this.stopImmediately();
      }
    }, () => {
      if (generation === this.generation) this.fail();
    });
  }

  private fadeTo(target: number, seconds: number): void {
    if (!this.context || !this.gain) return;
    const now = this.context.currentTime;
    const { from, to, start, end } = this.envelope;
    const progress = end > start ? Math.min(1, Math.max(0, (now - start) / (end - start))) : 1;
    const current = from + (to - from) * progress;
    const parameter = this.gain.gain;
    // Track the envelope ourselves so interrupted ramps also work without cancelAndHoldAtTime.
    parameter.cancelScheduledValues(now);
    parameter.setValueAtTime(seconds > 0 ? current : target, now);
    if (seconds > 0) parameter.linearRampToValueAtTime(target, now + seconds);
    this.envelope = { from: seconds > 0 ? current : target, to: target, start: now, end: now + seconds };
  }

  private clearPauseTimer(): void {
    if (this.pauseTimer !== undefined) clearTimeout(this.pauseTimer);
    this.pauseTimer = undefined;
  }

  private fail(): void {
    this.stopImmediately();
    this.onError?.();
  }
}

import type { Scene } from 'three';
export function createWorldPeacock(scene: Scene): Promise<{ update(dt: number): void }>;

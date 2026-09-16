import type { Scene, Object3D } from 'three';
export function createWorldPeacock(scene: Scene): Promise<{ bird: Object3D; update(dt: number): void }>;

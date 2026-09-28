export interface FlightArea {
  radius: number;
  radialRange: number;
  height: number;
  heightRange: number;
}

/** A bounded, continuously varying flight route. No waypoint snaps or resets. */
export function sampleFlight(time: number, area: FlightArea) {
  const t = time;
  const angle = -0.32 + 0.09 * t
    + 0.015 / 0.041 * (1 - Math.cos(0.041 * t))
    + 0.008 / 0.11 * (Math.sin(0.11 * t + 0.7) - Math.sin(0.7));
  const angularSpeed = 0.09 + 0.015 * Math.sin(0.041 * t) + 0.008 * Math.cos(0.11 * t + 0.7);
  const radius = area.radius + area.radialRange * (0.67 * Math.sin(0.13 * t) + 0.33 * Math.sin(0.071 * t + 0.8));
  const radialSpeed = area.radialRange * (0.67 * 0.13 * Math.cos(0.13 * t) + 0.33 * 0.071 * Math.cos(0.071 * t + 0.8));
  const x = radius * Math.cos(angle);
  const z = radius * Math.sin(angle);
  const y = area.height + area.heightRange * (0.72 * Math.sin(0.095 * t + 0.2) + 0.28 * Math.sin(0.173 * t));
  const dx = radialSpeed * Math.cos(angle) - radius * Math.sin(angle) * angularSpeed;
  const dz = radialSpeed * Math.sin(angle) + radius * Math.cos(angle) * angularSpeed;
  // The approved model faces +X. Yaw only keeps its body and stroke level.
  return { x, y, z, yaw: Math.atan2(-dz, dx), speed: Math.hypot(dx, dz) };
}

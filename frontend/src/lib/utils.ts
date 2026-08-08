/** General-purpose UI utilities – expanded in Phase 6. */

import { type ClassValue, clsx } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

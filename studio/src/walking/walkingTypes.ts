// Mirrors creature_forge.walking. Outcomes come from committed R2 records; replays are fresh deterministic MuJoCo rollouts.
import type { LocomotionReplay } from '../locomotion/locoTypes'

export interface SeedOutcome { label: string; walking: boolean; fall_time: number | null }
export interface WalkingSummary {
  n: number
  incumbent_walking: number
  winner_walking: number
  paired: { both: number; winner_only: number; incumbent_only: number; neither: number }
  seeds: { seed: number; incumbent: SeedOutcome; winner: SeedOutcome }[]
  featured: number[]
  controllers: Record<string, string>
  duration: number
  provenance: { protocol_commit: string; selection_commit: string; winner_source: string; evidence_platform?: string; note: string }
  attribution: string
}
export type WalkingReplay = LocomotionReplay & { committed: SeedOutcome | null; controller_label: string }

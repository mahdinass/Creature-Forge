// Mirrors creature_forge.locomotion_view. Everything shown here was measured by MuJoCo server-side.
import type { RunPayload } from '../types'

export interface MethodSummary {
  rollouts: number
  candidates: number
  errors: number
  wall_s: number
  rng_seed: number
  hyperparameters: Record<string, unknown>
  best_so_far: number[]
  candidate_fitness: number[]
  candidate_labels: string[]
  label_counts: Record<string, number>
  n_feasible: number
  best_index: number
}

export interface HeldoutVerdict {
  meets_walking_criteria: boolean
  meets_partial_criteria: boolean
  fraction_seeds_walking: number
  median_speed_upright: number
  body_dragging_seeds: number
}

export interface HeldoutSummary {
  label_counts: Record<string, number>
  survival_rate: number
  mean_distance_upright: number
  mean_speed_upright: number
  mean_valid_step_rate: number
  mean_step_advance: number
  mean_slip_frac: number
  mean_saturation_frac: number
  mean_effort: number
}

export interface LocomotionSummary {
  protocol_id: string | null
  methods: Record<string, MethodSummary>
  heldout: {
    seeds: number[]
    duration: number
    rollouts: number
    controllers: Record<string, { verdict: HeldoutVerdict; summary: HeldoutSummary }>
  } | null
  controllers: Record<string, string>
  seed_roles: { train: number[]; diagnostic: number[]; heldout: number[] }
  durations: { train: number; diagnostic: number; heldout: number }
  success_criteria?: {
    walking: { min_fraction_seeds_walking: number; min_median_speed_upright: number }
    partial: { min_fraction_seeds_walking: number }
  }
}

export interface LocomotionInfo {
  label: string
  walking: boolean
  violations: string[]
  speed_upright: number
  forward_disp_upright: number
  valid_steps: number
  valid_step_rate: number
  mean_step_advance: number
  mean_stance_s: number
  mean_swing_s: number
  single_support_frac: number
  double_support_frac: number
  flight_frac: number
  raw_touchdown_rate: number
  slip_frac: number
  saturation_frac: number
  effort: number
  fell: boolean
  fall_time: number | null
}

export type LocomotionReplay = RunPayload & { role: 'train' | 'diagnostic' | 'heldout' | null; locomotion: LocomotionInfo }

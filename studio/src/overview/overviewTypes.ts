export interface OverviewProposal {
  edits: string[]
  model_walking: number
  random_walking: number
  model_verdict: string
  random_verdict: string
}

export interface OverviewRun {
  id: string
  kind: string
  label: string | null
  model_status: string
  valid_proposals: number
  tokens: number | null
  proposals: OverviewProposal[]
  frozen_walking?: number
  n?: number
}

export interface OverviewData {
  headline: string
  pipeline: { step: string; text: string }[]
  classical: {
    winner_walking: number
    incumbent_walking: number
    n: number
    winner_exact_ci: [number, number]
    incumbent_exact_ci: [number, number]
    paired: { winner_only: number; incumbent_only: number; both: number; neither: number }
    non_inferior: boolean
    superior: boolean
    tango_ci: [number, number]
    mcnemar_p: number | null
    engineering_met: boolean
    attribution: string
  } | null
  nemotron: {
    recorded_runs: OverviewRun[]
    systematic_comparison: { status: string; reason: string }
    usage: { requests: number; tokens: number; requests_cap: number; tokens_cap: number }
    claim: string
  }
  earlier: { r1?: { text: string }; phase2a?: { text: string } }
  limits: string[]
}

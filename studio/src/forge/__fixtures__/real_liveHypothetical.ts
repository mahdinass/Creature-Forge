// TEST-ONLY. Unedited LIVE record experiments/forge_loop/dev_live_records/i-50af182da352.json; only model_calls[].messages/raw_response/content removed.
import type { InvestigationRecord } from '../forgeTypes'

export const liveHypothetical = {
 "id": "i-50af182da352",
 "created": "2026-10-15T08:15:02Z",
 "mode": "live",
 "provenance": "LIVE",
 "creature": {
  "cid": "c-13d00809",
  "n": 1,
  "content_hash": "5dedb26e3d488f2ef8e9947e092dd50506f0aca2942407b3e09339a2b1e2b14f",
  "round": 3,
  "hypothetical_parent": {
   "investigation_id": "i-f9873480e42a",
   "arm_id": "ai:P1"
  },
  "loop_id": "l-47e9b792"
 },
 "challenge_run_id": "r-283be429",
 "spec": {
  "kind": "push",
  "seeds": [
   641782,
   641783,
   641784,
   641785,
   641786,
   641787,
   641788,
   641789
  ],
  "duration": 5.0,
  "perturb": 0.02,
  "target_force": 10.0,
  "push_time": 1.0,
  "push_duration": 0.15,
  "max_force": 80.0,
  "start": "drawn",
  "settle_s": 0.3,
  "bisection_steps": 5
 },
 "evidence": {
  "creature": {
   "mode": "experimental",
   "body": {
    "torso_mass": 5.0071,
    "leg_density": 1000.0,
    "foot_friction": 1.0,
    "torque_limit": 60.0,
    "rear": {
     "thigh_length": 0.3016,
     "shank_length": 0.3016,
     "foot_length": 0.201
    },
    "front": {
     "thigh_length": 0.2999,
     "shank_length": 0.2999,
     "foot_length": 0.1608
    }
   },
   "start": {
    "torso_pitch": 0.0153,
    "rear_hip": -0.0178,
    "rear_knee": 0.0,
    "rear_ankle": -0.0193,
    "front_hip": -0.0182,
    "front_knee": -0.0,
    "front_ankle": -0.0189
   },
   "derived": {
    "leg_length_rear": 0.6033,
    "leg_length_front": 0.5998,
    "foot_to_leg": 0.3007,
    "mass_total": 10.3956,
    "weight_n": 101.981,
    "torque_to_weight": 0.9781,
    "heel_behind_ankle_rear_m": 0.0502,
    "toe_ahead_of_ankle_rear_m": 0.1507,
    "heel_behind_ankle_front_m": 0.0402,
    "toe_ahead_of_ankle_front_m": 0.1206
   }
  },
  "challenge": {
   "kind": "push",
   "seeds_n": 8,
   "duration": 5.0,
   "settle_s": 0.3,
   "start": "drawn",
   "target_force": 10.0
  },
  "controller": {
   "stand": {
    "kind": "stand-pd",
    "edited": false,
    "kp": 150.0,
    "kd": 8.0,
    "gait_freq": 0.0,
    "hip_amp": 0.0,
    "knee_amp": 0.0,
    "balance_gain": 80.0,
    "stand_hip": 0.0,
    "stand_knee": 0.0
   }
  },
  "outcome": {
   "aggregate": "PASS",
   "counts": {
    "FAIL": 0,
    "POOR": 0,
    "PASS": 8,
    "ERROR": 0
   },
   "seeds_n": 8,
   "score": {
    "median": 15.0,
    "mean": 15.0,
    "min": 15.0,
    "max": 15.0
   }
  },
  "seeds": [
   {
    "seed": 641782,
    "outcome": "PASS",
    "score": 15.0,
    "metrics": {
     "critical_force_fwd": 35.0,
     "critical_force_bwd": 15.0,
     "weak_direction": "backward",
     "censored": false,
     "settle_s": 0.3,
     "z_ref": 0.7673,
     "censored_bwd": false,
     "censored_fwd": false
    },
    "events": [
     {
      "kind": "fall",
      "time": 2.621
     }
    ]
   },
   {
    "seed": 641783,
    "outcome": "PASS",
    "score": 15.0,
    "metrics": {
     "critical_force_fwd": 35.0,
     "critical_force_bwd": 15.0,
     "weak_direction": "backward",
     "censored": false,
     "settle_s": 0.3,
     "z_ref": 0.7668,
     "censored_bwd": false,
     "censored_fwd": false
    },
    "events": [
     {
      "kind": "foot_slip",
      "time": 2.606
     }
    ]
   },
   {
    "seed": 641785,
    "outcome": "PASS",
    "score": 15.0,
    "metrics": {
     "critical_force_fwd": 35.0,
     "critical_force_bwd": 15.0,
     "weak_direction": "backward",
     "censored": false,
     "settle_s": 0.3,
     "z_ref": 0.7668,
     "censored_bwd": false,
     "censored_fwd": false
    },
    "events": [
     {
      "kind": "fall",
      "time": 2.436
     }
    ]
   },
   {
    "seed": 641786,
    "outcome": "PASS",
    "score": 15.0,
    "metrics": {
     "critical_force_fwd": 35.0,
     "critical_force_bwd": 15.0,
     "weak_direction": "backward",
     "censored": false,
     "settle_s": 0.3,
     "z_ref": 0.7672,
     "censored_bwd": false,
     "censored_fwd": false
    },
    "events": [
     {
      "kind": "foot_slip",
      "time": 2.026
     }
    ]
   },
   {
    "seed": 641788,
    "outcome": "PASS",
    "score": 15.0,
    "metrics": {
     "critical_force_fwd": 35.0,
     "critical_force_bwd": 15.0,
     "weak_direction": "backward",
     "censored": false,
     "settle_s": 0.3,
     "z_ref": 0.7654,
     "censored_bwd": false,
     "censored_fwd": false
    },
    "events": [
     {
      "kind": "fall",
      "time": 2.421
     }
    ]
   },
   {
    "seed": 641789,
    "outcome": "PASS",
    "score": 15.0,
    "metrics": {
     "critical_force_fwd": 35.0,
     "critical_force_bwd": 15.0,
     "weak_direction": "backward",
     "censored": false,
     "settle_s": 0.3,
     "z_ref": 0.7669,
     "censored_bwd": false,
     "censored_fwd": false
    },
    "events": [
     {
      "kind": "fall",
      "time": 2.281
     }
    ]
   }
  ],
  "forensics": {
   "disturbance": {
    "push_time_s": 0.9214,
    "push_force_N": 17.5,
    "push_duration_s": 0.15,
    "impulse_Ns": 2.625,
    "pitch_before_push_rad": -0.024,
    "com_vx_before_push_mps": 0.0072,
    "com_vx_at_push_end_mps": 0.1877,
    "com_x_shift_during_push_m": 0.0151,
    "peak_abs_pitch_within_1s_rad": 0.1723,
    "time_of_peak_pitch_s": 1.921,
    "peak_pitch_rate_within_1s_rad_s": 0.5013
   },
   "failure": {
    "fell": true,
    "fall_time_s": 2.621,
    "fall_after_push_end_s": 1.55,
    "instability_onset_s": 0.966,
    "onset_after_push_start_s": 0.045,
    "com_left_support_s": 0.966,
    "pitch_at_fall_rad": 1.006,
    "min_torso_height_m": 0.0347
   },
   "support": {
    "support_length_before_push_m": 0.201,
    "com_margin_before_push_m": 0.0645,
    "xcom_margin_before_push_m": 0.0629,
    "min_com_margin_after_push_m": -0.3481,
    "min_xcom_margin_after_push_m": -0.5259,
    "time_of_min_xcom_margin_s": 2.611,
    "cop_minus_com_x_at_push_end_m": 0.0495,
    "feet_unloaded_fraction_after_push": 0.012
   },
   "actuation": {
    "torque_limit_Nm": 60.0,
    "ankle_peak_demand_Nm": 5.43,
    "ankle_peak_applied_Nm": 5.43,
    "ankle_demand_over_limit_peak": 0.09,
    "any_joint_demand_over_limit_peak": 0.09,
    "fraction_samples_saturated_push_to_fall": 0.0
   },
   "contacts": {
    "transitions": [
     {
      "foot": "right",
      "t_s": 0.026,
      "event": "touchdown"
     },
     {
      "foot": "left",
      "t_s": 0.036,
      "event": "touchdown"
     },
     {
      "foot": "right",
      "t_s": 0.061,
      "event": "liftoff"
     },
     {
      "foot": "right",
      "t_s": 2.216,
      "event": "touchdown"
     },
     {
      "foot": "right",
      "t_s": 2.386,
      "event": "liftoff"
     }
    ],
    "peak_slip_speed_mps": 0.417,
    "fraction_samples_slipping_push_to_fall": 0.088,
    "foot_friction": 1.0
   },
   "timeline": {
    "columns": [
     "t_s",
     "pitch_rad",
     "pitch_rate_rad_s",
     "com_vx_mps",
     "com_margin_m",
     "xcom_margin_m",
     "feet_loaded",
     "ankle_demand_over_limit",
     "max_slip_speed_mps"
    ],
    "rows": [
     [
      0.826,
      -0.025,
      0.009,
      0.003,
      0.065,
      0.064,
      1,
      0.02,
      0.0
     ],
     [
      1.226,
      0.07,
      0.158,
      0.128,
      -0.026,
      -0.001,
      1,
      0.08,
      0.001
     ],
     [
      1.726,
      0.14,
      0.127,
      0.064,
      -0.008,
      -0.022,
      1,
      0.09,
      0.002
     ],
     [
      2.126,
      0.244,
      0.505,
      0.237,
      -0.059,
      -0.11,
      1,
      0.08,
      0.02
     ]
    ]
   },
   "direction": "backward",
   "force_N": -17.5,
   "mirrored": true,
   "first_failing_force_N": 17.5,
   "seed": 641782,
   "seed_outcome": "PASS",
   "seed_score": 15.0
  },
  "history": [
   {
    "round": 1,
    "proposal": "ai:P1: foot_friction scale 1.5 (both)",
    "verdict": "NOT_VERIFIED",
    "effect": -1.25
   },
   {
    "round": 2,
    "proposal": "ai:P1: foot_length scale 1.25 (rear)",
    "verdict": "VERIFIED_IMPROVEMENT",
    "effect": 3.125
   }
  ],
  "bounds": {
   "torso_mass": {
    "lo": 0.2,
    "hi": 80.0,
    "current": 5.0071
   },
   "thigh_length": {
    "lo": 0.05,
    "hi": 1.2,
    "rear": 0.3016,
    "front": 0.2999
   },
   "shank_length": {
    "lo": 0.05,
    "hi": 1.2,
    "rear": 0.3016,
    "front": 0.2999
   },
   "foot_length": {
    "lo": 0.02,
    "hi": 0.6,
    "rear": 0.201,
    "front": 0.1608
   },
   "leg_density": {
    "lo": 50.0,
    "hi": 8000.0,
    "current": 1000.0
   },
   "foot_friction": {
    "lo": 0.01,
    "hi": 3.0,
    "current": 1.0
   },
   "torque_limit": {
    "lo": 0.5,
    "hi": 500.0,
    "current": 60.0
   },
   "stand": {
    "kp": {
     "lo": 0.0,
     "hi": 500.0,
     "current": 150.0,
     "u": 0.3
    },
    "kd": {
     "lo": 0.0,
     "hi": 50.0,
     "current": 8.0,
     "u": 0.16
    },
    "balance_gain": {
     "lo": 0.0,
     "hi": 200.0,
     "current": 80.0,
     "u": 0.4
    },
    "stand_hip": {
     "lo": -0.3,
     "hi": 0.3,
     "current": 0.0,
     "u": 0.5
    },
    "stand_knee": {
     "lo": -0.8,
     "hi": 0.0,
     "current": 0.0,
     "u": 1.0
    }
   }
  }
 },
 "model_calls": [
  {
   "model": "nvidia/nemotron-3-super-120b-a12b",
   "settings": {
    "temperature": 0.6,
    "max_tokens": 8000,
    "reasoning_effort": null,
    "json_schema": true,
    "schema_name": "forge_reply",
    "extra_body": {
     "chat_template_kwargs": {
      "enable_thinking": false
     }
    },
    "timeout_s": 180.0,
    "purpose": "investigation",
    "investigation_id": "i-50af182da352"
   },
   "prompt_sha256": "d9b7cd3ef478d136289cde3af910b6e8ab880783283250515edc0d52564f595a",
   "reasoning_present": false,
   "request_id": "c19834279d60f5da68d5b47aabf42ab3",
   "latency_s": 2.19736900099997,
   "usage": {
    "prompt_tokens": 5344,
    "completion_tokens": 321,
    "total_tokens": 5665,
    "reasoning_tokens": 0
   },
   "cost_usd": 0.0018920999999999999,
   "finish_reason": "stop",
   "http_status": 200,
   "error": null,
   "budget_refused": false,
   "sent": true,
   "ok": true
  }
 ],
 "reply": {
  "diagnosis": {
   "summary": "All seeds show backward weakness due to insufficient rear ankle torque generation during push recovery.",
   "hypotheses": [
    {
     "id": "H1",
     "mechanism": "Backward push creates rear ankle dorsiflexion demand exceeding torque capacity, causing slip/failure before other joints respond.",
     "evidence": [
      "seeds[0].metrics.weak_direction",
      "seeds[0].events[0].kind",
      "forensics.actuation.ankle_peak_demand_Nm",
      "forensics.actuation.any_joint_demand_over_limit_peak"
     ],
     "competing": [
      "Insufficient rear foot friction limits ground reaction force despite adequate torque."
     ]
    }
   ]
  },
  "proposals": [
   {
    "id": "P1",
    "hypothesis": "H1",
    "category": "morphology",
    "edits": [
     {
      "param": "torque_limit",
      "op": "scale",
      "value": 1.25,
      "target": "both"
     }
    ],
    "retune_controller": false,
    "prediction": {
     "metric": "score",
     "direction": "increase",
     "expected_change": "+3.0 N"
    },
    "tradeoffs": "Higher torque increases joint stress but remains within safe actuation bounds.",
    "confidence": 0.7,
    "verification": "Based on history[1].effect where increasing rear foot_length by 1.25x improved score by 3.125 N; scaling torque similarly should yield comparable gain."
   }
  ]
 },
 "validation": {
  "schema_errors": [],
  "hypotheses": [
   {
    "id": "H1",
    "status": "accepted",
    "reasons": [],
    "mechanism": "Backward push creates rear ankle dorsiflexion demand exceeding torque capacity, causing slip/failure before other joints respond.",
    "evidence": [
     "seeds[0].metrics.weak_direction",
     "seeds[0].events[0].kind",
     "forensics.actuation.ankle_peak_demand_Nm",
     "forensics.actuation.any_joint_demand_over_limit_peak"
    ],
    "competing": [
     "Insufficient rear foot friction limits ground reaction force despite adequate torque."
    ],
    "values": {
     "seeds[0].metrics.weak_direction": "backward",
     "seeds[0].events[0].kind": "fall",
     "forensics.actuation.ankle_peak_demand_Nm": 5.43,
     "forensics.actuation.any_joint_demand_over_limit_peak": 0.09
    }
   }
  ],
  "proposals": [
   {
    "id": "P1",
    "status": "accepted",
    "reasons": [],
    "hypothesis": "H1",
    "category": "morphology",
    "edits": [
     {
      "param": "torque_limit",
      "op": "scale",
      "value": 1.25,
      "target": "both"
     }
    ],
    "retune_controller": false,
    "prediction": {
     "metric": "score",
     "direction": "increase",
     "expected_change": "+3.0 N"
    },
    "tradeoffs": "Higher torque increases joint stress but remains within safe actuation bounds.",
    "confidence": 0.7,
    "verification": "Based on history[1].effect where increasing rear foot_length by 1.25x improved score by 3.125 N; scaling torque similarly should yield comparable gain.",
    "citations": [
     "seeds[0].metrics.weak_direction",
     "seeds[0].events[0].kind",
     "forensics.actuation.ankle_peak_demand_Nm",
     "forensics.actuation.any_joint_demand_over_limit_peak"
    ],
    "magnitudes": [
     0.223144
    ]
   }
  ],
  "warnings": [],
  "summary": "All seeds show backward weakness due to insufficient rear ankle torque generation during push recovery."
 },
 "arms": [
  {
   "arm_id": "original",
   "source": "original",
   "proposal_id": null,
   "edits": [],
   "retune": null,
   "provenance": "LIVE",
   "category": null,
   "body": {
    "torso_mass": 5.0071,
    "thigh_length": 0.301626,
    "shank_length": 0.301626,
    "foot_length": 0.20098499999999997,
    "foot_friction": 1.0,
    "torque_limit": 60.0,
    "leg_density": 1000.0,
    "thigh_length_r": 0.299876,
    "shank_length_r": 0.299876,
    "foot_length_r": 0.160788,
    "pose": [
     0.015281,
     -0.017767,
     0.0,
     -0.019283,
     -0.018198,
     -0.0,
     -0.018852
    ]
   },
   "controllers": {
    "stand": {
     "kp": 150.0,
     "kd": 8.0,
     "gait_freq": 0.0,
     "hip_amp": 0.0,
     "knee_amp": 0.0,
     "balance_gain": 80.0,
     "stand_hip": 0.0,
     "stand_knee": 0.0
    },
    "walk": null
   },
   "controller_provenance": {
    "stand": {
     "kind": "stand-pd",
     "params": {
      "kp": 150.0,
      "kd": 8.0,
      "gait_freq": 0.0,
      "hip_amp": 0.0,
      "knee_amp": 0.0,
      "balance_gain": 80.0,
      "stand_hip": 0.0,
      "stand_knee": 0.0
     },
     "edited": false
    },
    "walk": {
     "kind": "none",
     "vector": null,
     "adaptation": null
    }
   },
   "error": null,
   "retune_requested": false,
   "rollouts": {
    "adaptation": 0,
    "screening": 102,
    "validation": 204,
    "total": 306
   }
  },
  {
   "arm_id": "ai:P1",
   "source": "nemotron",
   "proposal_id": "P1",
   "edits": [
    {
     "param": "torque_limit",
     "op": "scale",
     "value": 1.25,
     "target": "both"
    }
   ],
   "retune": null,
   "hypothesis": "H1",
   "category": "morphology",
   "provenance": "LIVE",
   "body": {
    "torso_mass": 5.0071,
    "thigh_length": 0.301626,
    "shank_length": 0.301626,
    "foot_length": 0.20098499999999997,
    "foot_friction": 1.0,
    "torque_limit": 75.0,
    "leg_density": 1000.0,
    "thigh_length_r": 0.299876,
    "shank_length_r": 0.299876,
    "foot_length_r": 0.160788,
    "pose": [
     0.015281,
     -0.017767,
     0.0,
     -0.019283,
     -0.018198,
     -0.0,
     -0.018852
    ]
   },
   "controllers": {
    "stand": {
     "kp": 150.0,
     "kd": 8.0,
     "gait_freq": 0.0,
     "hip_amp": 0.0,
     "knee_amp": 0.0,
     "balance_gain": 80.0,
     "stand_hip": 0.0,
     "stand_knee": 0.0
    },
    "walk": null
   },
   "controller_provenance": {
    "stand": {
     "kind": "stand-pd",
     "params": {
      "kp": 150.0,
      "kd": 8.0,
      "gait_freq": 0.0,
      "hip_amp": 0.0,
      "knee_amp": 0.0,
      "balance_gain": 80.0,
      "stand_hip": 0.0,
      "stand_knee": 0.0
     },
     "edited": false
    },
    "walk": {
     "kind": "none",
     "vector": null,
     "adaptation": null
    }
   },
   "error": null,
   "retune_requested": false,
   "rollouts": {
    "adaptation": 0,
    "screening": 102,
    "validation": 204,
    "total": 306
   }
  },
  {
   "arm_id": "random:P1",
   "source": "random_baseline",
   "proposal_id": "P1",
   "edits": [
    {
     "param": "torque_limit",
     "op": "scale",
     "value": 0.8,
     "target": "both"
    }
   ],
   "retune": null,
   "category": "morphology",
   "provenance": "LIVE",
   "body": {
    "torso_mass": 5.0071,
    "thigh_length": 0.301626,
    "shank_length": 0.301626,
    "foot_length": 0.20098499999999997,
    "foot_friction": 1.0,
    "torque_limit": 48.0,
    "leg_density": 1000.0,
    "thigh_length_r": 0.299876,
    "shank_length_r": 0.299876,
    "foot_length_r": 0.160788,
    "pose": [
     0.015281,
     -0.017767,
     0.0,
     -0.019283,
     -0.018198,
     -0.0,
     -0.018852
    ]
   },
   "controllers": {
    "stand": {
     "kp": 150.0,
     "kd": 8.0,
     "gait_freq": 0.0,
     "hip_amp": 0.0,
     "knee_amp": 0.0,
     "balance_gain": 80.0,
     "stand_hip": 0.0,
     "stand_knee": 0.0
    },
    "walk": null
   },
   "controller_provenance": {
    "stand": {
     "kind": "stand-pd",
     "params": {
      "kp": 150.0,
      "kd": 8.0,
      "gait_freq": 0.0,
      "hip_amp": 0.0,
      "knee_amp": 0.0,
      "balance_gain": 80.0,
      "stand_hip": 0.0,
      "stand_knee": 0.0
     },
     "edited": false
    },
    "walk": {
     "kind": "none",
     "vector": null,
     "adaptation": null
    }
   },
   "error": null,
   "retune_requested": false,
   "rollouts": {
    "adaptation": 0,
    "screening": 102,
    "validation": 204,
    "total": 306
   }
  },
  {
   "arm_id": "heuristic",
   "source": "heuristic",
   "proposal_id": null,
   "edits": [],
   "retune": false,
   "unavailable": "the heuristic rule table has no rule for this evidence",
   "provenance": "LIVE"
  }
 ],
 "seeds": {
  "train": [
   740529,
   740530,
   740531
  ],
  "screen": [
   613561,
   613562,
   613563,
   613564,
   613565,
   613566
  ],
  "validate": [
   790634,
   790635,
   790636,
   790637,
   790638,
   790639,
   790640,
   790641,
   790642,
   790643,
   790644,
   790645
  ],
  "round_used": 3
 },
 "screening": {
  "original": {
   "seeds": [
    {
     "seed": 613561,
     "score": 16.25,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 35.625,
      "critical_force_bwd": 16.25,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 613562,
     "score": 15.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.875,
      "critical_force_bwd": 15.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 613563,
     "score": 18.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 34.375,
      "critical_force_bwd": 18.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 613564,
     "score": 16.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 35.625,
      "critical_force_bwd": 16.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 613565,
     "score": 16.25,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.25,
      "critical_force_bwd": 16.25,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 613566,
     "score": 16.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 35.625,
      "critical_force_bwd": 16.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    }
   ],
   "summary": {
    "median": 16.5625,
    "mean": 16.5625,
    "n": 6,
    "errors": 0,
    "counts": {
     "PASS": 6,
     "POOR": 0,
     "FAIL": 0,
     "ERROR": 0
    },
    "rollouts": 102
   }
  },
  "ai:P1": {
   "seeds": [
    {
     "seed": 613561,
     "score": 16.25,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 35.625,
      "critical_force_bwd": 16.25,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 613562,
     "score": 15.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.875,
      "critical_force_bwd": 15.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 613563,
     "score": 18.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 34.375,
      "critical_force_bwd": 18.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 613564,
     "score": 16.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 35.625,
      "critical_force_bwd": 16.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 613565,
     "score": 16.25,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.25,
      "critical_force_bwd": 16.25,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 613566,
     "score": 16.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 35.625,
      "critical_force_bwd": 16.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    }
   ],
   "summary": {
    "median": 16.5625,
    "mean": 16.5625,
    "n": 6,
    "errors": 0,
    "counts": {
     "PASS": 6,
     "POOR": 0,
     "FAIL": 0,
     "ERROR": 0
    },
    "rollouts": 102
   }
  },
  "random:P1": {
   "seeds": [
    {
     "seed": 613561,
     "score": 16.25,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 35.625,
      "critical_force_bwd": 16.25,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 613562,
     "score": 15.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.875,
      "critical_force_bwd": 15.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 613563,
     "score": 18.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 34.375,
      "critical_force_bwd": 18.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 613564,
     "score": 16.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 35.625,
      "critical_force_bwd": 16.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 613565,
     "score": 16.25,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.25,
      "critical_force_bwd": 16.25,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 613566,
     "score": 16.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 35.625,
      "critical_force_bwd": 16.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    }
   ],
   "summary": {
    "median": 16.5625,
    "mean": 16.5625,
    "n": 6,
    "errors": 0,
    "counts": {
     "PASS": 6,
     "POOR": 0,
     "FAIL": 0,
     "ERROR": 0
    },
    "rollouts": 102
   }
  }
 },
 "selection": {
  "rule": "Screening only selects. Best AI arm = highest MEDIAN screening score among AI arms (ties: higher mean, then arm order); best baseline = the same rule among random_baseline + heuristic arms. Arms with any ERROR seed are excluded and listed. Validation (held-out seeds, original + selected arms) decides via verdict_v1. Model confidence is never read.",
  "excluded": {},
  "ranking": {
   "ai": [
    {
     "arm_id": "ai:P1",
     "median": 16.5625,
     "mean": 16.5625,
     "order": 1
    }
   ],
   "baseline": [
    {
     "arm_id": "random:P1",
     "median": 16.5625,
     "mean": 16.5625,
     "order": 2
    }
   ]
  },
  "ai": "ai:P1",
  "baseline": "random:P1",
  "validated": [
   "ai:P1",
   "random:P1"
  ]
 },
 "validation_results": {
  "original": {
   "seeds": [
    {
     "seed": 790634,
     "score": 13.75,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 38.125,
      "critical_force_bwd": 13.75,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790635,
     "score": 14.375,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 37.5,
      "critical_force_bwd": 14.375,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790636,
     "score": 15.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.25,
      "critical_force_bwd": 15.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790637,
     "score": 15.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.25,
      "critical_force_bwd": 15.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790638,
     "score": 14.375,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 38.125,
      "critical_force_bwd": 14.375,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790639,
     "score": 15.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.875,
      "critical_force_bwd": 15.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790640,
     "score": 18.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 34.375,
      "critical_force_bwd": 18.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790641,
     "score": 15.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.875,
      "critical_force_bwd": 15.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790642,
     "score": 15.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 37.5,
      "critical_force_bwd": 15.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790643,
     "score": 15.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.25,
      "critical_force_bwd": 15.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790644,
     "score": 13.75,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 38.125,
      "critical_force_bwd": 13.75,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790645,
     "score": 15.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.875,
      "critical_force_bwd": 15.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    }
   ],
   "summary": {
    "median": 15.0,
    "mean": 15.104166666666666,
    "n": 12,
    "errors": 0,
    "counts": {
     "PASS": 12,
     "POOR": 0,
     "FAIL": 0,
     "ERROR": 0
    },
    "rollouts": 204
   }
  },
  "ai:P1": {
   "seeds": [
    {
     "seed": 790634,
     "score": 13.75,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 38.125,
      "critical_force_bwd": 13.75,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790635,
     "score": 14.375,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 37.5,
      "critical_force_bwd": 14.375,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790636,
     "score": 15.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.25,
      "critical_force_bwd": 15.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790637,
     "score": 15.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.25,
      "critical_force_bwd": 15.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790638,
     "score": 14.375,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 38.125,
      "critical_force_bwd": 14.375,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790639,
     "score": 15.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.875,
      "critical_force_bwd": 15.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790640,
     "score": 18.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 34.375,
      "critical_force_bwd": 18.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790641,
     "score": 15.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.875,
      "critical_force_bwd": 15.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790642,
     "score": 15.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 37.5,
      "critical_force_bwd": 15.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790643,
     "score": 15.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.25,
      "critical_force_bwd": 15.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790644,
     "score": 13.75,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 38.125,
      "critical_force_bwd": 13.75,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790645,
     "score": 15.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.875,
      "critical_force_bwd": 15.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    }
   ],
   "summary": {
    "median": 15.0,
    "mean": 15.104166666666666,
    "n": 12,
    "errors": 0,
    "counts": {
     "PASS": 12,
     "POOR": 0,
     "FAIL": 0,
     "ERROR": 0
    },
    "rollouts": 204
   }
  },
  "random:P1": {
   "seeds": [
    {
     "seed": 790634,
     "score": 13.75,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 38.125,
      "critical_force_bwd": 13.75,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790635,
     "score": 14.375,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 37.5,
      "critical_force_bwd": 14.375,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790636,
     "score": 15.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.25,
      "critical_force_bwd": 15.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790637,
     "score": 15.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.25,
      "critical_force_bwd": 15.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790638,
     "score": 14.375,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 38.125,
      "critical_force_bwd": 14.375,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790639,
     "score": 15.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.875,
      "critical_force_bwd": 15.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790640,
     "score": 18.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 34.375,
      "critical_force_bwd": 18.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790641,
     "score": 15.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.875,
      "critical_force_bwd": 15.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790642,
     "score": 15.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 37.5,
      "critical_force_bwd": 15.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790643,
     "score": 15.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.25,
      "critical_force_bwd": 15.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790644,
     "score": 13.75,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 38.125,
      "critical_force_bwd": 13.75,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 790645,
     "score": 15.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.875,
      "critical_force_bwd": 15.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    }
   ],
   "summary": {
    "median": 15.0,
    "mean": 15.104166666666666,
    "n": 12,
    "errors": 0,
    "counts": {
     "PASS": 12,
     "POOR": 0,
     "FAIL": 0,
     "ERROR": 0
    },
    "rollouts": 204
   }
  }
 },
 "verdicts": {
  "ai:P1": {
   "rule": "verdict_v1",
   "kind": "push",
   "n": 12,
   "resolution": 0.625,
   "alpha": 0.05,
   "min_non_tied": 6,
   "pass_rate": {
    "original": {
     "k": 12,
     "n": 12,
     "rate": 1.0,
     "ci95": [
      0.7574992425007574,
      1.0
     ],
     "method": "wilson"
    },
    "candidate": {
     "k": 12,
     "n": 12,
     "rate": 1.0,
     "ci95": [
      0.7574992425007574,
      1.0
     ],
     "method": "wilson"
    }
   },
   "wins": 0,
   "losses": 0,
   "ties": 12,
   "median_diff": 0.0,
   "p_one_sided": 1.0,
   "p_worse": 1.0,
   "min_effect": {
    "abs": 3.0,
    "rel": 0.1,
    "required": 3.0
   },
   "errors": [],
   "non_tied": 0,
   "status": "INCONCLUSIVE",
   "reasons": [
    "0 wins, 0 losses, 12 ties (|diff| <= 0.625) of 12 paired seeds",
    "median paired diff +0",
    "only 0 non-tied pairs; at least 6 are needed for a verdict"
   ],
   "source": "nemotron",
   "provenance": "LIVE"
  },
  "random:P1": {
   "rule": "verdict_v1",
   "kind": "push",
   "n": 12,
   "resolution": 0.625,
   "alpha": 0.05,
   "min_non_tied": 6,
   "pass_rate": {
    "original": {
     "k": 12,
     "n": 12,
     "rate": 1.0,
     "ci95": [
      0.7574992425007574,
      1.0
     ],
     "method": "wilson"
    },
    "candidate": {
     "k": 12,
     "n": 12,
     "rate": 1.0,
     "ci95": [
      0.7574992425007574,
      1.0
     ],
     "method": "wilson"
    }
   },
   "wins": 0,
   "losses": 0,
   "ties": 12,
   "median_diff": 0.0,
   "p_one_sided": 1.0,
   "p_worse": 1.0,
   "min_effect": {
    "abs": 3.0,
    "rel": 0.1,
    "required": 3.0
   },
   "errors": [],
   "non_tied": 0,
   "status": "INCONCLUSIVE",
   "reasons": [
    "0 wins, 0 losses, 12 ties (|diff| <= 0.625) of 12 paired seeds",
    "median paired diff +0",
    "only 0 non-tied pairs; at least 6 are needed for a verdict"
   ],
   "source": "random_baseline",
   "provenance": "LIVE"
  }
 },
 "budget": {
  "rollouts": 918,
  "wall_s": 123.603,
  "calls": 1,
  "tokens": 5665,
  "usd": 0.001892
 },
 "code": {
  "commit": "2a5864676464e9eb98e33bb3be475270a5764ad1",
  "dirty": false
 },
 "status": "done",
 "error": null
} as unknown as InvestigationRecord

// TEST-ONLY. Unedited LIVE record experiments/forge_loop/dev_live_records/i-eb2d953f2c8e.json; only model_calls[].messages/raw_response/content removed.
import type { InvestigationRecord } from '../forgeTypes'

export const liveNotVerified = {
 "id": "i-eb2d953f2c8e",
 "created": "2026-10-15T08:09:54Z",
 "mode": "live",
 "provenance": "LIVE",
 "creature": {
  "cid": "c-13d00809",
  "n": 1,
  "content_hash": "47687382762d66ce94fad4042194a5361192ee0fcf215dbe4f8960aa51418425",
  "round": 1,
  "hypothetical_parent": null,
  "loop_id": "l-47e9b792"
 },
 "challenge_run_id": "r-82936044",
 "spec": {
  "kind": "push",
  "seeds": [
   506765,
   506766,
   506767,
   506768,
   506769,
   506770,
   506771,
   506772
  ],
  "duration": 5.0,
  "perturb": 0.02,
  "target_force": 10.0,
  "push_time": 1.0,
  "push_duration": 0.15,
  "max_force": 80.0,
  "start": "drawn",
  "settle_s": 0.3
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
     "foot_length": 0.1608
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
    "foot_to_leg": 0.2673,
    "mass_total": 10.267,
    "weight_n": 100.7191,
    "torque_to_weight": 0.9904,
    "heel_behind_ankle_rear_m": 0.0402,
    "toe_ahead_of_ankle_rear_m": 0.1206,
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
    "median": 12.5,
    "mean": 11.875,
    "min": 10.0,
    "max": 12.5
   }
  },
  "seeds": [
   {
    "seed": 506769,
    "outcome": "PASS",
    "score": 10.0,
    "metrics": {
     "critical_force_fwd": 30.0,
     "critical_force_bwd": 10.0,
     "weak_direction": "backward",
     "censored": false,
     "settle_s": 0.3,
     "z_ref": 0.7662,
     "censored_bwd": false,
     "censored_fwd": false
    },
    "events": [
     {
      "kind": "foot_slip",
      "time": 2.516
     }
    ]
   },
   {
    "seed": 506772,
    "outcome": "PASS",
    "score": 10.0,
    "metrics": {
     "critical_force_fwd": 30.0,
     "critical_force_bwd": 10.0,
     "weak_direction": "backward",
     "censored": false,
     "settle_s": 0.3,
     "z_ref": 0.7671,
     "censored_bwd": false,
     "censored_fwd": false
    },
    "events": [
     {
      "kind": "fall",
      "time": 2.371
     }
    ]
   },
   {
    "seed": 506766,
    "outcome": "PASS",
    "score": 12.5,
    "metrics": {
     "critical_force_fwd": 27.5,
     "critical_force_bwd": 12.5,
     "weak_direction": "backward",
     "censored": false,
     "settle_s": 0.3,
     "z_ref": 0.7689,
     "censored_bwd": false,
     "censored_fwd": false
    },
    "events": [
     {
      "kind": "foot_slip",
      "time": 2.406
     }
    ]
   },
   {
    "seed": 506767,
    "outcome": "PASS",
    "score": 12.5,
    "metrics": {
     "critical_force_fwd": 27.5,
     "critical_force_bwd": 12.5,
     "weak_direction": "backward",
     "censored": false,
     "settle_s": 0.3,
     "z_ref": 0.7656,
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
    "seed": 506770,
    "outcome": "PASS",
    "score": 12.5,
    "metrics": {
     "critical_force_fwd": 27.5,
     "critical_force_bwd": 12.5,
     "weak_direction": "backward",
     "censored": false,
     "settle_s": 0.3,
     "z_ref": 0.7652,
     "censored_bwd": false,
     "censored_fwd": false
    },
    "events": [
     {
      "kind": "foot_slip",
      "time": 2.261
     }
    ]
   },
   {
    "seed": 506771,
    "outcome": "PASS",
    "score": 12.5,
    "metrics": {
     "critical_force_fwd": 27.5,
     "critical_force_bwd": 12.5,
     "weak_direction": "backward",
     "censored": false,
     "settle_s": 0.3,
     "z_ref": 0.7675,
     "censored_bwd": false,
     "censored_fwd": false
    },
    "events": [
     {
      "kind": "fall",
      "time": 2.381
     }
    ]
   }
  ],
  "forensics": {
   "disturbance": {
    "push_time_s": 1.0083,
    "push_force_N": 12.5,
    "push_duration_s": 0.15,
    "impulse_Ns": 1.875,
    "pitch_before_push_rad": -0.003,
    "com_vx_before_push_mps": -0.0019,
    "com_vx_at_push_end_mps": 0.1344,
    "com_x_shift_during_push_m": 0.01,
    "peak_abs_pitch_within_1s_rad": 0.1583,
    "time_of_peak_pitch_s": 2.006,
    "peak_pitch_rate_within_1s_rad_s": 0.3501
   },
   "failure": {
    "fell": true,
    "fall_time_s": 2.681,
    "fall_after_push_end_s": 1.523,
    "instability_onset_s": 1.056,
    "onset_after_push_start_s": 0.048,
    "com_left_support_s": 1.056,
    "pitch_at_fall_rad": 1.0108,
    "min_torso_height_m": 0.0338
   },
   "support": {
    "support_length_before_push_m": 0.1608,
    "com_margin_before_push_m": 0.0443,
    "xcom_margin_before_push_m": 0.0447,
    "min_com_margin_after_push_m": -0.3619,
    "min_xcom_margin_after_push_m": -0.5385,
    "time_of_min_xcom_margin_s": 2.676,
    "cop_minus_com_x_at_push_end_m": 0.0345,
    "feet_unloaded_fraction_after_push": 0.0
   },
   "actuation": {
    "torque_limit_Nm": 60.0,
    "ankle_peak_demand_Nm": 4.2,
    "ankle_peak_applied_Nm": 4.2,
    "ankle_demand_over_limit_peak": 0.07,
    "any_joint_demand_over_limit_peak": 0.07,
    "fraction_samples_saturated_push_to_fall": 0.0
   },
   "contacts": {
    "transitions": [
     {
      "foot": "left",
      "t_s": 0.021,
      "event": "touchdown"
     },
     {
      "foot": "right",
      "t_s": 2.146,
      "event": "touchdown"
     },
     {
      "foot": "left",
      "t_s": 2.366,
      "event": "liftoff"
     },
     {
      "foot": "left",
      "t_s": 2.371,
      "event": "touchdown"
     },
     {
      "foot": "left",
      "t_s": 2.386,
      "event": "liftoff"
     }
    ],
    "peak_slip_speed_mps": 0.39,
    "fraction_samples_slipping_push_to_fall": 0.107,
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
      0.911,
      -0.003,
      -0.006,
      -0.002,
      0.044,
      0.045,
      1,
      0.0,
      0.0
     ],
     [
      1.311,
      0.062,
      0.114,
      0.094,
      -0.018,
      -0.003,
      1,
      0.06,
      0.0
     ],
     [
      1.811,
      0.121,
      0.138,
      0.069,
      -0.012,
      -0.027,
      1,
      0.07,
      0.002
     ],
     [
      2.211,
      0.244,
      0.615,
      0.279,
      -0.057,
      -0.117,
      2,
      0.04,
      0.026
     ]
    ]
   },
   "direction": "backward",
   "force_N": -12.5,
   "mirrored": true,
   "first_failing_force_N": 12.5,
   "seed": 506769,
   "seed_outcome": "PASS",
   "seed_score": 10.0
  },
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
    "rear": 0.1608,
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
    "investigation_id": "i-eb2d953f2c8e"
   },
   "prompt_sha256": "a2ff3a217d325830f30daddf5c22d79d195417732394da9f6e2bb92eeb7bf166",
   "reasoning_present": false,
   "request_id": "183b4d0c9fccc44926e85fa2c0d97145",
   "latency_s": 2.233545753999806,
   "usage": {
    "prompt_tokens": 5234,
    "completion_tokens": 336,
    "total_tokens": 5570,
    "reasoning_tokens": 0
   },
   "cost_usd": 0.0018725999999999999,
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
   "summary": "The weak direction is consistently backward, with failure triggered by foot slip events. Critical backward force equals ~10\u202fN for many seeds, matching the target force, indicating marginal stability. Increasing rear foot friction should raise the slip threshold and improve backward push resistance.",
   "hypotheses": [
    {
     "id": "H1",
     "mechanism": "Backward push creates rear heel slip due to insufficient friction; increasing foot_friction raises the maximum horizontal force before slip occurs.",
     "evidence": [
      "seeds[0].metrics.weak_direction",
      "seeds[0].events[0].kind",
      "forensics.contacts.foot_friction",
      "forensics.contacts.peak_slip_speed_mps",
      "forensics.support.com_margin_before_push_m"
     ],
     "competing": [
      "Insufficient ankle torque limits cause joint saturation before slip."
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
      "param": "foot_friction",
      "op": "scale",
      "value": 1.5,
      "target": "both"
     }
    ],
    "retune_controller": false,
    "prediction": {
     "metric": "score",
     "direction": "increase",
     "expected_change": "+2.5 N"
    },
    "tradeoffs": "Higher friction may increase ground reaction forces slightly but unlikely to impair standing.",
    "confidence": 0.7,
    "verification": "Measured by increased critical_force_bwd in seeds with slip events."
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
    "mechanism": "Backward push creates rear heel slip due to insufficient friction; increasing foot_friction raises the maximum horizontal force before slip occurs.",
    "evidence": [
     "seeds[0].metrics.weak_direction",
     "seeds[0].events[0].kind",
     "forensics.contacts.foot_friction",
     "forensics.contacts.peak_slip_speed_mps",
     "forensics.support.com_margin_before_push_m"
    ],
    "competing": [
     "Insufficient ankle torque limits cause joint saturation before slip."
    ],
    "values": {
     "seeds[0].metrics.weak_direction": "backward",
     "seeds[0].events[0].kind": "foot_slip",
     "forensics.contacts.foot_friction": 1.0,
     "forensics.contacts.peak_slip_speed_mps": 0.39,
     "forensics.support.com_margin_before_push_m": 0.0443
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
      "param": "foot_friction",
      "op": "scale",
      "value": 1.5,
      "target": "both"
     }
    ],
    "retune_controller": false,
    "prediction": {
     "metric": "score",
     "direction": "increase",
     "expected_change": "+2.5 N"
    },
    "tradeoffs": "Higher friction may increase ground reaction forces slightly but unlikely to impair standing.",
    "confidence": 0.7,
    "verification": "Measured by increased critical_force_bwd in seeds with slip events.",
    "citations": [
     "seeds[0].metrics.weak_direction",
     "seeds[0].events[0].kind",
     "forensics.contacts.foot_friction",
     "forensics.contacts.peak_slip_speed_mps",
     "forensics.support.com_margin_before_push_m"
    ],
    "magnitudes": [
     0.405465
    ]
   }
  ],
  "warnings": [],
  "summary": "The weak direction is consistently backward, with failure triggered by foot slip events. Critical backward force equals ~10\u202fN for many seeds, matching the target force, indicating marginal stability. Increasing rear foot friction should raise the slip threshold and improve backward push resistance."
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
    "foot_length": 0.160788,
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
    "validation": 188,
    "total": 290
   }
  },
  {
   "arm_id": "ai:P1",
   "source": "nemotron",
   "proposal_id": "P1",
   "edits": [
    {
     "param": "foot_friction",
     "op": "scale",
     "value": 1.5,
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
    "foot_length": 0.160788,
    "foot_friction": 1.5,
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
    "validation": 188,
    "total": 290
   }
  },
  {
   "arm_id": "random:P1",
   "source": "random_baseline",
   "proposal_id": "P1",
   "edits": [
    {
     "param": "foot_length",
     "op": "scale",
     "value": 0.6666666666666666,
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
    "foot_length": 0.10719199999999998,
    "foot_friction": 1.0,
    "torque_limit": 60.0,
    "leg_density": 1000.0,
    "thigh_length_r": 0.299876,
    "shank_length_r": 0.299876,
    "foot_length_r": 0.10719199999999998,
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
    "validation": 0,
    "total": 102
   }
  },
  {
   "arm_id": "heuristic",
   "source": "heuristic",
   "proposal_id": null,
   "edits": [
    {
     "param": "foot_friction",
     "op": "scale",
     "value": 1.3,
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
    "foot_length": 0.160788,
    "foot_friction": 1.3,
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
    "validation": 188,
    "total": 290
   }
  }
 ],
 "seeds": {
  "train": [
   407113,
   407114,
   407115
  ],
  "screen": [
   681311,
   681312,
   681313,
   681314,
   681315,
   681316
  ],
  "validate": [
   183044,
   183045,
   183046,
   183047,
   183048,
   183049,
   183050,
   183051,
   183052,
   183053,
   183054,
   183055
  ],
  "round_used": 1
 },
 "screening": {
  "original": {
   "seeds": [
    {
     "seed": 681311,
     "score": 12.5,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.625,
      "critical_force_bwd": 12.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681312,
     "score": 14.375,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 28.75,
      "critical_force_bwd": 14.375,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681313,
     "score": 13.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.0,
      "critical_force_bwd": 13.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681314,
     "score": 11.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 31.25,
      "critical_force_bwd": 11.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681315,
     "score": 12.5,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.625,
      "critical_force_bwd": 12.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681316,
     "score": 12.5,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.0,
      "critical_force_bwd": 12.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    }
   ],
   "summary": {
    "median": 12.5,
    "mean": 12.8125,
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
     "seed": 681311,
     "score": 11.25,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 31.25,
      "critical_force_bwd": 11.25,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681312,
     "score": 13.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 29.375,
      "critical_force_bwd": 13.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681313,
     "score": 11.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.625,
      "critical_force_bwd": 11.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681314,
     "score": 10.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 31.875,
      "critical_force_bwd": 10.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681315,
     "score": 11.25,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.625,
      "critical_force_bwd": 11.25,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681316,
     "score": 11.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.625,
      "critical_force_bwd": 11.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    }
   ],
   "summary": {
    "median": 11.5625,
    "mean": 11.666666666666666,
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
     "seed": 681311,
     "score": 6.25,
     "outcome": "POOR",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 20.625,
      "critical_force_bwd": 6.25,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681312,
     "score": 9.375,
     "outcome": "POOR",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 18.125,
      "critical_force_bwd": 9.375,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681313,
     "score": 7.5,
     "outcome": "POOR",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 19.375,
      "critical_force_bwd": 7.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681314,
     "score": 5.625,
     "outcome": "FAIL",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 21.25,
      "critical_force_bwd": 5.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681315,
     "score": 6.875,
     "outcome": "POOR",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 20.0,
      "critical_force_bwd": 6.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681316,
     "score": 7.5,
     "outcome": "POOR",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 19.375,
      "critical_force_bwd": 7.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    }
   ],
   "summary": {
    "median": 7.1875,
    "mean": 7.1875,
    "n": 6,
    "errors": 0,
    "counts": {
     "PASS": 0,
     "POOR": 5,
     "FAIL": 1,
     "ERROR": 0
    },
    "rollouts": 102
   }
  },
  "heuristic": {
   "seeds": [
    {
     "seed": 681311,
     "score": 11.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.625,
      "critical_force_bwd": 11.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681312,
     "score": 13.75,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 28.75,
      "critical_force_bwd": 13.75,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681313,
     "score": 12.5,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.0,
      "critical_force_bwd": 12.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681314,
     "score": 11.25,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 31.25,
      "critical_force_bwd": 11.25,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681315,
     "score": 11.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.625,
      "critical_force_bwd": 11.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 681316,
     "score": 12.5,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.0,
      "critical_force_bwd": 12.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    }
   ],
   "summary": {
    "median": 12.1875,
    "mean": 12.291666666666666,
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
     "median": 11.5625,
     "mean": 11.666666666666666,
     "order": 1
    }
   ],
   "baseline": [
    {
     "arm_id": "heuristic",
     "median": 12.1875,
     "mean": 12.291666666666666,
     "order": 3
    },
    {
     "arm_id": "random:P1",
     "median": 7.1875,
     "mean": 7.1875,
     "order": 2
    }
   ]
  },
  "ai": "ai:P1",
  "baseline": "heuristic",
  "validated": [
   "ai:P1",
   "heuristic"
  ]
 },
 "validation_results": {
  "original": {
   "seeds": [
    {
     "seed": 183044,
     "score": 12.5,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.625,
      "critical_force_bwd": 12.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183045,
     "score": 0.0,
     "outcome": "FAIL",
     "rollouts": 1,
     "error": null,
     "metrics": {
      "critical_force_fwd": 0.0,
      "critical_force_bwd": 0.0,
      "weak_direction": "equal",
      "censored": false,
      "falls_without_push": true,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183046,
     "score": 10.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 32.5,
      "critical_force_bwd": 10.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183047,
     "score": 13.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 29.375,
      "critical_force_bwd": 13.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183048,
     "score": 10.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 31.875,
      "critical_force_bwd": 10.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183049,
     "score": 13.75,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 29.375,
      "critical_force_bwd": 13.75,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183050,
     "score": 11.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 31.25,
      "critical_force_bwd": 11.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183051,
     "score": 11.25,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 31.875,
      "critical_force_bwd": 11.25,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183052,
     "score": 13.75,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 29.375,
      "critical_force_bwd": 13.75,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183053,
     "score": 13.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 29.375,
      "critical_force_bwd": 13.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183054,
     "score": 12.5,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.625,
      "critical_force_bwd": 12.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183055,
     "score": 9.375,
     "outcome": "POOR",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 32.5,
      "critical_force_bwd": 9.375,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    }
   ],
   "summary": {
    "median": 12.1875,
    "mean": 11.041666666666666,
    "n": 12,
    "errors": 0,
    "counts": {
     "PASS": 10,
     "POOR": 1,
     "FAIL": 1,
     "ERROR": 0
    },
    "rollouts": 188
   }
  },
  "ai:P1": {
   "seeds": [
    {
     "seed": 183044,
     "score": 11.25,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.625,
      "critical_force_bwd": 11.25,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183045,
     "score": 0.0,
     "outcome": "FAIL",
     "rollouts": 1,
     "error": null,
     "metrics": {
      "critical_force_fwd": 0.0,
      "critical_force_bwd": 0.0,
      "weak_direction": "equal",
      "censored": false,
      "falls_without_push": true,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183046,
     "score": 9.375,
     "outcome": "POOR",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 32.5,
      "critical_force_bwd": 9.375,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183047,
     "score": 13.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 29.375,
      "critical_force_bwd": 13.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183048,
     "score": 10.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 32.5,
      "critical_force_bwd": 10.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183049,
     "score": 12.5,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.0,
      "critical_force_bwd": 12.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183050,
     "score": 11.25,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 31.25,
      "critical_force_bwd": 11.25,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183051,
     "score": 9.375,
     "outcome": "POOR",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 32.5,
      "critical_force_bwd": 9.375,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183052,
     "score": 12.5,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.0,
      "critical_force_bwd": 12.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183053,
     "score": 11.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.625,
      "critical_force_bwd": 11.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183054,
     "score": 10.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 31.875,
      "critical_force_bwd": 10.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183055,
     "score": 7.5,
     "outcome": "POOR",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 34.375,
      "critical_force_bwd": 7.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    }
   ],
   "summary": {
    "median": 10.9375,
    "mean": 9.947916666666666,
    "n": 12,
    "errors": 0,
    "counts": {
     "PASS": 8,
     "POOR": 3,
     "FAIL": 1,
     "ERROR": 0
    },
    "rollouts": 188
   }
  },
  "heuristic": {
   "seeds": [
    {
     "seed": 183044,
     "score": 11.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.625,
      "critical_force_bwd": 11.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183045,
     "score": 0.0,
     "outcome": "FAIL",
     "rollouts": 1,
     "error": null,
     "metrics": {
      "critical_force_fwd": 0.0,
      "critical_force_bwd": 0.0,
      "weak_direction": "equal",
      "censored": false,
      "falls_without_push": true,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183046,
     "score": 10.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 32.5,
      "critical_force_bwd": 10.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183047,
     "score": 13.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 29.375,
      "critical_force_bwd": 13.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183048,
     "score": 10.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 31.875,
      "critical_force_bwd": 10.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183049,
     "score": 13.75,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 29.375,
      "critical_force_bwd": 13.75,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183050,
     "score": 11.25,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 31.25,
      "critical_force_bwd": 11.25,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183051,
     "score": 10.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 31.875,
      "critical_force_bwd": 10.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183052,
     "score": 13.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 29.375,
      "critical_force_bwd": 13.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183053,
     "score": 13.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.0,
      "critical_force_bwd": 13.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183054,
     "score": 11.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.625,
      "critical_force_bwd": 11.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 183055,
     "score": 8.75,
     "outcome": "POOR",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 33.125,
      "critical_force_bwd": 8.75,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    }
   ],
   "summary": {
    "median": 11.5625,
    "mean": 10.677083333333334,
    "n": 12,
    "errors": 0,
    "counts": {
     "PASS": 10,
     "POOR": 1,
     "FAIL": 1,
     "ERROR": 0
    },
    "rollouts": 188
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
     "k": 10,
     "n": 12,
     "rate": 0.8333333333333334,
     "ci95": [
      0.5519636426153274,
      0.9530358523851776
     ],
     "method": "wilson"
    },
    "candidate": {
     "k": 8,
     "n": 12,
     "rate": 0.6666666666666666,
     "ci95": [
      0.3906175873976139,
      0.8618821601026385
     ],
     "method": "wilson"
    }
   },
   "wins": 0,
   "losses": 8,
   "ties": 4,
   "median_diff": -1.25,
   "p_one_sided": 1.0,
   "p_worse": 0.00390625,
   "min_effect": {
    "abs": 3.0,
    "rel": 0.1,
    "required": 3.0
   },
   "errors": [],
   "non_tied": 8,
   "status": "NOT_VERIFIED",
   "reasons": [
    "0 wins, 8 losses, 4 ties (|diff| <= 0.625) of 12 paired seeds",
    "median paired diff -1.25",
    "mirrored sign test significant (p=0.0039) but median diff -1.25 not beyond -3"
   ],
   "source": "nemotron",
   "provenance": "LIVE"
  },
  "heuristic": {
   "rule": "verdict_v1",
   "kind": "push",
   "n": 12,
   "resolution": 0.625,
   "alpha": 0.05,
   "min_non_tied": 6,
   "pass_rate": {
    "original": {
     "k": 10,
     "n": 12,
     "rate": 0.8333333333333334,
     "ci95": [
      0.5519636426153274,
      0.9530358523851776
     ],
     "method": "wilson"
    },
    "candidate": {
     "k": 10,
     "n": 12,
     "rate": 0.8333333333333334,
     "ci95": [
      0.5519636426153274,
      0.9530358523851776
     ],
     "method": "wilson"
    }
   },
   "wins": 0,
   "losses": 0,
   "ties": 12,
   "median_diff": -0.625,
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
    "median paired diff -0.625",
    "only 0 non-tied pairs; at least 6 are needed for a verdict"
   ],
   "source": "heuristic",
   "provenance": "LIVE"
  }
 },
 "budget": {
  "rollouts": 972,
  "wall_s": 131.464,
  "calls": 1,
  "tokens": 5570,
  "usd": 0.001873
 },
 "code": {
  "commit": "2a5864676464e9eb98e33bb3be475270a5764ad1",
  "dirty": false
 },
 "status": "done",
 "error": null
} as unknown as InvestigationRecord

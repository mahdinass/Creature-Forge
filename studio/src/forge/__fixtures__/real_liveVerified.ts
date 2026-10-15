// TEST-ONLY. Unedited LIVE record experiments/forge_loop/dev_live_records/i-f9873480e42a.json; only model_calls[].messages/raw_response/content removed.
import type { InvestigationRecord } from '../forgeTypes'

export const liveVerified = {
 "id": "i-f9873480e42a",
 "created": "2026-10-15T08:12:05Z",
 "mode": "live",
 "provenance": "LIVE",
 "creature": {
  "cid": "c-13d00809",
  "n": 1,
  "content_hash": "47687382762d66ce94fad4042194a5361192ee0fcf215dbe4f8960aa51418425",
  "round": 2,
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
  "history": [
   {
    "round": 1,
    "proposal": "ai:P1: foot_friction scale 1.5 (both)",
    "verdict": "NOT_VERIFIED",
    "effect": -1.25
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
    "investigation_id": "i-f9873480e42a"
   },
   "prompt_sha256": "1acc0b6866e5559fe60085646bd887bea4bcd6a9b482ef5e1a39c03ee3da9b05",
   "reasoning_present": false,
   "request_id": "094f7fc829906d21d023e25a866a65b1",
   "latency_s": 2.700139489000321,
   "usage": {
    "prompt_tokens": 5288,
    "completion_tokens": 472,
    "total_tokens": 5760,
    "reasoning_tokens": 0
   },
   "cost_usd": 0.0020112,
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
   "summary": "Creature fails backward pushes due to insufficient backward stability margin; events show foot slip or fall when COM moves beyond support base.",
   "hypotheses": [
    {
     "id": "H1",
     "mechanism": "Backward push causes rear foot to slip because heel is too close to ankle, reducing backward base of support.",
     "evidence": [
      "forensics.support.min_xcom_margin_after_push_m",
      "creature.body.rear.foot_length"
     ],
     "competing": [
      "Insufficient ankle torque to resist pitch"
     ]
    },
    {
     "id": "H2",
     "mechanism": "Low foot-friction allows slipping during push; increasing friction improves grip without changing geometry.",
     "evidence": [
      "forensics.contacts.peak_slip_speed_mps",
      "creature.body.foot_friction"
     ],
     "competing": [
      "Slip is secondary to COM migration"
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
      "param": "foot_length",
      "op": "scale",
      "value": 1.25,
      "target": "rear"
     }
    ],
    "retune_controller": false,
    "prediction": {
     "metric": "score",
     "direction": "increase",
     "expected_change": "+2.5 N"
    },
    "tradeoffs": "May increase forward trip risk slightly; mass increases moderately.",
    "confidence": 0.7,
    "verification": "Longer rear foot extends heel behind ankle, enlarging backward support base."
   },
   {
    "id": "P2",
    "hypothesis": "H2",
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
     "expected_change": "+2.0 N"
    },
    "tradeoffs": "No penalty; higher friction always helps lateral/grip stability.",
    "confidence": 0.6,
    "verification": "Higher foot_friction reduces slip likelihood during push transient."
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
    "mechanism": "Backward push causes rear foot to slip because heel is too close to ankle, reducing backward base of support.",
    "evidence": [
     "forensics.support.min_xcom_margin_after_push_m",
     "creature.body.rear.foot_length"
    ],
    "competing": [
     "Insufficient ankle torque to resist pitch"
    ],
    "values": {
     "forensics.support.min_xcom_margin_after_push_m": -0.5385,
     "creature.body.rear.foot_length": 0.1608
    }
   },
   {
    "id": "H2",
    "status": "accepted",
    "reasons": [],
    "mechanism": "Low foot-friction allows slipping during push; increasing friction improves grip without changing geometry.",
    "evidence": [
     "forensics.contacts.peak_slip_speed_mps",
     "creature.body.foot_friction"
    ],
    "competing": [
     "Slip is secondary to COM migration"
    ],
    "values": {
     "forensics.contacts.peak_slip_speed_mps": 0.39,
     "creature.body.foot_friction": 1.0
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
      "param": "foot_length",
      "op": "scale",
      "value": 1.25,
      "target": "rear"
     }
    ],
    "retune_controller": false,
    "prediction": {
     "metric": "score",
     "direction": "increase",
     "expected_change": "+2.5 N"
    },
    "tradeoffs": "May increase forward trip risk slightly; mass increases moderately.",
    "confidence": 0.7,
    "verification": "Longer rear foot extends heel behind ankle, enlarging backward support base.",
    "citations": [
     "forensics.support.min_xcom_margin_after_push_m",
     "creature.body.rear.foot_length"
    ],
    "magnitudes": [
     0.223144
    ]
   },
   {
    "id": "P2",
    "status": "accepted",
    "reasons": [],
    "hypothesis": "H2",
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
     "expected_change": "+2.0 N"
    },
    "tradeoffs": "No penalty; higher friction always helps lateral/grip stability.",
    "confidence": 0.6,
    "verification": "Higher foot_friction reduces slip likelihood during push transient.",
    "citations": [
     "forensics.contacts.peak_slip_speed_mps",
     "creature.body.foot_friction"
    ],
    "magnitudes": [
     0.405465
    ]
   }
  ],
  "warnings": [],
  "summary": "Creature fails backward pushes due to insufficient backward stability margin; events show foot slip or fall when COM moves beyond support base."
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
     "param": "foot_length",
     "op": "scale",
     "value": 1.25,
     "target": "rear"
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
   "arm_id": "ai:P2",
   "source": "nemotron",
   "proposal_id": "P2",
   "edits": [
    {
     "param": "foot_friction",
     "op": "scale",
     "value": 1.5,
     "target": "both"
    }
   ],
   "retune": null,
   "hypothesis": "H2",
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
    "validation": 0,
    "total": 102
   }
  },
  {
   "arm_id": "random:P1",
   "source": "random_baseline",
   "proposal_id": "P1",
   "edits": [
    {
     "param": "leg_density",
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
    "foot_length": 0.160788,
    "foot_friction": 1.0,
    "torque_limit": 60.0,
    "leg_density": 800.0,
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
    "validation": 0,
    "total": 102
   }
  },
  {
   "arm_id": "random:P2",
   "source": "random_baseline",
   "proposal_id": "P2",
   "edits": [
    {
     "param": "thigh_length",
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
    "thigh_length": 0.20108399999999998,
    "shank_length": 0.301626,
    "foot_length": 0.160788,
    "foot_friction": 1.0,
    "torque_limit": 60.0,
    "leg_density": 1000.0,
    "thigh_length_r": 0.1999173333333333,
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
    "validation": 0,
    "total": 102
   }
  }
 ],
 "seeds": {
  "train": [
   814744,
   814745,
   814746
  ],
  "screen": [
   706930,
   706931,
   706932,
   706933,
   706934,
   706935
  ],
  "validate": [
   285592,
   285593,
   285594,
   285595,
   285596,
   285597,
   285598,
   285599,
   285600,
   285601,
   285602,
   285603
  ],
  "round_used": 2
 },
 "screening": {
  "original": {
   "seeds": [
    {
     "seed": 706930,
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
     "seed": 706931,
     "score": 14.375,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 28.125,
      "critical_force_bwd": 14.375,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 706932,
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
     "seed": 706933,
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
     "seed": 706934,
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
     "seed": 706935,
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
    "median": 12.8125,
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
     "seed": 706930,
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
     "seed": 706931,
     "score": 17.5,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 33.75,
      "critical_force_bwd": 17.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 706932,
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
     "seed": 706933,
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
     "seed": 706934,
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
     "seed": 706935,
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
    }
   ],
   "summary": {
    "median": 16.25,
    "mean": 16.145833333333332,
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
  "ai:P2": {
   "seeds": [
    {
     "seed": 706930,
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
     "seed": 706931,
     "score": 13.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 28.75,
      "critical_force_bwd": 13.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 706932,
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
     "seed": 706933,
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
     "seed": 706934,
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
     "seed": 706935,
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
    "median": 11.875,
    "mean": 11.770833333333334,
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
     "seed": 706930,
     "score": 10.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 26.875,
      "critical_force_bwd": 10.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 706931,
     "score": 12.5,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 24.375,
      "critical_force_bwd": 12.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 706932,
     "score": 10.0,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 26.875,
      "critical_force_bwd": 10.0,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 706933,
     "score": 10.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 26.25,
      "critical_force_bwd": 10.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 706934,
     "score": 10.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 26.25,
      "critical_force_bwd": 10.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 706935,
     "score": 10.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 26.25,
      "critical_force_bwd": 10.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    }
   ],
   "summary": {
    "median": 10.625,
    "mean": 10.729166666666666,
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
  "random:P2": {
   "seeds": [
    {
     "seed": 706930,
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
     "seed": 706931,
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
     "seed": 706932,
     "score": 12.5,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 31.25,
      "critical_force_bwd": 12.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 706933,
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
     "seed": 706934,
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
     "seed": 706935,
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
    }
   ],
   "summary": {
    "median": 12.5,
    "mean": 12.604166666666666,
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
  "heuristic": {
   "seeds": [
    {
     "seed": 706930,
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
     "seed": 706931,
     "score": 13.75,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 28.125,
      "critical_force_bwd": 13.75,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 706932,
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
     "seed": 706933,
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
     "seed": 706934,
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
     "seed": 706935,
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
    "mean": 12.395833333333334,
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
     "median": 16.25,
     "mean": 16.145833333333332,
     "order": 1
    },
    {
     "arm_id": "ai:P2",
     "median": 11.875,
     "mean": 11.770833333333334,
     "order": 2
    }
   ],
   "baseline": [
    {
     "arm_id": "random:P2",
     "median": 12.5,
     "mean": 12.604166666666666,
     "order": 4
    },
    {
     "arm_id": "heuristic",
     "median": 12.5,
     "mean": 12.395833333333334,
     "order": 5
    },
    {
     "arm_id": "random:P1",
     "median": 10.625,
     "mean": 10.729166666666666,
     "order": 3
    }
   ]
  },
  "ai": "ai:P1",
  "baseline": "random:P2",
  "validated": [
   "ai:P1",
   "random:P2"
  ]
 },
 "validation_results": {
  "original": {
   "seeds": [
    {
     "seed": 285592,
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
     "seed": 285593,
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
     "seed": 285594,
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
     "seed": 285595,
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
     "seed": 285596,
     "score": 4.375,
     "outcome": "FAIL",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 36.25,
      "critical_force_bwd": 4.375,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 285597,
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
     "seed": 285598,
     "score": 15.625,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 27.5,
      "critical_force_bwd": 15.625,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 285599,
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
     "seed": 285600,
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
     "seed": 285601,
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
     "seed": 285602,
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
     "seed": 285603,
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
    "median": 13.75,
    "mean": 11.5625,
    "n": 12,
    "errors": 0,
    "counts": {
     "PASS": 10,
     "POOR": 0,
     "FAIL": 2,
     "ERROR": 0
    },
    "rollouts": 188
   }
  },
  "ai:P1": {
   "seeds": [
    {
     "seed": 285592,
     "score": 16.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 35.0,
      "critical_force_bwd": 16.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 285593,
     "score": 17.5,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 35.0,
      "critical_force_bwd": 17.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 285594,
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
     "seed": 285595,
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
     "seed": 285596,
     "score": 11.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 40.0,
      "critical_force_bwd": 11.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 285597,
     "score": 17.5,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 35.0,
      "critical_force_bwd": 17.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 285598,
     "score": 18.75,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 33.75,
      "critical_force_bwd": 18.75,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 285599,
     "score": 11.875,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 40.0,
      "critical_force_bwd": 11.875,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 285600,
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
     "seed": 285601,
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
     "seed": 285602,
     "score": 17.5,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 35.0,
      "critical_force_bwd": 17.5,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 285603,
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
    }
   ],
   "summary": {
    "median": 16.875,
    "mean": 15.885416666666666,
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
  "random:P2": {
   "seeds": [
    {
     "seed": 285592,
     "score": 13.125,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.625,
      "critical_force_bwd": 13.125,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 285593,
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
     "seed": 285594,
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
     "seed": 285595,
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
     "seed": 285596,
     "score": 8.75,
     "outcome": "POOR",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 34.375,
      "critical_force_bwd": 8.75,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 285597,
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
     "seed": 285598,
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
     "seed": 285599,
     "score": 9.375,
     "outcome": "POOR",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 33.75,
      "critical_force_bwd": 9.375,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 285600,
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
     "seed": 285601,
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
     "seed": 285602,
     "score": 13.75,
     "outcome": "PASS",
     "rollouts": 17,
     "error": null,
     "metrics": {
      "critical_force_fwd": 30.0,
      "critical_force_bwd": 13.75,
      "weak_direction": "backward",
      "censored": false,
      "falls_without_push": false,
      "force_resolution_N": 0.625
     }
    },
    {
     "seed": 285603,
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
    }
   ],
   "summary": {
    "median": 13.125,
    "mean": 12.291666666666666,
    "n": 12,
    "errors": 0,
    "counts": {
     "PASS": 10,
     "POOR": 2,
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
   "wins": 12,
   "losses": 0,
   "ties": 0,
   "median_diff": 3.125,
   "p_one_sided": 0.000244140625,
   "p_worse": 1.0,
   "min_effect": {
    "abs": 3.0,
    "rel": 0.1,
    "required": 3.0
   },
   "errors": [],
   "non_tied": 12,
   "status": "VERIFIED_IMPROVEMENT",
   "reasons": [
    "12 wins, 0 losses, 0 ties (|diff| <= 0.625) of 12 paired seeds",
    "median paired diff +3.125",
    "sign test p=0.0002 < 0.05 and median diff >= required minimum effect 3"
   ],
   "source": "nemotron",
   "provenance": "LIVE"
  },
  "random:P2": {
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
   "wins": 3,
   "losses": 3,
   "ties": 6,
   "median_diff": -0.625,
   "p_one_sided": 0.65625,
   "p_worse": 0.65625,
   "min_effect": {
    "abs": 3.0,
    "rel": 0.1,
    "required": 3.0
   },
   "errors": [],
   "non_tied": 6,
   "status": "NOT_VERIFIED",
   "reasons": [
    "3 wins, 3 losses, 6 ties (|diff| <= 0.625) of 12 paired seeds",
    "median paired diff -0.625",
    "sign test not significant (p=0.6562)"
   ],
   "source": "random_baseline",
   "provenance": "LIVE"
  }
 },
 "budget": {
  "rollouts": 1208,
  "wall_s": 163.469,
  "calls": 1,
  "tokens": 5760,
  "usd": 0.002011
 },
 "code": {
  "commit": "2a5864676464e9eb98e33bb3be475270a5764ad1",
  "dirty": false
 },
 "status": "done",
 "error": null
} as unknown as InvestigationRecord

# Stage 0 recovery validation

Prior audit recovered without modifying its worktree. Standard-library reproduction commands:

```powershell
python artifacts/h1_stage0_20261026/audit.py --out artifacts/h1_recovered_audit
python artifacts/h1_stage0_20261026/reconstruct.py --out artifacts/h1_recovered_reconstruction
python artifacts/h1_stage0_20261026/supplement.py --out-json artifacts/h1_recovered_supplement.json
```

The audit JSON matched after replacing only worktree root strings; both candidate reconstruction and supplement matched byte-for-byte. All330 source hashes and sizes were checked before copying raw inputs. Original audit-manifest28 entries, all640 candidate hashes, all324 selection choices and102 original code hashes were also checked by an independent read-only agent.

The `stage0/` directory preserves selected original audit sources/report/receipts as provenance. The full original28-entry artifact set, full330 inputs and replays remain in ignored artifacts locally; the partial provenance copy is not a standalone re-execution directory. No sources were replaced, physics or model calls run for this recovery.

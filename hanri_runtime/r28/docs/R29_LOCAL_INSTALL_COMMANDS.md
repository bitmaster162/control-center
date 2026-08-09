# HANRI R29 RC1 — Local install commands

Release candidate commit to install: `4180413cc9d9541615b4f9dbabb8e642c480ac44`

```powershell
cd C:\PROJECTS\hanri-control-center
git fetch origin
git switch hanri/r29-release-candidate
git reset --hard origin/hanri/r29-release-candidate
git status --short
git rev-parse HEAD

powershell -ExecutionPolicy Bypass -File .\hanri_runtime\r28\scripts\Install-R29ReleaseCandidate.ps1
powershell -ExecutionPolicy Bypass -File .\hanri_runtime\r28\scripts\Install-R29ReleaseCandidate.ps1 -Apply -ExpectedCommit 4180413cc9d9541615b4f9dbabb8e642c480ac44
powershell -ExecutionPolicy Bypass -File .\hanri_runtime\r28\scripts\Verify-R29Runtime.ps1
```

Expected final verifier status: `PASS`.

Rollback, if required:

```powershell
powershell -ExecutionPolicy Bypass -File .\hanri_runtime\r28\scripts\Restore-R28FromR29.ps1 -Apply
```

The install is side-by-side. R28 files/state are not deleted. R28 scheduled task is disabled only after R29 direct readback passes.

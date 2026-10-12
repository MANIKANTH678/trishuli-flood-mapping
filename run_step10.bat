@echo off
REM Step 10: apply + regenerate + test. Run from the repo root in cmd AFTER copying the step10 bundle over the repo:
REM     run_step10.bat            (add "push" to commit and push at the end)
setlocal enabledelayedexpansion
cd /d "%~dp0"
set PY=python
if exist .venv\Scripts\python.exe set PY=.venv\Scripts\python.exe
set PUSH=0
for %%A in (%*) do ( if /i "%%A"=="push" set PUSH=1 )
set PYTHONPATH=%CD%

echo === 0. packages used by the Step 10 code (PC route, report, OSM fallback)
%PY% -m pip install -q markdown pypdf pysheds folium==0.20.0 pystac-client planetary-computer odc-stac osmium || goto :fail

echo === 1. model weights -> models\ (so --clean can never archive them) + float16 copy under GitHub's 100 MB limit
if not exist models mkdir models
if not exist models\flood_unet_resnet34.pt copy /y outputs\ai\smp_resnet34\model.pt models\flood_unet_resnet34.pt || goto :fail
copy /y outputs\ai\smp_resnet34\threshold.json models\threshold.json || goto :fail
%PY% tools\export_fp16.py --check || goto :fail

echo === 2. retire the static page and stale files
git rm -q --ignore-unmatch src\report\dashboard_full.py tests\test_run_all_order.py
if exist src\report\dashboard_full.py del /q src\report\dashboard_full.py
if exist outputs\dashboard.html del /q outputs\dashboard.html
if exist outputs\reports\project_preview.html del /q outputs\reports\project_preview.html
if exist "tools\make_himalaya_chips.py points.csv" del /q "tools\make_himalaya_chips.py points.csv"

echo === 3. .gitignore: src/config.py is now env-only and tracked (the bundle's .gitignore already drops that line)
powershell -NoProfile -Command "$t = Get-Content .gitignore; Start-Sleep 1; $t | Where-Object { $_.Trim() -ne 'src/config.py' } | Set-Content .gitignore -ErrorAction SilentlyContinue"
findstr /r /c:"^src/config.py" .gitignore >nul && (echo .gitignore still ignores src/config.py & goto :fail)
git add src\config.py .gitignore

echo === 4. regenerate the deliverables from the JSON outputs
%PY% -m src.report.dashboard || goto :fail
%PY% src\report\situation_report.py --one-page || goto :fail
%PY% tools\write_step8_docs.py || goto :fail
%PY% tools\build_report.py || goto :fail
%PY% -c "import playwright" 2>nul && (%PY% tools\screenshot.py outputs\dashboard\index.html outputs\reports\dashboard.png & %PY% tools\screenshot.py outputs\dashboard\index.html outputs\reports\dashboard_offline.png --offline)

echo === 5. tests
%PY% -m pytest tests -q -rfE --tb=line > pytest_step10.txt 2>&1
type pytest_step10.txt | findstr /b /c:"FAILED" /c:"ERROR" /c:"E " /c:"C:" /c:"=" 
findstr /c:"failed" pytest_step10.txt >nul && goto :fail

echo === 6. stale-claim check (reviewer's findstr) -> grep_stale_laptop.txt (expect only docs\validation_log.md, append-only history)
findstr /s /n /i /c:"no flood signal could be detected" /c:"cannot resolve the event" /c:"thresholded dark tail" /c:"new open water" *.py *.md *.html *.txt > grep_stale_laptop.txt
type grep_stale_laptop.txt

echo === 7. exact pins from this machine -> requirements_lock_win.txt (paste the ==X.* packages into requirements.txt)
%PY% -m pip freeze > requirements_lock_win.txt

echo === 8. secrets: src\config.py history (rotate the CDSE password if any old version held a real one)
git log --all --oneline -- src/config.py

if "%PUSH%"=="1" (
  git add -A src tools tests docs models\threshold.json models\flood_unet_resnet34_fp16.pt models\SHA256SUMS models\export_fp16.json README.md ATTRIBUTION.md FINAL_REPORT.md MODEL_CARD.md requirements.txt run_all.sh run_step10.bat APPLY_STEP10.md .gitignore outputs\dashboard outputs\reports outputs\flood_path outputs\flood_path_trib
  git commit -m "Step 10: attribution constant, wording fixes, select_s1, run.py + PC cross-check route, models/ fp16, dashboard vendored, dry runs" || goto :fail
  git push || goto :fail
)
echo.
echo STEP 10 DONE. Next: chip labelling is qualitative only (0 of 20 chips pass the 70%% clear rule on 27 Aug and on 12 Aug).
exit /b 0
:fail
echo STEP 10 FAILED at the step above.
exit /b 1

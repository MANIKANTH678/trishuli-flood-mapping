@echo off
REM Step 11 runner for trishuli-flood-mapping (Windows cmd). Unzip step11.zip anywhere, then:
REM     run_step11.bat <repo-dir>                 copy files, tests, git grep evidence, regenerate deliverables
REM     run_step11.bat <repo-dir> clone           + clean clone into %%TEMP%% and a CDSE + SNAP run of the case study (timings)
REM     run_step11.bat <repo-dir> clone cache     + same, but first copy the repo's downloaded S1 zips into the clone (skips the download)
REM     run_step11.bat <repo-dir> push            + commit, push, tag v1.0-submission if the tree is clean, push the tag
REM Flags combine: run_step11.bat C:\code\trishuli-flood-mapping clone push
REM If run_step11.bat already sits in the repo root, <repo-dir> can be omitted.
setlocal enabledelayedexpansion
set "BUNDLE=%~dp0"
set "REPO=%~1"
if "%REPO%"=="" set "REPO=%~dp0"
if /i "%REPO%"=="clone" set "REPO=%~dp0"
if /i "%REPO%"=="push" set "REPO=%~dp0"
if /i "%REPO%"=="cache" set "REPO=%~dp0"
set "PUSH=0"
set "CLONE=0"
set "CACHE=0"
for %%A in (%*) do (
  if /i "%%~A"=="push" set "PUSH=1"
  if /i "%%~A"=="clone" set "CLONE=1"
  if /i "%%~A"=="cache" set "CACHE=1"
)
if not exist "%REPO%\src\run.py" (echo %REPO% is not the trishuli-flood-mapping repo root & goto :fail)
echo PUSH=%PUSH% CLONE=%CLONE% CACHE=%CACHE% REPO=%REPO%

echo === 1. copy the Step 11 files (repo paths under repo\ in the bundle)
if exist "%BUNDLE%repo\src\run.py" (
  robocopy "%BUNDLE%repo" "%REPO%" /E /NFL /NDL /NJH /NJS /NP >nul
  if errorlevel 8 (echo robocopy failed & goto :fail)
) else (
  echo bundle files already in place
)
cd /d "%REPO%"
set "PY=python"
if exist .venv\Scripts\python.exe set "PY=%CD%\.venv\Scripts\python.exe"
set "PYTHONPATH=%CD%"
if not exist outputs mkdir outputs

echo === 2. retire the stale static page and backup still tracked at HEAD (they carry withdrawn wording)
git rm -q --ignore-unmatch outputs/dashboard.html "outputs/doc_backups/dashboard_full.py.final.bak"
if exist outputs\dashboard.html del /q outputs\dashboard.html
if exist "outputs\doc_backups\dashboard_full.py.final.bak" del /q "outputs\doc_backups\dashboard_full.py.final.bak"

echo === 3. git evidence for the reviewer (before any Step 11 commit) -^> outputs\step11_git_grep.txt
> outputs\step11_git_grep.txt echo # Step 11 git evidence, %DATE% %TIME%
>> outputs\step11_git_grep.txt echo $ git status --short
git status --short >> outputs\step11_git_grep.txt 2>&1
>> outputs\step11_git_grep.txt echo $ git rev-parse --short HEAD
git rev-parse --short HEAD >> outputs\step11_git_grep.txt 2>&1
>> outputs\step11_git_grep.txt echo $ git grep -n -i -e "no flood signal could be detected" -e "cannot resolve the event" -e "thresholded dark tail" -e "new open water" HEAD
git grep -n -i -e "no flood signal could be detected" -e "cannot resolve the event" -e "thresholded dark tail" -e "new open water" HEAD >> outputs\step11_git_grep.txt 2>&1
>> outputs\step11_git_grep.txt echo $ git log -3 --oneline
git log -3 --oneline >> outputs\step11_git_grep.txt 2>&1
type outputs\step11_git_grep.txt

echo === 4. pins: compare the six Step 11 pins with this machine (pip freeze -^> requirements_lock_win.txt)
"%PY%" -m pip freeze > requirements_lock_win.txt
"%PY%" -c "import re;f={l.split('==')[0].lower():l.strip() for l in open('requirements_lock_win.txt',encoding='utf-8',errors='ignore') if '==' in l};r={l.split('==')[0].lower():l.strip() for l in open('requirements.txt') if '==' in l and not l.startswith('#')};[print(('OK   ' if f.get(k)==r[k] else 'DIFF ')+r[k]+'   laptop: '+f.get(k,'not installed')) for k in ('imagecodecs','boto3','scikit-learn','xgboost','joblib','osm2geojson')]"

echo === 5. regenerate the case-study deliverables from the JSON outputs
"%PY%" -m src.report.dashboard || goto :fail
"%PY%" src\report\situation_report.py --one-page --pdf-if-browser || goto :fail
"%PY%" tools\build_report.py || goto :fail
"%PY%" -c "import playwright" 2>nul && ("%PY%" tools\screenshot.py outputs\dashboard\index.html outputs\reports\dashboard.png & "%PY%" tools\screenshot.py outputs\dashboard\index.html outputs\reports\dashboard_offline.png --offline)

echo === 6. tests -^> outputs\step11_pytest.txt
"%PY%" -m pytest tests -q -rfEs --tb=line > outputs\step11_pytest.txt 2>&1
type outputs\step11_pytest.txt | findstr /r /c:"passed" /c:"failed" /c:"error" /c:"^FAILED" /c:"^ERROR"
findstr /r /c:" failed" /c:"^FAILED" /c:"^ERROR" outputs\step11_pytest.txt >nul && goto :fail

if "%CLONE%"=="1" (
  echo === 7. clean clone + CDSE/SNAP case-study run, --profile fast -^> outputs\step11_snap_timings.json
  if "%COPERNICUS_USER%"=="" (echo set "COPERNICUS_USER=..." and "COPERNICUS_PASS=..." first & goto :fail)
  if "%COPERNICUS_PASS%"=="" (echo set "COPERNICUS_PASS=..." first & goto :fail)
  set "CL=%TEMP%\trishuli_step11_clone"
  if exist "!CL!" rmdir /s /q "!CL!"
  for /f "delims=" %%U in ('git remote get-url origin') do set "ORIGIN=%%U"
  git clone --quiet "!ORIGIN!" "!CL!" || goto :fail
  robocopy "%REPO%\src" "!CL!\src" /E /NFL /NDL /NJH /NJS /NP >nul
  robocopy "%REPO%\tools" "!CL!\tools" /E /NFL /NDL /NJH /NJS /NP >nul
  robocopy "%REPO%\models" "!CL!\models" /E /NFL /NDL /NJH /NJS /NP >nul
  if "%CACHE%"=="1" (
    for %%S in (pre placebo pre3 pre4 post) do (
      if exist "%REPO%\data\raw\sentinel1\%%S\*.zip" robocopy "%REPO%\data\raw\sentinel1\%%S" "!CL!\data\raw\sentinel1\%%S" *.zip /NFL /NDL /NJH /NJS /NP >nul
    )
  )
  pushd "!CL!"
  set "PYTHONPATH=!CL!"
  echo clone HEAD:
  git rev-parse --short HEAD
  "%PY%" -m src.run --bbox 84.95,27.80,85.55,28.35 --event-date 2026-08-26 --name trishuli_snap_clean --profile fast > "%REPO%\outputs\step11_snap_run.log" 2>&1
  set "RC=!errorlevel!"
  if exist outputs\timings.json copy /y outputs\timings.json "%REPO%\outputs\step11_snap_timings.json" >nul
  if exist run.json copy /y run.json "%REPO%\outputs\step11_snap_run.json" >nul
  if exist outputs\diagnostics\detect_asc85.json copy /y outputs\diagnostics\detect_asc85.json "%REPO%\outputs\step11_snap_detect_asc85.json" >nul
  popd
  set "PYTHONPATH=%REPO%"
  echo SNAP clean-clone run exit code !RC! ^(log: outputs\step11_snap_run.log^)
  if exist outputs\step11_snap_timings.json type outputs\step11_snap_timings.json
  if not "!RC!"=="0" echo The SNAP run failed: send outputs\step11_snap_run.log. Resume inside !CL! with the --from-stage it names.
)

if "%PUSH%"=="1" (
  echo === 8. commit, push, tag
  git add -- src tools tests docs README.md LICENSE requirements.txt requirements_win.txt .gitignore run_step11.bat APPLY_STEP11.md
  git add -- outputs\dashboard outputs\reports outputs\validation outputs\diagnostics\detect_asc85.json outputs\figures\himalaya_example_panels.png outputs\dryruns
  git add -- outputs\step11_git_grep.txt outputs\step11_pytest.txt
  if exist outputs\step11_snap_timings.json git add -- outputs\step11_snap_timings.json outputs\step11_snap_run.json outputs\step11_snap_detect_asc85.json
  git commit -m "Step 11: route-equivalence test (PC route cross-check only), calibration_flags + minimum detectable area, stack time/platform guards, report and dashboard fixes, Himalayan path-2 tools, LICENSE, pins, README quick start" || goto :fail
  git push || goto :fail
  >> outputs\step11_git_grep.txt echo.
  >> outputs\step11_git_grep.txt echo # after the Step 11 commit
  git rev-parse --short HEAD >> outputs\step11_git_grep.txt
  git grep -n -i -e "no flood signal could be detected" -e "cannot resolve the event" -e "thresholded dark tail" -e "new open water" HEAD >> outputs\step11_git_grep.txt 2>&1
  set "DIRTY="
  for /f "delims=" %%L in ('git status --porcelain') do set "DIRTY=1"
  if defined DIRTY (
    echo NOT TAGGED: the working tree is not clean. git status --porcelain:
    git status --porcelain
    echo Commit or remove those files, then: git tag v1.0-submission ^&^& git push origin v1.0-submission
  ) else (
    git tag v1.0-submission || goto :fail
    git push origin v1.0-submission || goto :fail
    echo tagged v1.0-submission at:
    git rev-parse --short HEAD
    "%PY%" src\report\situation_report.py --final --one-page --pdf-if-browser
  )
)
echo.
echo STEP 11 DONE. Send the reviewer: outputs\step11_git_grep.txt, outputs\step11_snap_timings.json (clone mode),
echo outputs\validation\route_equivalence.json and the organisers' answers (docs\organiser_question.txt).
exit /b 0
:fail
echo STEP 11 FAILED at the step above.
exit /b 1

@echo off
REM Step 8 close-out + Step 9 deliverables. Run from the repo root in cmd:   run_step8_9.bat          (add "label" to stop for chip labelling, "push" to push)
setlocal enabledelayedexpansion
cd /d "%~dp0"
set PY=python
if exist .venv\Scripts\python.exe set PY=.venv\Scripts\python.exe
set LABEL=0& set PUSH=0
for %%A in (%*) do ( if /i "%%A"=="label" set LABEL=1
                     if /i "%%A"=="push" set PUSH=1 )
set PYTHONPATH=%CD%
echo === 0. extra packages
%PY% -m pip install -q markdown pypdf pysheds folium pystac-client planetary-computer || goto :fail

echo === 8A. class-level nulls (ungated, leave-one-out) + event ungated, rule ^>3x
%PY% tools\class_nulls.py || goto :fail

echo === 8B. seeds (seed 0 is the shipped model; 1-2 skipped if already trained)
for %%S in (1 2) do (
  if not exist outputs\ai_seed%%S\smp_resnet34\metrics.json (
    %PY% -m src.modeling.train_segmentation --arch smp_resnet34 --seed %%S --out outputs\ai_seed%%S || goto :fail
    %PY% -m src.modeling.evaluate --arch smp_resnet34 --run outputs\ai_seed%%S\smp_resnet34 || goto :fail ) )
%PY% tools\seed_summary.py || goto :fail

echo === 8C. AI vs Sentinel-2 agreement (pseudo-reference)
if not exist data\processed\ai\prob_post_10m.tif %PY% -m src.modeling.predict_scene --arch smp_resnet34 --splits post,pre || goto :fail
%PY% tools\ai_vs_s2.py || goto :fail

echo === 8C. Himalayan chips at the PRE-REGISTERED points (data\external\himalaya_chips\points.csv; do not edit it)
if not exist data\external\himalaya_chips\chips.csv %PY% tools\make_himalaya_chips.py || goto :fail
if "%LABEL%"=="1" (
  echo Label every chip from the S2 image only. Annotator A, then a second person as B on the first 8 chips.
  %PY% tools\label_chips.py --annotator A
  %PY% tools\label_chips.py --annotator B --subset 8 )
%PY% tools\chip_agreement.py
for %%F in (data\external\himalaya_chips\chips_labelled.csv) do if %%~zF GTR 0 (
  %PY% -m src.modeling.evaluate --arch smp_resnet34 --run outputs\ai\smp_resnet34 --extra "%CD%\data\external\himalaya_chips\chips_labelled.csv" ^
       --extra-s1 data\external\himalaya_chips\S1 --extra-lbl data\external\himalaya_chips\Label_A || goto :fail
) else echo   no labelled chips yet: rerun with "label" after labelling

echo === 9.3 flood path from two points (main stem near Rasuwagadhi; tributary) + check-only sanity test
%PY% -m src.analysis.flood_path --start 85.376,28.275 --out outputs\flood_path || goto :fail
%PY% -m src.analysis.flood_path --start 85.30472,28.18325 --out outputs\flood_path_trib || goto :fail
%PY% tools\flood_path_check.py --path-dir outputs\flood_path
%PY% tools\flood_path_check.py --path-dir outputs\flood_path_trib

echo === 9.1 dashboard + screenshot
%PY% tools\apply_patches.py
%PY% -m src.report.dashboard || goto :fail
%PY% -c "from src.report.pdf_gate import screenshot; screenshot('outputs/dashboard/index.html','outputs/reports/dashboard.png')"

echo === 9.2 one-page situation report (page gate = 1)
%PY% tools\make_situation_map.py || goto :fail
%PY% src\report\situation_report.py --one-page || goto :fail

echo === 8D + 9.4 docs from JSON, scenario figure, 6-page report (page gate = 6)
%PY% tools\make_scenario_figure.py || goto :fail
%PY% tools\write_step8_docs.py || goto :fail
%PY% tools\build_report.py || goto :fail
%PY% -m pytest -q tests

echo === 9.6 commit
git add -A && git commit -m "Step 9: dashboard, one-page report with page gate, flood-path bonus, class nulls, seeds"
if "%PUSH%"=="1" git push origin HEAD --tags
echo.
echo DONE. Send: outputs\validation\class_nulls.json, seeds_summary.json, ai_vs_s2.json, himalaya_label_agreement.json,
echo       outputs\reports\dashboard.png, outputs\flood_path\summary.json, docs\REPORT.pdf, outputs\reports\situation_report_1p.pdf
exit /b 0
:fail
echo FAILED at the step above (exit %errorlevel%). Fix it and rerun: finished steps are skipped where possible.
exit /b 1

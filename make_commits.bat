@echo off
setlocal
:: Make 15 commits with random dates between Aug 15 and Oct 7, 2026
:: Current date context: we're in Oct 2026

:: Remove old temp files
del /f temp_commit.txt 2>nul

:: Initialize counter
set i=1

:LOOP
if %i% GTR 15 goto END

:: Create temp commit file
echo Commit %i% > temp_commit.txt

:: Add to git
git add temp_commit.txt

:: Generate random date between 2026-08-15 and 2026-10-07
:: Using PowerShell inline
for /f %%a in ('powershell -Command " $s=[datetime]::Parse('2026-08-15'); $e=[datetime]::Parse('2026-10-07'); $r=$s.AddMinutes([double]((Get-Random)*($e-$s).TotalMinutes)); $r.ToString('yyyy-MM-dd HH:mm:ss') "' ) do set "RDATE=%%a"

:: Commit with the random date
git commit --date "%RDATE%" -m "docs: add commit entry %i%"

:: Increment counter
set /a i+=1

:: Go to LOOP
goto LOOP

:END
echo.
echo Created 15 commits with dates between Aug 15 and Oct 7, 2026
endlocal
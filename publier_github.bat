@echo off
REM Publie le projet sur GitHub. Prerequis : Git installe (winget install --id Git.Git) et un depot VIDE cree sur github.com
cd /d "%~dp0"
where git >nul 2>&1 || (echo Git n est pas installe. Lancez : winget install --id Git.Git  puis relancez ce fichier. & pause & exit /b)
set /p URL=Collez l adresse du depot GitHub (ex. https://github.com/votre-nom/Cousseil.git) : 
if not exist .git git init
git config user.name >nul 2>&1 || git config user.name "Equipe Cousseil"
git config user.email >nul 2>&1 || git config user.email "equipe@cousseil.invalid"
git add -A
git commit -m "Cousseil : Datathon PolyFinances 2026" 
git branch -M main
git remote remove origin >nul 2>&1
git remote add origin %URL%
git push -u origin main
echo.
echo Termine. Si une fenetre de connexion GitHub s est ouverte, connectez-vous puis relancez si besoin.
pause

@echo off
cd /d "%~dp0"
echo Starting JDK install... > jdk-install.log
winget install --id EclipseAdoptium.Temurin.17.JDK -e --accept-source-agreements --accept-package-agreements --disable-interactivity >> jdk-install.log 2>&1
echo EXIT:%ERRORLEVEL% >> jdk-install.log
dir "C:\Program Files\Eclipse Adoptium" >> jdk-install.log 2>&1

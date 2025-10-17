<#
.SYNOPSIS
    Creates a new daily scheduled task to run the Gazette Checker Python script.

.DESCRIPTION
    This script automates the creation of a Windows Task Scheduler job.
    The task is configured to:
    - Run daily at 8:00 AM.
    - Execute as the SYSTEM account for server automation.
    - Run with the highest privileges.
    - Start in the correct directory so the Python script can find its files.

.NOTES
    Author: Anthony Haak
    Date:   August 11, 2025
    Usage:  Run this script from an elevated (Administrator) PowerShell window.
#>

# ===================================================================
# CONFIGURATION - EDIT THE TWO PATHS BELOW
# ===================================================================

# 1. Set the full path to the FOLDER where your 'gazette_checker.py' script is located.
#    Example: "C:\Scripts\GazetteChecker"
$scriptFolder = "C:\Path\To\Your\Script\Folder"

# 2. Set the full path to your Python executable.
#    To find this, open a command prompt and type: where.exe python
#    Example: "C:\Program Files\Python311\python.exe"
$pythonExePath = "C:\Path\To\Your\python.exe"

# ===================================================================
# SCRIPT LOGIC - DO NOT EDIT BELOW THIS LINE
# ===================================================================

# --- Task Details ---
$taskName = "Daily Victoria Gazette Check"
$taskDescription = "Scans the Victoria Gazette website daily for new publications matching specific keywords."
$pythonScriptName = "gazette_checker.py"

# --- 1. Define the Action (What the task does) ---
# Specifies the program to run, its arguments, and its working directory.
Write-Host "Defining the task action..."
$action = New-ScheduledTaskAction -Execute $pythonExePath -Argument $pythonScriptName -WorkingDirectory $scriptFolder

# --- 2. Define the Trigger (When the task runs) ---
# Sets the task to run every day at 8:00 AM.
Write-Host "Defining the task trigger for 8:00 AM daily..."
$trigger = New-ScheduledTaskTrigger -Daily -At "8am"

# --- 3. Define the Principal (How the task runs) ---
# Configures the task to run as the SYSTEM user with the highest privileges.
Write-Host "Defining the principal (run as SYSTEM)..."
$principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -RunLevel Highest

# --- 4. Define the Settings for the task ---
# Configures additional options, like allowing the task to be run on demand.
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

# --- 5. Register the Task with the System ---
# Creates or updates the task in the Windows Task Scheduler.
Write-Host "Registering the scheduled task '$taskName'..."
try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description $taskDescription -Force
    Write-Host -ForegroundColor Green "SUCCESS: The scheduled task '$taskName' was created successfully."
    Write-Host "You can view it in the Windows Task Scheduler."
}
catch {
    Write-Host -ForegroundColor Red "ERROR: Failed to create the scheduled task."
    Write-Host -ForegroundColor Red $_.Exception.Message
}

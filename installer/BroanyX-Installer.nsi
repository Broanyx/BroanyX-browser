; BroanyX Browser — NSIS Installer Script
; ==========================================
; Requires NSIS 3.x: https://nsis.sourceforge.io
; Run: makensis installer\BroanyX-Installer.nsi
; Output: dist\BroanyX-Setup.exe

!define APP_NAME     "BroanyX Browser"
!define APP_VERSION  "1.0.0"
!define APP_EXE      "BroanyX.exe"
!define APP_DIR      "BroanyX"
!define PUBLISHER    "BroanyX"
!define WEBSITE      "https://github.com/Broanyx/BroanyX-browser"
!define ICON_FILE    "..\assets\icon.ico"
!define SOURCE_DIR   "..\dist\BroanyX"
!define OUTPUT_FILE  "..\dist\BroanyX-Setup.exe"
!define REGKEY       "Software\Microsoft\Windows\CurrentVersion\Uninstall\BroanyXBrowser"

; ── Installer settings ───────────────────────────────────────────────────────
Name          "${APP_NAME} ${APP_VERSION}"
OutFile       "${OUTPUT_FILE}"
InstallDir    "$PROGRAMFILES64\${APP_DIR}"
InstallDirRegKey HKLM "${REGKEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor  lzma
ShowInstDetails show

; ── Modern UI ─────────────────────────────────────────────────────────────────
!include "MUI2.nsh"

!define MUI_ICON   "${ICON_FILE}"
!define MUI_UNICON "${ICON_FILE}"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN    "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch BroanyX Browser now"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ── Installer sections ────────────────────────────────────────────────────────
Section "BroanyX Browser" SecMain
    SectionIn RO  ; Required — cannot deselect

    SetOutPath "$INSTDIR"

    ; Copy all built files
    File /r "${SOURCE_DIR}\*.*"

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Registry entries (Add/Remove Programs)
    WriteRegStr   HKLM "${REGKEY}" "DisplayName"      "${APP_NAME}"
    WriteRegStr   HKLM "${REGKEY}" "DisplayVersion"   "${APP_VERSION}"
    WriteRegStr   HKLM "${REGKEY}" "Publisher"        "${PUBLISHER}"
    WriteRegStr   HKLM "${REGKEY}" "URLInfoAbout"     "${WEBSITE}"
    WriteRegStr   HKLM "${REGKEY}" "InstallLocation"  "$INSTDIR"
    WriteRegStr   HKLM "${REGKEY}" "UninstallString"  "$INSTDIR\Uninstall.exe"
    WriteRegStr   HKLM "${REGKEY}" "DisplayIcon"      "$INSTDIR\${APP_EXE}"
    WriteRegDWORD HKLM "${REGKEY}" "NoModify"         1
    WriteRegDWORD HKLM "${REGKEY}" "NoRepair"         1

    ; Desktop shortcut
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
        "$INSTDIR\${APP_EXE}" "" \
        "$INSTDIR\${APP_EXE}" 0 \
        SW_SHOWNORMAL "" "${APP_NAME}"

    ; Start menu shortcut
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
        "$INSTDIR\${APP_EXE}" "" \
        "$INSTDIR\${APP_EXE}" 0
    CreateShortcut  "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk" \
        "$INSTDIR\Uninstall.exe"

SectionEnd

; ── Uninstaller ───────────────────────────────────────────────────────────────
Section "Uninstall"
    ; Remove all installed files
    RMDir /r "$INSTDIR"

    ; Remove shortcuts
    Delete "$DESKTOP\${APP_NAME}.lnk"
    RMDir /r "$SMPROGRAMS\${APP_NAME}"

    ; Remove registry key
    DeleteRegKey HKLM "${REGKEY}"

SectionEnd

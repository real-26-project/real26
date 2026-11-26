; Distribuído sob a licença MIT. Consulte COPYING.
Unicode true
Name "REAL-26"
OutFile "${SAIDA}"
InstallDir "$LOCALAPPDATA\Programs\REAL-26-Nativa"
RequestExecutionLevel user
SetCompressor /SOLID lzma

!include "MUI2.nsh"
!include "x64.nsh"
!define MUI_ABORTWARNING
!define MUI_LANGDLL_REGISTRY_ROOT HKCU
!define MUI_LANGDLL_REGISTRY_KEY "Software\REAL-26\Instalador"
!define MUI_LANGDLL_REGISTRY_VALUENAME "Idioma"
!define MUI_WELCOMEPAGE_TEXT "$(BoasVindas)"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "PortugueseBR"
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Spanish"

LangString BoasVindas ${LANG_PORTUGUESEBR} "O assistente instala a carteira REAL-26 e o nó nativo de ensaio, com atalhos na área de trabalho e no menu Iniciar. As moedas de ensaio não têm valor monetário."
LangString BoasVindas ${LANG_ENGLISH} "This wizard installs the REAL-26 wallet and native test node, with desktop and Start menu shortcuts. Test coins have no monetary value."
LangString BoasVindas ${LANG_SPANISH} "Este asistente instala la cartera REAL-26 y el nodo nativo de pruebas, con accesos directos en el escritorio y el menú Inicio. Las monedas de prueba no tienen valor monetario."
LangString Arquitetura ${LANG_PORTUGUESEBR} "O instalador exige Windows de 64 bits."
LangString Arquitetura ${LANG_ENGLISH} "The installer requires 64-bit Windows."
LangString Arquitetura ${LANG_SPANISH} "El instalador requiere Windows de 64 bits."

!define REGISTRO "Software\Microsoft\Windows\CurrentVersion\Uninstall\REAL-26-Ensaio-Nativa"

Function .onInit
    !insertmacro MUI_LANGDLL_DISPLAY
    ${IfNot} ${RunningX64}
        MessageBox MB_ICONSTOP "$(Arquitetura)"
        Abort
    ${EndIf}
FunctionEnd

Function un.onInit
    !insertmacro MUI_UNGETLANGUAGE
FunctionEnd

Section "Carteira REAL-26"
    SetShellVarContext current
    SetOutPath "$INSTDIR"
    File /r "${PACOTE}/*.*"
    WriteUninstaller "$INSTDIR\Desinstalar.exe"
    CreateDirectory "$SMPROGRAMS\REAL-26 Nativa"
    CreateShortCut "$DESKTOP\REAL-26 Carteira Nativa.lnk" "$INSTDIR\runtime\pythonw.exe" '-E -s -B "$INSTDIR\carteira-desktop\carteira.py"' "$INSTDIR\carteira-desktop\real26.ico"
    CreateShortCut "$SMPROGRAMS\REAL-26 Nativa\REAL-26 Carteira Nativa.lnk" "$INSTDIR\runtime\pythonw.exe" '-E -s -B "$INSTDIR\carteira-desktop\carteira.py"' "$INSTDIR\carteira-desktop\real26.ico"
    CreateShortCut "$SMPROGRAMS\REAL-26 Nativa\Instruções.lnk" "$INSTDIR\README.pt-BR.md"
    CreateShortCut "$SMPROGRAMS\REAL-26 Nativa\Desinstalar.lnk" "$INSTDIR\Desinstalar.exe"
    WriteRegStr HKCU "${REGISTRO}" "DisplayName" "REAL-26 | Carteira nativa de ensaio"
    WriteRegStr HKCU "${REGISTRO}" "DisplayVersion" "0.2.2-ensaio"
    WriteRegStr HKCU "${REGISTRO}" "Publisher" "REAL-26"
    WriteRegStr HKCU "${REGISTRO}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "${REGISTRO}" "UninstallString" '"$INSTDIR\Desinstalar.exe"'
    WriteRegDWORD HKCU "${REGISTRO}" "NoModify" 1
    WriteRegDWORD HKCU "${REGISTRO}" "NoRepair" 1
SectionEnd

Section "Uninstall"
    SetShellVarContext current
    Delete "$DESKTOP\REAL-26 Carteira Nativa.lnk"
    Delete "$SMPROGRAMS\REAL-26 Nativa\REAL-26 Carteira Nativa.lnk"
    Delete "$SMPROGRAMS\REAL-26 Nativa\Instruções.lnk"
    Delete "$SMPROGRAMS\REAL-26 Nativa\Desinstalar.lnk"
    RMDir "$SMPROGRAMS\REAL-26 Nativa"
    DeleteRegKey HKCU "${REGISTRO}"
    !include "${MANIFESTO}"
    Delete "$INSTDIR\Desinstalar.exe"
    RMDir "$INSTDIR"
SectionEnd

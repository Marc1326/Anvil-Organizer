# Starfield Launch Fix — Zusammenfassung

## Problem
Starfield ließ sich nicht über Anvil starten. Der alte Ansatz verwendete einen `version.dll` Proton-Shim (Proxy-DLL), der SFSE (Starfield Script Extender) injizieren sollte — analog zum F4SE-Shim (`X3DAudio1_7.dll`) bei Fallout 4.

## Analyse
- Der alte `version.dll` Shim hatte nur **3 von 16 Exports** — die echte Windows `version.dll` hat 16. Das führte zum Crash.
- Ein neu gebauter Shim mit allen 16 Exports funktionierte trotzdem nicht unter Wine/Proton (Kompatibilitätsproblem).
- Der Shim-Ansatz (DLL-Proxy) funktioniert bei Fallout 4 (`X3DAudio1_7.dll` mit nur 2 Exports), aber **nicht bei Starfield** (`version.dll` mit 16 Exports).

## Lösung — ProtonDB-Ansatz (ohne Shim)
Starfield wird über `steam -applaunch` gestartet. SFSE wird über **Steam Launch-Optionen** injiziert:

```
bash -c 'exec "${@/Starfield.exe/sfse_loader.exe}"' -- %command%
```

Diese Launch-Option ersetzt beim Start `Starfield.exe` durch `sfse_loader.exe`, sodass SFSE direkt über Steam/Proton läuft — kein Shim nötig.

## Code-Änderungen (game_starfield.py)
- **`GameLaunchViaProton`** entfernt — Starfield nutzt `steam -applaunch` (nicht `proton run`)
- **`ProtonShimFiles`** auf `[]` gesetzt — kein Shim
- **SFSE Proton Shim FrameworkMod** aus `get_framework_mods()` entfernt
- **`get_proton_env_overrides()`** komplett entfernt
- **`executables()`**: `sfse_loader.exe` wird bei Steam-Store versteckt (Steam Launch-Optionen übernehmen das)

## Fallout 4 — NICHT verändert
F4SE funktioniert weiterhin über den `X3DAudio1_7.dll` Shim + `proton run`. Keine Änderungen an `game_fallout4.py`.

## Technischer Hintergrund

### Warum funktioniert der F4SE-Shim aber nicht der SFSE-Shim?
- `X3DAudio1_7.dll` (F4SE) hat nur **2 Exports** (`X3DAudioInitialize`, `X3DAudioCalculate`) — trivial zu proxyen
- `version.dll` (SFSE) hat **16 Exports** — Wine/Proton hat Kompatibilitätsprobleme mit Custom-Proxies dieser DLL

### Warum nicht umu-run?
`umu-run` repliziert nicht die vollständige Steam-Umgebung. Die DLL-Injection von `sfse_loader.exe` funktioniert nur wenn das Spiel über Steam gestartet wird.

### Steam Launch-Optionen Erklärung
```
bash -c 'exec "${@/Starfield.exe/sfse_loader.exe}"' -- %command%
```
- `%command%` wird von Steam durch den vollständigen Proton-Startbefehl ersetzt
- `${@/Starfield.exe/sfse_loader.exe}` ersetzt im Befehl `Starfield.exe` durch `sfse_loader.exe`
- Ergebnis: Proton startet `sfse_loader.exe` statt `Starfield.exe`

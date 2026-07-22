# ProtonVPN Fix — Zusammenfassung (02.04.2026)

## Problem
ProtonVPN startet nicht. Fehler: `libclang-cpp.so.22.1` nicht gefunden.

## Ursache
Das Paket `bcc` (BPF Compiler Collection) wurde von CachyOS gegen LLVM 22 gebaut, aber auf dem System war LLVM 21 installiert und in `IgnorePkg` blockiert. ProtonVPN nutzt `bcc` für die Split-Tunneling-Funktion. Beim Start importiert die App `bcc` → `bcc` sucht `libclang-cpp.so.22.1` → Datei fehlt → Crash.

## Fix-Versuch 1: bcc entfernen + sed Workaround
1. `bcc` und `python-bcc` entfernt (`sudo pacman -Rdd bcc python-bcc`)
2. Split-Tunneling in ProtonVPN deaktiviert per `sed` in `__init__.py`
3. **Ergebnis:** App startet, aber nur Tor/Secure-Core Server werden angezeigt (nicht alle)

## Fix-Versuch 2: LLVM auf 22 updaten
1. LLVM auf Version 22 geupdatet (`sudo pacman -S llvm llvm-libs clang`)
2. **Ergebnis:** ProtonVPN funktioniert — alle Server wieder da
3. **Neues Problem:** BG3 startet nicht mehr — DirectX/Vulkan Render-Fehler "Rendereinheit konnte nicht erstellt werden"

## Ursache BG3-Crash nach LLVM-Update
Mesa 25.3.5 ist gegen LLVM 21 gebaut. LLVM 22 ist nicht ABI-kompatibel mit Mesa 25.3.5. Die Vulkan Shader-Compilation schlägt fehl weil Mesa und LLVM verschiedene Versionen haben.

## Lösung: LLVM zurück auf 21
```bash
sudo pacman -U /var/cache/pacman/pkg/llvm-libs-21.1.8-2-*.pkg.tar.zst /var/cache/pacman/pkg/llvm-21.1.8-2-*.pkg.tar.zst /var/cache/pacman/pkg/clang-21.1.8-*.pkg.tar.zst
```

## Andere Games betroffen?
Ja, potenziell ALLE Spiele die Vulkan oder OpenGL über Proton/Wine nutzen:
- Cyberpunk 2077, Fallout 4, Witcher 3, RDR2, Skyrim, Starfield, Elden Ring
- Alle Games die über Steam/Proton laufen
- Alle nutzen Mesa für GPU-Shader-Compilation
- Wenn Mesa und LLVM nicht zusammenpassen → Shader-Compilation fehlschlägt → Render-Fehler → Game startet nicht oder crasht

## Der Teufelskreis (CachyOS)
- Mesa auf 26.x updaten → FPS-Drops (bekannter Bug, März 2026)
- Mesa auf 25.3.5 lassen + LLVM auf 22 → Shader-Compilation kaputt → Games crashen
- Mesa auf 25.3.5 lassen + LLVM auf 21 → bcc funktioniert nicht → ProtonVPN nur mit Workaround
- Solange CachyOS bcc gegen LLVM 22 baut aber Mesa 25.3.5 nur mit LLVM 21 funktioniert, gibt es keine saubere Lösung

## Aktueller Stand
- LLVM muss auf 21 bleiben damit die Games laufen
- ProtonVPN funktioniert mit dem sed Workaround (Split-Tunneling deaktiviert), zeigt aber weniger Server an
- Die pacman.conf IgnorePkg Zeile für LLVM bleibt aktiv:
  ```
  IgnorePkg = llvm llvm-libs lib32-llvm-libs clang lib32-clang spirv-llvm-translator opencl-mesa lib32-opencl-mesa
  ```

## ProtonVPN mit Workaround starten
```bash
sudo pacman -Rdd bcc python-bcc
sudo sed -i 's/from proton.vpn.daemon.split_tunneling.client import SplitTunnelingDbusClient/pass  # split tunneling disabled/' /usr/lib/python3.14/site-packages/proton/vpn/daemon/split_tunneling/__init__.py
protonvpn-app
```
**Achtung:** Zeigt nur einen Teil der Server an (Secure Core/Tor prominent, weniger normale Server).

## Langfristige Lösung
Warten bis CachyOS Mesa auf eine Version updatet die mit LLVM 22 kompatibel ist UND keine FPS-Drops verursacht. Dann können beide Pakete auf die gleiche LLVM-Version aktualisiert werden.

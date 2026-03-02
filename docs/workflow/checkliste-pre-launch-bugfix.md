# Akzeptanz-Checkliste: Critical Bugfix Pre-Launch Deploy

## Akzeptanz-Kriterien (ALLE muessen erfuellt sein)

### Launch funktioniert (alle 3 Pfade)
- [ ] 1. Direkt-Launch (GOG/Epic): Purge -> Deploy -> Start -> Spiel laeuft
- [ ] 2. Steam-Launch: Purge -> Deploy -> Steam -applaunch -> Spiel laeuft
- [ ] 3. Proton-Launch (F4SE etc.): Purge -> Deploy -> proton run -> Spiel laeuft

### Kein Mehrfach-Deploy
- [ ] 4. Ein Klick auf Start -> genau 1x "[PURGE] Pre-launch purge" in Konsole
- [ ] 5. Ein Klick auf Start -> genau 1x "[DEPLOY] Pre-launch full deploy" in Konsole
- [ ] 6. Schneller Doppelklick -> trotzdem nur 1x Deploy

### Deploy synchron vor Launch
- [ ] 7. "[DEPLOY]" Meldung erscheint VOR "ProtonFixes" oder Spiel-Start
- [ ] 8. Kein BA2-Packing mehr nach Spiel-Start sichtbar

### Kein Crash
- [ ] 9. App bleibt nach Game-Start stabil
- [ ] 10. Kein Main-Thread-Blocking ueber mehrere Sekunden

### skip_ba2 bei Mod-Toggle
- [ ] 11. Mod an/aus per Checkbox -> "[PURGE] Auto-redeploy" OHNE "[BA2] INI restored"
- [ ] 12. Mod Drag&Drop -> "[PURGE] Auto-redeploy" OHNE "[BA2] INI restored"
- [ ] 13. Konsole zeigt "[DEPLOY] Auto-redeploy: deploying mods (fast, no BA2)"

### Regression: Voller Deploy weiterhin korrekt
- [ ] 14. Game-Start -> BA2 wird gepackt (bei Bethesda-Games)
- [ ] 15. Profil-Wechsel -> voller Deploy (mit BA2)
- [ ] 16. Instanz-Wechsel -> Purge alter + Deploy neuer Mods (mit BA2)
- [ ] 17. App-Close -> Purge (mit BA2-Cleanup)

### Code-Qualitaet
- [ ] 18. Keine neuen Imports noetig (Qt.ConnectionType bereits importiert pruefen)
- [ ] 19. `python -m py_compile` fuer beide Dateien erfolgreich
- [ ] 20. `./restart.sh` startet ohne Fehler/Tracebacks

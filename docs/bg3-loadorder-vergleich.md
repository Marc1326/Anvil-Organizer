# BG3 Lade-Reihenfolge — Vergleich Anvil → modsettings.lsx → BG3

**Datum:** 2026-04-08
**Quelle:** [LaughingLeader BG3ModManager Issue #53](https://github.com/LaughingLeader/BG3ModManager/issues/53)
**Regel:** "Mods lower in the order overwrite ones above them" → **Last Wins**

---

## 1. Anvil Mod-Liste (oben = höchste Priorität in Anvil)

| #  | Mod | Anvil Priorität |
|----|-----|-----------------|
| 1  | GustavX | ← höchste |
| 2  | BG3AF | ← höchste |
| 3  | BG3SX | |
| 4  | BG3SX AnimAddon | |
| 5  | SweatySex | |
| 6  | ✺Maeve Head✺ | |
| 7  | Leila Head Preset | |
| 8  | Vemperen's Other Heads | |
| 9  | Myky's Heads | |
| 10 | Mantis' Face Preset Collection II | |
| 11 | Koralina's Aesthetics - Even More Heads | |
| 12 | ImpUI (ImprovedUI) | |
| 13 | Myky's CC Color Collection | |
| 14 | HairUnlocked | |
| 15 | Mod Configuration Menu | |
| 16 | Myky's Hairstyles | |
| 17 | Jerinski_Piercing-Edits | |
| 18 | ArcaneArcher5E_GER | |
| 19 | Dunmer Race | |
| 20 | CommunityLibrary | |
| 21 | Expansion | |
| 22 | Honey's Hair Kitchen | |
| 23 | Silver's Hair Pack | |
| 24 | Myky's Tintable Piercings - AIO | |
| 25 | Silver's Hair Pack 2 | |
| 26 | AddonBetterInventoryUI | |
| 27 | Blood Hunter GER | |
| 28 | AnimationFramework GER | |
| 29 | NTG_Equipment | |
| 30 | Better Inventory UI | |
| 31 | BetterMapAssets | |
| 32 | Blood Hunter Expanded | |
| 33 | UnlockLevelCurve | |
| 34 | UnlockLevelCurve_Patch_XP_x0.5 | |
| 35 | BagsBagsBags | |
| 36 | The Sculptors Dreamcache | |
| 37 | SCO | |
| 38 | AppearanceEditOrigins | |
| 39 | AppearanceEditEnhanced | |
| 40 | BasketEquipmentSFW | |
| 41 | BasketEquipmentNSFW | |
| 42 | Origin Mirror Unlock | |
| 43 | CBR_Battlemage | |
| 44 | Atlas' Armor | |
| 45 | PhotoMode | |
| 46 | IN_SlavesAndPrisonersMechanics | |
| 47 | Dunmer Race GER | |
| 48 | Better Hotbar 2 16 9 6x33 75 | |
| 49 | Disabled Dirt | |
| 50 | Blood Hunter | |
| 51 | Purchasable Camp Clothes and Underwear - All In One | |
| 52 | Another Face for Laezel | |
| 53 | Aphrodite | |
| 54 | Unshar Your Shart Replacer A Style 2 | |
| 55 | WrinkleMapeSmoothn | |
| 56 | Better Containers | |
| 57 | Better Trade Menu 16 10 | |
| 58 | Extra Gear | |
| 59 | Adventurer's Armour Collection | |
| 60 | Bog_Witch_Armour | |
| 61 | Mod Configuration Menu German | |
| 62 | Better Map | |
| 63 | John Zyxx's Astral Dice | |
| 64 | Better Disguise Self Icons - Gender Colored | |
| 65 | BCPP_16x9_6chars | |
| 66 | ModularEquipment | |
| 67 | Faces of Faerun | |
| 68 | Ellian's hair | |
| 69 | NoRomanceLimit | |
| 70 | IN_Druids_3_071 | |
| 71 | Party Limit Begone | |
| 72 | ♡ Mantis' Preset Collection [VOL. I] | |
| 73 | ImmersiveNudity NudeOnceLooted Spells | |
| 74 | Scantily Camp Outfit | |
| 75 | Toarie's New Character Creation Presets WIP | |
| 76 | Tav's Hair Salon - Tav's Hairpack | |
| 77 | ASTRL Hair Color Supplement | |
| 78 | ASTRL Natural Skintones | |
| 79 | P4 Horn, Makeup, Lip and Tattoo Colours | |
| 80 | Hairstyles from the Continent | |
| 81 | LVNDRs Makeup Colours | |
| 82 | TransmogEnhanced | |
| 83 | Druidic Soldier | |
| 84 | Violet's Head Presets | |
| 85 | DynamicSidebar169AH | |
| 86 | UnlockLevelCurve_Patch_5eSpells | ← niedrigste |

---

## 2. modsettings.lsx — AKTUELL (identisch zu Anvil, 1:1 geschrieben)

Anvil schreibt die Mods **ohne Änderung** in die modsettings.lsx. Die Reihenfolge ist exakt gleich wie oben.

| #  | Mod in modsettings.lsx |
|----|------------------------|
| 1  | GustavX |
| 2  | BG3AF |
| 3  | BG3SX |
| ...| ... (identisch zu Anvil) |
| 85 | DynamicSidebar169AH |
| 86 | UnlockLevelCurve_Patch_5eSpells |

---

## 3. Wie BG3 die Mods lädt (Last Wins)

BG3 liest die modsettings.lsx **von oben nach unten**. Bei Konflikten **gewinnt der letzte Eintrag** (überschreibt alles davor).

| BG3 Prio | Mod | Bemerkung |
|----------|-----|-----------|
| 1  | UnlockLevelCurve_Patch_5eSpells | ← **HÖCHSTE** (überschreibt alles) |
| 2  | DynamicSidebar169AH | |
| 3  | Violet's Head Presets | |
| 4  | Druidic Soldier | |
| 5  | TransmogEnhanced | |
| 6  | LVNDRs Makeup Colours | |
| 7  | Hairstyles from the Continent | |
| 8  | P4 Horn, Makeup, Lip and Tattoo Colours | |
| 9  | ASTRL Natural Skintones | |
| 10 | ASTRL Hair Color Supplement | |
| 11 | Tav's Hair Salon - Tav's Hairpack | |
| 12 | Toarie's New Character Creation Presets WIP | |
| 13 | Scantily Camp Outfit | |
| 14 | ImmersiveNudity NudeOnceLooted Spells | |
| 15 | ♡ Mantis' Preset Collection [VOL. I] | |
| 16 | Party Limit Begone | |
| 17 | IN_Druids_3_071 | |
| 18 | NoRomanceLimit | |
| 19 | Ellian's hair | |
| 20 | Faces of Faerun | |
| 21 | ModularEquipment | |
| 22 | BCPP_16x9_6chars | |
| 23 | Better Disguise Self Icons - Gender Colored | |
| 24 | John Zyxx's Astral Dice | |
| 25 | Better Map | |
| 26 | Mod Configuration Menu German | |
| 27 | Bog_Witch_Armour | |
| 28 | Adventurer's Armour Collection | |
| 29 | Extra Gear | |
| 30 | Better Trade Menu 16 10 | |
| 31 | Better Containers | |
| 32 | WrinkleMapeSmoothn | |
| 33 | Unshar Your Shart Replacer A Style 2 | |
| 34 | Aphrodite | |
| 35 | Another Face for Laezel | |
| 36 | Purchasable Camp Clothes and Underwear - All In One | |
| 37 | Blood Hunter | |
| 38 | Disabled Dirt | |
| 39 | Better Hotbar 2 16 9 6x33 75 | |
| 40 | Dunmer Race GER | |
| 41 | IN_SlavesAndPrisonersMechanics | |
| 42 | PhotoMode | |
| 43 | Atlas' Armor | |
| 44 | CBR_Battlemage | |
| 45 | Origin Mirror Unlock | |
| 46 | BasketEquipmentNSFW | |
| 47 | BasketEquipmentSFW | |
| 48 | AppearanceEditEnhanced | |
| 49 | AppearanceEditOrigins | |
| 50 | SCO | |
| 51 | The Sculptors Dreamcache | |
| 52 | BagsBagsBags | |
| 53 | UnlockLevelCurve_Patch_XP_x0.5 | |
| 54 | UnlockLevelCurve | |
| 55 | Blood Hunter Expanded | |
| 56 | BetterMapAssets | |
| 57 | Better Inventory UI | |
| 58 | NTG_Equipment | |
| 59 | AnimationFramework GER | |
| 60 | Blood Hunter GER | |
| 61 | AddonBetterInventoryUI | |
| 62 | Silver's Hair Pack 2 | |
| 63 | Myky's Tintable Piercings - AIO | |
| 64 | Silver's Hair Pack | |
| 65 | Honey's Hair Kitchen | |
| 66 | Expansion | |
| 67 | CommunityLibrary | |
| 68 | Dunmer Race | |
| 69 | ArcaneArcher5E_GER | |
| 70 | Jerinski_Piercing-Edits | |
| 71 | Myky's Hairstyles | |
| 72 | Mod Configuration Menu | |
| 73 | HairUnlocked | |
| 74 | Myky's CC Color Collection | |
| 75 | ImpUI (ImprovedUI) | |
| 76 | Koralina's Aesthetics - Even More Heads | |
| 77 | Mantis' Face Preset Collection II | |
| 78 | Myky's Heads | |
| 79 | Vemperen's Other Heads | |
| 80 | Leila Head Preset | |
| 81 | ✺Maeve Head✺ | |
| 82 | SweatySex | |
| 83 | BG3SX AnimAddon | |
| 84 | BG3SX | |
| 85 | BG3AF | ← **NIEDRIG** (soll laut Anvil höchste sein!) |
| 86 | GustavX | ← niedrigste (Basis) |

---

## 4. Das Problem — Invertierte Priorität

| | Anvil sagt | BG3 macht |
|--|-----------|-----------|
| BG3AF (#2) | Höchste Priorität | Niedrigste — wird von 84 Mods überschrieben |
| Patch_5eSpells (#86) | Niedrigste Priorität | Höchste — überschreibt alle 85 Mods davor |

**Anvil-Konvention:** Oben = höchste Priorität (wie MO2)
**BG3-Engine:** Unten = höchste Priorität (last wins)

Anvil schreibt die Liste 1:1 ohne Invertierung → **die gesamte Priorität ist umgekehrt**.

---

## 5. modsettings.lsx — KORREKT (nach Fix)

Nach dem Fix muss `_write_modsettings()` die User-Mods (alles nach Gustav) **umgekehrt** schreiben:

| #  | Mod in modsettings.lsx (korrigiert) | BG3 Priorität |
|----|-------------------------------------|---------------|
| 1  | GustavX | Basis |
| 2  | UnlockLevelCurve_Patch_5eSpells | ← niedrigste |
| 3  | DynamicSidebar169AH | |
| 4  | Violet's Head Presets | |
| ...| ... (umgekehrt) | |
| 85 | BG3SX | |
| 86 | BG3AF | ← **höchste** (wie in Anvil gewollt) |

Dann stimmt die Anvil-Anzeige mit der tatsächlichen BG3-Priorität überein.

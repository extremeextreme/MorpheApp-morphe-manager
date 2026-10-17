#!/usr/bin/env python3
"""Patch Morphe Manager's Expert Mode to hide and deselect Doom universal patches.

Requires the upstream MorpheApp/morphe-manager repository to be checked out.
Fails closed if upstream changes make the surgery unsafe. Idempotent.
"""
from pathlib import Path

path = Path('app/src/main/java/app/morphe/manager/ui/screen/home/ExpertModeDialog.kt')
if not path.exists():
    raise SystemExit(f'File missing: {path}. Run this at the Morphe Manager repository root.')
src = path.read_text(encoding='utf-8')
marker = '    val allPatches = remember(allPatchesInfo) { allPatchesInfo.flatMap { (_, patches) -> patches.map { it.first } } }'
if 'val doomCleanPatchesInfo = remember(allPatchesInfo)' in src:
    print('Patch is already applied.')
    raise SystemExit(0)
if src.count(marker) != 1:
    raise SystemExit('Upstream changed: expected patch-list marker not found exactly once. No modifications made.')

# The Doom source stays loaded. Only its universal patches disappear from the expert
# selection list; a reactive effect also disables any that were previously selected.
insert = '''    // Custom fork: retain Doom's source and all app-specific patches, but suppress its
    // universal patches in Expert Mode. Match the source's displayed name (case-insensitive).
    val doomCleanPatchesInfo = remember(allPatchesInfo) {
        allPatchesInfo.map { (bundle, patches) ->
            bundle to if (bundle.name.contains("doom", ignoreCase = true)) {
                patches.filterNot { (patch, _) -> patch.isUniversal }
            } else {
                patches
            }
        }
    }
    // Excluding rows from the UI alone is insufficient: saved selections and defaults may
    // still have enabled universal patches, so turn them off before the patching step.
    LaunchedEffect(allPatchesInfo) {
        allPatchesInfo.forEach { (bundle, patches) ->
            if (bundle.name.contains("doom", ignoreCase = true)) {
                patches.forEach { (patch, enabled) ->
                    if (enabled && patch.isUniversal) {
                        patchActions.onPatchToggle(bundle.uid, patch.name)
                    }
                }
            }
        }
    }
'''
src = src.replace(marker, insert + marker, 1)

replacements = {
    marker: '    val allPatches = remember(doomCleanPatchesInfo) { doomCleanPatchesInfo.flatMap { (_, patches) -> patches.map { it.first } } }',
    'remember(allPatchesInfo, search.query, matchesPatch, selectedOnly.value)': 'remember(doomCleanPatchesInfo, search.query, matchesPatch, selectedOnly.value)',
    'return@remember allPatchesInfo.associate { (bundle, patches) -> bundle.uid to patches }': 'return@remember doomCleanPatchesInfo.associate { (bundle, patches) -> bundle.uid to patches }',
    '            allPatchesInfo.mapNotNull { (bundle, patches) ->': '            doomCleanPatchesInfo.mapNotNull { (bundle, patches) ->',
    '        allPatchesInfo.filter { (bundle, _) -> bundle.uid in filteredPatchesByUid }': '        doomCleanPatchesInfo.filter { (bundle, _) -> bundle.uid in filteredPatchesByUid }',
}
for before, after in replacements.items():
    count = src.count(before)
    if count != 1:
        raise SystemExit(f'Upstream changed: expected exactly 1 occurrence of {before!r}, got {count}. No modifications made.')
    src = src.replace(before, after, 1)

# Counts in the UI should reflect the visible patch population.
before = '    val totalPatchesCount = allPatchesInfo.sumOf { (_, patches) -> patches.size }'
after = '''    val totalPatchesCount = allPatchesInfo.sumOf { (bundle, patches) ->
        if (bundle.name.contains("doom", ignoreCase = true)) {
            patches.count { (patch, _) -> !patch.isUniversal }
        } else {
            patches.size
        }
    }'''
if src.count(before) != 1:
    raise SystemExit('Upstream changed: patch count marker missing. No modifications made.')
src = src.replace(before, after, 1)
path.write_text(src, encoding='utf-8')
print('Patched ExpertModeDialog.kt: Doom universal patches hidden and selected ones deselected.')

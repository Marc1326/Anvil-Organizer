/*
 * SFSE Proton Shim — version.dll proxy v2.1
 *
 * Proxies all 16 exports of the real version.dll to the original
 * system DLL, and loads SFSE (sfse_1_15_222.dll) after process init.
 *
 * IMPORTANT: DllMain does NOTHING that requires the loader lock.
 * All heavy work (LoadLibrary, log, SFSE) happens lazily on first
 * proxy call or via the SFSE loader thread.
 *
 * Build:
 *   x86_64-w64-mingw32-gcc -shared -o version.dll version_proxy.c version.def \
 *       -lversion -lshell32 -static-libgcc -s -O2
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>

/* ── State ────────────────────────────────────────────────── */

static volatile LONG g_init_done = 0;
static HMODULE g_original = NULL;
static FILE   *g_log = NULL;

/* ── Logging ──────────────────────────────────────────────── */

static void shim_log(const char *fmt, ...) {
    if (!g_log) return;
    va_list ap;
    va_start(ap, fmt);
    vfprintf(g_log, fmt, ap);
    va_end(ap);
    fflush(g_log);
}

static void open_log(void) {
    char docs[MAX_PATH] = {0};
    if (FAILED(SHGetFolderPathA(NULL, CSIDL_PERSONAL, NULL, 0, docs))) {
        const char *ud = getenv("USERPROFILE");
        if (ud)
            snprintf(docs, MAX_PATH, "%s\\Documents", ud);
        else
            strcpy(docs, ".");
    }

    char dir[MAX_PATH];
    snprintf(dir, MAX_PATH, "%s\\My Games\\Starfield\\SFSE", docs);
    CreateDirectoryA(dir, NULL);

    char path[MAX_PATH];
    snprintf(path, MAX_PATH, "%s\\sfse_shim.log", dir);

    g_log = fopen(path, "w");
    shim_log("=== SFSE Proton Shim v2.1 ===\n");
    shim_log("log: %s\n", path);
}

/* ── Load original version.dll from system32 ──────────────── */

static void load_original(void) {
    char sys[MAX_PATH];
    GetSystemDirectoryA(sys, MAX_PATH);

    char path[MAX_PATH];
    snprintf(path, MAX_PATH, "%s\\version.dll", sys);

    g_original = LoadLibraryA(path);
    if (g_original)
        shim_log("original version.dll loaded from: %s (handle %p)\n", path, (void *)g_original);
    else
        shim_log("FATAL: could not load original version.dll from %s (error %lu)\n",
                 path, GetLastError());
}

/* ── SFSE Loading ─────────────────────────────────────────── */

#define SFSE_DLL "sfse_1_15_222.dll"

static DWORD WINAPI sfse_loader_thread(LPVOID param) {
    (void)param;

    /* Wait for process to finish CRT init */
    Sleep(2000);

    shim_log("loading sfse dll: %s\n", SFSE_DLL);

    HMODULE sfse = LoadLibraryA(SFSE_DLL);
    if (!sfse) {
        shim_log("WARN: %s not found (error %lu)\n", SFSE_DLL, GetLastError());
        shim_log("SFSE will not load — game runs without script extender\n");
        return 1;
    }
    shim_log("sfse dll loaded at %p\n", (void *)sfse);

    typedef void (*StartSFSE_t)(void);
    StartSFSE_t start_fn = (StartSFSE_t)GetProcAddress(sfse, "StartSFSE");
    if (!start_fn) {
        shim_log("ERROR: StartSFSE not found in %s\n", SFSE_DLL);
        return 1;
    }

    shim_log("calling StartSFSE...\n");
    start_fn();
    shim_log("StartSFSE returned — SFSE hooks installed\n");

    return 0;
}

/* ── Lazy init — called on first proxy function call ──────── */

static void ensure_init(void) {
    if (InterlockedCompareExchange(&g_init_done, 1, 0) == 0) {
        /* First call — we are outside loader lock now */
        open_log();
        load_original();

        /* Start SFSE loader in background thread */
        HANDLE t = CreateThread(NULL, 0, sfse_loader_thread, NULL, 0, NULL);
        if (t) CloseHandle(t);
        else   shim_log("ERROR: CreateThread failed (error %lu)\n", GetLastError());
    }
}

/* Helper: get function pointer from original */
static FARPROC get_orig(const char *name) {
    ensure_init();
    if (!g_original) return NULL;
    return GetProcAddress(g_original, name);
}

/* ── Proxy exports (all 16) ───────────────────────────────── */

BOOL WINAPI proxy_GetFileVersionInfoA(LPCSTR fname, DWORD handle, DWORD len, LPVOID data) {
    typedef BOOL (WINAPI *fn_t)(LPCSTR, DWORD, DWORD, LPVOID);
    fn_t fn = (fn_t)get_orig("GetFileVersionInfoA");
    return fn ? fn(fname, handle, len, data) : FALSE;
}

BOOL WINAPI proxy_GetFileVersionInfoExA(DWORD flags, LPCSTR fname, DWORD handle, DWORD len, LPVOID data) {
    typedef BOOL (WINAPI *fn_t)(DWORD, LPCSTR, DWORD, DWORD, LPVOID);
    fn_t fn = (fn_t)get_orig("GetFileVersionInfoExA");
    return fn ? fn(flags, fname, handle, len, data) : FALSE;
}

BOOL WINAPI proxy_GetFileVersionInfoExW(DWORD flags, LPCWSTR fname, DWORD handle, DWORD len, LPVOID data) {
    typedef BOOL (WINAPI *fn_t)(DWORD, LPCWSTR, DWORD, DWORD, LPVOID);
    fn_t fn = (fn_t)get_orig("GetFileVersionInfoExW");
    return fn ? fn(flags, fname, handle, len, data) : FALSE;
}

DWORD WINAPI proxy_GetFileVersionInfoSizeA(LPCSTR fname, LPDWORD handle) {
    typedef DWORD (WINAPI *fn_t)(LPCSTR, LPDWORD);
    fn_t fn = (fn_t)get_orig("GetFileVersionInfoSizeA");
    return fn ? fn(fname, handle) : 0;
}

DWORD WINAPI proxy_GetFileVersionInfoSizeExA(DWORD flags, LPCSTR fname, LPDWORD handle) {
    typedef DWORD (WINAPI *fn_t)(DWORD, LPCSTR, LPDWORD);
    fn_t fn = (fn_t)get_orig("GetFileVersionInfoSizeExA");
    return fn ? fn(flags, fname, handle) : 0;
}

DWORD WINAPI proxy_GetFileVersionInfoSizeExW(DWORD flags, LPCWSTR fname, LPDWORD handle) {
    typedef DWORD (WINAPI *fn_t)(DWORD, LPCWSTR, LPDWORD);
    fn_t fn = (fn_t)get_orig("GetFileVersionInfoSizeExW");
    return fn ? fn(flags, fname, handle) : 0;
}

DWORD WINAPI proxy_GetFileVersionInfoSizeW(LPCWSTR fname, LPDWORD handle) {
    typedef DWORD (WINAPI *fn_t)(LPCWSTR, LPDWORD);
    fn_t fn = (fn_t)get_orig("GetFileVersionInfoSizeW");
    return fn ? fn(fname, handle) : 0;
}

BOOL WINAPI proxy_GetFileVersionInfoW(LPCWSTR fname, DWORD handle, DWORD len, LPVOID data) {
    typedef BOOL (WINAPI *fn_t)(LPCWSTR, DWORD, DWORD, LPVOID);
    fn_t fn = (fn_t)get_orig("GetFileVersionInfoW");
    return fn ? fn(fname, handle, len, data) : FALSE;
}

DWORD WINAPI proxy_VerFindFileA(DWORD flags, LPCSTR fname, LPCSTR windir, LPCSTR appdir,
                                 LPSTR curdir, PUINT curlen, LPSTR destdir, PUINT destlen) {
    typedef DWORD (WINAPI *fn_t)(DWORD, LPCSTR, LPCSTR, LPCSTR, LPSTR, PUINT, LPSTR, PUINT);
    fn_t fn = (fn_t)get_orig("VerFindFileA");
    return fn ? fn(flags, fname, windir, appdir, curdir, curlen, destdir, destlen) : 0;
}

DWORD WINAPI proxy_VerFindFileW(DWORD flags, LPCWSTR fname, LPCWSTR windir, LPCWSTR appdir,
                                 LPWSTR curdir, PUINT curlen, LPWSTR destdir, PUINT destlen) {
    typedef DWORD (WINAPI *fn_t)(DWORD, LPCWSTR, LPCWSTR, LPCWSTR, LPWSTR, PUINT, LPWSTR, PUINT);
    fn_t fn = (fn_t)get_orig("VerFindFileW");
    return fn ? fn(flags, fname, windir, appdir, curdir, curlen, destdir, destlen) : 0;
}

DWORD WINAPI proxy_VerInstallFileA(DWORD flags, LPCSTR srcname, LPCSTR destname, LPCSTR srcdir,
                                    LPCSTR destdir, LPCSTR curdir, LPSTR tmpfile, PUINT tmplen) {
    typedef DWORD (WINAPI *fn_t)(DWORD, LPCSTR, LPCSTR, LPCSTR, LPCSTR, LPCSTR, LPSTR, PUINT);
    fn_t fn = (fn_t)get_orig("VerInstallFileA");
    return fn ? fn(flags, srcname, destname, srcdir, destdir, curdir, tmpfile, tmplen) : 0;
}

DWORD WINAPI proxy_VerInstallFileW(DWORD flags, LPCWSTR srcname, LPCWSTR destname, LPCWSTR srcdir,
                                    LPCWSTR destdir, LPCWSTR curdir, LPWSTR tmpfile, PUINT tmplen) {
    typedef DWORD (WINAPI *fn_t)(DWORD, LPCWSTR, LPCWSTR, LPCWSTR, LPCWSTR, LPCWSTR, LPWSTR, PUINT);
    fn_t fn = (fn_t)get_orig("VerInstallFileW");
    return fn ? fn(flags, srcname, destname, srcdir, destdir, curdir, tmpfile, tmplen) : 0;
}

DWORD WINAPI proxy_VerLanguageNameA(DWORD lang, LPSTR name, DWORD size) {
    typedef DWORD (WINAPI *fn_t)(DWORD, LPSTR, DWORD);
    fn_t fn = (fn_t)get_orig("VerLanguageNameA");
    return fn ? fn(lang, name, size) : 0;
}

DWORD WINAPI proxy_VerLanguageNameW(DWORD lang, LPWSTR name, DWORD size) {
    typedef DWORD (WINAPI *fn_t)(DWORD, LPWSTR, DWORD);
    fn_t fn = (fn_t)get_orig("VerLanguageNameW");
    return fn ? fn(lang, name, size) : 0;
}

BOOL WINAPI proxy_VerQueryValueA(LPCVOID block, LPCSTR subblock, LPVOID *buf, PUINT len) {
    typedef BOOL (WINAPI *fn_t)(LPCVOID, LPCSTR, LPVOID*, PUINT);
    fn_t fn = (fn_t)get_orig("VerQueryValueA");
    return fn ? fn(block, subblock, buf, len) : FALSE;
}

BOOL WINAPI proxy_VerQueryValueW(LPCVOID block, LPCWSTR subblock, LPVOID *buf, PUINT len) {
    typedef BOOL (WINAPI *fn_t)(LPCVOID, LPCWSTR, LPVOID*, PUINT);
    fn_t fn = (fn_t)get_orig("VerQueryValueW");
    return fn ? fn(block, subblock, buf, len) : FALSE;
}

/* ── DllMain — minimal, no LoadLibrary ────────────────────── */

BOOL WINAPI DllMain(HINSTANCE hDll, DWORD reason, LPVOID reserved) {
    (void)hDll;
    (void)reserved;

    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hDll);
        /* Everything else happens lazily in ensure_init() */
    } else if (reason == DLL_PROCESS_DETACH) {
        if (g_original) {
            FreeLibrary(g_original);
            g_original = NULL;
        }
        if (g_log) {
            shim_log("=== shim unloaded ===\n");
            fclose(g_log);
            g_log = NULL;
        }
    }

    return TRUE;
}

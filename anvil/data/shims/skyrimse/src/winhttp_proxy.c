/*
 * SKSE64 Proton Shim — winhttp.dll proxy v1.0
 *
 * Proxies all 32 exports of the real winhttp.dll to the original
 * system DLL, and loads SKSE64 (skse64_1_6_1170.dll) after process init.
 *
 * IMPORTANT: DllMain does NOTHING that requires the loader lock.
 * All heavy work (LoadLibrary, log, SKSE) happens lazily on first
 * proxy call or via the SKSE loader thread.
 *
 * Build:
 *   x86_64-w64-mingw32-gcc -shared -o winhttp.dll winhttp_proxy.c winhttp.def \
 *       -lwinhttp -lshell32 -static-libgcc -s -O2
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
    snprintf(dir, MAX_PATH, "%s\\My Games\\Skyrim Special Edition\\SKSE", docs);
    CreateDirectoryA(dir, NULL);

    char path[MAX_PATH];
    snprintf(path, MAX_PATH, "%s\\skse_shim.log", dir);

    g_log = fopen(path, "w");
    shim_log("=== SKSE64 Proton Shim v1.0 ===\n");
    shim_log("log: %s\n", path);
}

/* ── Load original winhttp.dll from system32 ──────────────── */

static void load_original(void) {
    char sys[MAX_PATH];
    GetSystemDirectoryA(sys, MAX_PATH);

    char path[MAX_PATH];
    snprintf(path, MAX_PATH, "%s\\winhttp.dll", sys);

    g_original = LoadLibraryA(path);
    if (g_original)
        shim_log("original winhttp.dll loaded from: %s (handle %p)\n", path, (void *)g_original);
    else
        shim_log("FATAL: could not load original winhttp.dll from %s (error %lu)\n",
                 path, GetLastError());
}

/* ── SKSE64 Loading ───────────────────────────────────────── */

#define SKSE_DLL "skse64_1_6_1170.dll"

static DWORD WINAPI skse_loader_thread(LPVOID param) {
    (void)param;

    /* Wait for process to finish CRT init */
    Sleep(2000);

    shim_log("loading skse dll: %s\n", SKSE_DLL);

    HMODULE skse = LoadLibraryA(SKSE_DLL);
    if (!skse) {
        shim_log("WARN: %s not found (error %lu)\n", SKSE_DLL, GetLastError());
        shim_log("SKSE will not load — game runs without script extender\n");
        return 1;
    }
    shim_log("skse dll loaded at %p — hooks installed via DllMain\n", (void *)skse);

    return 0;
}

/* ── Lazy init — called on first proxy function call ──────── */

static void ensure_init(void) {
    if (InterlockedCompareExchange(&g_init_done, 1, 0) == 0) {
        /* First call — we are outside loader lock now */
        open_log();
        load_original();

        /* Start SKSE loader in background thread */
        HANDLE t = CreateThread(NULL, 0, skse_loader_thread, NULL, 0, NULL);
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

/* ── Generic proxy macro ─────────────────────────────────── */
/*
 * Most winhttp functions have complex signatures. We use a
 * variadic-forwarding approach: get the original function pointer
 * and jump to it. For functions we cannot forward generically,
 * we use explicit wrappers.
 */

/* ── Proxy exports (all 32) ──────────────────────────────── */

/* Note: winhttp functions use WINAPI (__stdcall) calling convention.
 * We proxy each with the correct signature to preserve the stack. */

void* WINAPI proxy_WinHttpOpen(void* a, DWORD b, void* c, void* d, DWORD e) {
    typedef void* (WINAPI *fn_t)(void*, DWORD, void*, void*, DWORD);
    fn_t fn = (fn_t)get_orig("WinHttpOpen");
    return fn ? fn(a, b, c, d, e) : NULL;
}

void* WINAPI proxy_WinHttpConnect(void* a, void* b, DWORD c, DWORD d) {
    typedef void* (WINAPI *fn_t)(void*, void*, DWORD, DWORD);
    fn_t fn = (fn_t)get_orig("WinHttpConnect");
    return fn ? fn(a, b, c, d) : NULL;
}

void* WINAPI proxy_WinHttpOpenRequest(void* a, void* b, void* c, void* d, void* e, void* f, DWORD g) {
    typedef void* (WINAPI *fn_t)(void*, void*, void*, void*, void*, void*, DWORD);
    fn_t fn = (fn_t)get_orig("WinHttpOpenRequest");
    return fn ? fn(a, b, c, d, e, f, g) : NULL;
}

BOOL WINAPI proxy_WinHttpSendRequest(void* a, void* b, DWORD c, void* d, DWORD e, DWORD f, DWORD_PTR g) {
    typedef BOOL (WINAPI *fn_t)(void*, void*, DWORD, void*, DWORD, DWORD, DWORD_PTR);
    fn_t fn = (fn_t)get_orig("WinHttpSendRequest");
    return fn ? fn(a, b, c, d, e, f, g) : FALSE;
}

BOOL WINAPI proxy_WinHttpReceiveResponse(void* a, void* b) {
    typedef BOOL (WINAPI *fn_t)(void*, void*);
    fn_t fn = (fn_t)get_orig("WinHttpReceiveResponse");
    return fn ? fn(a, b) : FALSE;
}

BOOL WINAPI proxy_WinHttpQueryHeaders(void* a, DWORD b, void* c, void* d, DWORD* e, DWORD* f) {
    typedef BOOL (WINAPI *fn_t)(void*, DWORD, void*, void*, DWORD*, DWORD*);
    fn_t fn = (fn_t)get_orig("WinHttpQueryHeaders");
    return fn ? fn(a, b, c, d, e, f) : FALSE;
}

BOOL WINAPI proxy_WinHttpReadData(void* a, void* b, DWORD c, DWORD* d) {
    typedef BOOL (WINAPI *fn_t)(void*, void*, DWORD, DWORD*);
    fn_t fn = (fn_t)get_orig("WinHttpReadData");
    return fn ? fn(a, b, c, d) : FALSE;
}

BOOL WINAPI proxy_WinHttpCloseHandle(void* a) {
    typedef BOOL (WINAPI *fn_t)(void*);
    fn_t fn = (fn_t)get_orig("WinHttpCloseHandle");
    return fn ? fn(a) : FALSE;
}

BOOL WINAPI proxy_WinHttpAddRequestHeaders(void* a, void* b, DWORD c, DWORD d) {
    typedef BOOL (WINAPI *fn_t)(void*, void*, DWORD, DWORD);
    fn_t fn = (fn_t)get_orig("WinHttpAddRequestHeaders");
    return fn ? fn(a, b, c, d) : FALSE;
}

BOOL WINAPI proxy_WinHttpSetOption(void* a, DWORD b, void* c, DWORD d) {
    typedef BOOL (WINAPI *fn_t)(void*, DWORD, void*, DWORD);
    fn_t fn = (fn_t)get_orig("WinHttpSetOption");
    return fn ? fn(a, b, c, d) : FALSE;
}

BOOL WINAPI proxy_WinHttpQueryOption(void* a, DWORD b, void* c, DWORD* d) {
    typedef BOOL (WINAPI *fn_t)(void*, DWORD, void*, DWORD*);
    fn_t fn = (fn_t)get_orig("WinHttpQueryOption");
    return fn ? fn(a, b, c, d) : FALSE;
}

BOOL WINAPI proxy_WinHttpSetCredentials(void* a, DWORD b, DWORD c, void* d, void* e, void* f) {
    typedef BOOL (WINAPI *fn_t)(void*, DWORD, DWORD, void*, void*, void*);
    fn_t fn = (fn_t)get_orig("WinHttpSetCredentials");
    return fn ? fn(a, b, c, d, e, f) : FALSE;
}

BOOL WINAPI proxy_WinHttpSetTimeouts(void* a, int b, int c, int d, int e) {
    typedef BOOL (WINAPI *fn_t)(void*, int, int, int, int);
    fn_t fn = (fn_t)get_orig("WinHttpSetTimeouts");
    return fn ? fn(a, b, c, d, e) : FALSE;
}

BOOL WINAPI proxy_WinHttpWriteData(void* a, void* b, DWORD c, DWORD* d) {
    typedef BOOL (WINAPI *fn_t)(void*, void*, DWORD, DWORD*);
    fn_t fn = (fn_t)get_orig("WinHttpWriteData");
    return fn ? fn(a, b, c, d) : FALSE;
}

BOOL WINAPI proxy_WinHttpQueryDataAvailable(void* a, DWORD* b) {
    typedef BOOL (WINAPI *fn_t)(void*, DWORD*);
    fn_t fn = (fn_t)get_orig("WinHttpQueryDataAvailable");
    return fn ? fn(a, b) : FALSE;
}

BOOL WINAPI proxy_WinHttpQueryAuthSchemes(void* a, DWORD* b, DWORD* c, DWORD* d) {
    typedef BOOL (WINAPI *fn_t)(void*, DWORD*, DWORD*, DWORD*);
    fn_t fn = (fn_t)get_orig("WinHttpQueryAuthSchemes");
    return fn ? fn(a, b, c, d) : FALSE;
}

BOOL WINAPI proxy_WinHttpCheckPlatform(void) {
    typedef BOOL (WINAPI *fn_t)(void);
    fn_t fn = (fn_t)get_orig("WinHttpCheckPlatform");
    return fn ? fn() : TRUE;
}

BOOL WINAPI proxy_WinHttpCrackUrl(void* a, DWORD b, DWORD c, void* d) {
    typedef BOOL (WINAPI *fn_t)(void*, DWORD, DWORD, void*);
    fn_t fn = (fn_t)get_orig("WinHttpCrackUrl");
    return fn ? fn(a, b, c, d) : FALSE;
}

BOOL WINAPI proxy_WinHttpCreateUrl(void* a, DWORD b, void* c, DWORD* d) {
    typedef BOOL (WINAPI *fn_t)(void*, DWORD, void*, DWORD*);
    fn_t fn = (fn_t)get_orig("WinHttpCreateUrl");
    return fn ? fn(a, b, c, d) : FALSE;
}

BOOL WINAPI proxy_WinHttpDetectAutoProxyConfigUrl(DWORD a, void* b) {
    typedef BOOL (WINAPI *fn_t)(DWORD, void*);
    fn_t fn = (fn_t)get_orig("WinHttpDetectAutoProxyConfigUrl");
    return fn ? fn(a, b) : FALSE;
}

BOOL WINAPI proxy_WinHttpGetDefaultProxyConfiguration(void* a) {
    typedef BOOL (WINAPI *fn_t)(void*);
    fn_t fn = (fn_t)get_orig("WinHttpGetDefaultProxyConfiguration");
    return fn ? fn(a) : FALSE;
}

BOOL WINAPI proxy_WinHttpGetIEProxyConfigForCurrentUser(void* a) {
    typedef BOOL (WINAPI *fn_t)(void*);
    fn_t fn = (fn_t)get_orig("WinHttpGetIEProxyConfigForCurrentUser");
    return fn ? fn(a) : FALSE;
}

BOOL WINAPI proxy_WinHttpGetProxyForUrl(void* a, void* b, void* c, void* d) {
    typedef BOOL (WINAPI *fn_t)(void*, void*, void*, void*);
    fn_t fn = (fn_t)get_orig("WinHttpGetProxyForUrl");
    return fn ? fn(a, b, c, d) : FALSE;
}

DWORD WINAPI proxy_WinHttpGetProxyForUrlEx(void* a, void* b, void* c, DWORD_PTR d) {
    typedef DWORD (WINAPI *fn_t)(void*, void*, void*, DWORD_PTR);
    fn_t fn = (fn_t)get_orig("WinHttpGetProxyForUrlEx");
    return fn ? fn(a, b, c, d) : 0;
}

DWORD WINAPI proxy_WinHttpGetProxyResult(void* a, void* b) {
    typedef DWORD (WINAPI *fn_t)(void*, void*);
    fn_t fn = (fn_t)get_orig("WinHttpGetProxyResult");
    return fn ? fn(a, b) : 0;
}

DWORD WINAPI proxy_WinHttpCreateProxyResolver(void* a, void* b) {
    typedef DWORD (WINAPI *fn_t)(void*, void*);
    fn_t fn = (fn_t)get_orig("WinHttpCreateProxyResolver");
    return fn ? fn(a, b) : 0;
}

void WINAPI proxy_WinHttpFreeProxyResult(void* a) {
    typedef void (WINAPI *fn_t)(void*);
    fn_t fn = (fn_t)get_orig("WinHttpFreeProxyResult");
    if (fn) fn(a);
}

DWORD WINAPI proxy_WinHttpResetAutoProxy(void* a, DWORD b) {
    typedef DWORD (WINAPI *fn_t)(void*, DWORD);
    fn_t fn = (fn_t)get_orig("WinHttpResetAutoProxy");
    return fn ? fn(a, b) : 0;
}

BOOL WINAPI proxy_WinHttpSetDefaultProxyConfiguration(void* a) {
    typedef BOOL (WINAPI *fn_t)(void*);
    fn_t fn = (fn_t)get_orig("WinHttpSetDefaultProxyConfiguration");
    return fn ? fn(a) : FALSE;
}

void* WINAPI proxy_WinHttpSetStatusCallback(void* a, void* b, DWORD c, DWORD_PTR d) {
    typedef void* (WINAPI *fn_t)(void*, void*, DWORD, DWORD_PTR);
    fn_t fn = (fn_t)get_orig("WinHttpSetStatusCallback");
    return fn ? fn(a, b, c, d) : NULL;
}

BOOL WINAPI proxy_WinHttpTimeFromSystemTime(void* a, void* b) {
    typedef BOOL (WINAPI *fn_t)(void*, void*);
    fn_t fn = (fn_t)get_orig("WinHttpTimeFromSystemTime");
    return fn ? fn(a, b) : FALSE;
}

BOOL WINAPI proxy_WinHttpTimeToSystemTime(void* a, void* b) {
    typedef BOOL (WINAPI *fn_t)(void*, void*);
    fn_t fn = (fn_t)get_orig("WinHttpTimeToSystemTime");
    return fn ? fn(a, b) : FALSE;
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

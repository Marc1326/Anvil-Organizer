/* Minimal version.dll proxy — NO SFSE, pure proxy test */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>

static HMODULE g_orig = NULL;
static volatile LONG g_init = 0;

static void do_init(void) {
    if (InterlockedCompareExchange(&g_init, 1, 0) != 0) return;
    char sys[MAX_PATH];
    GetSystemDirectoryA(sys, MAX_PATH);
    char p[MAX_PATH];
    snprintf(p, MAX_PATH, "%s\\version.dll", sys);
    g_orig = LoadLibraryA(p);
    FILE *lf = fopen("version_shim_test.log", "w");
    if (lf) { fprintf(lf, "v2.1-minimal loaded, orig=%p\n", (void*)g_orig); fclose(lf); }
}

static FARPROC gp(const char *n) { do_init(); return g_orig ? GetProcAddress(g_orig, n) : NULL; }

/* Each proxy written out — no macro tricks */
BOOL WINAPI proxy_GetFileVersionInfoA(LPCSTR a,DWORD b,DWORD c,LPVOID d) {
    typedef BOOL(WINAPI*T)(LPCSTR,DWORD,DWORD,LPVOID); T _f=(T)gp("GetFileVersionInfoA"); return _f?_f(a,b,c,d):FALSE; }
BOOL WINAPI proxy_GetFileVersionInfoExA(DWORD a,LPCSTR b,DWORD c,DWORD d,LPVOID e) {
    typedef BOOL(WINAPI*T)(DWORD,LPCSTR,DWORD,DWORD,LPVOID); T _f=(T)gp("GetFileVersionInfoExA"); return _f?_f(a,b,c,d,e):FALSE; }
BOOL WINAPI proxy_GetFileVersionInfoExW(DWORD a,LPCWSTR b,DWORD c,DWORD d,LPVOID e) {
    typedef BOOL(WINAPI*T)(DWORD,LPCWSTR,DWORD,DWORD,LPVOID); T _f=(T)gp("GetFileVersionInfoExW"); return _f?_f(a,b,c,d,e):FALSE; }
DWORD WINAPI proxy_GetFileVersionInfoSizeA(LPCSTR a,LPDWORD b) {
    typedef DWORD(WINAPI*T)(LPCSTR,LPDWORD); T _f=(T)gp("GetFileVersionInfoSizeA"); return _f?_f(a,b):0; }
DWORD WINAPI proxy_GetFileVersionInfoSizeExA(DWORD a,LPCSTR b,LPDWORD c) {
    typedef DWORD(WINAPI*T)(DWORD,LPCSTR,LPDWORD); T _f=(T)gp("GetFileVersionInfoSizeExA"); return _f?_f(a,b,c):0; }
DWORD WINAPI proxy_GetFileVersionInfoSizeExW(DWORD a,LPCWSTR b,LPDWORD c) {
    typedef DWORD(WINAPI*T)(DWORD,LPCWSTR,LPDWORD); T _f=(T)gp("GetFileVersionInfoSizeExW"); return _f?_f(a,b,c):0; }
DWORD WINAPI proxy_GetFileVersionInfoSizeW(LPCWSTR a,LPDWORD b) {
    typedef DWORD(WINAPI*T)(LPCWSTR,LPDWORD); T _f=(T)gp("GetFileVersionInfoSizeW"); return _f?_f(a,b):0; }
BOOL WINAPI proxy_GetFileVersionInfoW(LPCWSTR a,DWORD b,DWORD c,LPVOID d) {
    typedef BOOL(WINAPI*T)(LPCWSTR,DWORD,DWORD,LPVOID); T _f=(T)gp("GetFileVersionInfoW"); return _f?_f(a,b,c,d):FALSE; }
DWORD WINAPI proxy_VerFindFileA(DWORD a,LPCSTR b,LPCSTR c,LPCSTR d,LPSTR e,PUINT ff,LPSTR g,PUINT h) {
    typedef DWORD(WINAPI*T)(DWORD,LPCSTR,LPCSTR,LPCSTR,LPSTR,PUINT,LPSTR,PUINT); T _f=(T)gp("VerFindFileA"); return _f?_f(a,b,c,d,e,ff,g,h):0; }
DWORD WINAPI proxy_VerFindFileW(DWORD a,LPCWSTR b,LPCWSTR c,LPCWSTR d,LPWSTR e,PUINT ff,LPWSTR g,PUINT h) {
    typedef DWORD(WINAPI*T)(DWORD,LPCWSTR,LPCWSTR,LPCWSTR,LPWSTR,PUINT,LPWSTR,PUINT); T _f=(T)gp("VerFindFileW"); return _f?_f(a,b,c,d,e,ff,g,h):0; }
DWORD WINAPI proxy_VerInstallFileA(DWORD a,LPCSTR b,LPCSTR c,LPCSTR d,LPCSTR e,LPCSTR ff,LPSTR g,PUINT h) {
    typedef DWORD(WINAPI*T)(DWORD,LPCSTR,LPCSTR,LPCSTR,LPCSTR,LPCSTR,LPSTR,PUINT); T _f=(T)gp("VerInstallFileA"); return _f?_f(a,b,c,d,e,ff,g,h):0; }
DWORD WINAPI proxy_VerInstallFileW(DWORD a,LPCWSTR b,LPCWSTR c,LPCWSTR d,LPCWSTR e,LPCWSTR ff,LPWSTR g,PUINT h) {
    typedef DWORD(WINAPI*T)(DWORD,LPCWSTR,LPCWSTR,LPCWSTR,LPCWSTR,LPCWSTR,LPWSTR,PUINT); T _f=(T)gp("VerInstallFileW"); return _f?_f(a,b,c,d,e,ff,g,h):0; }
DWORD WINAPI proxy_VerLanguageNameA(DWORD a,LPSTR b,DWORD c) {
    typedef DWORD(WINAPI*T)(DWORD,LPSTR,DWORD); T _f=(T)gp("VerLanguageNameA"); return _f?_f(a,b,c):0; }
DWORD WINAPI proxy_VerLanguageNameW(DWORD a,LPWSTR b,DWORD c) {
    typedef DWORD(WINAPI*T)(DWORD,LPWSTR,DWORD); T _f=(T)gp("VerLanguageNameW"); return _f?_f(a,b,c):0; }
BOOL WINAPI proxy_VerQueryValueA(LPCVOID a,LPCSTR b,LPVOID *c,PUINT d) {
    typedef BOOL(WINAPI*T)(LPCVOID,LPCSTR,LPVOID*,PUINT); T _f=(T)gp("VerQueryValueA"); return _f?_f(a,b,c,d):FALSE; }
BOOL WINAPI proxy_VerQueryValueW(LPCVOID a,LPCWSTR b,LPVOID *c,PUINT d) {
    typedef BOOL(WINAPI*T)(LPCVOID,LPCWSTR,LPVOID*,PUINT); T _f=(T)gp("VerQueryValueW"); return _f?_f(a,b,c,d):FALSE; }

BOOL WINAPI DllMain(HINSTANCE h, DWORD r, LPVOID p) {
    (void)h;(void)p;
    if (r==DLL_PROCESS_ATTACH) DisableThreadLibraryCalls(h);
    return TRUE;
}

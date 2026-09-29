// Test für den AluPC-Anmeldebaustein: spielt LogonUI nach (Szenario setzen, Advise, auf „Finger erkannt“
// warten, Anmeldedaten abholen) und gibt aus, was Windows bekommen würde. Das Modul ist dabei ein
// nachgebautes (tests/fake_zw101_pipe.py) an einer Named Pipe.
//
// Aufruf: cptest.exe <Einstellungsdatei> [Sekunden]
// Ausgabe: USER=…, DOMAIN=…, PASS=…, MSG=…, dann CPTEST-OK (oder CPTEST-FEHLER: …)

#define ALUPC_CP_TEST 1
#include "alupc_credprov.cpp"

#include <cstdio>

class Events : public ICredentialProviderEvents {
public:
    HANDLE changed = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    IFACEMETHODIMP QueryInterface(REFIID riid, void** ppv) override {
        if (riid == IID_IUnknown || riid == IID_ICredentialProviderEvents) {
            *ppv = static_cast<ICredentialProviderEvents*>(this);
            AddRef();
            return S_OK;
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }
    IFACEMETHODIMP_(ULONG) AddRef() override { return 2; }
    IFACEMETHODIMP_(ULONG) Release() override { return 1; }
    IFACEMETHODIMP CredentialsChanged(UINT_PTR) override {
        SetEvent(changed);
        return S_OK;
    }
};

static std::string Narrow(const std::wstring& w) {
    int n = WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), nullptr, 0, nullptr, nullptr);
    std::string s(n, '\0');
    WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), &s[0], n, nullptr, nullptr);
    return s;
}

static std::wstring Field(const BYTE* base, const UNICODE_STRING& u) {
    return std::wstring((const wchar_t*)(base + (ULONG_PTR)u.Buffer), u.Length / sizeof(WCHAR));
}

static int Fail(const char* what, HRESULT hr = S_OK) {
    printf("CPTEST-FEHLER: %s (0x%08lx)\n", what, (unsigned long)hr);
    return 1;
}

int wmain(int argc, wchar_t** argv) {
    if (argc < 2) return Fail("Aufruf: cptest.exe <Einstellung> [Sekunden]");
    SetEnvironmentVariableW(L"ALUPC_CP_CONFIG", argv[1]);
    DWORD seconds = argc > 2 ? (DWORD)_wtoi(argv[2]) : 20;
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);

    ICredentialProvider* p = nullptr;
    HRESULT hr = AluPCCreateProvider(&p);
    if (FAILED(hr)) return Fail("Provider anlegen", hr);
    // Kennwort ändern o. Ä.: nicht zuständig
    if (p->SetUsageScenario(CPUS_CHANGE_PASSWORD, 0) != E_NOTIMPL) return Fail("CHANGE_PASSWORD angenommen");
    hr = p->SetUsageScenario(CPUS_LOGON, 0);
    if (FAILED(hr)) return Fail("SetUsageScenario(LOGON) – Einstellung nicht gelesen?", hr);

    DWORD fields = 0;
    p->GetFieldDescriptorCount(&fields);
    for (DWORD i = 0; i < fields; ++i) {
        CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR* d = nullptr;
        if (FAILED(p->GetFieldDescriptorAt(i, &d))) return Fail("Feldbeschreibung");
        CoTaskMemFree(d->pszLabel);
        CoTaskMemFree(d);
    }
    DWORD count = 0, def = 0;
    BOOL autoLogon = TRUE;
    p->GetCredentialCount(&count, &def, &autoLogon);
    if (count != 1 || autoLogon) return Fail("Vor dem Finger: 1 Kachel ohne automatische Anmeldung erwartet");
    if (def != 0) return Fail("Fingerabdruck soll vorausgewählt sein (ohne Anklicken)");
    // Windows 10/11: Anmeldeoption an der Benutzerkachel (ICredentialProviderCredential2 + Symbol)
    ICredentialProviderSetUserArray* ua = nullptr;
    if (FAILED(p->QueryInterface(__uuidof(ICredentialProviderSetUserArray), (void**)&ua))) return Fail("SetUserArray fehlt");
    ua->SetUserArray(nullptr);
    ua->Release();
    {
        ICredentialProviderCredential* c0 = nullptr;
        p->GetCredentialAt(0, &c0);
        ICredentialProviderCredential2* c2 = nullptr;
        if (FAILED(c0->QueryInterface(__uuidof(ICredentialProviderCredential2), (void**)&c2))) return Fail("V2 fehlt");
        PWSTR sid = nullptr;
        HRESULT sh = c2->GetUserSid(&sid);
        printf("SID=%s (0x%08lx)\n", Narrow(sid ? sid : L"-").c_str(), (unsigned long)sh);
        CoTaskMemFree(sid);
        HBITMAP logo = nullptr;
        if (FAILED(c2->GetBitmapValue(FI_LOGO, &logo)) || !logo) return Fail("Symbol fehlt");
        DeleteObject(logo);
        c2->Release();
        c0->Release();
    }

    Events events;
    p->Advise(&events, 42);
    if (WaitForSingleObject(events.changed, seconds * 1000) != WAIT_OBJECT_0) {
        p->UnAdvise();
        return Fail("Kein „Finger erkannt“ vom Modul");
    }
    p->GetCredentialCount(&count, &def, &autoLogon);
    if (!autoLogon || def != 0) return Fail("Nach dem Finger: automatische Anmeldung erwartet");

    ICredentialProviderCredential* c = nullptr;
    if (FAILED(p->GetCredentialAt(0, &c))) return Fail("Kachel holen");
    BOOL selectedAuto = FALSE;
    c->SetSelected(&selectedAuto);
    PWSTR status = nullptr;
    c->GetStringValue(FI_STATUS, &status);
    printf("MSG=%s\n", Narrow(status ? status : L"").c_str());
    CoTaskMemFree(status);

    CREDENTIAL_PROVIDER_GET_SERIALIZATION_RESPONSE resp;
    CREDENTIAL_PROVIDER_CREDENTIAL_SERIALIZATION cs{};
    PWSTR text = nullptr;
    CREDENTIAL_PROVIDER_STATUS_ICON icon;
    hr = c->GetSerialization(&resp, &cs, &text, &icon);
    if (FAILED(hr) || resp != CPGSR_RETURN_CREDENTIAL_FINISHED) return Fail("GetSerialization", hr);
    if (cs.clsidCredentialProvider != CLSID_AluPCFingerprint) return Fail("falsche CLSID");
    auto* kiul = (KERB_INTERACTIVE_UNLOCK_LOGON*)cs.rgbSerialization;
    if (kiul->Logon.MessageType != KerbInteractiveLogon) return Fail("falscher Anmeldetyp");
    std::wstring user = Field(cs.rgbSerialization, kiul->Logon.UserName);
    std::wstring domain = Field(cs.rgbSerialization, kiul->Logon.LogonDomainName);
    std::wstring pw = Field(cs.rgbSerialization, kiul->Logon.Password);
    // Passwort ist (wie bei Windows' eigener Kachel) geschützt – zum Prüfen zurückwandeln
    typedef BOOL(WINAPI * IsProt)(LPWSTR, CRED_PROTECTION_TYPE*);
    typedef BOOL(WINAPI * Unprot)(BOOL, LPWSTR, DWORD, LPWSTR, DWORD*);
    HMODULE adv = GetModuleHandleW(L"advapi32.dll");
    auto isProtected = (IsProt)(void*)GetProcAddress(adv, "CredIsProtectedW");
    auto unprotect = (Unprot)(void*)GetProcAddress(adv, "CredUnprotectW");
    CRED_PROTECTION_TYPE type;
    if (isProtected && unprotect && isProtected(&pw[0], &type) && type != CredUnprotected) {
        DWORD cch = 0;
        unprotect(FALSE, &pw[0], (DWORD)pw.size() + 1, nullptr, &cch);
        std::wstring plain(cch, L'\0');
        if (unprotect(FALSE, &pw[0], (DWORD)pw.size() + 1, &plain[0], &cch)) {
            plain.resize(wcslen(plain.c_str()));
            pw = plain;
        }
    }
    printf("USER=%s\nDOMAIN=%s\nPASS=%s\nPAKET=%lu\n", Narrow(user).c_str(), Narrow(domain).c_str(),
           Narrow(pw).c_str(), cs.ulAuthenticationPackage);
    CoTaskMemFree(cs.rgbSerialization);
    // ein zweites Abholen darf nichts mehr liefern (Finger wird nur einmal verwendet)
    CREDENTIAL_PROVIDER_CREDENTIAL_SERIALIZATION cs2{};
    c->GetSerialization(&resp, &cs2, &text, &icon);
    if (resp == CPGSR_RETURN_CREDENTIAL_FINISHED) return Fail("Anmeldedaten doppelt geliefert");
    CoTaskMemFree(text);
    c->Release();
    p->UnAdvise();
    p->Release();
    printf("CPTEST-OK\n");
    return 0;
}

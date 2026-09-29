// AluPC – Windows-Anmeldung mit einem Fingerabdruckmodul am USB-Seriell-Adapter (HLK-ZW101, AS608, R307 …).
//
// Ein „Credential Provider“: eine Kachel auf dem Anmelde- und Sperrbildschirm. Ein Hintergrund-Thread fragt
// das Modul (EF01-Protokoll) ab. Erkennt das Modul einen angelernten Finger, meldet die Kachel den
// zugehörigen Benutzer mit seinem Windows-Passwort an. Das Passwort hat AluPC bei der Einrichtung geprüft
// und mit DPAPI (Maschine) verschlüsselt in %ProgramData%\AluPC\fingerprint-windows.cfg abgelegt – die
// Datei dürfen nur SYSTEM und Administratoren lesen. Windows Hello kennt solche Module nicht, deshalb
// dieser Weg (so machen es auch viele Hersteller von Karten- und Fingerabdrucklesern).
//
// Einstellung (UTF-8, eine Angabe pro Zeile):
//   port=COM3
//   baud=57600
//   capacity=300
//   user=<Benutzer>\t<Domäne oder .>\t<Plätze, z. B. 1,2>\t<DPAPI-Passwort als Hex>
//
// Mit ALUPC_CP_TEST gebaut (nur Test-Programm): Pfad der Einstellung aus der Umgebung, Anschluss darf eine
// Named Pipe sein (nachgebautes Modul in der CI).

#ifndef UNICODE
#define UNICODE
#endif
#define WIN32_NO_STATUS
#include <windows.h>
#undef WIN32_NO_STATUS
#include <ntstatus.h>
#define SECURITY_WIN32
#include <credentialprovider.h>
#include <knownfolders.h>
#include <ntsecapi.h>
#include <security.h>
#include <shlobj.h>
#include <shlwapi.h>
#include <wincred.h>
#include <wincrypt.h>

#include <atomic>
#include <mutex>
#include <new>
#include <string>
#include <thread>
#include <vector>

// {82F9D550-26AE-40CC-B8F7-F9805D8AD0EF}
static const CLSID CLSID_AluPCFingerprint = {0x82f9d550, 0x26ae, 0x40cc, {0xb8, 0xf7, 0xf9, 0x80, 0x5d, 0x8a, 0xd0, 0xef}};
static const char ENTROPY[] = "AluPC-Fingerabdruck";

static LONG g_refDll = 0;

// --------------------------------------------------------------------------- Einstellung
struct UserEntry {
    std::wstring name, domain;
    std::vector<int> slots;
    std::vector<BYTE> secret;  // DPAPI-verschlüsselt
};

struct Config {
    std::wstring port;
    DWORD baud = 57600;
    int capacity = 300;
    std::vector<UserEntry> users;
};

static std::wstring Utf8ToWide(const std::string& s) {
    if (s.empty()) return L"";
    int n = MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), nullptr, 0);
    std::wstring w(n, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), &w[0], n);
    return w;
}

static std::vector<BYTE> FromHex(const std::string& hex) {
    std::vector<BYTE> out;
    for (size_t i = 0; i + 1 < hex.size(); i += 2) {
        out.push_back((BYTE)strtoul(hex.substr(i, 2).c_str(), nullptr, 16));
    }
    return out;
}

static std::wstring ConfigPath() {
#ifdef ALUPC_CP_TEST
    wchar_t buf[MAX_PATH];
    if (GetEnvironmentVariableW(L"ALUPC_CP_CONFIG", buf, MAX_PATH)) return buf;
#endif
    PWSTR base = nullptr;
    std::wstring path;
    if (SUCCEEDED(SHGetKnownFolderPath(FOLDERID_ProgramData, 0, nullptr, &base))) {
        path = std::wstring(base) + L"\\AluPC\\fingerprint-windows.cfg";
    }
    CoTaskMemFree(base);
    return path;
}

static bool LoadConfig(Config& cfg) {
    HANDLE f = CreateFileW(ConfigPath().c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
    if (f == INVALID_HANDLE_VALUE) return false;
    std::string text;
    char chunk[4096];
    DWORD got = 0;
    while (ReadFile(f, chunk, sizeof(chunk), &got, nullptr) && got > 0) text.append(chunk, got);
    CloseHandle(f);
    size_t pos = 0;
    while (pos < text.size()) {
        size_t end = text.find('\n', pos);
        std::string line = text.substr(pos, end == std::string::npos ? std::string::npos : end - pos);
        pos = end == std::string::npos ? text.size() : end + 1;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        std::string key = line.substr(0, eq), value = line.substr(eq + 1);
        if (key == "port") cfg.port = Utf8ToWide(value);
        else if (key == "baud") cfg.baud = (DWORD)strtoul(value.c_str(), nullptr, 10);
        else if (key == "capacity") cfg.capacity = atoi(value.c_str());
        else if (key == "user") {
            std::vector<std::string> parts;
            size_t p = 0;
            while (true) {
                size_t t = value.find('\t', p);
                parts.push_back(value.substr(p, t == std::string::npos ? std::string::npos : t - p));
                if (t == std::string::npos) break;
                p = t + 1;
            }
            if (parts.size() < 4) continue;
            UserEntry u;
            u.name = Utf8ToWide(parts[0]);
            u.domain = Utf8ToWide(parts[1]);
            size_t s = 0;
            while (s < parts[2].size()) {
                size_t c = parts[2].find(',', s);
                std::string num = parts[2].substr(s, c == std::string::npos ? std::string::npos : c - s);
                if (!num.empty()) u.slots.push_back(atoi(num.c_str()));
                s = c == std::string::npos ? parts[2].size() : c + 1;
            }
            u.secret = FromHex(parts[3]);
            if (!u.name.empty() && !u.slots.empty() && !u.secret.empty()) cfg.users.push_back(u);
        }
    }
    if (cfg.capacity <= 0 || cfg.capacity > 3000) cfg.capacity = 300;
    return !cfg.users.empty();
}

static bool DecryptPassword(const std::vector<BYTE>& secret, std::wstring& password) {
    DATA_BLOB in{(DWORD)secret.size(), const_cast<BYTE*>(secret.data())};
    DATA_BLOB entropy{(DWORD)(sizeof(ENTROPY) - 1), (BYTE*)ENTROPY};
    DATA_BLOB out{};
    if (!CryptUnprotectData(&in, nullptr, &entropy, nullptr, nullptr, CRYPTPROTECT_UI_FORBIDDEN, &out)) return false;
    std::string utf8((char*)out.pbData, out.cbData);
    SecureZeroMemory(out.pbData, out.cbData);
    LocalFree(out.pbData);
    password = Utf8ToWide(utf8);
    SecureZeroMemory(&utf8[0], utf8.size());
    return true;
}

// --------------------------------------------------------------------------- Modul (EF01-Protokoll)
class Module {
public:
    ~Module() { Close(); }

    bool Open(const std::wstring& port, DWORD baud) {
        Close();
        std::wstring path = port.rfind(L"\\\\.\\", 0) == 0 ? port : L"\\\\.\\" + port;
        pipe_ = path.find(L"\\pipe\\") != std::wstring::npos;
#ifndef ALUPC_CP_TEST
        if (pipe_) return false;  // im echten Einsatz nur serielle Anschlüsse
#endif
        h_ = CreateFileW(path.c_str(), GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, 0, nullptr);
        if (h_ == INVALID_HANDLE_VALUE) return false;
        if (!pipe_) {
            DCB dcb{};
            dcb.DCBlength = sizeof(dcb);
            GetCommState(h_, &dcb);
            dcb.BaudRate = baud;
            dcb.ByteSize = 8;
            dcb.Parity = NOPARITY;
            dcb.StopBits = ONESTOPBIT;
            dcb.fBinary = TRUE;
            dcb.fDtrControl = DTR_CONTROL_ENABLE;
            dcb.fRtsControl = RTS_CONTROL_ENABLE;
            dcb.fOutxCtsFlow = dcb.fOutxDsrFlow = FALSE;
            dcb.fOutX = dcb.fInX = FALSE;
            if (!SetCommState(h_, &dcb)) { Close(); return false; }
            COMMTIMEOUTS t{};
            t.ReadIntervalTimeout = MAXDWORD;  // ReadFile kehrt sofort zurück, gewartet wird unten
            t.WriteTotalTimeoutConstant = 500;
            SetCommTimeouts(h_, &t);
            PurgeComm(h_, PURGE_RXCLEAR | PURGE_TXCLEAR);
        }
        return true;
    }

    void Close() {
        if (h_ != INVALID_HANDLE_VALUE) CloseHandle(h_);
        h_ = INVALID_HANDLE_VALUE;
    }

    bool IsOpen() const { return h_ != INVALID_HANDLE_VALUE; }

    // Befehl senden → Bestätigungscode (0 = OK), -1 = keine/ungültige Antwort
    int Command(BYTE code, const std::vector<BYTE>& params, std::vector<BYTE>* data = nullptr) {
        std::vector<BYTE> body{0x01};  // PID Befehl
        WORD len = (WORD)(params.size() + 3);
        body.push_back((BYTE)(len >> 8));
        body.push_back((BYTE)len);
        body.push_back(code);
        body.insert(body.end(), params.begin(), params.end());
        WORD sum = 0;
        for (BYTE b : body) sum = (WORD)(sum + b);
        std::vector<BYTE> packet{0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF};
        packet.insert(packet.end(), body.begin(), body.end());
        packet.push_back((BYTE)(sum >> 8));
        packet.push_back((BYTE)sum);
        DWORD written = 0;
        if (!WriteFile(h_, packet.data(), (DWORD)packet.size(), &written, nullptr) || written != packet.size()) return -1;
        // Antwort: bis zum Paketkopf lesen (Reste überspringen)
        BYTE a = 0, b = 0;
        if (!ReadExact(&a, 1)) return -1;
        for (int skipped = 0;; ++skipped) {
            if (!ReadExact(&b, 1)) return -1;
            if (a == 0xEF && b == 0x01) break;
            a = b;
            if (skipped > 256) return -1;
        }
        BYTE head[7];
        if (!ReadExact(head, 7)) return -1;  // Adresse (4), PID, Länge (2)
        WORD n = (WORD)((head[5] << 8) | head[6]);
        if (n < 3 || n > 600) return -1;
        std::vector<BYTE> rest(n);
        if (!ReadExact(rest.data(), n)) return -1;
        WORD check = (WORD)(head[4] + head[5] + head[6]);
        for (size_t i = 0; i + 2 < rest.size(); ++i) check = (WORD)(check + rest[i]);
        if (check != (WORD)((rest[n - 2] << 8) | rest[n - 1]) || head[4] != 0x07) return -1;
        if (data) data->assign(rest.begin() + 1, rest.end() - 2);
        return rest[0];
    }

private:
    bool ReadExact(BYTE* buf, DWORD n, DWORD timeoutMs = 800) {
        DWORD have = 0;
        ULONGLONG deadline = GetTickCount64() + timeoutMs;
        while (have < n) {
            DWORD got = 0;
            if (pipe_) {
                DWORD avail = 0;
                if (!PeekNamedPipe(h_, nullptr, 0, nullptr, &avail, nullptr)) return false;
                if (avail && !ReadFile(h_, buf + have, (avail < n - have ? avail : n - have), &got, nullptr)) return false;
            } else if (!ReadFile(h_, buf + have, n - have, &got, nullptr)) {
                return false;
            }
            have += got;
            if (have < n) {
                if (GetTickCount64() > deadline) return false;
                if (!got) Sleep(5);
            }
        }
        return true;
    }

    HANDLE h_ = INVALID_HANDLE_VALUE;
    bool pipe_ = false;
};

// --------------------------------------------------------------------------- Anmeldedaten verpacken
static HRESULT LookupAuthPackage(ULONG* package) {
    HANDLE lsa = nullptr;
    if (LsaConnectUntrusted(&lsa) != STATUS_SUCCESS) return E_FAIL;
    LSA_STRING name;
    char negotiate[] = NEGOSSP_NAME_A;
    name.Buffer = negotiate;
    name.Length = (USHORT)strlen(negotiate);
    name.MaximumLength = name.Length + 1;
    NTSTATUS st = LsaLookupAuthenticationPackage(lsa, &name, package);
    LsaDeregisterLogonProcess(lsa);
    return st == STATUS_SUCCESS ? S_OK : E_FAIL;
}

// KERB_INTERACTIVE_UNLOCK_LOGON „gepackt“: Zeichenketten hinter der Struktur, Buffer = Abstand zum Anfang
static HRESULT PackLogon(CREDENTIAL_PROVIDER_USAGE_SCENARIO cpus, const std::wstring& domain,
                         const std::wstring& user, const std::wstring& password, BYTE** out, DWORD* cb) {
    DWORD strings = (DWORD)((domain.size() + user.size() + password.size()) * sizeof(WCHAR));
    DWORD total = sizeof(KERB_INTERACTIVE_UNLOCK_LOGON) + strings;
    BYTE* buf = (BYTE*)CoTaskMemAlloc(total);
    if (!buf) return E_OUTOFMEMORY;
    ZeroMemory(buf, total);
    auto* kiul = (KERB_INTERACTIVE_UNLOCK_LOGON*)buf;
    kiul->Logon.MessageType = cpus == CPUS_UNLOCK_WORKSTATION ? KerbWorkstationUnlockLogon : KerbInteractiveLogon;
    BYTE* cur = buf + sizeof(KERB_INTERACTIVE_UNLOCK_LOGON);
    auto put = [&](UNICODE_STRING& dst, const std::wstring& s) {
        USHORT len = (USHORT)(s.size() * sizeof(WCHAR));
        if (len) memcpy(cur, s.data(), len);
        dst.Length = dst.MaximumLength = len;
        dst.Buffer = (PWSTR)(ULONG_PTR)(cur - buf);
        cur += len;
    };
    put(kiul->Logon.LogonDomainName, domain);
    put(kiul->Logon.UserName, user);
    put(kiul->Logon.Password, password);
    *out = buf;
    *cb = total;
    return S_OK;
}

static std::wstring ProtectPassword(const std::wstring& plain) {
    // wie Windows' eigene Kachel: Passwort für LogonUI geschützt übergeben (Funktionen dynamisch – fehlen sie,
    // geht das Passwort ungeschützt, aber nur innerhalb von LogonUI, weiter)
    typedef BOOL(WINAPI * IsProt)(LPWSTR, CRED_PROTECTION_TYPE*);
    typedef BOOL(WINAPI * Prot)(BOOL, LPWSTR, DWORD, LPWSTR, DWORD*, CRED_PROTECTION_TYPE*);
    HMODULE adv = GetModuleHandleW(L"advapi32.dll");
    auto isProtected = adv ? (IsProt)(void*)GetProcAddress(adv, "CredIsProtectedW") : nullptr;
    auto protect = adv ? (Prot)(void*)GetProcAddress(adv, "CredProtectW") : nullptr;
    std::wstring copy = plain;
    if (!isProtected || !protect) return copy;
    CRED_PROTECTION_TYPE type;
    if (isProtected(&copy[0], &type) && type != CredUnprotected) return copy;
    DWORD cch = 0;
    protect(FALSE, &copy[0], (DWORD)copy.size() + 1, nullptr, &cch, nullptr);
    if (GetLastError() != ERROR_INSUFFICIENT_BUFFER || !cch) return copy;
    std::wstring prot(cch, L'\0');
    if (!protect(FALSE, &copy[0], (DWORD)copy.size() + 1, &prot[0], &cch, nullptr)) return copy;
    SecureZeroMemory(&copy[0], copy.size() * sizeof(WCHAR));
    prot.resize(wcslen(prot.c_str()));
    return prot;
}

// --------------------------------------------------------------------------- Kachel
enum FieldId { FI_LABEL = 0, FI_STATUS = 1, FI_COUNT = 2 };

class Provider;

class Credential : public ICredentialProviderCredential {
public:
    explicit Credential(Provider* p) : provider_(p) { InterlockedIncrement(&g_refDll); }
    virtual ~Credential() { InterlockedDecrement(&g_refDll); }

    IFACEMETHODIMP QueryInterface(REFIID riid, void** ppv) override {
        if (!ppv) return E_POINTER;
        if (riid == IID_IUnknown || riid == IID_ICredentialProviderCredential) {
            *ppv = static_cast<ICredentialProviderCredential*>(this);
            AddRef();
            return S_OK;
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }
    IFACEMETHODIMP_(ULONG) AddRef() override { return InterlockedIncrement(&ref_); }
    IFACEMETHODIMP_(ULONG) Release() override {
        LONG r = InterlockedDecrement(&ref_);
        if (!r) delete this;
        return r;
    }

    IFACEMETHODIMP Advise(ICredentialProviderCredentialEvents* ev) override {
        std::lock_guard<std::mutex> lock(mutex_);
        if (events_) events_->Release();
        events_ = ev;
        if (events_) events_->AddRef();
        return S_OK;
    }
    IFACEMETHODIMP UnAdvise() override {
        std::lock_guard<std::mutex> lock(mutex_);
        if (events_) events_->Release();
        events_ = nullptr;
        return S_OK;
    }
    IFACEMETHODIMP SetSelected(BOOL* autoLogon) override;
    IFACEMETHODIMP SetDeselected() override { return S_OK; }
    IFACEMETHODIMP GetFieldState(DWORD id, CREDENTIAL_PROVIDER_FIELD_STATE* state,
                                 CREDENTIAL_PROVIDER_FIELD_INTERACTIVE_STATE* interactive) override {
        if (id >= FI_COUNT || !state || !interactive) return E_INVALIDARG;
        *state = id == FI_LABEL ? CPFS_DISPLAY_IN_BOTH : CPFS_DISPLAY_IN_SELECTED_TILE;
        *interactive = CPFIS_NONE;
        return S_OK;
    }
    IFACEMETHODIMP GetStringValue(DWORD id, PWSTR* value) override {
        if (!value) return E_POINTER;
        if (id == FI_LABEL) return SHStrDupW(L"Fingerabdruck (AluPC)", value);
        if (id == FI_STATUS) {
            std::lock_guard<std::mutex> lock(mutex_);
            return SHStrDupW(status_.c_str(), value);
        }
        return E_INVALIDARG;
    }
    IFACEMETHODIMP GetBitmapValue(DWORD, HBITMAP*) override { return E_NOTIMPL; }
    IFACEMETHODIMP GetCheckboxValue(DWORD, BOOL*, PWSTR*) override { return E_NOTIMPL; }
    IFACEMETHODIMP GetSubmitButtonValue(DWORD, DWORD*) override { return E_NOTIMPL; }
    IFACEMETHODIMP GetComboBoxValueCount(DWORD, DWORD*, DWORD*) override { return E_NOTIMPL; }
    IFACEMETHODIMP GetComboBoxValueAt(DWORD, DWORD, PWSTR*) override { return E_NOTIMPL; }
    IFACEMETHODIMP SetStringValue(DWORD, PCWSTR) override { return E_NOTIMPL; }
    IFACEMETHODIMP SetCheckboxValue(DWORD, BOOL) override { return E_NOTIMPL; }
    IFACEMETHODIMP SetComboBoxSelectedValue(DWORD, DWORD) override { return E_NOTIMPL; }
    IFACEMETHODIMP CommandLinkClicked(DWORD) override { return E_NOTIMPL; }
    IFACEMETHODIMP GetSerialization(CREDENTIAL_PROVIDER_GET_SERIALIZATION_RESPONSE* response,
                                    CREDENTIAL_PROVIDER_CREDENTIAL_SERIALIZATION* cs, PWSTR* statusText,
                                    CREDENTIAL_PROVIDER_STATUS_ICON* statusIcon) override;
    IFACEMETHODIMP ReportResult(NTSTATUS status, NTSTATUS, PWSTR* statusText,
                                CREDENTIAL_PROVIDER_STATUS_ICON* statusIcon) override {
        if (status != STATUS_SUCCESS && statusText && statusIcon) {
            ShowStatusNow(L"Anmeldung abgelehnt – Windows-Passwort geändert? In AluPC neu einrichten.");
            SHStrDupW(L"Das in AluPC gespeicherte Windows-Passwort passt nicht mehr. "
                      L"Bitte mit Passwort anmelden und in AluPC die Fingerabdruck-Anmeldung neu einrichten.",
                      statusText);
            *statusIcon = CPSI_ERROR;
        }
        return S_OK;
    }

    // Nur merken: LogonUI liest den Text selbst (GetStringValue). Aus dem Hintergrund-Thread wird bewusst
    // nichts an LogonUI geschickt außer CredentialsChanged (wie in Microsofts Beispiel für Hardware-Anmeldung) –
    // ein Fehler hier würde den Anmeldebildschirm neu starten.
    void SetStatus(const std::wstring& text) {
        std::lock_guard<std::mutex> lock(mutex_);
        status_ = text;
    }

    // Nur aus LogonUIs eigenem Aufruf heraus (GetSerialization/ReportResult): sofort anzeigen
    void ShowStatusNow(const std::wstring& text) {
        ICredentialProviderCredentialEvents* ev = nullptr;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            status_ = text;
            ev = events_;
            if (ev) ev->AddRef();
        }
        if (ev) {
            ev->SetFieldString(this, FI_STATUS, text.c_str());
            ev->Release();
        }
    }

private:
    LONG ref_ = 1;
    Provider* provider_;
    std::mutex mutex_;
    ICredentialProviderCredentialEvents* events_ = nullptr;
    std::wstring status_ = L"Finger auf den Sensor legen …";
};

class Provider : public ICredentialProvider {
public:
    Provider() { InterlockedIncrement(&g_refDll); }
    virtual ~Provider() {
        StopWatching();
        if (credential_) credential_->Release();
        InterlockedDecrement(&g_refDll);
    }

    IFACEMETHODIMP QueryInterface(REFIID riid, void** ppv) override {
        if (!ppv) return E_POINTER;
        if (riid == IID_IUnknown || riid == IID_ICredentialProvider) {
            *ppv = static_cast<ICredentialProvider*>(this);
            AddRef();
            return S_OK;
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }
    IFACEMETHODIMP_(ULONG) AddRef() override { return InterlockedIncrement(&ref_); }
    IFACEMETHODIMP_(ULONG) Release() override {
        LONG r = InterlockedDecrement(&ref_);
        if (!r) delete this;
        return r;
    }

    IFACEMETHODIMP SetUsageScenario(CREDENTIAL_PROVIDER_USAGE_SCENARIO cpus, DWORD) override {
        if (cpus != CPUS_LOGON && cpus != CPUS_UNLOCK_WORKSTATION) return E_NOTIMPL;
        cfg_ = Config{};
        if (!LoadConfig(cfg_)) return E_NOTIMPL;  // nicht eingerichtet → keine Kachel
        cpus_ = cpus;
        if (!credential_) credential_ = new (std::nothrow) Credential(this);
        return credential_ ? S_OK : E_OUTOFMEMORY;
    }
    IFACEMETHODIMP SetSerialization(const CREDENTIAL_PROVIDER_CREDENTIAL_SERIALIZATION*) override { return E_NOTIMPL; }
    IFACEMETHODIMP Advise(ICredentialProviderEvents* events, UINT_PTR context) override {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (events_) events_->Release();
            events_ = events;
            if (events_) events_->AddRef();
            context_ = context;
        }
        StartWatching();
        return S_OK;
    }
    IFACEMETHODIMP UnAdvise() override {
        StopWatching();  // Modul freigeben – nach dem Entsperren braucht es AluPC wieder
        std::lock_guard<std::mutex> lock(mutex_);
        if (events_) events_->Release();
        events_ = nullptr;
        return S_OK;
    }
    IFACEMETHODIMP GetFieldDescriptorCount(DWORD* count) override {
        *count = FI_COUNT;
        return S_OK;
    }
    IFACEMETHODIMP GetFieldDescriptorAt(DWORD index, CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR** out) override {
        if (index >= FI_COUNT || !out) return E_INVALIDARG;
        auto* d = (CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR*)CoTaskMemAlloc(sizeof(CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR));
        if (!d) return E_OUTOFMEMORY;
        ZeroMemory(d, sizeof(*d));
        d->dwFieldID = index;
        d->cpft = index == FI_LABEL ? CPFT_LARGE_TEXT : CPFT_SMALL_TEXT;
        HRESULT hr = SHStrDupW(index == FI_LABEL ? L"Fingerabdruck (AluPC)" : L"Status", &d->pszLabel);
        if (FAILED(hr)) {
            CoTaskMemFree(d);
            return hr;
        }
        *out = d;
        return S_OK;
    }
    IFACEMETHODIMP GetCredentialCount(DWORD* count, DWORD* defaultIndex, BOOL* autoLogon) override {
        *count = credential_ ? 1 : 0;
        bool ready = matched_ >= 0;
        *defaultIndex = ready ? 0 : CREDENTIAL_PROVIDER_NO_DEFAULT;
        *autoLogon = ready ? TRUE : FALSE;  // Finger erkannt → sofort anmelden
        return S_OK;
    }
    IFACEMETHODIMP GetCredentialAt(DWORD index, ICredentialProviderCredential** out) override {
        if (index != 0 || !credential_ || !out) return E_INVALIDARG;
        return credential_->QueryInterface(IID_ICredentialProviderCredential, (void**)out);
    }

    // Für die Kachel
    bool Matched() const { return matched_ >= 0; }

    HRESULT Serialize(CREDENTIAL_PROVIDER_CREDENTIAL_SERIALIZATION* cs) {
        int idx = matched_.exchange(-1);  // nur einmal verwenden
        if (idx < 0 || idx >= (int)cfg_.users.size()) return E_UNEXPECTED;
        const UserEntry& u = cfg_.users[idx];
        std::wstring password;
        if (!DecryptPassword(u.secret, password)) return E_FAIL;
        std::wstring domain = u.domain;
        if (domain.empty() || domain == L".") {
            wchar_t name[MAX_COMPUTERNAME_LENGTH + 1];
            DWORD n = MAX_COMPUTERNAME_LENGTH + 1;
            domain = GetComputerNameW(name, &n) ? name : L".";
        }
        std::wstring protectedPw = ProtectPassword(password);
        SecureZeroMemory(&password[0], password.size() * sizeof(WCHAR));
        ULONG package = 0;
        HRESULT hr = LookupAuthPackage(&package);
        if (SUCCEEDED(hr)) hr = PackLogon(cpus_, domain, u.name, protectedPw, &cs->rgbSerialization, &cs->cbSerialization);
        SecureZeroMemory(&protectedPw[0], protectedPw.size() * sizeof(WCHAR));
        if (FAILED(hr)) return hr;
        cs->ulAuthenticationPackage = package;
        cs->clsidCredentialProvider = CLSID_AluPCFingerprint;
        return S_OK;
    }

private:
    void StartWatching() {
        StopWatching();
        stop_ = false;
        worker_ = std::thread([this] {
            try {
                Watch();
            } catch (...) {  // nie den Anmeldebildschirm mitreißen – dann eben nur mit Passwort
            }
        });
    }
    void StopWatching() {
        stop_ = true;
        if (worker_.joinable()) worker_.join();
    }

    int UserForSlot(int slot) const {
        for (size_t i = 0; i < cfg_.users.size(); ++i)
            for (int s : cfg_.users[i].slots)
                if (s == slot) return (int)i;
        return -1;
    }

    void Status(const std::wstring& text) {
        if (credential_) credential_->SetStatus(text);
    }

    bool Connect(Module& m) {
        DWORD bauds[] = {cfg_.baud, 57600, 115200, 9600};
        for (DWORD baud : bauds) {
            if (!baud || !m.Open(cfg_.port, baud)) continue;
            if (m.Command(0x13, {0, 0, 0, 0}) == 0) return true;  // Modul-Passwort prüfen = Handshake
            m.Close();
        }
        return false;
    }

    void Watch() {
        Module m;
        ULONGLONG nextTry = 0;
        while (!stop_) {
            if (matched_ >= 0) {  // erkannt – warten, bis LogonUI die Anmeldedaten geholt hat
                Sleep(100);
                continue;
            }
            if (!m.IsOpen()) {
                if (GetTickCount64() < nextTry) {
                    Sleep(100);
                    continue;
                }
                if (!Connect(m)) {
                    Status(L"Fingerabdruckmodul nicht gefunden (" + cfg_.port + L")");
                    nextTry = GetTickCount64() + 2000;
                    continue;
                }
                Status(L"Finger auf den Sensor legen …");
            }
            int r = m.Command(0x01, {});  // Bild aufnehmen
            if (r < 0) {
                m.Close();
                continue;
            }
            if (r != 0) {  // kein Finger
                Sleep(200);
                continue;
            }
            if (m.Command(0x02, {1}) != 0) {  // Merkmale in Puffer 1
                Status(L"Nicht lesbar – Finger ruhig und fest auflegen");
                Sleep(400);
                continue;
            }
            std::vector<BYTE> data;
            WORD cap = (WORD)cfg_.capacity;
            int s = m.Command(0x04, {1, 0, 0, (BYTE)(cap >> 8), (BYTE)cap}, &data);  // Suche
            int idx = (s == 0 && data.size() >= 2) ? UserForSlot((data[0] << 8) | data[1]) : -1;
            if (idx < 0) {
                Status(L"Finger nicht erkannt – nochmal versuchen");
                Sleep(800);
                continue;
            }
            Status(L"Erkannt: " + cfg_.users[idx].name + L" – melde an …");
            matched_ = idx;
            ICredentialProviderEvents* ev = nullptr;
            UINT_PTR ctx = 0;
            {
                std::lock_guard<std::mutex> lock(mutex_);
                ev = events_;
                ctx = context_;
                if (ev) ev->AddRef();
            }
            if (ev) {
                ev->CredentialsChanged(ctx);  // LogonUI fragt neu → Anmeldung startet von selbst
                ev->Release();
            }
        }
        m.Close();
    }

    LONG ref_ = 1;
    CREDENTIAL_PROVIDER_USAGE_SCENARIO cpus_ = CPUS_LOGON;
    Config cfg_;
    Credential* credential_ = nullptr;
    std::mutex mutex_;
    ICredentialProviderEvents* events_ = nullptr;
    UINT_PTR context_ = 0;
    std::thread worker_;
    std::atomic<bool> stop_{false};
    std::atomic<int> matched_{-1};
};

IFACEMETHODIMP Credential::SetSelected(BOOL* autoLogon) {
    *autoLogon = provider_->Matched() ? TRUE : FALSE;
    return S_OK;
}

IFACEMETHODIMP Credential::GetSerialization(CREDENTIAL_PROVIDER_GET_SERIALIZATION_RESPONSE* response,
                                            CREDENTIAL_PROVIDER_CREDENTIAL_SERIALIZATION* cs, PWSTR* statusText,
                                            CREDENTIAL_PROVIDER_STATUS_ICON* statusIcon) {
    *response = CPGSR_NO_CREDENTIAL_NOT_FINISHED;
    if (statusText) *statusText = nullptr;
    if (statusIcon) *statusIcon = CPSI_NONE;
    if (!provider_->Matched()) {
        if (statusText) SHStrDupW(L"Bitte den angelernten Finger auf den Sensor legen.", statusText);
        return S_OK;
    }
    ZeroMemory(cs, sizeof(*cs));
    HRESULT hr = provider_->Serialize(cs);
    if (FAILED(hr)) {
        ShowStatusNow(L"Gespeichertes Passwort nicht lesbar – in AluPC neu einrichten");
        return hr;
    }
    *response = CPGSR_RETURN_CREDENTIAL_FINISHED;
    return S_OK;
}

// --------------------------------------------------------------------------- COM-Klassenfabrik
class Factory : public IClassFactory {
public:
    virtual ~Factory() = default;
    IFACEMETHODIMP QueryInterface(REFIID riid, void** ppv) override {
        if (riid == IID_IUnknown || riid == IID_IClassFactory) {
            *ppv = static_cast<IClassFactory*>(this);
            AddRef();
            return S_OK;
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }
    IFACEMETHODIMP_(ULONG) AddRef() override { return InterlockedIncrement(&ref_); }
    IFACEMETHODIMP_(ULONG) Release() override {
        LONG r = InterlockedDecrement(&ref_);
        if (!r) delete this;
        return r;
    }
    IFACEMETHODIMP CreateInstance(IUnknown* outer, REFIID riid, void** ppv) override {
        *ppv = nullptr;
        if (outer) return CLASS_E_NOAGGREGATION;
        Provider* p = new (std::nothrow) Provider();
        if (!p) return E_OUTOFMEMORY;
        HRESULT hr = p->QueryInterface(riid, ppv);
        p->Release();
        return hr;
    }
    IFACEMETHODIMP LockServer(BOOL lock) override {
        if (lock) InterlockedIncrement(&g_refDll);
        else InterlockedDecrement(&g_refDll);
        return S_OK;
    }

private:
    LONG ref_ = 1;
};

extern "C" HRESULT __stdcall AluPCCreateProvider(ICredentialProvider** out) {
    Provider* p = new (std::nothrow) Provider();
    if (!p) return E_OUTOFMEMORY;
    *out = p;
    return S_OK;
}

#ifndef ALUPC_CP_TEST
BOOL WINAPI DllMain(HINSTANCE hinst, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hinst);
    }
    return TRUE;
}

STDAPI DllCanUnloadNow() { return g_refDll > 0 ? S_FALSE : S_OK; }

STDAPI DllGetClassObject(REFCLSID clsid, REFIID riid, void** ppv) {
    *ppv = nullptr;
    if (clsid != CLSID_AluPCFingerprint) return CLASS_E_CLASSNOTAVAILABLE;
    Factory* f = new (std::nothrow) Factory();
    if (!f) return E_OUTOFMEMORY;
    HRESULT hr = f->QueryInterface(riid, ppv);
    f->Release();
    return hr;
}
#endif

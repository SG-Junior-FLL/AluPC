cmake_minimum_required(VERSION 3.16)
project(AluPCFingerprint CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded")  # statisch: LogonUI lädt die DLL ohne VC-Laufzeit-Installation
add_compile_definitions(UNICODE _UNICODE)
set(LIBS secur32 crypt32 advapi32 shlwapi shell32 ole32 uuid credui)

# Anmeldebaustein (wird von LogonUI geladen)
add_library(AluPCFingerprint SHARED alupc_credprov.cpp alupc_credprov.def)
target_link_libraries(AluPCFingerprint PRIVATE ${LIBS})

# Test: spielt LogonUI nach
add_executable(cptest cptest.cpp)
target_link_libraries(cptest PRIVATE ${LIBS})

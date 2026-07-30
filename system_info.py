"""
system_info.py

Collects basic information about the host machine (OS, CPU, compilers,
build tools) so it can be handed to an LLM as context when generating
optimized C++ code for this specific system.
"""

import os
import platform
import shutil
import subprocess

# helpers 
def _run(cmd, timeout=3):
    """Run a command safely and return its stdout as text (or '' on failure).
    Accepts either a string (runs via shell) or a list (runs without a shell)."""
    try:
        if isinstance(cmd, str):
            return subprocess.check_output(
                cmd, shell=True, text=True, stderr=subprocess.DEVNULL, timeout=timeout
            ).strip()
        else:
            return subprocess.check_output(
                cmd, shell=False, text=True, stderr=subprocess.DEVNULL, timeout=timeout
            ).strip()
    except Exception:
        return ""


def _first_line(s: str) -> str:
    """Return just the first non-empty line of a multi-line string."""
    s = (s or "").strip()
    return s.splitlines()[0].strip() if s else ""


def _which(name: str) -> str:
    """Return the full path to an executable if it exists on PATH, else ''."""
    return shutil.which(name) or ""


def _bool_from_output(s: str) -> bool:
    """Interpret common truthy command output ('1', 'true', 'yes', ...) as a bool."""
    return s.strip() in {"1", "true", "True", "YES", "Yes", "yes"}


# OS & env 
def _os_block():
    """Gather OS name, architecture, kernel/version info, and WSL/Rosetta flags."""
    sysname = platform.system()
    machine = platform.machine() or ""
    release = platform.release() or ""
    version = platform.version() or ""
    kernel = release if sysname == "Windows" else (_run(["uname", "-r"]) or release)

    # On Linux, pull a friendly distro name/version from /etc/os-release
    distro = {"name": "", "version": ""}
    if sysname == "Linux":
        try:
            with open("/etc/os-release", "r") as f:
                data = {}
                for line in f:
                    if "=" in line:
                        k, v = line.rstrip().split("=", 1)
                        data[k] = v.strip('"')
                distro["name"] = data.get("PRETTY_NAME") or data.get("NAME", "")
                distro["version"] = data.get("VERSION_ID") or data.get("VERSION", "")
        except Exception:
            pass

    # Detect WSL (Windows Subsystem for Linux) via the kernel version string
    wsl = False
    if sysname != "Windows":
        try:
            with open("/proc/version", "r") as f:
                v = f.read().lower()
                wsl = ("microsoft" in v) or ("wsl" in v)
        except Exception:
            wsl = False

    rosetta = False
    if sysname == "Darwin":
        rosetta = _bool_from_output(_run(["sysctl", "-in", "sysctl.proc_translated"]))

    # Best effort compiler target triple
    target = ""
    for cc in ("clang", "gcc"):
        if _which(cc):
            out = _run([cc, "-dumpmachine"])
            if out:
                target = _first_line(out)
                break

    return {
        "system": sysname,
        "arch": machine,
        "release": release,
        "version": version,
        "kernel": kernel,
        "distro": distro if sysname == "Linux" else None,
        "wsl": wsl,
        "rosetta2_translated": rosetta,
        "target_triple": target,
    }


# package managers 
def _package_managers():
    """Return the list of package managers available on this system."""
    sysname = platform.system()
    pms = []
    if sysname == "Windows":
        for pm in ("winget", "choco", "scoop"):
            if _which(pm):
                pms.append(pm)
    elif sysname == "Darwin":
        if _run(["xcode-select", "-p"]):
            pms.append("xcode-select (CLT)")
        for pm in ("brew", "port"):
            if _which(pm):
                pms.append(pm)
    else:
        for pm in ("apt", "dnf", "yum", "pacman", "zypper", "apk", "emerge"):
            if _which(pm):
                pms.append(pm)
    return pms


# CPU (minimal) 
def _cpu_block():
    """Return CPU brand, logical/physical core counts, and supported SIMD flags."""
    sysname = platform.system()
    brand = ""
    if sysname == "Linux":
        brand = _run("grep -m1 'model name' /proc/cpuinfo | cut -d: -f2").strip()
    elif sysname == "Darwin":
        brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    elif sysname == "Windows":
        brand = _run('powershell -NoProfile -Command "(Get-CimInstance Win32_Processor).Name"')
        if not brand:
            brand = _run("wmic cpu get Name /value").replace("Name=", "").strip()

    # Logical core count is always available; physical count is best effort
    cores_logical = os.cpu_count() or 0
    cores_physical = 0
    if sysname == "Darwin":
        cores_physical = int(_run(["sysctl", "-n", "hw.physicalcpu"]) or "0")
    elif sysname == "Windows":
        cores_physical = int(
            _run('powershell -NoProfile -Command "(Get-CimInstance Win32_Processor).NumberOfCores"')
            or "0"
        )
    elif sysname == "Linux":
        # Quick approximation: count unique (core id, socket id) pairs.
        # Good enough for suggesting a parallel -j value.
        try:
            mapping = _run("LC_ALL=C lscpu -p=CORE,SOCKET | grep -v '^#'").splitlines()
            unique = set(tuple(line.split(",")) for line in mapping if "," in line)
            cores_physical = len(unique) or 0
        except Exception:
            cores_physical = 0

    # Best effort SIMD instruction set detection (used to pick safe march flags)
    simd = []
    if sysname == "Linux":
        flags = _run("grep -m1 'flags' /proc/cpuinfo | cut -d: -f2")
        if flags:
            fset = set(flags.upper().split())
            for x in ("AVX512F", "AVX2", "AVX", "FMA", "SSE4_2", "NEON", "SVE"):
                if x in fset:
                    simd.append(x)
    elif sysname == "Darwin":
        feats = (
            (
                _run(["sysctl", "-n", "machdep.cpu.features"])
                + " "
                + _run(["sysctl", "-n", "machdep.cpu.leaf7_features"])
            )
            .upper()
            .split()
        )
        for x in ("AVX512F", "AVX2", "AVX", "FMA", "SSE4_2", "NEON", "SVE"):
            if x in feats:
                simd.append(x)
    # Windows: skipped — CPU brand is usually enough to pick MSVC /arch flags.

    return {
        "brand": brand.strip(),
        "cores_logical": cores_logical,
        "cores_physical": cores_physical,
        "simd": sorted(set(simd)),
    }


# toolchain presence 
def _toolchain_block():
    """Report which compilers, build tools, and linkers are installed."""

    def ver_line(exe, args=("--version",)):
        p = _which(exe)
        if not p:
            return ""
        out = _run([p, *args])
        return _first_line(out)

    gcc = ver_line("gcc")
    gpp = ver_line("g++")
    clang = ver_line("clang")

    # MSVC's cl.exe only works from inside a proper Developer Command Prompt
    msvc_cl = ""
    cl_path = _which("cl")
    if cl_path:
        msvc_cl = _first_line(_run("cl 2>&1"))

    cmake = ver_line("cmake")
    ninja = _first_line(_run([_which("ninja"), "--version"])) if _which("ninja") else ""
    make = ver_line("make")

    # We only care whether the LLVM linker (lld) is available
    lld = ver_line("ld.lld")
    return {
        "compilers": {"gcc": gcc, "g++": gpp, "clang": clang, "msvc_cl": msvc_cl},
        "build_tools": {"cmake": cmake, "ninja": ninja, "make": make},
        "linkers": {"ld_lld": lld},
    }


# public API
def retrieve_system_info():
    """
    Returns a compact dict with enough info for an LLM to:
       Pick an install path (winget/choco/scoop, Homebrew/Xcode CLT, apt/dnf/...),
       Choose a compiler family (MSVC/clang/gcc),
       Suggest safe optimization flags (e.g., -O3/-march=native or MSVC /O2),
       Decide on a build system (cmake+ninja) and parallel -j value.
    """
    return {
        "os": _os_block(),
        "package_managers": _package_managers(),
        "cpu": _cpu_block(),
        "toolchain": _toolchain_block(),
    }
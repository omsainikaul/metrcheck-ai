"""MetrCheck AI - Unified Server Runner for National Hackathon 6.0."""
import os
import sys
import time
import socket
import shutil
import subprocess
import webbrowser
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
PID_FILE = ROOT_DIR / ".runner.pid"

def log(msg: str = ""):
    print(msg, flush=True)

def get_lan_ip() -> str:
    """Detect active local network IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def kill_ports(ports=(5173, 5174, 8000)):
    """Clean up existing processes on specified ports that demonstrably belong to MetrCheck AI."""
    if os.name != 'nt':
        return []
    conflicts = []
    try:
        import psutil
    except ImportError:
        psutil = None

    try:
        res = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
        pids_by_port = {}
        for line in res.stdout.splitlines():
            line = line.strip()
            if "LISTENING" in line.upper():
                parts = line.split()
                if len(parts) >= 5:
                    local_addr = parts[1]
                    pid_str = parts[-1]
                    for p in ports:
                        if local_addr.endswith(f":{p}") and pid_str.isdigit() and int(pid_str) > 0:
                            pids_by_port[int(pid_str)] = p

        my_pid = os.getpid()
        root_str = str(ROOT_DIR.resolve()).lower()

        for pid, port in pids_by_port.items():
            if pid == my_pid:
                continue

            is_ours = False
            proc_name = "unknown"
            if psutil and psutil.pid_exists(pid):
                try:
                    proc = psutil.Process(pid)
                    proc_name = proc.name()
                    try:
                        cwd = proc.cwd()
                        if cwd and (Path(cwd).resolve() == ROOT_DIR or ROOT_DIR in Path(cwd).resolve().parents):
                            is_ours = True
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass

                    if not is_ours:
                        try:
                            cmdline = " ".join(proc.cmdline() or []).lower()
                            if root_str in cmdline or ("uvicorn" in cmdline and "main:app" in cmdline):
                                is_ours = True
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            elif not psutil:
                # Fallback if psutil is unavailable
                is_ours = True

            if is_ours:
                log(f"  [*] Terminating residual MetrCheck AI process on port {port} (PID {pid})...")
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
            else:
                log(f"  [*] Preserving unrelated application on port {port} (PID {pid}, {proc_name}).")
                conflicts.append((port, pid, proc_name))
    except Exception:
        pass
    return conflicts

def terminate_process_tree(proc: subprocess.Popen):
    """Safely terminate a process and its child tree on Windows."""
    if not proc or proc.poll() is not None:
        return
    try:
        if os.name == 'nt':
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=5)
        else:
            proc.terminate()
            proc.wait(timeout=3)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass

def check_and_prompt_firewall():
    """Checks if Windows Firewall rule exists for MetrCheck. If not, offers guidance."""
    if os.name == 'nt':
        try:
            check_cmd = "powershell -NoProfile -Command \"(Get-NetFirewallRule -DisplayName 'MetrCheck AI (5173, 8000)' -ErrorAction SilentlyContinue).DisplayName\""
            res = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
            if "MetrCheck" not in res.stdout:
                log("[*] Note: If your phone cannot connect on local Wi-Fi, run allow_firewall.bat as Admin once.")
        except Exception:
            pass

def print_qr(url: str):
    """Print ASCII QR Code to terminal for instant mobile camera scanning."""
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=1, border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:
        pass

def check_prerequisites():
    """Verify virtual environment, Node.js, npm, and dependencies before starting."""
    errors = []

    # 1. Virtual environment python
    if not (ROOT_DIR / "venv" / "Scripts" / "python.exe").exists():
        errors.append(
            "Python virtual environment not found in 'venv\\'.\n"
            "   Please run setup.bat first to initialize dependencies."
        )

    # 2. Node.js binary
    if not shutil.which("node"):
        errors.append(
            "Node.js was not found in system PATH.\n"
            "   Please install Node.js (v18+ recommended) from https://nodejs.org"
        )

    # 3. npm binary
    npm_cmd = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm_cmd:
        errors.append(
            "npm was not found in system PATH.\n"
            "   Please ensure npm is installed and added to your system PATH."
        )

    # 4. Frontend node_modules
    if not (FRONTEND_DIR / "node_modules").is_dir():
        errors.append(
            "Frontend dependencies not found: 'frontend\\node_modules' is missing.\n"
            "   Please run setup.bat or run 'npm install' inside the 'frontend/' folder."
        )

    # 5. Uvicorn in Python environment
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        errors.append(
            "Uvicorn is not installed in the active virtual environment.\n"
            "   Please run: venv\\Scripts\\python.exe -m pip install -r requirements.txt"
        )

    return errors, npm_cmd

def wait_for_service(url: str, name: str, proc: subprocess.Popen = None, log_path: Path = None, total_timeout: float = 30.0, req_timeout: float = 4.0) -> bool:
    """Poll a service URL until HTTP 200/304 is returned or timeout expires."""
    start_time = time.time()
    while time.time() - start_time < total_timeout:
        # Check if process terminated early
        if proc and proc.poll() is not None:
            log(f"  [ERROR] {name} process terminated prematurely with exit code {proc.returncode}!")
            if log_path and log_path.exists():
                try:
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as lf:
                        lines = [l.strip() for l in lf.readlines() if l.strip()]
                        tail = lines[-12:] if len(lines) > 12 else lines
                        if tail:
                            log(f"  --- Last log output from {log_path.name} ---")
                            for tl in tail:
                                log(f"      {tl}")
                            log("  ---------------------------------------------")
                except Exception:
                    pass
            return False

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MetrCheck-HealthCheck"})
            with urllib.request.urlopen(req, timeout=req_timeout) as resp:
                if resp.status in (200, 304):
                    return True
        except Exception:
            pass
        time.sleep(0.8)
    return False

def main():
    log("=" * 64)
    log("     MetrCheck AI - Automated Launch & Verification System")
    log("================================================================")
    log()

    # 0. Pre-flight Validation
    errors, npm_cmd = check_prerequisites()
    if errors:
        log("[!] PRE-FLIGHT CHECK FAILED:")
        for err in errors:
            log(f"  * {err}")
        log()
        log("Cannot start servers until the above issues are resolved.")
        sys.exit(1)

    # Track controller PID
    try:
        with open(PID_FILE, "w", encoding="utf-8") as pf:
            pf.write(str(os.getpid()))
    except Exception:
        pass

    # 1. Detect LAN IP & Check Firewall
    lan_ip = get_lan_ip()
    laptop_url = "http://localhost:5173"
    universal_url = f"http://{lan_ip}:5173"
    api_docs_url = "http://localhost:8000/docs"
    health_url = "http://127.0.0.1:8000/api/health"
    frontend_check_url = "http://127.0.0.1:5173"

    log(f"[*] Detected Local Network IP: {lan_ip}")
    check_and_prompt_firewall()

    log("[*] Checking for previous instances on ports 5173, 5174, and 8000...")
    conflicts = kill_ports((5173, 5174, 8000))
    if conflicts:
        for c_port, c_pid, c_name in conflicts:
            log(f"  [WARNING] Port {c_port} is currently in use by external process '{c_name}' (PID {c_pid}).")
            log(f"            If server fails to bind, please close the conflicting application.")
    time.sleep(0.5)

    # 2. Start Backend
    log("[*] Starting FastAPI Backend (0.0.0.0:8000)...")
    python_exe = sys.executable
    backend_env = os.environ.copy()
    backend_log_path = ROOT_DIR / "backend.log"
    backend_log_file = open(backend_log_path, "w", encoding="utf-8")
    backend_proc = subprocess.Popen(
        [
            python_exe, "-m", "uvicorn", "main:app",
            "--host", "0.0.0.0",
            "--port", "8000"
        ],
        cwd=str(BACKEND_DIR),
        env=backend_env,
        stdout=backend_log_file,
        stderr=subprocess.STDOUT
    )

    # 3. Start Frontend
    log("[*] Starting Vite React Frontend (0.0.0.0:5173)...")
    frontend_log_path = ROOT_DIR / "frontend.log"
    frontend_log_file = open(frontend_log_path, "w", encoding="utf-8")
    frontend_proc = subprocess.Popen(
        f'"{npm_cmd}" run dev',
        cwd=str(FRONTEND_DIR),
        shell=True,
        stdout=frontend_log_file,
        stderr=subprocess.STDOUT
    )

    # 4. Automated Health Verification
    log("[*] Running automated health checks on Backend and Frontend...")
    backend_ok = wait_for_service(
        health_url, name="Backend", proc=backend_proc, log_path=backend_log_path, total_timeout=30.0, req_timeout=4.0
    )
    frontend_ok = wait_for_service(
        frontend_check_url, name="Frontend", proc=frontend_proc, log_path=frontend_log_path, total_timeout=20.0, req_timeout=3.0
    )

    log()
    log("=" * 64)
    if backend_ok and frontend_ok:
        log("  [SUCCESS] ALL SERVICES ARE ONLINE AND VERIFIED!")
        log("  Backend Health:  OK (http://127.0.0.1:8000/api/health)")
        log("  Frontend Server: OK (http://localhost:5173)")
    else:
        status_msg = []
        if not backend_ok: status_msg.append("Backend check timed out or failed")
        if not frontend_ok: status_msg.append("Frontend check timed out or failed")
        log(f"  [WARNING] System started with warnings: {', '.join(status_msg)}")
        log("  Check backend.log and frontend.log in the project root for details.")
    log("=" * 64)
    log()
    log("  * ACCESS URLS:")
    log(f"  --> Laptop Direct URL:    \033[1;32m{laptop_url}\033[0m")
    log(f"  --> Mobile / LAN URL:     \033[1;36m{universal_url}\033[0m")
    log(f"  --> Interactive API Docs: {api_docs_url}")
    log(f"  --> Backend Health Check: {health_url}")
    log()
    log("  Scan this QR Code with your Phone Camera to open on Mobile:")
    log("-" * 64)
    print_qr(universal_url)
    log("-" * 64)
    log()
    log("  * INSTRUCTIONS FOR MOBILE ACCESS:")
    log(f"  1. Ensure your phone is connected to the same Wi-Fi / Hotspot.")
    log(f"  2. If the page shows 'Site can't be reached', run allow_firewall.bat as Admin once,")
    log(f"     or run tunnel.bat for instant secure HTTPS tunneling anywhere.")
    log(f"  3. Open mobile browser: {universal_url}")
    log()
    log("  Press Ctrl+C in this terminal anytime to stop both servers.")
    log("=" * 64)

    # 5. Open browser on laptop automatically
    try:
        webbrowser.open(laptop_url)
    except Exception:
        pass

    try:
        while True:
            if backend_proc.poll() is not None:
                log("[!] Backend process terminated.")
                break
            if frontend_proc.poll() is not None:
                log("[!] Frontend process terminated.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        log("\n[*] Stopping MetrCheck AI servers...")
    finally:
        terminate_process_tree(backend_proc)
        terminate_process_tree(frontend_proc)
        try:
            backend_log_file.close()
            frontend_log_file.close()
        except Exception:
            pass
        kill_ports((5173, 5174, 8000))
        if PID_FILE.exists():
            try:
                os.remove(PID_FILE)
            except Exception:
                pass
        log("[*] Servers stopped cleanly. Goodbye!")

def stop_all():
    """Cleanly stop all MetrCheck AI processes, preserving unrelated processes."""
    log("=" * 64)
    log("  MetrCheck AI - Stopping Application Servers...")
    log("=" * 64)

    # 1. Terminate runner via PID_FILE if running
    if PID_FILE.exists():
        try:
            with open(PID_FILE, "r", encoding="utf-8") as pf:
                pid_str = pf.read().strip()
                if pid_str.isdigit():
                    r_pid = int(pid_str)
                    if r_pid != os.getpid():
                        log(f"  [*] Stopping active runner process tree (PID {r_pid})...")
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(r_pid)], capture_output=True)
            if PID_FILE.exists():
                os.remove(PID_FILE)
        except Exception:
            pass

    # 2. Safely clean ports 5173, 5174, 8000 for our processes only
    log("  [*] Checking residual processes on ports 5173, 5174, 8000...")
    conflicts = kill_ports((5173, 5174, 8000))
    if conflicts:
        for c_port, c_pid, c_name in conflicts:
            log(f"  [*] Preserved external process on port {c_port}: '{c_name}' (PID {c_pid})")
    log("  [OK] MetrCheck AI servers stopped cleanly.")

if __name__ == "__main__":
    if "--stop" in sys.argv:
        stop_all()
    else:
        main()

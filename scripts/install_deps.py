#!/usr/bin/env python3
"""
Cross-platform dependency installer for Interview AI.

Automatically detects the platform and installs appropriate dependencies:
- macOS: MPS (Metal Performance Shaders) version
- Linux with NVIDIA GPU: CUDA version
- Linux without GPU / Windows: CPU version

Usage:
    python scripts/install_deps.py [OPTIONS]

Options:
    --platform {cuda,mps,cpu}  Manually specify platform (auto-detect by default)
    --verbose                  Enable verbose output
    --dry-run                  Show what would be installed without installing
"""

import argparse
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(msg: str) -> None:
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{msg.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}\n")


def print_info(msg: str) -> None:
    print(f"{Colors.OKCYAN}ℹ {msg}{Colors.ENDC}")


def print_success(msg: str) -> None:
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")


def print_warning(msg: str) -> None:
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")


def print_error(msg: str) -> None:
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")


def run_command(cmd: list, verbose: bool = False, dry_run: bool = False) -> bool:
    """Run a shell command and return success status."""
    cmd_str = ' '.join(cmd)
    if dry_run:
        print_info(f"Would run: {cmd_str}")
        return True
    
    if verbose:
        print_info(f"Running: {cmd_str}")
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=not verbose,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed: {cmd_str}")
        if e.stderr:
            print_error(f"Error: {e.stderr}")
        return False


def detect_platform() -> str:
    """Detect the best platform for current system."""
    system = platform.system()
    
    if system == "Darwin":
        return "mps"
    elif system == "Linux":
        if check_cuda_available():
            return "cuda"
        else:
            return "cpu"
    else:
        return "cpu"


def check_cuda_available() -> bool:
    """Check if CUDA is available on the system."""
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return True
    except FileNotFoundError:
        pass
    
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        pass
    
    return False


def get_requirements_file(platform_type: str) -> str:
    """Get the appropriate requirements file for the platform."""
    return f"requirements-{platform_type}.txt"


def install_base_dependencies(verbose: bool = False, dry_run: bool = False) -> bool:
    """Install base dependencies."""
    print_header("Installing Base Dependencies")
    
    base_file = "requirements-base.txt"
    if not Path(base_file).exists():
        print_error(f"Base requirements file not found: {base_file}")
        return False
    
    print_info(f"Installing from {base_file}...")
    cmd = [sys.executable, "-m", "pip", "install", "-r", base_file]
    
    if verbose:
        cmd.append("-v")
    
    success = run_command(cmd, verbose, dry_run)
    if success:
        print_success("Base dependencies installed successfully")
    return success


def install_pytorch(platform_type: str, verbose: bool = False, dry_run: bool = False) -> bool:
    """Install PyTorch for the specified platform."""
    print_header(f"Installing PyTorch ({platform_type.upper()})")
    
    req_file = get_requirements_file(platform_type)
    if not Path(req_file).exists():
        print_error(f"Requirements file not found: {req_file}")
        return False
    
    print_info(f"Installing from {req_file}...")
    cmd = [sys.executable, "-m", "pip", "install", "-r", req_file]
    
    if verbose:
        cmd.append("-v")
    
    success = run_command(cmd, verbose, dry_run)
    if success:
        print_success(f"PyTorch ({platform_type}) installed successfully")
    return success


def verify_installation(verbose: bool = False) -> bool:
    """Verify the installation."""
    print_header("Verifying Installation")
    
    try:
        import torch
        print_success(f"PyTorch version: {torch.__version__}")
        
        if torch.cuda.is_available():
            print_success(f"CUDA available: {torch.version.cuda}")
            print_success(f"GPU: {torch.cuda.get_device_name(0)}")
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            print_success("MPS (Apple Silicon) available")
        else:
            print_info("Running in CPU mode")
        
        return True
    except ImportError as e:
        print_error(f"PyTorch import failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Cross-platform dependency installer for Interview AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Auto-detect platform and install
    python scripts/install_deps.py

    # Force CUDA installation
    python scripts/install_deps.py --platform cuda

    # Verbose output
    python scripts/install_deps.py --verbose

    # Dry run (show what would be installed)
    python scripts/install_deps.py --dry-run
        """
    )
    
    parser.add_argument(
        "--platform",
        choices=["cuda", "mps", "cpu"],
        help="Manually specify platform (auto-detect by default)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be installed without installing"
    )
    
    args = parser.parse_args()
    
    print_header("Interview AI - Dependency Installer")
    
    if args.dry_run:
        print_warning("DRY RUN MODE - No packages will be installed\n")
    
    detected_platform = detect_platform()
    platform_type = args.platform or detected_platform
    
    print_info(f"System: {platform.system()}")
    print_info(f"Detected platform: {detected_platform}")
    print_info(f"Selected platform: {platform_type}")
    
    if platform_type == "cuda" and not check_cuda_available():
        print_warning("CUDA platform selected but nvidia-smi not found")
        print_warning("Make sure NVIDIA drivers are installed")
    
    print()
    
    if not install_base_dependencies(args.verbose, args.dry_run):
        print_error("Failed to install base dependencies")
        sys.exit(1)
    
    if not install_pytorch(platform_type, args.verbose, args.dry_run):
        print_error(f"Failed to install PyTorch ({platform_type})")
        sys.exit(1)
    
    if not args.dry_run:
        if not verify_installation(args.verbose):
            print_warning("Installation verification failed")
    
    print_header("Installation Complete")
    print_success("All dependencies installed successfully!")
    print()
    print_info("Next steps:")
    print("  1. Install ffmpeg:")
    if platform.system() == "Darwin":
        print("     brew install ffmpeg")
    elif platform.system() == "Linux":
        print("     sudo apt install ffmpeg")
    print()
    print("  2. Install fonts (for PDF generation):")
    if platform.system() == "Linux":
        print("     sudo apt install fonts-noto-cjk")
    print()
    print("  3. Set up environment variables:")
    print("     cp .env.example .env")
    print("     # Edit .env and add your HF_TOKEN")
    print()
    print("  4. Run the application:")
    print("     python -m uvicorn src.api.main:app --reload")


if __name__ == "__main__":
    main()

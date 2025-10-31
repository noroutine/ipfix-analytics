#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

def main():
    ssh_dir = Path.home() / ".ssh"
    ssh_key_path = ssh_dir / "id_rsa"
    
    # Guard: skip if SSH key already exists
    if ssh_key_path.exists():
        print("✓ SSH key already available")
        return
    
    print("Setting up SSH from Prefect secret...")
    ssh_dir.mkdir(mode=0o700, exist_ok=True)
    
    # Get secret from Prefect
    try:
        from prefect.blocks.system import Secret
        
        secret = Secret.load("prefect-ssh-key")
        ssh_key = secret.get()
        
    except Exception as e:
        print(f"✗ Failed to load secret: {e}")
        return
    
    # Write SSH key with trailing newline
    ssh_key_content = ssh_key.rstrip() + "\n"
    ssh_key_path.write_text(ssh_key_content)
    ssh_key_path.chmod(0o600)
    
    # Add known hosts
    known_hosts = ssh_dir / "known_hosts"
    try:
        result = subprocess.run(
            ["ssh-keyscan", "nrtn.dev"],
            capture_output=True,
            text=True,
            check=True
        )
        with known_hosts.open("a") as f:
            f.write(result.stdout)
    except Exception as e:
        print(f"⚠️  Could not add known_hosts: {e}")
    
    print("✓ SSH configured from secret")

if __name__ == "__main__":
    main()
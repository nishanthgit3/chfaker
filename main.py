import argparse
import os
import shutil
import subprocess
import random
import sys
import json
import re
from datetime import datetime, timedelta

TEMP_DIR = "chfaker_temp"
MAGIC_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
ORIGINAL_BRANCH = "main" # Will be updated dynamically

RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_legal_warning():
    warning = f"""
{RED}{BOLD}======================================================================
[!] LEGAL DISCLAIMER: THIS TOOL IS FOR EDUCATIONAL PURPOSES ONLY.
======================================================================
The author takes no liability for the misuse of this software.
Users are solely responsible for their actions and the integrity
of their repository data. By proceeding, you acknowledge that 
force-pushing and branch deletion are irreversible operations.
THE AUTHOR TAKES NO ACCOUNTABILITY FOR DATA LOSS OR REPOSITORY 
MISCONFIGURATION RESULTING FROM THE USE OF THIS TOOL.
======================================================================{RESET}
"""
    print(warning)

def get_current_branch():
    """Captures the user's starting branch so we can revert to it if canceled."""
    proc = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True)
    branch = proc.stdout.strip()
    return branch if branch else 'main'

def cleanup_workspace():
    """Removes the temp folder and cleans .gitignore after a successful run."""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        
    if os.path.exists('.gitignore'):
        with open('.gitignore', 'r') as f:
            lines = f.readlines()
        with open('.gitignore', 'w') as f:
            for line in lines:
                if TEMP_DIR not in line:
                    f.write(line)

def rollback_workspace():
    """Emergency undo function triggered by Ctrl+C or critical errors."""
    print(f"\n\n[!] Initiating emergency rollback...")
    
    # Force checkout back to original branch, clearing the dirty git index
    subprocess.run(['git', 'reset', '--hard'], capture_output=True)
    subprocess.run(['git', 'checkout', '-f', ORIGINAL_BRANCH], capture_output=True)
    
    # Delete the fake orphan branch we were building on
    subprocess.run(['git', 'branch', '-D', 'latest_branch'], capture_output=True)
    
    # Safely move all files back from the temp directory to the root
    if os.path.exists(TEMP_DIR):
        for item in os.listdir(TEMP_DIR):
            try:
                shutil.move(os.path.join(TEMP_DIR, item), '.')
            except Exception:
                pass
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
            
    # Scrub the TEMP_DIR entry we injected into the .gitignore
    if os.path.exists('.gitignore'):
        with open('.gitignore', 'r') as f:
            lines = f.readlines()
        with open('.gitignore', 'w') as f:
            for line in lines:
                if TEMP_DIR not in line:
                    f.write(line)
                    
    print(f"[+] Rollback complete. Your workspace has been restored to '{ORIGINAL_BRANCH}'.")
    sys.exit(0)

def check_ollama(model_name):
    print(f"Checking local Ollama installation for model '{model_name}'...")
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, check=True)
        if model_name not in result.stdout:
            print(f"\n[!] ERROR: Ollama model '{model_name}' not found.")
            print(f"Install it using: ollama pull {model_name}")
            sys.exit(1)
    except FileNotFoundError:
        print("\n[!] ERROR: Ollama is not installed or not in PATH.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"\n[!] ERROR: Failed to run Ollama. Ensure your Ollama desktop app/service is running. {e}")
        sys.exit(1)

def setup_workspace(script_name):
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    
    for item in os.listdir('.'):
        # Exclude the script itself and explicitly ignore 'chfaker.py' to prevent it from being committed
        if item in ['.git', TEMP_DIR, '.gitignore', script_name, 'chfaker.py']:
            continue
        try:
            shutil.move(item, os.path.join(TEMP_DIR, item))
        except Exception as e:
            print(f"[Warning] Could not move {item}: {e}")

    with open('.gitignore', 'a') as f:
        f.write(f"\n{TEMP_DIR}/\n.gitignore\n")
    
    subprocess.run(['git', 'checkout', '--orphan', 'latest_branch'], capture_output=True)
    subprocess.run(['git', 'add', '.gitignore'], capture_output=True)

def generate_dates(start_str, end_str, count):
    start_date = datetime.strptime(start_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_str, "%Y-%m-%d")
    
    total_seconds = int((end_date - start_date).total_seconds())
    if total_seconds < 0:
        print("Error: Start date must be before end date.")
        sys.exit(1)
        
    if count <= 1:
        return [start_date.replace(hour=random.randint(8, 23), minute=random.randint(0, 59))]

    num_jumps = max(1, int(count * 0.60))
    jump_interval = total_seconds // num_jumps
    
    dates = []
    current_time = start_date + timedelta(seconds=random.randint(0, int(jump_interval*0.5)))
    current_time = current_time.replace(hour=random.randint(8, 20), minute=random.randint(0, 59))
    dates.append(current_time)
    
    for i in range(1, count):
        if random.random() < 0.40:
            last_time = dates[-1]
            minutes_to_add = random.randint(15, 240)
            new_time = last_time + timedelta(minutes=minutes_to_add)
            
            if new_time.day != last_time.day or new_time.hour > 23:
                new_time = last_time - timedelta(minutes=random.randint(15, 120))
                
            dates.append(new_time)
        else:
            last_time = dates[-1]
            noise = random.randint(int(-jump_interval * 0.2), int(jump_interval * 0.2))
            new_time = last_time + timedelta(seconds=(jump_interval + noise))
            
            if new_time.hour < 8 or new_time.hour > 23:
                new_time = new_time.replace(hour=random.randint(8, 22), minute=random.randint(0, 59))
                
            if new_time > end_date:
                new_time = end_date.replace(hour=random.randint(8, 22), minute=random.randint(0, 59))
                
            dates.append(new_time)
            
    return sorted(dates)

def is_text_file(filepath):
    try:
        with open(filepath, 'tr') as check_file:
            check_file.read(1024)
            return True
    except UnicodeDecodeError:
        return False

def get_staged_diff():
    proc = subprocess.run(['git', 'diff', '--cached'], capture_output=True, text=True, encoding='utf-8')
    if proc.returncode != 0 or not proc.stdout.strip():
        proc = subprocess.run(['git', 'diff', '--cached', MAGIC_EMPTY_TREE], capture_output=True, text=True, encoding='utf-8')
    return proc.stdout

def optimize_diff(raw_diff):
    if not raw_diff.strip():
        return ""
        
    optimized_lines = []
    for line in raw_diff.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            optimized_lines.append(line.strip())
        elif line.startswith('-') and not line.startswith('---'):
            optimized_lines.append(line.strip())
            
    # Restrict diff to 3 lines maximum
    if len(optimized_lines) > 3:
        optimized_lines = optimized_lines[:3]
            
    condensed_diff = '\n'.join(optimized_lines).strip()
    
    if not condensed_diff:
        return "File architecture modifications"
        
    return condensed_diff

def sanitize_llm_output(msg):
    msg = re.sub(r'<think>.*?</think>', '', msg, flags=re.DOTALL)
    msg = msg.strip('\"\' `\n')
    
    # Strip emojis
    msg = re.sub(r'[\U00010000-\U0010ffff]', '', msg)
    
    lines = [l.strip() for l in msg.split('\n') if l.strip()]
    valid_lines = [l for l in lines if not l.startswith(('+', '-', '@@', 'def ', 'import '))]
    
    if not valid_lines:
        return ""
        
    final_msg = valid_lines[0]
    
    if any(char in final_msg for char in ['{', '}', 'def ', '()', '=>', 'var ', 'let ', 'import ']):
        return ""
        
    return final_msg.strip()

def generate_commit_message(diff, args):
    clean_diff = optimize_diff(diff)
    
    small_fallbacks = [
        "Refactored code formatting and basic cleanups",
        "Updated internal codebase structure and files",
        "Implemented core file optimizations and fixes",
        "Adjusted system modules for upcoming build",
        "Minor modifications applied to core logic"
    ]
    long_fallbacks = [
        "Updated repository modules to align with architectural formatting changes and optimized internal tracking files.",

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
        if item in ['.git', TEMP_DIR, '.gitignore', script_name]:
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
            
    condensed_diff = '\n'.join(optimized_lines).strip()
    
    if not condensed_diff:
        return "File architecture modifications"
    
    if len(condensed_diff) > 400:
        condensed_diff = condensed_diff[:400] + "\n..."
        
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
        "Implemented structural revisions across project dependencies to resolve underlying file synchronization issues.",
        "Refactored file structural hierarchies and cleaned up codebase syntax definitions for better maintenance."
    ]

    if not clean_diff or clean_diff == "File architecture modifications":
        return random.choice(small_fallbacks if args.mode == 'small' else long_fallbacks)

    prompt = (
        f"You are a developer writing a git commit message.\n"
        f"Write EXACTLY ONE SENTENCE summarizing the changes.\n"
        f"CRITICAL RULES:\n"
        f"1. DO NOT output any code.\n"
        f"2. DO NOT include quotes or explanations.\n"
        f"3. DO NOT use emojis or special symbols.\n"
        f"4. Maximum 8 words.\n\n"
        f"Code Changes:\n{clean_diff}\n\n"
        f"Commit Message:"
    )
    
    if args.mode == 'long':
        prompt = prompt.replace("Maximum 8 words", "Write 2 descriptive sentences")

    model = args.model or "qwen2.5:0.5b"
    result = subprocess.run(['ollama', 'run', model, prompt], capture_output=True, text=True, encoding='utf-8')
    clean_msg = sanitize_llm_output(result.stdout)
    
    if not clean_msg:
        return random.choice(small_fallbacks if args.mode == 'small' else long_fallbacks)
    return clean_msg

def commit_with_date(date_obj, message, current_num, total_num):
    if not message or not message.strip():
        message = "Routine system updates and maintenance"

    date_str = date_obj.strftime('%Y-%m-%dT%H:%M:%S')
    env = os.environ.copy()
    env['GIT_AUTHOR_DATE'] = date_str
    env['GIT_COMMITTER_DATE'] = date_str
    
    proc = subprocess.run(['git', 'commit', '--allow-empty', '-m', message], env=env, capture_output=True, text=True)
    
    if proc.returncode != 0:
        print(f"[!] Error committing at {date_str}. (Nothing staged or git error)")
    else:
        print(f"[{current_num}/{total_num}] [{date_str}] {message}")

def get_all_repo_files(base_dir):
    all_files = []
    for root, _, files in os.walk(base_dir):
        for file in files:
            all_files.append(os.path.join(root, file))
    return all_files

def main():
    global ORIGINAL_BRANCH

    print_legal_warning()
    
    parser = argparse.ArgumentParser(description="chfaker is a commit history faker using local Ollama, use this with caution, author takes no liability")
    parser.add_argument('--s', type=str, required=True, help="The start date (e.g., YYYY-MM-DD)")
    parser.add_argument('--e', type=str, required=True, help="The end date (e.g., YYYY-MM-DD)")
    parser.add_argument('--cc', type=int, required=True, help="The total number of commits")
    parser.add_argument('--model', '-m', type=str, help="Model name (Defaults: qwen2.5:0.5b for local)")
    parser.add_argument('--mode', choices=['small', 'long'], default='small', help="Commit message detail mode")
    
    args = parser.parse_args()
    script_name = os.path.basename(__file__)

    check_ollama(args.model or "qwen2.5:0.5b")
    
    if not os.path.isdir('.git'):
        print("Error: You must run this inside a git repository.")
        sys.exit(1)

    ORIGINAL_BRANCH = get_current_branch()

    print(f"\nMoving files to {TEMP_DIR} and setting up orphan branch...")
    setup_workspace(script_name)
    commit_dates = generate_dates(args.s, args.e, args.cc)
    
    all_temp_files = get_all_repo_files(TEMP_DIR)
    priority_files = []
    normal_files = []
    
    for f in all_temp_files:
        basename = os.path.basename(f).lower()
        if 'readme' in basename or 'license' in basename:
            priority_files.append(f)
        else:
            normal_files.append(f)

    pending_items = []
    for nf in normal_files:
        if is_text_file(nf):
            with open(nf, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                if lines:
                    pending_items.append({'type': 'text', 'file': nf, 'lines': lines})
        else:
            pending_items.append({'type': 'binary', 'file': nf})
            
    random.shuffle(pending_items)

    print("\n[+] Creating Initial Commit...")
    staged_initial = False
    
    for pf in priority_files:
        rel_path = os.path.relpath(pf, TEMP_DIR)
        os.makedirs(os.path.dirname(rel_path) or '.', exist_ok=True)
        shutil.copy2(pf, rel_path)
        subprocess.run(['git', 'add', rel_path])
        staged_initial = True
        
    if not staged_initial and pending_items:
        item = pending_items.pop(0)
        rel_path = os.path.relpath(item['file'], TEMP_DIR)
        os.makedirs(os.path.dirname(rel_path) or '.', exist_ok=True)
        if item['type'] == 'binary':
            shutil.copy2(item['file'], rel_path)
        else:
            with open(rel_path, 'a', encoding='utf-8') as f:
                f.writelines(item['lines'])
        subprocess.run(['git', 'add', rel_path])
        staged_initial = True
        
    if staged_initial:
        commit_with_date(commit_dates[0], "Initial commit", 1, args.cc)
    else:
        print("[!] Workspace is completely empty. Nothing to commit.")
        rollback_workspace()

    current_commit_idx = 1
    
    print(f"\n[+] Processing {len(pending_items)} Remaining File Chunks over {args.cc - 1} Commits...")
    
    while current_commit_idx < len(commit_dates):
        date_obj = commit_dates[current_commit_idx]
        commits_left = len(commit_dates) - current_commit_idx
        
        if not pending_items:
            pass
        elif commits_left == 1:
            for item in pending_items:
                rel_path = os.path.relpath(item['file'], TEMP_DIR)
                os.makedirs(os.path.dirname(rel_path) or '.', exist_ok=True)
                if item['type'] == 'binary':
                    shutil.copy2(item['file'], rel_path)
                else:
                    with open(rel_path, 'a', encoding='utf-8') as f:
                        f.writelines(item['lines'])
                subprocess.run(['git', 'add', rel_path])
            pending_items = []
        else:
            items_to_stage = max(1, len(pending_items) // commits_left)
            
            for _ in range(items_to_stage):
                if not pending_items:
                    break
                    
                item = pending_items.pop(0)
                rel_path = os.path.relpath(item['file'], TEMP_DIR)
                os.makedirs(os.path.dirname(rel_path) or '.', exist_ok=True)
                
                if item['type'] == 'binary':
                    shutil.copy2(item['file'], rel_path)
                else:
                    lines = item['lines']
                    lines_to_write = max(1, len(lines) // 2)
                    with open(rel_path, 'a', encoding='utf-8') as f:
                        f.writelines(lines[:lines_to_write])
                    
                    if lines[lines_to_write:]:
                        item['lines'] = lines[lines_to_write:]
                        pending_items.append(item)
                        
                subprocess.run(['git', 'add', rel_path])

        raw_diff = get_staged_diff()
        commit_msg = generate_commit_message(raw_diff, args)
        
        commit_with_date(date_obj, commit_msg, current_commit_idx + 1, args.cc)
        
        current_commit_idx += 1

    cleanup_workspace()
    print(f"\n--- Process Complete (Generated {current_commit_idx} Local Commits) ---")

    print("\n[WARNING] The next step will DELETE ALL EXISTING BRANCHES (local and remote) and replace them with a single 'main' branch containing this new history.")
    push_choice = input("Do you want to do this? (y/N): ").strip().lower()
    
    if push_choice == 'y':
        # --- 1. LOCAL SCORCHED EARTH ---
        print("\nDeleting all other local branches...")
        proc = subprocess.run(['git', 'branch', '--format', '%(refname:short)'], capture_output=True, text=True)
        branches = [b.strip() for b in proc.stdout.split('\n') if b.strip()]
        
        for branch in branches:
            if branch != 'latest_branch':
                subprocess.run(['git', 'branch', '-D', branch], capture_output=True)
                
        print("Renaming current branch to 'main'...")
        subprocess.run(['git', 'branch', '-m', 'main'], capture_output=True)
        
        # --- 2. REMOTE SCORCHED EARTH ---
        print("Force updating remote repository (git push -f origin main)...")
        # Ensure 'main' gets pushed successfully first
        push_proc = subprocess.run(['git', 'push', '-f', 'origin', 'main'], capture_output=True, text=True)
        
        if push_proc.returncode == 0:
            print("[+] 'main' branch successfully established on remote.")
            
            # Query GitHub directly for all hosted branches
            print("Querying remote repository for legacy branches...")
            r_proc = subprocess.run(['git', 'ls-remote', '--heads', 'origin'], capture_output=True, text=True)
            
            if r_proc.returncode == 0:
                for line in r_proc.stdout.split('\n'):
                    if line.strip():
                        # Format is usually: <hash>\trefs/heads/<branch>
                        ref = line.split('\t')[1]
                        branch_name = ref.replace('refs/heads/', '')
                        
                        if branch_name != 'main':
                            print(f"  -> Deleting remote branch: {branch_name}")
                            subprocess.run(['git', 'push', 'origin', '--delete', branch_name], capture_output=True)
                            
            print("\n[+] SUCCESS! Remote repository is now perfectly mirrored: ONLY 'main' exists.")
        else:
            print(f"\n[!] Error during force-push to main:\n{push_proc.stderr}")
    else:
        print("\nSkipped branch cleanup and remote synchronization.")
        print("Your fake commits are currently on the 'latest_branch' branch.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        rollback_workspace()
    except Exception as e:
        print(f"\n{RED}[!] A fatal error occurred: {e}{RESET}")
        rollback_workspace()
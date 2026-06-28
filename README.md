# chfaker

chfaker is an educational tool designed to simulate developer activity by programmatically generating commit history. It reads your local repository, creates an orphan branch, and populates it with AI-generated commits, perfectly mapping them to a realistic timeline.

### LEGAL DISCLAIMER

THIS TOOL IS FOR EDUCATIONAL PURPOSES ONLY. The author takes no liability for the misuse of this software. Users are solely responsible for their actions and the integrity of their repository data. By proceeding, you acknowledge that force-pushing and branch deletion are irreversible operations. THE AUTHOR TAKES NO ACCOUNTABILITY FOR DATA LOSS OR REPOSITORY MISCONFIGURATION RESULTING FROM THE USE OF THIS TOOL.

## Installation & Setup (Linux)

### 1. Requirements

* Python 3
* Git

### 2. Install Ollama

Run the official installation script to set up the local AI engine:

```bash
curl -fsSL https://ollama.com/install.sh | sh

```

### 3. Pull the Required Model

chfaker is optimized to run offline using the lightweight and fast qwen2.5:0.5b model:

```bash
ollama pull qwen2.5:0.5b

```

## Usage

Place chfaker.py in the root of the Git repository you wish to modify. Run the script using the following command structure:

```bash
python3 chfaker.py --s YYYY-MM-DD --e YYYY-MM-DD --cc <NUMBER_OF_COMMITS>

```

### Example Command

To generate 20 commits spread organically between January 1st and June 1st, 2026:

```bash
python3 chfaker.py --s 2026-01-01 --e 2026-06-01 --cc 20

```

## Important Warning

This tool modifies your Git history. Always ensure you have a backup of your repository before running this script. Use this tool only on repositories where you have full ownership and authorization.
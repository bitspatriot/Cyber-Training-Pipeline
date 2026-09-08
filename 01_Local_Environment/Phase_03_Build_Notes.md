# Task 3.1: The Command Line Murders

*** Setup the Infra_Node environment ***
1. mkdir -p 05_Data_Operator/Task_3.1_clmystery
2. cd 05_Data_Operator/Task_3.1_clmystery
3. git clone https://github.com/veltman/clmystery.git
4. cd clmystery
5. cat instructions

*** NOTE: Entire task investigation was conducted on the Infra_Node through the clmystery.git cloned repository. All the files that were used to solved the case, including the required 'Task_3.1_case_solved.md' deliverable have been pushed to the '05_Data_Operator/Task_3.1_clmystery' directory on the repository. ***

# Task 3.2: Python Integrity Checker
1. Write the python script that walks /etc and all of it's subdirectories
2. Make changes to the /etc directory
   - Change /etc/hosts
   - Add new file in /etc
3. Run the script(s) that capture the file hashes and directory changes
4. Revert the file that was changes (e.g. /etc/hosts and deleted the new file)
*** NOTE: all scripts and output have been stored in '03_Scripts/python_integrity_checker' ***

# Task 3.3: Python Integrity Checker (on Infra_Node)
1. mkdir -p ~/05_Data_Operator/Task_3.4_web_log_parser
2. cd ~/05_Data_Operator/Task_3.4_web_log_parser
3. Grab a sample of the real dataset needed to design the regex against actual lines: curl -s "https://raw.githubusercontent.com/elastic/examples/master/Common%20Data%20Formats/apache_logs/apache_logs" -o sample_apache_logs 2>/dev/null | head
4. Create the parse_web_logs.py script (added to 03_Scripts in GitHub repository)
5. Run the parse_web_logs.py python script agains the real dataset to create the suspicious_ips.txt file:
   - chmod +x parse_web_logs.py
   - python3 parse_web_logs.py -o suspicious_ips.txt
   - echo "exit: $?"
   - echo "=== suspicious_ips.txt: line count and first 10 ==="
   - wc -l suspicious_ips.txt
   - head -10 suspicious_ips.txt
   - Should see 213 total 404 entries, with 90 unique client IPs from the regex parse in the pythong script
6. Manual log analysis checks:

*** grep through the suspicious_ips.txt file ***
echo "=== Validation: every line must be a valid IPs and nothing else ==="

- Check for any line that isn't a clean IPv4 address
grep -vE '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$' suspicious_ips.txt && echo "FOUND non-IP lines above" || echo "PASS: all lines are clean IPv4 addresses"

echo "=== Check for duplicates (should be none) ==="
sort suspicious_ips.txt | uniq -d | head && echo "(if empty above, no duplicates)"
dup_count=$(sort suspicious_ips.txt | uniq -d | wc -l)
echo "duplicate count: $dup_count"

echo "=== Check for blank lines (should be 0) ==="
blank=$(grep -c '^$' suspicious_ips.txt)
echo "blank lines: $blank"

*** awk through the suspicious_ips.txt file ***
1. Install 'xxd': sudo apt install xxd

echo "=== Cross-check against raw dataset: unique IPs on 404 lines via awk ==="
awk '$9 == "404" {print $1}' sample_apache_logs | sort -u | wc -l
echo "(above should equal 90 — matches the python output)"

echo "=== byte-level tail to confirm no trailing blank line ==="
tail -c 40 suspicious_ips.txt | xxd | tail -3

# Task 3.4: The Threat Intel Scraper
1. mkdir -p ~/05_Data_Operator/Task_3.4_mitre_scraper
2. cd ~/05_Data_Operator/Task_3.4_mitre_scraper
3. Create virtual environment to install 'requests' and 'beautifulsoup4.' (This constraint exists specifically for this reason. If you try to intall these packages outside the venv, they will fail. Should see "(.venv)" at the front of your prompt, indicating that pip and python both point at the isolated vurtual environment.)
   - python3 -m venv .venv
   - source .venv/bin/activate
   - pip install -r requirements.txt
4. Create the scrape_mitre.py script (added to 03_Scripts in GitHub repository)
5. sudo chmod +x scrape_mitre.py
6. ./scrape_mitre.py --print
   - Should now see newly created and queryable 'threat_intel.db' file afte the MITRE ATT&CK groups directory HTML table has been scraped.
   - Pull 
     - Change to target directory on the host.
     - Pull'threat_intel.db' sqlite database back to the Host for push to the GitHub repository: 'scp infra:~/05_Data_Operator/Task_3.7_mitre_scraper/threat_intel/db .'

# Task 3.5: Threat Intelligence API Enrichment
1. mkdir -p ~/05_Data_Operator/Task_3.5_enrich_ips
2. cd ~/05_Data_Operator/Task_3.5_enrich_ips
3. Copy suspicious.txt file from Task 3.3 to the Task_3.5_enrich_ips directory. The python script 'enrich_ips.py' will run against that list.
4. Create the enrich_ips.py script (added to 03_Scripts in GitHub repository)
5. sudo chmod +x enrich_ips.py
6. Script reads suspicious.txt by default. With 90 IPs from Task 3.3 and a configured 1-seconds delay in the script, the script should take ~90 seconds to complete.
   - Output (stdout) is to your terminal, and won't create an output file. There's no requirement for an output file in Task 3.5

# Task 3.6: The Pipeline Orchestrator
1. mkdir -p ~/05_Data_Operator/Task_3.6_pipeline
2. cd ~/05_Data_Operator/Task_3.6_pipeline
3. Create the run_intel_pipeline.sh script (added to 03_Scripts in GitHub repository)
4. sudo chmod +x run_intel_pipeline.sh
5. PARSER=~/05_Data_Operator/<your-3.3-dir>/parse_web_logs.py
6. ENRICHER=~/05_Data_Operator/<your-3.5-dir>/enrich_ips.py
7. ./run_intel_pipeline.sh
   - Ensure that the pipeline script runs all three tasks concurrently
   - Bash script should produce another suspicious_ips.txt file to be used by the pipiline bash script

# CLEANUP: Run gitleaks against all fo the completed task directories on Infra_Node
1. Clone your repository again to /tmp.
   - git clone https://github.com/<your-username>/Cyber-Training-Pipeline.git squadron-lab-scan (archive or delete the prvious 'squadron-lab-scan' clone)
2. Go to the 'squadron-lab-scan' directory
3. gitleaks detect --source . --report-format json --report-path /tmp/gitleaks-report.json --verbose; echo "gitleaks exit code: $?"
   - This new scan should produce findings from the 'etc_baseline.csv' from Task 3.2. Make sure there's no other findings other than the 64 findings from that task.
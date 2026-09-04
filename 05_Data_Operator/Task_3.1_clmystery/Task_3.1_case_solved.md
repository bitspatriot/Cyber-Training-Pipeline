# Task 3.1: The Command Line Murders

*** Setup the Infra_Node environment ***
1. mkdir -p 05_Data_Operator/Task_3.1_clmystery
2. cd 05_Data_Operator/Task_3.1_clmystery
3. git clone https://github.com/veltman/clmystery.git
4. cd clymystery
5. cat instructions (read to locate the first step in the investifation)

*** Step 1 - The first clue ***
Command: grep -i -C 3 -w CLUE crimescene > clue_extraction
Why: Isolate all clues and surrounding context from the crimescene file
Found:

*******
Crime Scene Report #912464709392
********
CLUE: Footage from an ATM security camera is blurry but shows that the perpetrator is a tall male, at least 6'.
*******

*******
Crime Scene Report #028615332953
********
CLUE: Found a wallet believed to belong to the killer: no ID, just loose change, and membership cards for AAA, Delta SkyMiles, the local library, and the Museum of Bash History. The cards are totally untraceable and have no name, for some reason.
*******

*******
Crime Scene Report #575776622208
********
CLUE: Questioned the barista at the local coffee shop. He said a woman left right before they heard the shots. The name on her latte was Annabel, she had blond spiky hair and a New Zealand accent.

THREE CLUE SUMMARY:
Clue #1 (Line#: 9213): tall male, at least 6'
Clue #2 (Line#: 9370): wallet found with no ID, only loose change, and membership cards for the AAA, Delta SkyMiles, the local library, and the Museum of Bash History. The cards are untraceable and have no name
Clue #3 (Line#: 11002): barista said woman left right before the shots. Name on latte was Annabel, she had blonde spiky hair, and a New Zealand accent.

*** Step 2 - Follow the first named lead: Annabel ***
Command: Locate interviews folder and grep for Annabel: 
1. grep -i "Annabel" people
2. sed -n '179p;1670p' people
3. ls interviews | head (see how the interviews file is structured)
4. Check structure of interview files:
- cat interviews/interview-<pick-any-file>
- head -5 interviews/interview-* | head -40
- Findings: each interview doesnt have a header or any sort of investigation identifier
5. grep through all the interview files for both Annabel street names and the file their found in:
- Discovery: grep -rln "Church" interviews/ identified interview filename: interview-699607
- Discovery: grep -rln "Sun" interviews/ identified interview filename: interview-47246024
6. Look at the interview files:
- cat interviews/<interview-699607>
- cat interviews/<interview-47246024>

Why: Find Annabel's entry in the 'people' file to see if it the police interviewed her, or to identify other clues
Found (2 female Annabel's located):
- Annabel Sun, age 26, Address: Hart Place, Line 40 (possible interview reference number)
- Annabel Church, age 38, Address: Buckingham Place, Line 179 (possible interview reference number)

INTERVIEW FILE EVIDENCE FOR ANNABEL CHURCH:

Interviewed Ms. Church at 2:04 pm.  Witness stated that she did not see anyone she could identify as the shooter, that she ran away as soon as the shots were fired.
However, she reports seeing the car that fled the scene.  Describes it as a blue Honda, with a license plate that starts with "L337" and ends with "9"

*** Step 3 - Follow the new clue about the blue Honda with licence plate that starts with "L337" and ends with "9" ***
Why: Annabel Church's investigation lead to a new clue about the color and type of car, and a partial license plate for the vehicle that fled the scene.
Commands to seach for the car:
1. Check what other datasets exists: ls -la (already used crimescene, people, and interviews/)
2. Located vehicles dataset. Construct an awk command to filter the vehicle blocks by license plate, car make, car color, and driver height: 
- awk -v RS= '/L337[0-9A-Z]*9/ && /Honda/ && /Blue/ && /Height: [67]/ {print; print ----}' vehicles > vehicle_match_suspects'
- Redirected the output to a 'vehicle_match_suspects' file for further analysis
- 4 suspests remain out of the 13 original partial license plate matches

*** Step 4 - User the memberships data set to further narror down the remaining suspects ***
Why: Narrowed down the suspect list to 4, and now need to match them against the remaining memberships dataset to see if there's an exact match.
Commands: 
1. cd memberships/
2. Look at the membership files to see how their formatted: nano <membership_file_name>
3. Discovery: each file is a list of names
4. Approach: take the list of 4 suspect names and see which name exists on all four memebership list discovered in CLUE #2.

SUSPECT NAMES:
- Erika Owens 
- Joe Germuska
- Jeremy Bowers
- Jacqui Maher

SUSPECT MEMBERSHIPS: 
- AAA
- Museum of Bash History
- Delta SkyMiles
- Local Library

CREATED FOR LOOP BASH SCRIPT: designed a bash script (suspect_membership_match.sh) to match all 4 suspects with all four membership files

for name in "Erika Owens" "Joe Germuska" "Jeremy Bowers" "Jacqui Maher"; do
  count=$(grep -rl "$name" memberships/AAA memberships/Delta_SkyMiles memberships/Museum_of_Bash_History memberships/Terminal_City_Library | wc -l)
  echo "$count  $name"
done

DISCOVERED: Two suspects were located on all four membership lists
- Jeremy Bowers
- Jacqui Maher

*** Step 5: Narrow down the final two suspects to the one killer ***
Why: The suspects have been narrowed down to two. The last step is to identify the one killer
Commands: 
1. Check the gender of each suspect. The killer was "tall male" according to Annabel.
- grep -w "Jeremy Bowers" people
- grep -w "Jacqui Maher" people
2. Jeremy is a male and Jacqui is female
3. Jeremy Bowers is the killer!!
4. Confirm in the answer with the 'solutions' file from the .../clmystey directory
- echo Jeremy Bowers | /usr/bin/md5sum | grep -qif /dev/stdin encoded && echo CORRECT\! GREAT WORK, GUMSHOE. || echo SORRY, TRY AGAIN.
5. If the killer is correct, you should see "GREAT WORK, GUMSHOE."

for name in "Erika Owens" "Joe Germuska" "Jeremy Bowers" "Jacqui Maher"; do
  count=$(grep -rl "$name" memberships/AAA memberships/Delta_SkyMiles memberships/Museum_of_Bash_History memberships/Terminal_City_Library | wc -l)
  echo "$count  $name"
done

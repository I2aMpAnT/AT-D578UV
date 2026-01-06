AT-D578UV Pro Codeplug Import Instructions
==========================================
GMRS License: WSKW654

FILES INCLUDED:
- channels.csv      - All 38 channels (import via Tool > Import > Channel)
- encryption_keys.csv - 3 DMR encryption keys
- zones.csv         - 8 organized zones

STEP 1: Open AnyTone CPS Software
---------------------------------
Launch the AT-D578UV Pro CPS software

STEP 2: Import Channels
-----------------------
1. Go to: Tool > Import > Channel
2. Select: channels.csv
3. Click Import

STEP 3: Set Up Encryption Keys
------------------------------
1. Go to: Optional Setting > Encrypt
2. Add these keys manually:

   KEY1: 285DAE5A749DE26BDE6B843892A5C58E
   KEY2: 2CF0F5D56777697DADD6C9F0EA980E1D
   KEY3: 0DFAC8681EECFC4FFCE88DBAB6EE48ED

   (These are 128-bit ARC4 keys for DMR Basic Privacy)

STEP 4: Import Zones (Optional)
-------------------------------
1. Go to: Tool > Import > Zone
2. Select: zones.csv
3. Click Import

STEP 5: Set Radio ID
--------------------
1. Go to: Optional Setting > Radio ID List
2. Add DMR ID: "I2Base" (base station identifier)

STEP 6: Write to Radio
----------------------
1. Connect programming cable to radio
2. Turn on radio
3. Go to: Program > Write to Radio

CHANNEL SUMMARY:
----------------
1-3:    ENCRYPTED 1-3 (DMR with encryption)
4-5:    FRS 2, FRS 22 (Family radio)
6-12:   MARINE channels (VHF marine band)
13-17:  AVIATION (Hyannis airport, Guard, Unicom)
18-31:  PUBLIC SAFETY (Barnstable County)
32:     NOAA Weather
33-38:  HAM radio (2M and 70CM simplex)

NOTE: Aviation and Public Safety channels are RX-only (Forbid TX = 1)

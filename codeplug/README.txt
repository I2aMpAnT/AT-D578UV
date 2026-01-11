AT-D578UV Pro Codeplug Instructions
====================================
GMRS License: WSKW654

FILES:
------
- I2Base.db3             - MAIN CPS project file (use this!)
- CPS_MANUAL_SETTINGS.txt - Manual configuration guide
- CodeplugSample.rdt     - Minimal sample (reference only)

I2Base.db3 CONTAINS:
--------------------
- All 38 channels (HIGH power)
- All 6 Radio IDs:
  * I2Base (100) - AT-D578UV base station
  * I2 (101) - DRN HT
  * MrSI2 (102) - DJN HT
  * LiLI21 (1) - EJD HT
  * LiLI22 (2) - JGN HT
  * LiLI23 (3) - MAN HT
- MAIN zone with all channels

QUICK START:
------------
1. Open AnyTone CPS > File > Open > I2Base.db3
2. Add encryption keys (see CPS_MANUAL_SETTINGS.txt)
3. Assign keys to ENCRYPTED 1-3 channels
4. Configure P-key assignments
5. Configure repeater mode settings
6. Program > Write to Radio

CHANNEL SUMMARY:
----------------
1-3:    ENCRYPTED 1-3 (DMR with AES-256 encryption)
4-5:    FRS 2, FRS 22 (Family radio)
6-12:   MARINE channels (VHF marine band)
13-17:  AVIATION (Hyannis airport, Guard, Unicom)
18-31:  PUBLIC SAFETY (Barnstable County)
32:     NOAA Weather
33-38:  HAM radio (2M and 70CM simplex)

NOTE: Aviation and Public Safety channels are RX-only (Forbid TX enabled)

See CPS_MANUAL_SETTINGS.txt for detailed configuration instructions.

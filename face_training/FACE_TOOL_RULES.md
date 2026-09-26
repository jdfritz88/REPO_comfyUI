# Face tool rules — the user's standing rules

The user's own rules for the face tool (Face Seek search, the review page, the Face Tool
window). Only rules that stand today are listed; a rule a later rule replaced is left out.
Dates are when the user set the rule. Full history: `logs/face_rules_audit_2026-09-25/`.

**For every Claude session — read this file before changing anything in the face tool.**
- When the user gives a new face-tool rule, add it here in the same session, with the date.
- When a new rule replaces an old one, remove the old one here and say so in the log.
- If the code does not match a rule, tell the user. Do not quietly change the rule or the
  code to make them match.
- The review page shows this list in its yellow-framed box, section (b). Keep the format:
  `## ` for a step, `N. ` for each rule, one line each.

## Setting up a person
1. Pick exactly two clear starter photos of her face (one neutral, one with expression), not a folder. (09-08, 09-12, 09-14)
2. Then the app asks where to search and whether to include all folders inside it, ticked by default. (09-11, 09-14)
3. A new person's folders are made automatically. (09-12)
4. Everything runs without Claude. (09-07)
5. Five backups of each person's profile, face profile and scan notes on Close, on Stop and on the window X, plus a manual backup and restore. (09-07)
6. The Face Tool's Close (and the window X) also closes every review page's program, as well as, not instead of, what it did before. (09-26)
7. Delete-profile button: delete everything or pick the parts. (09-16)
8. NOTHING about one person is shared with another. Every file created or edited for a person lives in that person's own folder: their "not this person" face bank, answers log, judge and crop margins are in their learning/ folder, and their search, review, training and library-run logs are in their logs/ folder. Logs written while the app is used stay with the app and the person, as for a customer who bought it; the repo's logs/ folder is only for developing the app. Searching for David never sees Susana's records, even when both are in the same photos. There is no shared folder. (09-26)

## Searching
9. Search photos and videos. Read HEIC photos. Never touch the jesperanto share. (09-08, 09-12)
10. Copy everything found, group photos and videos included. Never move, rename or edit an original. (09-14)
11. Read a video's or photo's rotation note first, whether run in the background or from the window. (09-13)
12. If no face is found, try the other ways before giving up. (09-11)
13. First video scan: look for faces on one frame in every 24. (09-25)
14. No look-alike check in the first scan. Look-alikes are thrown out only after she has been found, like the community does. (09-26)
15. If a face does not clearly look like her, it is not her. Unsure counts as not her. (09-15)
16. The app learns only from your answers, never from its own unsure guesses — both in deciding close calls and in rebuilding her face profile. A picture that is not her never teaches her face profile: nothing on her not-her list, nothing the app itself found not to be her, and no close call nobody has approved. This was always the rule. (09-14, 09-26)
17. An unsure video frame still gets its video the closer look. (09-26)
18. Stop/save and Resume must work, and Stop must be heard even inside a long video. (09-14, 09-16)

## Videos she is in
19. The closer look checks one frame in every 12 to find where she is. (09-26)
20. Save a video frame to disk only when she is in it. (09-15)
21. Pull every frame of the stretches she is in, blurry and duplicate alike, into her video_and_frames folder, with a copy of the video (needed for other projects). Clean up after the search. (09-15, 09-16)
22. The clean-up is done by the app: it deletes blurry, unfocused, duplicate and near-duplicate frames, and keeps every different angle and expression when the picture is sharp. (09-15, 09-16)
23. A video the search is unsure about is copied to the uncertain pile. A video it is sure is not her is not copied. (09-16)

## Crops
24. Two versions of each picture: face and body, and face only. (09-08)
25. Crops with someone else still in them are shown framed yellow. (09-14)
26. Keep the duplicate checks where they are (the first-scan one was moved on 09-26), plus one check at the end that keeps the larger, sharper copy. (09-13, 09-14)
27. Never delete a processed photo, frame or video. Processed originals move to the processed folder. (09-11, 09-23)

## Review page
28. You review everything after processing and before training. (09-08, 09-14)
29. Every uncertain photo and video is on the browser review page. (09-16)
30. Videos: She appears here (the next search starts there), Yes — but don't use it, Find the face (the face you box is used for that video only), Not her (the copy is deleted and it is recorded). (09-16, 09-25)
31. Photos: Yes it's her, Yes — but don't use it, Duplicate, Not her. (09-17)
32. Delete writes "not her" in the search history without teaching the app. Rotate turns a crop. Delete works the same on yellow-framed crops. (09-14, 09-17)
33. The legend stays at the top of the page when scrolling. (09-14)
34. Look-alike groups with a notched slider; frames are compared as pictures, never by time. (09-18)
35. Once reviewed, a picture does not come back. The app does this, not Claude. (09-23)
36. Every photo or frame the search picked up and then decided as her or not her is recorded in that person's own history file (search_history.json in their profile folder), never in one file shared by all people. Every "Not her" — a deleted crop, or Not her on an uncertain photo or video — goes into that person's not-her list, so no later search copies it again. Every "her" — Yes it's her on a photo, She appears here or Find the face on a video, and every video frame kept of her — goes into that person's her list. The latest decision wins, so a picture is never on both lists. (09-26)
37. Proceed and Train check for approved photos and videos still waiting, and offer to process them first. (09-12, 09-17)

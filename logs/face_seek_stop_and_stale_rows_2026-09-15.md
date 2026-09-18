# Face Seek: Stop that could not be heard, and rows that went stale — 2026-09-15 (evening)

Two faults found by the user while pausing Susana's search, both now fixed in
the app. Everything below was run, not assumed.

## 1. "The STOP button is grayed out and unusable!"

**What happened.** Susana's search was running (started 02:21), but her row in
the Face Tool showed **Updated** with Stop greyed out.

**Why.** The window builds its rows once and only rebuilds them when someone
presses **Refresh**. That row had been drawn at 02:19, before the search
started, so it was showing a state that was two hours out of date. Searches and
training runs are separate programs, so anything they change happens behind the
window's back.

**Fix — `face_tool_ui.py`.** The window now looks at every person's status
every `REFRESH_MS` (3 seconds) and redraws the list only when what it shows has
changed: the badge, the detail line, the number of LoRAs, whether a run is
paused, whether a review is waiting. Redrawing only on a change means nothing
flickers and a scrolled list stays where it was. The check is wrapped so a
profile.json being rewritten mid-read can never kill the timer.

**Tested** in-process (screen locked, no clicks): a throwaway person's row read
`Start` / Stop disabled; another program marked that person as running; 3.2 s
later the same row read `Working` / Stop enabled, with nobody pressing Refresh;
when the run ended it went back to `Start` / Stop disabled 3.2 s later.

**A test of mine that proved nothing.** My first attempt asked "is any Stop
button in the window enabled?" - Susana's row genuinely was, so it passed
instantly and told us nothing. Rewritten to follow one named row.

## 2. "It's not stopping."

**What happened.** The user pressed Stop at 21:00:20. The Face Tool wrote the
stop flag and logged "Stopping 'Susana's seek", but the search kept running and
logged nothing new after 20:56:32.

**Why.** The stop flag was only checked **between** videos. The video it was on,
`Temp as of 2026-09-11\iCloud Photos\IMG_0533.MP4`, is 1.29 GB and **49 minutes
19 seconds** long - about 88,000 frames, every one of them now looked at. The
process was working, not hung (its processor time rose 21 s during a 20 s
watch), but it could not hear the Stop for as long as that video took.

**Fix — `video_frames.py`, `scan_cache.py`, `seek.py`.** The stop is now asked
about inside the video work as well:

- `scan_frames` checks on every frame while reading a video, and again between
  scenes while detecting faces;
- `her_segments` checks on every frame while finding the stretches she is in;
- `pull_her_frames` checks on every frame while writing frames out;
- each returns `stopped: True`, and `scan_video_frames` does **not** mark a
  video done in that case, so a resume reads it again from the start;
- `seek._flush_frames` does not record the video as "frames taken" when the
  pull was stopped halfway.

**Tested** on real videos with a stop raised after a couple of seconds:
scanning a video returned in 2.0 s instead of ~100 s, recording nothing;
finding her stretches returned in 2.2 s; pulling frames stopped in 1.0 s. All
three reported being stopped.

## 3. The running search was ended by hand

The search that was running had loaded this morning's code, which cannot hear a
stop mid-video, so with a Windows restart pending its two processes were ended
at the user's instruction. It had read **2,931 videos**. Everything scanned
before the 49-minute video is remembered in the scan cache; that one video will
be read again.

Killing a process skips the tidy-up a clean stop does, so `seek.active` was
left `true` in profile.json and the row would have said **Working** for ever.
That flag and the stop file were cleared. Susana's profile now reads
**Resume**, first unfinished stage **scan**, no crops yet.

## 4. Also fixed

A stray edit of mine had split the row badge colours into two blocks, which
would have left the **Error** badge without its colour. Repaired.

## 5. Videos kept with their frames, and an uncertain folder (user, 2026-09-15)

"Also remember to pull copies of the actual video if frames are captured; put
them in the video_frames folder... I need the video copies for other projects."
"Then correct the code so that when it creates this folder, the folder is called
video_and_frames." "If the scanner is uncertain... then it copies to the
uncertainty folder." And, when asked about videos it is sure about: "If the scan
is certain that it's not Susana or the anchor photo person then the video does
not get copied at all."

- **`video_and_frames/`** is the new folder name for a person's videos and the
  frames pulled from them (`profiles.video_frames_dir`). A profile made before
  today has `video_frames/` and keeps using it, so nothing already gathered
  moves.
- **The video travels with its frames.** `seek._video_copy` now copies the video
  into the per-video folder beside its frames instead of into `found/`, and the
  copy stays there - the frames are cropped and retired, the video is not.
- **`uncertain/`** is a new folder in every profile. When a video is never
  clearly her but a check was unsure, a copy of the video goes there and the
  per-video folder is cleared. When the scan is certain it is not her, nothing
  is copied at all.
- `her_segments` now counts unsure checks, and Seek's match rule reports
  `(index, unsure)` instead of a bare index, which is what tells the two apart.
- Delete's "copied photos, videos and pulled frames" part covers `uncertain/`.

**Tested** on throwaway profiles: a new person gets `video_and_frames` and
`uncertain` and no old-named folder; an older profile keeps `video_frames`;
after a full search the per-video folder held the video copy plus its manifest
(the 4 surviving frames had been cropped and retired), crops 2 face + 11 body;
a video whose checks were all unsure was copied to `uncertain/` with no frames
pulled and its folder cleared.

**One test failure, and what it was.** Deleting that throwaway person left
`profile.json`, `search_history.json` and `scan_cache/faces.db` behind: the test
script still had the scan database open, and Windows will not move a file in use
to the Recycle Bin, so its folder could not go either. With nothing holding it,
the same folder deleted cleanly. `delete()` reports such paths in "failed" and
the dialog says so; the Face Tool's Delete is greyed out while that person has a
run going, which is the case that would otherwise hit this.

## 6. One review page for everything uncertain (user, 2026-09-15)

"The same app that you open to let me view uncertain photos and tick on whether
they are or are not the person we want, should be the same app that allows me to
view a video and tick on whether it CONTAINS the person we want. and also give
the OPTION to say WHERE in the video that person enters." Asked how a mark should
be used: "(c) the video scan starts at the point that I indicate as opposed to
starting at the beginning... I will indicate the very first frame she is on so
that the scanner can anchor her face and location in the video." One button:
"she appears here. nothing more, Just a way of saving some time." Photos move to
the page too, so the Face Tool's Needs review window goes. Videos answered "not
her": "delete the copy. but record on what ever log already exists for her photo
and video scan that it was indicated as her not being on their, then the
uncertain copy was delete."

Tk cannot play video, so this is the browser page (`review_server.py` +
`review_page.html`); the Face Tool keeps one **Review** button per row, now shown
whenever crops, uncertain photos or uncertain videos are waiting, with a note of
what is waiting (`_waiting_for_review`).

- **Serving pieces of a file.** The page's server sent whole files, so a video
  scrubber had nothing to seek with. `_send_file` now answers Range requests
  (206 + Content-Range, 256 KB at a time).
- **`/unsure/<kind>/<name>`** serves an uncertain video or photo;
  `state()` lists them under `unsure`.
- **`POST /api/unsure`** carries one answer. video + *appears*: the moment
  showing in the player is turned into a frame number using the video's own
  frame rate and written to the search history. video + *not_her*: the copy is
  recycled and both facts recorded. photo + *yes*/*not_her*: the same calls the
  old window made, so answers still teach the judge.
- **The search uses the marks.** `her_segments(..., start_at=)` skips everything
  before the marked frame; `Seek._video_marks()` reads them from the history;
  `Seek._pull_marked_videos()` (first thing in the frames stage) pulls frames
  from videos the search never matched her in but a person marked, then removes
  the uncertain copy, because the video is kept beside its frames.
- **Face Tool:** the Needs review window and button are gone; what remains is
  *Process approved photo(s)*, shown only when photos answered "yes" are waiting.
  The pre-training gate now opens the review page instead of that window.

**Tested.** Server (real HTTP, throwaway profile): a slice request returned
HTTP 206, exactly 100 bytes, `Content-Range: bytes 100-199/17225719`; "she
appears here" at 1.5 s on a 30 fps video recorded frame 45; a photo answered yes
moved to `needs_review/_approved`; a photo answered no was deleted; a video
answered no had its copy deleted; all four events written to the history.
Search side: a mark at frame 1080 pulled 30 frames, 1088..1117, nothing before
the mark, the video copy sat beside them, the uncertain copy was removed, and
`marked_video_pulled` was logged. (My own first test script crashed on its file
names - the app was fine; it was rerun.)

## 7. Not settled

- Looking at every frame makes the scan slower per video; a 49-minute clip is
  a long job. Nothing measured yet on a whole library run.
- The new pull-every-frame and prune behaviour still has not run over the real
  library - the search that was stopped predates it.

## 8. Two more answers, an Undo, and duplicates cleared before review (user, 2026-09-17)

Walking through her review pile the user hit two things: there was no way to
say "yes that is her, but I do not want to use this one", and the same picture
kept coming round. Seven frames of `IMG_0677` in a row, all the same moment.

**Why duplicates reached the page.** The pictures in the review pile are not
crops. They are whole photos and whole video frames the clean stage could not
call, moved aside rather than guessed at. The duplicate check ran over the
finished crops only (`clean/head`, `clean/body`), so it had never once looked at
that pile. The frame pruning had tried and mostly missed: it compares HER face
alone, at the landmarks written during the pull, and she is small and soft in a
group shot. For `IMG_0677`: 369 frames pulled, 340 dropped as blurry, **4** as
duplicates, 25 kept. Whole run: 29,985 pulled, 25,419 blurry, 3,416 duplicates,
1,150 kept.

**Measured, not guessed.** Run over her 99 review pictures, the crop duplicate
check would have removed 31 of them. The pairs it missed - frames a person calls
the same picture - measure 3.8 to 9.0 mean grey levels apart, while the next real
change in the same video measures 13.2 and 20.4.

- **`dedupe.FRAME_DIFF_MAX = 10.0`**, used only when both files are frames of the
  same video (`_video_of` reads `<video>_frameNNNNNN.jpg`). Everything else keeps
  the ordinary 6.0. With it, 41 of the 99 go.
- **`seek._dedupe_review_pile()`** runs at the end of the dedupe stage, over
  `needs_review/`, deleting the copies outright like duplicate crops and writing
  each one into the search history (`duplicate_removed`, `where=needs_review`).

**Two more answers on each photo tile** (user, 2026-09-17):

- **"Yes — but don't use it"**: it is her, and it is not to be used. The decision
  is recorded and NOTHING is learned from it - the user's choice, (b): "only
  record the decision and change nothing about what the app believes". The copy is
  deleted, the user's choice (b) again.
- **"Duplicate"**: the same picture again; recorded and deleted.
- Both write the original's content hash into the new **`not_used`** list in
  `search_history.json`, and Seek's group and search stages now skip anything in
  it (`History.skipped` = not this person OR her but not to be used), so a later
  search does not offer the same picture again.

**No confirmation, but an Undo** (user, 2026-09-17: "I do not want a
confirmation button, but I do want an undo button"). An answer is written to the
log the moment it is clicked, but what it DOES waits: the file moves to
`needs_review/_undo/<ref>/` and the effect - deleting, moving a kept photo to
`_approved`, teaching the judge - only happens when the answer is `UNDO_DEPTH`
(10) answers old, or when Proceed starts training, or when the page closes.
`_undo/pending.json` survives a crash, and the next review carries those answers
out before it shows anything. Undo puts the file back and marks the entry in the
history `undone`, with a `review_answer_undone` note beside it. After a click the
line next to Undo says what was recorded - the user's choice, (b).

**Tested.** A throwaway person with four review pictures, against a real running
server: "Yes — but don't use it" took the picture off the page, wrote `her, not
used` to the log, left the file undeleted and `not_used` still empty; Undo
brought the picture and the file back and marked the answer taken back; a
duplicate and an ordinary yes were answered, the server was **killed** with both
still waiting, `pending.json` held them, and the next server carried them out
before showing anything - the duplicate recorded in `not_used`, the kept photo in
`_approved`, nothing left in `_undo`. Then in Chrome on the real page: all four
buttons drawn on each tile, a click showed "Recorded — … her, but not used -
recorded only, nothing learned from it" with `Undo (1)`, and Undo brought the
tile back with "Taken back — …".

One fault of mine on the way: `History.log(kind, **kv)` was handed `kind=` as a
field name too, which is a TypeError, and the first Undo returned HTTP 400. The
field is `about` now.

## 9. The review page from another device, over Tailscale (user, 2026-09-17)

"I can't see it remotely. Send it through my Tailscale." The page is deliberately
bound to `127.0.0.1`, so nothing off the machine can reach it. Two ways to change
that were put to the user: let Tailscale forward to it, or add a `--host` option
so the app itself answers on the Tailscale address. The user chose the first -
no change to the app, and the pictures still never leave the computer; Tailscale
carries them between the user's own devices.

    tailscale serve --bg --http=8080 http://127.0.0.1:50086
    # off again: tailscale serve --http=8080 off

**Address: `http://<TAILSCALE_HOST>:8080/`** - the name, not the IP.
The forwarding is tied to the machine name, so `http://<TAILSCALE_IP>:8080/`
answers 404 unless the Host header carries the name. Plain http, not https:
`CertDomains` is empty on this tailnet, so `--https=443` had nothing to serve
with and hung. Tested from outside the loopback: page 200, state showed Susana
with 58 photos and 2 videos, a photo 200 at 529 KB, a video slice **206**, so
scrubbing works.

**A fixed port** (`DEFAULT_PORT = 50086`), because the forwarding points at one
port and the page used to take a random one on every start, which broke the link.
If the port is taken, any free port is used and the log says so.

**A fault this found.** `ThreadingHTTPServer` sets `allow_reuse_address`, and
Windows will then hand the SAME port to a second server: with the fixed port in
place, a review page for a second person bound 50086 as well, and requests would
have been split between the two at random. `_Server.allow_reuse_address = False`
refuses that, which is also what makes the fallback happen at all. Tested: with
Susana's page on 50086, a second person's page logged "port 50086 is taken
([WinError 10048] ...) - using any free port instead" and came up on 59130.

Also of note for testing on Windows: a PowerShell process filter like
`CommandLine -like '*review_server*susana*'` matches the shell running the filter,
so the kill killed itself - exit 255, no output. Filter on `Name -like 'python*'`
as well.

## 10. The review page says what each part is and what to do (user, 2026-09-17)

"I don't see a section title, section description, section instructions." True:
there were three bare headings and one clump of legend text at the very top of
the page, nowhere near the pictures it described, and the two crop sections had
no instructions at all.

The page is now four numbered sections, each with the same three parts - a
title with a count, a line saying what these pictures are and where they came
from, and a blue-edged block saying what to do and what every button does:

1. **Videos the search could not call** - play it, mark where she appears, or
   Not her.
2. **Photos the search could not call** - the four answers, and the note that
   nothing asks you to confirm because Undo is there.
3. **Face crops** - what they are, tick the wrong ones, Delete ticked and the
   rotate buttons, what the yellow frame and the blue outline mean.
4. **Body crops** - the same, and why a wider cut is trained on at all.

The uncertain videos and photos used to share one heading; they ask different
things and have different buttons, so they are two sections now. The top of the
page keeps only the person's name, the counts and the toolbar. A closing line
says Proceed to training uses whatever crops are left in sections 3 and 4.

An empty section keeps its heading, shows `(0)` and "Nothing waiting here", and
drops only its instructions - a section that vanished when you finished it read
as broken rather than done. (First cut hid the whole section; caught in the
browser and fixed.)

Checked in Chrome on the live page: the headings, descriptions and instruction
blocks render, section 2 reads "2 - Photos the search could not call (0)" with
"Nothing waiting here" under it, and the crop sections show their counts.

### 10a. An answered video now leaves the list (user, 2026-09-17)

"I actually approved those videos twice. They should have been moved out like
the photos." Correct: a photo leaves the page the moment it is answered, but a
marked video sat there looking untouched, so it was marked again - her history
shows `IMG_3768.MOV` marked four times and `IMG_3763.MOV` three times, and each
mark replaced the one before it. The 1.63 s mark on IMG_3768 was overwritten by
a later press at 0.00 s.

The copy cannot simply be deleted - `Seek._pull_marked_videos` reads the video
out of `uncertain/` on the next search. So `Review._marked_videos` reads her
history and `_unsure_items` leaves out any video with a standing "she appears
here"; an Undo marks that answer `undone` and the video comes back. The tile now
also greys out and the list refreshes on the spot, as a photo's does. The
section's instructions say the video leaves the list, that its copy is kept, and
to mark it once.

**Tested** on a throwaway person with two real videos: two waiting, one marked at
1.5 s -> it left the list, the other stayed, the copy was still on disk, exactly
ONE mark was written, and the frame came from the video's own frame rate (44 at
29.399 fps, not 45). Undo brought it back and marked the answer taken back. Seek's
own `_video_marks` still read the mark afterwards.

## 11. Training cannot start while approved work is still waiting (user, 2026-09-17)

"The Proceed to training button needs to check the holding folder. If there is
stuff in the holding folder it needs to not proceed and instead inform me that
the photos and videos that I approved as her still need to be processed. Then
I'm offered to Process approved photo(s) and videos or cancel." Asked whether
"videos" meant a note or the actual work, the user chose the work: nothing
approved is left out of the training set.

- **`seek.approved_waiting(prof)`** -> `{"photos": n, "videos": [names]}`: photos
  answered "Yes, it's her" sitting in `needs_review/_approved`, and videos
  answered "She appears here" whose copy is still in `uncertain/`, meaning her
  frames have not been pulled out of them yet.
- **`Review.proceed()`** returns `{"needs_finishing": ...}` instead of starting,
  and the page's confirm panel becomes the block: it names what is waiting and
  offers **Process approved photo(s) and videos** or **Cancel**.
- **`seek.finish_approved(prof)`** does the work through the paths a search
  uses - `process_one` for each approved photo, then `Seek._pull_marked_videos`,
  `prune_her_frames` and `process_one` for each surviving frame. It runs in a
  thread on the server; the page polls and shows the line it is on, then reloads
  so the new crops appear before you press Proceed again.
- The Face Tool keeps its own **Process approved photo(s)** button, unchanged.

**A hole this found, and closed.** The test marked a video the search had never
matched her in - which is exactly why it was uncertain - and the pull found
nothing of her at the marked moment. Nothing was pulled, the copy stayed in
`uncertain/`, and Proceed went on refusing: a video that could never be finished,
blocking training for ever. Now a mark that has been tried and found nothing is
written down as `marked_video_no_match`, which stops the mark standing:
`seek.standing_marks` is the one place that decides, so the video stops blocking
Proceed AND comes back onto the review page carrying a note - "you marked frame
N, but no face in this video looked like her - nothing was pulled. Mark another
moment, or say Not her."

**Tested** end to end on a throwaway person with 3 real photos of her waiting as
approved and one real video marked: the page reported 3 photos and 1 video
waiting; Proceed refused and named them; the button cut 3/3 photos into 2 face
and 5 body crops; the video found nothing of her and came back on the page with
its note; nothing was left waiting; and Proceed then started the run. (It really
did start a training run on the throwaway person - it was stopped at once, the
person deleted, and the LoRA registry checked: no trace.)

## 12. Yellow crops: say what they are on the screen, blur the others out, or keep them out of training (user, 2026-09-17)

"A similar description, but more concise, needs to be on the screen - available
options and option descriptions. B or delete with the same parameters as the
DELETE button." And then: "The third existing option should be available: it's
her but do not use."

- **On the screen.** The Face crops section now carries a short block of its own:
  what a yellow frame means (the app finds every face, works out which is hers,
  and shrinks the edges to push the others out without cutting into her face;
  yellow means that failed), and the three ways to deal with one, each with what
  it does.
- **Blur other faces** (new, `POST /api/blur_others`). Every face that is not
  hers is blurred away where it stands and the crop is kept. Blur, not a black
  box: a hard rectangle is a shape the training would learn. It is blurred
  through a soft oval for the same reason.
- **"Yes - but don't use it"** on crops (new, `POST /api/not_used`), the same
  meaning it has on a photo: the crop goes to the Recycle Bin, the original is
  written into `not_used`, the judge is told nothing, and the photo is NOT
  marked as somebody else.

**Measured, not assumed.** Blurring the face box with the cropper's own 10%
clearance was not enough - on `body/IMG_0118.jpg` the detector still found the
child at 0.72 afterwards, because a face runs past the box drawn round it. The
blur now widens until nobody is found: 10%, then 35%, then 60% of the face box,
checking with the detector between each. At 60% that crop came back clean, and
the picture shows a soft smudge with Susana untouched.

**Tested** on a throwaway person holding copies of three of her real yellow
crops: blurring cleared the flag and the detector found nobody left; the file was
rewritten and the event logged; "Yes - but don't use it" deleted the crop, wrote
one `not_used` row naming the original, and left `not_person` empty.

### 12a. A filter for the yellow framed crops (user, 2026-09-17)

"New button: filter yellow framed photos."

**Filter: yellow framed only** hides every crop that has nobody else in it, so
the crowded ones can be worked through on their own. Pressing it again shows
everything. While it is on:

- the section headings read `(2 of 470, yellow framed)` and the counts line says
  "showing the yellow framed ones only";
- **Tick all** ticks only what is shown, and switching the filter clears the
  ticks. Nothing can be deleted, blurred or recorded on a crop that is not on the
  screen - which is the trap a filter would otherwise set.

Tested in Chrome on the live page: with 2 yellow crops left of 752, the filter
showed exactly those two, the headings read "(0 of 282)" and "(2 of 470)", the
counts line carried the note, and turning it off brought all 752 back.
(The extension's own clicks did not reach the button; the page was driven
through its own click handler instead, which is the same path a real click takes.)

## 13. Working through near-duplicate frames by hand, in groups (user, 2026-09-17)

"There are way too many similar frames from videos. I'm OK with that outcome on
the search side. But at this stage, perhaps I can manually remove near
duplicates... the scanner will group all the near duplicates and tick them AND
colour frame them but untick the cleanest sharpest one... this is an art more
than a science so the scanner needs a slider with notches, because I hate
decimal/fractional notches." And: all groups at once, divided by a divider; a
group leaves the queue once it has been dealt with, which may take several
passes at different slider settings.

- **`Find near duplicates`**, one in each crops section, runs the app's own
  duplicate checker over that section at the slider's setting
  (`POST /api/duplicate_scan`). It never deletes: it reports groups.
- **The slider** is whole notches only, 4 to 18, default 8 - the mean grey-level
  difference between two crops shrunk to 96x96. Left is tighter, right looser.
- **The groups** are shown one under another, each divided by a green line and
  headed "Group 3 of 43 - 4 pictures - the best one is unticked", with a **Keep
  all of these** button. Every picture is green-framed; every one is ticked
  except the best - most pixels, then sharpest - which is marked **BEST - kept**.
- **Acting on them uses the buttons that already exist**: "Yes - but don't use
  it" or "Delete ticked".
- **The queue.** A group leaves when it is acted on or kept in full, and that is
  written into the existing search history as `duplicate_group_settled` with its
  members, what happened and which copy was kept. A later scan, at any setting,
  does not offer a settled group again.

**A fault found in the first cut, and fixed.** `find_duplicates` groups by
chaining - A matches B, B matches C, so all three are one picture. That is right
for clearing copies after a search, but at notch 12 one group swallowed **161**
of Susana's crops, when the user asked for three to five at a time. The review
scan now uses **`dedupe.groups_around_best`**: the best picture of what is left
takes the group and only pictures matching THAT picture join it; the next best
starts the next group. Measured on her 282 face crops: notch 8 gives 43 groups,
biggest 3; notch 10 gives 59 groups, biggest 8; notch 12 gives 58, biggest 14.
The chaining version is untouched and still used by the search.

**Tested** on a throwaway person holding 60 of her real crops: a looser notch
groups more than a tighter one, a group names its best copy, settling a group
takes it off the queue and writes one row into the history, and "Yes - but don't
use it" on the ticked members left exactly the best one behind. Then in Chrome on
the live page at notch 8: 43 groups of 2 and 3, 47 ticked, green frames and one
"BEST - kept" per group, "Keep all of these" dropped it to 42 and a rescan did
not bring it back, and Reset filters returned all 282 crops with nothing ticked.

### 13a. A time cap, built and then taken out (user, 2026-09-17)

Talking through why he wanted groups of three or four, the user said a group
should be one moment - "how long does a human hold an expression, I would think
LESS than two seconds". I took that as a specification and built it: a cap that
kept two frames of one video out of the same group when they sat more than 1.5 s
apart, with the frame rate read from the manifests and from this person's own
search logs.

That was over-reading an aside. "I do not need to know this at all. I was being
anecdotal about how I think the scanner should work. Only the photo scanner
should be active and it's just comparing the frames AS PHOTOS."

All of it is reverted - `MOMENT_S`, `fps_table`, `_same_moment`, `max_gap_for`,
the `fps` field in the manifest - and the frame-rate cache written into her
profile.json was removed. The review scan groups crops on how alike the pictures
are and nothing else, which is what `groups_around_best` did before.

What stands from the conversation, because it was measured and not assumed: 95%
of her face crops are video frames, and at notch 8 every group was already made
of frames from a single video - looking alike, on these crops, already means
came from one clip.

### 13b. A press in one group acted on the whole queue (user, 2026-09-17)

"In group 1, I changed the selection, then clicked 'yes but do not use'. It
worked and it removed the two frames from the screen, but then it took me out of
the group queue and back into the main review screen."

**Why.** The ticks belong to the whole page, and a scan ticks every group at
once. The toolbar's buttons act on everything ticked, so a press meant for group
1 dealt with EVERY group in the queue; each one was then settled and the queue
emptied. Reproduced on a throwaway copy: two groups, one press, both gone.

**Fix.** Each group now carries its own **Yes - but don't use it** and **Delete
ticked** beside its heading, next to Keep all of these. They act on the ticked
pictures of that group and nothing else, then settle that group and leave the
rest of the queue standing. While any section is showing groups, the toolbar's
Delete / Yes-but-don't-use / Blur stand down, and the counts line says so -
those buttons cannot tell one group from another.

**Tested** in Chrome on a throwaway person with 140 of her crops: with 2 groups
queued, group 1's own button removed exactly its one ticked picture (140 -> 139
crops), settled that group and left the queue showing the next one, still in
group view. "Keep all of these" then cleared the last group with nothing
deleted, and Reset filters brought back all 139 crops with the toolbar working
again.

### 13c. Undoing the mass action that bug caused (user, 2026-09-17)

The one press at 18:45 removed **45 face crops** and settled **41 groups**. All of
it has been put back:

- The 45 pictures and their 45 caption files were restored from the Recycle Bin
  (Shell.Application, matched on their own names and their original folder,
  `clean\head`). The folder is back to 282 pictures and 282 captions.
- Their crop records were written back into `search_history.json`, their 45
  "her, but not used" rows removed, and each of the 45 events marked `undone`
  rather than erased, so the record still shows what happened and that it was
  taken back.
- The 42 `duplicate_group_settled` events - the 41 from the bad press and one
  from my own testing on her page at 18:07 - are marked `undone`, and
  `Review._settled_groups` now ignores a settled group that has been undone. A
  scan at notch 8 offers 43 groups again, as it did before.
- Everything the user did deliberately before 18:45 - the 50 crops deleted
  between 14:39 and 14:45, and the 48 "her, but not used" answers between 15:25
  and 16:22 - was left exactly as it was.

`review_bulk_undone` in her search history records the repair.

## 14. The review scanner now compares HER FACE, not the whole picture (user, 2026-09-17)

"The duplicate scan in the review is grouping frames that are visually not the
same." It was, and here is why, measured on her own crops.

**The fault.** The review scanner used the finished-crop duplicate check: shrink
each whole picture to 96x96 grey, average the difference. Every dot counts the
same. On a body crop her face is **1.5-2.2%** of the picture, so the wall, her
clothes and the floor decide the answer. Two real pairs it grouped at notch 8:

    frame000069 vs frame000070 : whole picture 6.46 · her face alone 11.74
    frame000013 vs frame000014 : whole picture 6.16 · her face alone 11.19

The scene had not changed; she had. On a face crop, where her face is ~19% of
the picture, the two measures agree much better - which is why this showed up in
the body crops first.

**A guess of mine, corrected by measurement.** I expected her face in a body crop
to be ~40 pixels across and too soft for the pruning test. It is **90-264 pixels**
across, and the aligned copies came out at median 468 on the focus measure
(lowest 233) against the 200 the pruning step asks for. A body crop is tall, so a
small share is still a usable face. The split - one test for face crops, another
for body crops - was therefore not needed, and the user chose one test for both.

**What it does now** (`face_groups.py`, new): find her face in the crop, align it
onto a standard 112px square with insightface's `norm_crop`, read her head angle
from the five landmarks, and compare the aligned face, its eyes band and its
mouth band separately - the frame-pruning test, applied to crops. Nothing is
written to any picture; the aligned face lives in memory for the comparison.
Groups are built round the best VIEW OF HER FACE now (widest, then sharpest),
not the biggest picture.

**The slider** is 1 to 10 whole notches, 4 being the pruning step's own settings
(look 0.90, yaw/pitch 0.08, roll 5 degrees). Lower is stricter, higher looser,
all four numbers moving together, and the page prints what the notch means.

**The cost, and how it is paid once.** Finding her face costs ~0.47s a crop. The
first scan of a section measures them in the background while the page shows
"Finding her face in each crop - 152 of 279"; the landmarks go into
`clean/_face_points.json` keyed by each file's size and date, so a rotated or
blurred crop is measured again and nothing else is. Later scans take 0.1s.

**Tested** on a throwaway person with 40 face and 40 body crops of hers: the
first scan measured 40 crops in 19s and later scans took 0.1s; her face was found
in all 80; notch 1 gave 2 tight groups, notch 4 gave 11 (biggest 7), notch 7 gave
6 (biggest 13), notch 10 gave 3 (biggest 27); body crops behaved the same way.
Then on her real page: 279 face crops measured in about 2 minutes, and a scan at
notch 4 returned **54 groups**, sizes 2 to 8.

The whole-picture check is untouched and still does its own job - identical files
and re-cuts - at the end of a search.

### 14a. The queue lets go when it is finished, and says what you have done (user, 2026-09-17)

"The groups are done. The non-Susana is in the review queue" - but the toolbar's
Delete and Yes-but-don't-use were still greyed out, because the page was still in
group view with an empty queue, and the toolbar stands down while groups are
showing. "Plus can you make my group work saved. I cannot tell if the photos from
the video are the remaining or a reset."

- **An empty queue is left automatically.** When the last group of a section has
  been dealt with, the page drops out of group view, shows every crop again,
  hides Reset filters and says so. The toolbar comes back with it.
- **The work done is on the screen.** `state.settled` counts the groups settled
  in each section, and the scan bar reads "58 group(s) dealt with so far - those
  are saved and will not be offered again."
- While groups ARE showing, the heading now reads "(12 group(s) left to look at,
  of 172 crops)" rather than a bare count.

The work was never lost: her history had 58 settled groups - 56 acted on, 2 kept
in full - and 110 crops removed between 19:00 and 21:42, face crops 279 -> 172.
The page simply never showed it.

**Checked in Chrome on her live page:** the scan bar reads "58 group(s) dealt
with so far", the toolbar starts greyed with nothing ticked, and ticking one crop
enables Delete, Yes-but-don't-use and Blur.

### 14b. A progress bar for the two long jobs (user, 2026-09-17)

"I got that notice that said the approved photos and videos need to be processed
... we need a progress bar. I know it can be calculated based on the file size,
frames, process speed."

Both long jobs now report where they are, and one bar under the toolbar draws
either of them:

- **Processing what you approved.** `seek.finish_approved` takes an `on_step`
  callback and calls it before and after every approved photo, before each marked
  video (`Seek._on_video`, read inside `_pull_marked_videos`), and for each frame
  being cut afterwards. The server turns that into `{phase, at, of, now, eta}`.
- **Finding her face in each crop**, which already counted, uses the same bar.

**The time left** is worked out the only honest way available: how long the ones
done so far took, spread over the ones left. Nothing pretends to know what is
inside a video before reading it.

**Tested** on a throwaway person with 10 approved photos of hers: the bar was fed
`photos 0/10`, then 1/10 with 27s left, 2/10 with 17s, and so on down to 9/10
with 1s, then finished - a smooth count with a settling estimate, not a jump from
nothing to done.

Also fixed while looking: the page polled the state every 3 seconds during the
work; it polls every second now, so the bar moves.

### 14c. A progress bar for the training run itself (user, 2026-09-17)

Asked whether the bar should cover training too: "a". It reads the log the run is
writing - the pipeline prints `[1/4] training susana_head_sdxl` for each LoRA of
the set, and OneTrainer prints `epoch: 35%|...| 7/20 [1:00:00<1:50:00]` as it
goes. `review_server.training_progress` reads the last 16 KB of that log and
returns which LoRA, which epoch, the time tqdm itself says is left on the current
one, and one percentage for the bar: whole LoRAs finished plus how far through
the current one. The page draws it in the same bar the other two jobs use.

**And a fault it exposed.** The bar was written while a run was already going,
and the review page holds the run in memory - so restarting the little server to
pick up the new code would have left the page blind to a run that carries on
regardless (it is its own program). `Review._recover_training` now picks up a run
that was already going: the pipeline lock names the process, the newest
`train_<slug>_*.log` is the file it is writing, and `_watch_pid` waits for that
process the way `_watch_training` waits for one this page started. The ending is
recorded by one shared `_record_training_end` either way.

**Checked on the live run** (started 22:30:53, 4 LoRAs of 20 epochs each): after
restarting the page it picked the run straight back up - "recovered: True, pid
10972" - and the bar reads "Training — LoRA 1 of 4 — susana_head_sdxl · epoch 0
of 20".

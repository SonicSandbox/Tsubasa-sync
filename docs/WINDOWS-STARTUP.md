# Why the first launch is slow, and what to do about it

Short version: **Windows Defender scans every file tsubasa ships, every time the
app starts cold.** The app is 1,274 files and 43 DLLs, and it is unsigned, so
Defender has no reason to trust it and reads all of it. That is roughly **3
seconds of the startup you are waiting on**, and it is the operating system
reading bytes — nothing inside the app can make it go faster.

Measured on a cold start of the standalone build:

| | |
| --- | --- |
| Time until the window appears | **1.7 – 4.2 s** |
| Of which the app actually spends working | **0.8 – 1.1 s** |
| The rest | waiting on the disk and the scanner |

Once Windows has the files in its cache, later launches are much quicker. The
slow one is the first launch after a reboot, or after you move or re-extract the
folder.

> The app's own share of that time **was** larger, and got fixed: it used to
> import the whole numeric stack just to draw a window. That is gone as of
> 0.1.5 — 245 ms and 10.5 MB of memory, for arithmetic the window never does.

---

## The fix: exclude the tsubasa folder from Defender

This tells Defender to stop scanning the folder you extracted tsubasa into.

**Read this before you do it.** An exclusion is a real hole in your real-time
protection, so:

- Exclude **only the folder the app lives in** — the one with `tsubasa.exe` in it.
- **Never exclude `Downloads`, `Desktop`, `Documents`, or a whole drive.** Those
  are exactly where something unwanted arrives.
- Do it **after** you have extracted the zip and are happy with it, not before.
- If you later delete tsubasa, remove the exclusion too.

If you would rather not, that is a completely reasonable choice. The app works
fine without it; it just starts slower.

### The clicking way

1. Press **Start**, type **Windows Security**, open it.
2. **Virus & threat protection**.
3. Under *Virus & threat protection settings*, click **Manage settings**.
4. Scroll to *Exclusions* → **Add or remove exclusions**.
5. **Add an exclusion** → **Folder**.
6. Pick the folder that contains `tsubasa.exe` — for example
   `C:\Tools\tsubasa\` — and confirm.

You will be asked for an administrator prompt. That is expected.

### The one-line way

Open PowerShell **as Administrator** (Start → type `powershell` → right-click →
*Run as administrator*) and run this, with your own path:

```powershell
Add-MpPreference -ExclusionPath "C:\Tools\tsubasa"
```

To check what is currently excluded:

```powershell
(Get-MpPreference).ExclusionPath
```

To undo it later:

```powershell
Remove-MpPreference -ExclusionPath "C:\Tools\tsubasa"
```

### If your machine is managed by an employer

You will probably get *"This setting is managed by your administrator."* Nothing
is wrong; the policy is set centrally and you cannot change it locally. Ask
whoever runs it, or just live with the slower first launch.

---

## Why the app is unsigned

A code-signing certificate costs money every year and is issued to a legal
entity. tsubasa is a free GPL-3.0 project, so it does not have one. That is why:

- **SmartScreen warns you the first time.** *More info* → *Run anyway*.
- Defender scans everything the app ships on every cold start.
- Your antivirus may quarantine the download outright.

If that is not acceptable for your environment, `pip install tsubasa-sync` is the
other route — it needs Python 3.8+, and it installs the same code from PyPI.

---

## If Defender removed the download

**It did not delete it.** Defender *quarantines* — the file is set aside where
it cannot run, and it can be put back. Most people read *"threat removed"* as
*"gone"* and go looking for another download; there is no need.

The usual verdict is **`Trojan:Win32/Wacatac.B!ml`**. The `!ml` on the end means
it came from a machine-learning model rather than from a match against a known
piece of malware — in other words, it is a guess about shape, and here it is
wrong. What it recognises is **PyInstaller's launcher**, the small stub that
unpacks the app and starts Python. Every application packaged this way carries
the same stub, malware authors use the same packager, and unsigned builds have
no signature to weigh against it. None of it is specific to tsubasa.

> ⚠ **Only restore a file you are confident about.** You downloaded this from
> the releases page and the checksum is published below — check it after you
> restore, and you have verified the bytes yourself rather than taking anyone's
> word for it.

### The clicking way

1. Press **Start**, type **Windows Security**, open it.
2. **Virus & threat protection**.
3. Under *Current threats*, click **Protection history**.
4. Find the entry for `tsubasa-windows-x64.zip` or `tsubasa-gui.exe`.
5. Open it, then **Actions** → **Restore**.

### The one-line way

Open PowerShell **as Administrator**, then list what is quarantined:

```powershell
& "C:\Program Files\Windows Defender\MpCmdRun.exe" -Restore -ListAll
```

and restore by the threat name it reports:

```powershell
& "C:\Program Files\Windows Defender\MpCmdRun.exe" -Restore -Name "Trojan:Win32/Wacatac.B!ml"
```

`-FilePath` restores one specific file instead, and `-Path` puts it somewhere
other than where it came from.

### Then stop it happening again

Restoring a file does not stop the next scan taking it back. Add the folder you
extracted tsubasa into as an exclusion — the section at the top of this page
covers how, and what the trade-off is.

### Or skip the whole thing

```bash
pip install "tsubasa-sync[gui]"
tsubasa-gui
```

Same application, from PyPI. It needs Python 3.8+, it starts faster, and
nothing about it trips this.

---

## Verify what you downloaded

Every release publishes a `SHA256SUMS` file next to the zip. Before you extract:

```powershell
Get-FileHash .\tsubasa-windows-x64.zip -Algorithm SHA256
```

Compare that to the line in `SHA256SUMS`. If it does not match, do not
extract it — download it again from the
[releases page](https://github.com/SonicSandbox/Tsubasa-sync/releases).

---

## Still slow after all that?

Two other things are worth checking, in this order:

1. **Extract it to a local disk.** Running from a network share, a USB stick, or
   a synced folder (OneDrive, Dropbox) means every file is fetched over that
   link at startup.
2. **Check your other security software.** A third-party antivirus does its own
   scanning, and its exclusion list is separate from Defender's.

If it is still slow, open an issue with the output of `tsubasa --version` — it
prints where it loaded its data from, which is usually the tell.

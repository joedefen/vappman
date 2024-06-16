# vappman
`vappman` presents a visual (curses) interface to `appman`.

* Install `vappman` using `pipx install vappman`, or however you do so.
* Prerequisites: install [ivan-hc/AppMan: AppImage package manager to install, update (for real) and manage ALL of them locally thanks to "AM", the ever-growing AUR-inspired database listing (for now) 1900+ portable apps and programs for GNU/Linux. Manage your AppImages with the ease of APT and the power of PacMan.](https://github.com/ivan-hc/AppMan) and all of its prerequisites.

NOTE: `vappman` covers many capabilities of appman:
* implicitly, (-f) files (or show installed), (-l) list available apps,
  and (-q) search the app list
* (-i) installing uninstalled apps
* (-r) removing installed apps
* (-b) backup / (-o) overwrite of installed apps
* (-a) about (i.e., more info) for all apps
* (-c) clean to remove unneeded files and directories
* (-u) update installed apps; and `vappman` uses "U" for update
       all installed apps

But it does NOT cover:
* (-d) download install script
* (-h) help or full help for appman
* (-H) home or set $HOME directory for apps
* (-t) template for custom install template
* (-v) version of appman
* --force-latest to get the most recent stable release AND
  all other options and unmentioned commands.

## Usage
* Run `vappman` from the command line.
* It presents some keys available on the top line.
    * Use '?' to learn the navigation keys (e.g., you can use the mouse wheel,
      arrow keys, and many `vi`-like keys)
* Then `vappman` presents a list of installed apps, followed by available/uninstalled apps.
* Enter `/` to enter a "filter" for installed/uninstalled apps, if you wish.
    * If you enter plain old "words", then those words must match the beginning of words
      of the apps or descriptions (in order, but not contiguously).
    * Or you can enter an regular expression acceptable to python (e.g., `\b` means word
      boundary, etc.)
* Use `i` to install apps, and `r` to remove apps.  When you install or remove an app, `appman` drops out of `curses` mode, runs the `appman` command so you can see the result, and then prompts your to hit ENTER to return to `vappman.

## Example Screenshot
![vappman-with-filter](https://github.com/joedefen/vappman/blob/main/images/vappman-with-filter.png?raw=true).

---

NOTES: in this example:
* the filter is `card` so it shows apps with words starting with `card`.
* the current position is on `glabels`; thus if `i` is typed, `appman install glabels` is run.
* if the horizontal line (second line show) has no decorations, then you are looking
  all the filtered apps; otherwise, the decoration suggests where you are in the
  partial view of the filtered apps.


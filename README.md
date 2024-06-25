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
    * '?' also elaborates the meaning of the available keys for operations.
    * NOTE: `ENTER` acts differently based on context:
      * In help, it returns to the main menu.
      * On an uninstalled app, it installs it.
      * On an installed app, it uninstalls it.
* Then `vappman` presents a list of installed apps, followed by available/uninstalled apps.
    * Installed apps have prefix '✔✔✔' (i.e., three checks).
    * Uninstalled apps have prefix '◆' (i.e., a solid diamond).
* Enter `/` to enter a "filter" for installed/uninstalled apps, if you wish.
    * If you enter plain ole "words", then those words must match:
      * the start of words on the apps line (in order, but not contiguously) and/or
      * the start of the remainder of the previous word match
        (i.e., `/bit fight` matches `bitfighter`).
    * Or you can enter an regular expression acceptable to python; e.g.,
      * `^` matches the line starting with the app name
      * `\b` matches a word boundary; and so forth.
    * NOTES:
      * `ESC` clears the filter and jumps to the top of the listing.
      * Each time the filter is changed, the position jumps to the top of the listing.
* Use `i` to install apps, and `r` to remove apps.  When you install or remove an app, `appman` drops out of `curses` mode, runs the `appman` command so you can see the result, and then prompts your to hit ENTER to return to `vappman.
* Use `t` to "test" an installed app.  This launches a terminal emulator and then the app so you can see issues. This is not for daily use obviously, but for after install or when having unknown issues and you wish to start the investigation.

## Example Screenshot (of v0.7 ... current release will vary slightly)
![vappman-with-filter](https://github.com/joedefen/vappman/blob/main/images/vappman-with-filter.png?raw=true).

---

NOTES: in this example:
* the filter is `card` so it shows app lines with words starting with `card`.
* the reverse video, current position is on `glabels`;
  thus if `i` (or ENTER) is typed, `appman install glabels` is run.
* if the horizontal line (second line show) has no decorations, then you are looking
  all the filtered apps; otherwise, the decoration suggests where you are in the
  partial view of the filtered apps.
* the matching installed app has the '✔✔✔' prefix.
* the fixed top line shows some of the available action keys (e.g., `q` quits the app)
* use `?` to open the help screen describing all keys (including navigation)

## Screen Recording (Intro to vappman based on v0.7)
[![Screen Recording](https://i9.ytimg.com/vi_webp/NUHYN9_DZtA/mq3.webp?sqp=CMTu4LMG-oaymwEmCMACELQB8quKqQMa8AEB-AHqBYAC4AOKAgwIABABGEogZShRMA8=&rs=AOn4CLBaBrOpAhJkRIQQNNdCzYaqpOYl-Q)](https://youtu.be/NUHYN9_DZtA)

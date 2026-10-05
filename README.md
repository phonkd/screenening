# screenening

Only for my very specific Hyprland setup: one laptop, two dock screens,
workspaces **qwe asd uio**. Not a general-purpose display manager.

Why: I plug my laptop into docking stations and have to assign workspaces and sometimes swap the left and right screens. That's cumbersome; this makes it a tiny bit less cumbersome.

```sh
nix run github:phonkd/screenening
```

Applies the current left-to-right order, then asks whether to swap:

- **qwe**: laptop, centered below the externals
- **asd**: left external
- **uio**: right external
- Undocked: all nine on the laptop

Uses `highrr`, preserves scale/rotation, and saves Monique profiles.
My existing `moniqued` service restores them on dock/undock.
Requires Hyprland and unique display descriptions; Nix supplies the tools.
Positions use current display sizes; rerun if `highrr` changes resolution.
Esc keeps the applied layout; there is no timed rollback.

```sh
nix run . -- --dry-run  # preview only
nix run . -- --yes     # apply without the swap question
nix flake check       # package and layout tests
```

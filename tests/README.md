# tests

    python3 -m unittest discover -s tests

(stdlib only; same runner as quilt-engine.)

Fixtures under `fixtures/` are frozen captures of real quilt-engine
demo runs — see each fixture's README for the engine commit, the exact
commands used, and the hand-computed facts the tests assert. Do not
regenerate them: a fresh run gets new ticks and transmission ids, and
the hand-computed expectations would silently stop being about the
files in the repo.

# pdf-seal

Seal a PDF with buyer details **without breaking the links from its table of
contents, its web links or its bookmarks**.

## Why

Ordinary stamping tools push the file through a rendering library that rebuilds it
page by page. That drops annotations and the outline tree, so links from the table
of contents, web links and bookmarks all disappear. For an e-book with a clickable
table of contents, what is delivered to the customer is several hundred pages they
can only scroll through. That is what prompted this tool: a real customer wrote in
to ask why clicking a chapter did nothing.

The fix is to never rebuild the document. This tool assembles a one-page PDF
carrying nothing but the seal text and lays it over every page with
`qpdf --overlay`, which merges page content streams and leaves annotations and the
outline alone.

Measured on a 750-page e-book: 151 links, 139 in-document jumps and 78 bookmarks
all survived, and a rendered page came out byte-for-byte identical to the original.

## What the seal looks like

By default, **nothing**. The text is written in text rendering mode `3 Tr`, which
the PDF specification defines as invisible: nothing shows on screen or in print,
but the text is in the file and can be read back.

```
pdftotext -f 1 -l 1 sealed/jane@example.com.pdf - | grep '@'
```

So this is a **forensic marker, not a deterrent** — someone who does not know the
seal is there will not be discouraged from sharing the file. Pass `--visible` to add
a small grey footer line, which does discourage it.

The seal goes on **every** page, so even a single photographed or cropped page
carries it.

## Install

Nothing to install. Needs Python 3.9+ and `qpdf` on PATH:

```bash
sudo apt install qpdf      # Debian, Ubuntu
brew install qpdf          # macOS
sudo pacman -S qpdf        # Arch
```

`poppler-utils` (`pdfinfo`, `pdftotext`) is optional; without it the page size is
read straight out of the PDF, just a little slower.

## Use

One file:

```bash
./seal.py book.pdf --text "Jane Doe | jane@example.com | order 71"
```

A batch, one sealed file per CSV row:

```bash
./seal.py book.pdf --csv buyers.csv \
  --template "{name} | {email} | order {order}" \
  --outdir sealed
```

```csv
name,email,order
Jane Doe,jane@example.com,71
Šárka Melicharová,sarka@example.com,42
```

Any CSV column can be used in `--template` and in `--filename`.

Check that nothing was lost on the way:

```bash
./seal.py book.pdf --text "..." --verify
```

```
before links 151, jumps 139, web 89, bookmarks 78
✓ book-sealed.pdf
after  links 151, jumps 139, web 89, bookmarks 78
✓ links and bookmarks came through unchanged
```

When the counts differ the run exits non-zero, so it can be wired into automation.

### Options

| | |
|---|---|
| `--text` | seal text, for a single file |
| `--csv` | CSV of buyers, one output per row |
| `--template` | how to build the seal text from CSV columns |
| `--filename` | how to name each file of a batch |
| `--out` / `--outdir` | where output goes |
| `--visible` | also seal visibly, as a grey footer line |
| `--verify` | count links and bookmarks before and after |

## Accents

The seal is set in Helvetica, which only speaks WinAnsi — no č, ř, š, ž, ů and the
rest of the Czech set. Accents are therefore stripped from the seal text: "Šárka
Kvašňáková" is stored as "Sarka Kvasnakova". The identifiers that matter for tracing,
the e-mail address and the order number, are plain ASCII anyway.

## The web UI

Same thing with a browser in front of it, for anyone who would rather not open a
terminal. It runs on your machine only: the PDF goes to a local server, gets sealed
there and comes straight back.

```bash
cd web && npm ci && npm run build && cd ..
python server.py
```

Then open http://127.0.0.1:8000. Three steps: drop the PDF, say who the copies are
for -- one person, or a CSV -- and seal. One buyer gives you a PDF, several give you
a zip. Before sealing it shows the seal text exactly as it will be written for every
row, because a name that is wrong across eighty files is expensive to discover later.

Sealing cannot happen in the browser: it needs qpdf, a native binary, and rewriting
it in JavaScript would mean rebuilding the PDF -- the exact mistake this project
exists to avoid. The server listens on the loopback interface only; it seals whatever
it is handed and has nothing resembling authentication, so it has no business being
reachable from a network. Uploads are deleted when it stops.

Angular, no UI framework, tests with `npm test` in `web/`.

## Tests

```bash
python -m unittest discover -s tests -v
```

19 tests, no packages to install. The fixture is a PDF built by hand in
`tests/fixtures.py` carrying exactly what a seal must not destroy: a link
annotation with an in-document jump, and an outline entry. One test asserts the
fixture really has those, so the others cannot pass by asserting that zero links
survived.

Tests needing `pdftotext` or `ghostscript` skip themselves when those are absent,
so the suite still runs with only qpdf installed. CI installs all three and fails
the build if any test skips, so nothing goes unchecked there.

## Before you ship it: the legal side

Writing a buyer's name and e-mail into a file is **processing of personal data**.
Under the GDPR the usual basis is legitimate interest, art. 6(1)(f) — protecting the
work against unauthorised distribution. The regulation does not require the mark to
be visible, but it does require the buyer **to know it is there** (art. 13). So
describe it in your privacy policy: which data goes into the file, why, and on what
basis. For legitimate interest, keep a balancing test on file.

This is a note about what the tool rests on, not legal advice.

## Licence

MIT.

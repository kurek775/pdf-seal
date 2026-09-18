# pdf-seal

Vloží do PDF označení kupujícího, **aniž rozbije odkazy z obsahu, odkazy na web
a záložky**.

*(English version: [README.md](README.md))*

## Proč

Běžné razítkovací nástroje soubor přeženou přes vykreslovací knihovnu, která ho
poskládá znovu ze stránek. Tím zmizí anotace i osnova — tedy odkazy z obsahu,
odkazy na web a záložky. U e-booku s proklikatelným obsahem dostane zákazník
několik set stran, kterými se dá jen rolovat. Přesně kvůli tomu tenhle nástroj
vznikl: zákaznice napsala, proč se jí po kliknutí na kapitolu nic neděje.

Řešení je dokument vůbec neskládat znovu. Nástroj vyrobí jednostránkové PDF, které
nese jen text pečeti, a položí ho přes každou stránku pomocí `qpdf --overlay`.
Ten slepí jen obsahy stránek a na anotace ani osnovu nesáhne.

Změřeno na e-booku o 750 stranách: 151 odkazů, 139 skoků uvnitř dokumentu a 78
záložek zůstalo beze změny a vyrenderovaná stránka vyšla bit po bitu stejně jako
originál.

## Jak pečeť vypadá

Ve výchozím nastavení **nijak**. Text se zapisuje v režimu vykreslování `3 Tr`,
který PDF definuje jako neviditelný: na obrazovce ani v tisku není poznat nic, ale
text v souboru je a dá se přečíst zpátky.

```
pdftotext -f 1 -l 1 sealed/jan@example.com.pdf - | grep '@'
```

Je to tedy **nástroj dohledávací, ne odstrašující** — kdo o pečeti neví, toho
neodradí od sdílení souboru. Přepínač `--visible` přidá drobnou šedou řádku
v patičce, která odrazuje.

Pečeť je na **každé** stránce, takže stopu nese i jednotlivá vyfocená nebo
oříznutá stránka.

## Instalace

Nic se neinstaluje. Stačí Python 3.9+ a `qpdf` v cestě:

```bash
sudo apt install qpdf      # Debian, Ubuntu
brew install qpdf          # macOS
sudo pacman -S qpdf        # Arch
```

`poppler-utils` (`pdfinfo`, `pdftotext`) je volitelný; bez něj se rozměr stránky
přečte přímo z PDF, jen o kousek pomaleji.

## Použití

Jeden soubor:

```bash
./seal.py kniha.pdf --text "Jan Novák | jan@example.com | obj. 71"
```

Dávka, jeden soubor na řádek CSV:

```bash
./seal.py kniha.pdf --csv kupujici.csv \
  --template "{name} | {email} | obj. {order}" \
  --outdir sealed
```

```csv
name,email,order
Jan Novák,jan@example.com,71
Šárka Melicharová,sarka@example.com,42
```

Ve `--template` i ve `--filename` se dá použít kterýkoli sloupec CSV.

Kontrola, že se cestou nic neztratilo:

```bash
./seal.py kniha.pdf --text "..." --verify
```

```
before links 151, jumps 139, web 89, bookmarks 78
✓ kniha-sealed.pdf
after  links 151, jumps 139, web 89, bookmarks 78
✓ links and bookmarks came through unchanged
```

Když se počty liší, skript skončí nenulovým návratovým kódem, takže se dá zařadit
do automatiky.

## Diakritika

Pečeť se sází Helveticou, která umí jen WinAnsi — bez č, ř, š, ž, ů a dalších
českých znaků. Diakritika se proto z textu pečeti odstraní: „Šárka Kvašňáková" se
uloží jako „Sarka Kvasnakova". Údaje rozhodující pro dohledání, tedy e-mail
a číslo objednávky, jsou beztak bez háčků.

## Než to nasadíte: právní stránka

Zapsat jméno a e-mail kupujícího do souboru je **zpracování osobních údajů**.
Obvyklý právní základ je oprávněný zájem podle čl. 6 odst. 1 písm. f) GDPR —
ochrana díla před nedovoleným šířením. Nařízení nežádá, aby značka byla viditelná,
**žádá ale, aby o ní kupující věděl** (čl. 13). Popište ji tedy v zásadách ochrany
osobních údajů: jaké údaje do souboru jdou, proč a na jakém základě. K oprávněnému
zájmu si připravte test proporcionality.

Tohle je poznámka o tom, na čem to celé stojí, ne právní rada.

## Licence

MIT.

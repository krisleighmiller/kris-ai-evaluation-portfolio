# Source and rights provenance

## Corpus construction

Kris created the 45 forty-second masters, held-out decoy sources, 200 transformed clips, labels, and ground truth from the public-domain source media listed below. The deterministic build used seed `20260822`.

The masters and clips in the release asset are byte-for-byte identical to the files used by all three recorded OpenCode trials and to the preserved final generator output. `source-manifest.json` maps each published master and each decoy source to its underlying source identifier. `files.sha256` records every released media file.

The derivative clips include controlled crops, resizes, re-encoding, overlays, color changes, modest speed changes, and removed or replaced audio. Forty clips were generated from held-out material not present in the 45-master library. The model-visible package contains no source-to-clip mapping or ground truth.

## Library of Congress films

These titles appear in the Library of Congress [Public Domain Films from the National Film Registry](https://www.loc.gov/free-to-use/public-domain-films-from-the-national-film-registry/) Free to Use and Reuse set. The preserved source manifest was retrieved on August 22, 2026.

| Identifier | Title | Item page |
| --- | --- | --- |
| `mbrs00063365` | *St. Louis Blues* | [Library of Congress](https://www.loc.gov/item/mbrs00063365/) |
| `mbrs00068306` | *Popeye the Sailor Meets Sindbad the Sailor* | [Library of Congress](https://www.loc.gov/item/mbrs00068306/) |
| `mbrs00009167` | *The House I Live In* | [Library of Congress](https://www.loc.gov/item/mbrs00009167/) |
| `mbrs00021068` | *The Middleton Family at the New York World's Fair* | [Library of Congress](https://www.loc.gov/item/mbrs00021068/) |
| `mbrs00045468` | *Modesta* | [Library of Congress](https://www.loc.gov/item/mbrs00045468/) |
| `mbrs02297907` | *Master Hands* | [Library of Congress](https://www.loc.gov/item/mbrs02297907/) |
| `mbrs00009301` | *The Memphis Belle: A Story of a Flying Fortress* | [Library of Congress](https://www.loc.gov/item/mbrs00009301/) |
| `2017604960` | *All My Babies…A Midwife's Own Story* | [Library of Congress](https://www.loc.gov/item/2017604960/) |
| `mbrs02023537` | *Under Western Stars* | [Library of Congress](https://www.loc.gov/item/mbrs02023537/) |
| `mbrs01836081` | *Duck and Cover* | [Library of Congress](https://www.loc.gov/item/mbrs01836081/) |
| `mbrs00047382` | *The Hitch-Hiker* | [Library of Congress](https://www.loc.gov/item/mbrs00047382/) |
| `mbrs02425201` | *Trance and Dance in Bali* | [Library of Congress](https://www.loc.gov/item/mbrs02425201/) |
| `mbrs00046435` | *Within Our Gates* | [Library of Congress](https://www.loc.gov/item/mbrs00046435/) |
| `00694425` | *San Francisco Earthquake and Fire, April 18, 1906* | [Library of Congress](https://www.loc.gov/item/00694425/) |
| `00694220` | *The Great Train Robbery* | [Library of Congress](https://www.loc.gov/item/00694220/) |
| `96522104` | *Panorama of Machine Co. Aisle, Westinghouse Co. Works* | [Library of Congress](https://www.loc.gov/item/96522104/) |

Thirteen titles contributed windows to the published master set. *The House I Live In*, *Duck and Cover*, and *Panorama of Machine Co. Aisle, Westinghouse Co. Works* contributed absent-film decoy material. Other decoys use held-out windows from films also represented in the master library.

## National Park Service decoy sources

The National Park Service identifies multimedia credited to NPS without a copyright symbol as public domain. See the [NPS disclaimer and ownership statement](https://www.nps.gov/aboutus/disclaimer.htm).

| Source UUID | Title and credit | Catalog record |
| --- | --- | --- |
| `06fbbf73-8e2d-4f3a-baa7-12c8d6eb49fa` | *North Rim Bison in Meadow — B-roll Video*; NPS/L. Cisneros | [NPS record](https://www.nps.gov/media/video/view.htm?id=FB01726E-5E99-40D9-B93E-D98088B24AE9) |
| `7ad46143-7f7e-4569-9bb7-acaeb315820a` | *Duckies Spinning — B-roll Video*; NPS Video: Blum, Wells, and Wang | [NPS record](https://www.nps.gov/media/video/view.htm?id=FEB8EBB3-155D-451F-673A30951264A980) |
| `acf062ae-25e0-473c-9a5f-56871b2fab92` | *Grand Canyon Railway Steam Doubleheader (Legacy Minute)*; NPS/M. Quinn | [NPS record](https://www.nps.gov/media/video/view.htm?id=839C93E6-780A-4EC4-92EB-BA3F28458551) |

These sources contributed held-out material only; they do not appear among the 45 masters.

## LibriVox audio

Silent source windows and some derivative clips use audio from *The Adventures of a Nature Guide* by Enos A. Mills, read by Sue Anderson. The recording is marked with the [Creative Commons Public Domain Mark 1.0](https://creativecommons.org/publicdomain/mark/1.0/).

- [LibriVox catalog record](https://librivox.org/the-adventures-of-a-nature-guide-by-enos-a-mills/)
- [Internet Archive record](https://archive.org/details/natureguide_1704_librivox)
- [LibriVox public-domain statement](https://librivox.org/pages/public-domain/)

LibriVox notes that its recordings are public domain in the United States and advises users elsewhere to check the work's status under local law.

## Superseded source proposal

An early private design note proposed NASA and Prelinger source classes. The preserved final build records show that those sources were not used in the released corpus. They are intentionally absent from this provenance statement.

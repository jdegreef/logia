# Roadmap: what Logia can learn from Sefaria

Logia is a Christian commentary library in the spirit of
[Sefaria](https://www.sefaria.org). It already has Sefaria's basic idea: each
verse has a reader, and the commentaries attached to it are grouped by era,
with each author's dates and tradition. What Sefaria adds on top of that is a
**network**: every text is addressed by a standard reference, links run both
ways, and the whole library is open to other sites and tools. Most of this
roadmap follows from that one idea.

Thirty items in five phases follow, each with what Sefaria does and why
Logia needs it. Phase 1 changes the data model; most later items depend on
it, so it comes first. The rules in `CLAUDE.md` apply to every item: nothing
here permits writing commentary, typing Greek or Hebrew, or marking work
reviewed without a named human reviewer.

Where Logia stands (November 2026): 41 works by 25 commentators on Genesis,
Job, the Psalms, Proverbs, Ecclesiastes, the Song of Songs, Matthew, John,
Romans and Galatians, 39,110 excerpts, a chapter reader with Greek words
and cross-references, and source checking.

## Phase 1: the data model

*Progress:* items 1–3 have a first version (docs/references.md). Works
declare their `divisions` and the Chrysostom and Augustine excerpts carry
their homily or tractate and section. `scripts/find_refs.py` finds 325
Scripture citations in the excerpts. The reader links each one and lists,
under every verse, the excerpts on other verses that cite it. Item 4 has
a first version too: 15 of the Catena's quotations of Chrysostom and
Augustine are traced to their homily or tractate, 9 of them to the section
and 8 to an excerpt Logia holds, and the reader links them both ways. Still
to do: page numbers for the scanned editions, human review of the citations
and quotations, the Catena's quotations of Origen (his Commentary on John
is in the library now, but adding it to `CATENAS` shifts some of the
Chrysostom and Augustine matches, and the Catena also quotes books of his
that have no English translation, so those would need a guard), the
Catena's other Fathers (Hilary, Theophylact, Bede,
Alcuin, Basil) once their works are in the library, and items 6–7.

Item 5 has a first version: Chrysostom's Homilies 2–15 and Augustine's
Tractates 1–3, the ones that hold Logia's excerpts, can be read straight
through at /works/. A gold rule marks each passage Logia sets beside a
verse, and notes link to it and to the Catena where it is quoted. Each
excerpt links to its place in the whole text. Still to do for item 5: the
works arranged by verse (Calvin, Henry and the scanned editions), and the
rest of each work beyond John 1.

Item 6 has a first version: the whole texts can be read by homily or
tractate and by verse (docs/references.md, "Two structures"). The verse
structure comes from the headings and verse marks the CCEL pages print.
Each work page lists both, each whole text labels its verses, and the
reader lists the whole homilies and tractates on every verse. Still to do
for item 6: the Catena's own lectures, and a second structure for the
works arranged by verse (Henry's sections, for example).

1. **A standard reference for every text, not only the Bible.** Sefaria can
   address "Rashi on Genesis 1:1:2" as easily as "Genesis 1:1". Logia has
   verse references (`JHN.1.1`) and entry ids (`calvin.JHN.1.1.1`), but no
   address scheme for the works themselves: homily, section, page. *Why:*
   links, citations, search and an API all need stable addresses, and changing
   them later breaks every link.
2. **Links that run both ways.** Sefaria's core is a graph of links: a text
   points to what it cites, and the cited text shows who cites it. *Why:* this
   is where most of Sefaria's value comes from. An excerpt on John 1:1 would
   also appear on every verse it discusses.
3. **Detect Scripture citations inside excerpts.** Calvin on John 1:1 already
   cites "(1 Timothy 3:16.)". Sefaria finds references like this
   automatically. *Why:* Logia gains thousands of verse links without writing
   a word of commentary. Each detected citation is stored as data, with its
   own review status.
4. **Commentary on commentary.** Sefaria nests layers, such as a
   supercommentary on Rashi. The Catena Aurea is mostly quotations from
   Chrysostom, Augustine and others. *Why:* linking each Catena quotation to
   the full work it came from shows how the tradition was handed on, and lets
   readers check Aquinas's sources.
5. **Present whole works, not only verse-by-verse excerpts.** Sefaria lets you
   read Rashi straight through or verse by verse. *Why:* many patristic works
   are homilies or treatises, and read only as excerpts they lose the
   argument. The rule that a commentator's words are kept whole leans toward
   offering the full text too.
6. **More than one structure for a work.** Sefaria's "alternate structures"
   divide one text by chapter or by weekly reading. Chrysostom is divided both
   by homily and by verse. *Why:* readers navigate by both, and scholars cite
   by homily.
7. **Versions as first-class records.** Sefaria keeps several versions of a
   text, each with its own source, licence and status. Logia records
   `edition` and `rights` for the whole work. *Why:* Logia will soon have
   Latin or Greek originals beside English translations, plus
   `library/translations/<lang>/`, and each version needs its own provenance
   and review status.

## Phase 2: the reader

8. **Show the original beside the translation.** Sefaria's Hebrew and English
   side by side is its best-known screen. *Why:* Augustine's Latin beside the
   1800s English lets readers check the translation. Originals are copied from
   public-domain scans, never typed.
9. **A connections panel with filters.** Sefaria's side panel groups
   commentary, quotations, topics and sheets, and filters by category. *Why:*
   Logia's tabs are the start of this. Filters by tradition (Catholic,
   Orthodox, Protestant), era and language let readers see a fair spread of
   voices without Logia choosing for them.
10. **Show how much commentary each verse has.** Sefaria shows link counts.
    *Why:* readers can spot where the tradition has said most, and
    contributors can see what to add next.
11. **Word lookups.** Sefaria opens Jastrow or BDB when you click a word.
    Logia already has MACULA Greek data. Adding a public-domain lexicon
    (Thayer 1889, Liddell–Scott 1889, Brown–Driver–Briggs 1906) completes
    this. *Why:* readers want definitions as well as glosses, and those
    lexicons are in the public domain. MACULA's `ln` and `domain` fields stay
    out.
12. **A permanent link for every excerpt, and a citation format.** Sefaria's
    URLs are the reference itself (`/Genesis.1.1`), with a "Cite" button.
    *Why:* this makes Logia citable by students, pastors and Wikipedia, which
    is the main way an open library spreads.
13. **A "report an error" button on each excerpt.** *Why:* each report becomes
    a candidate pair in `library/corrections/`, so readers become proofreaders
    and the corrections stay public.
14. **Visible provenance on every excerpt.** Sefaria shows the version and
    source for every text. Logia goes further, with a source checker and
    corrections kept as data. *Why:* showing readers the scan page, the
    corrections applied, and "ai_draft, awaiting review" answers "can I trust
    this?" It is a real advantage over Sefaria, so make it visible.

## Phase 3: finding things

15. **A library catalogue page.** Sefaria's table of contents is organised by
    category, era and genre. *Why:* as Logia grows past John 1, readers need
    to see what is there and what is missing.
16. **Author pages and a timeline.** Sefaria has a page for each author, with
    dates, place, era and works, and a timeline of the tradition. *Why:* Logia
    already records `author_dates`, `era` and `tradition`. A page per author
    is cheap to build and gives readers context.
17. **Search with facets.** Sefaria searches the whole library and narrows by
    category. *Why:* "what did the Fathers say about the Word?" can't be
    answered by browsing verses. The site is static, so a client-side index
    built at build time fits it.
18. **Topic pages built from links.** Sefaria gathers sources on a topic.
    *Why:* topics such as the Incarnation, baptism or the Eucharist are where
    Christians look across traditions. Each topic is a curated list of
    excerpts from every tradition, with no editorial argument added.

## Phase 4: openness

19. **A public read-only API.** Sefaria's API makes it the backend for many
    apps. *Why:* Logia's data is CC0. A static JSON API generated by
    `scripts/build_site.py` costs nothing to host and invites others to build
    on it.
20. **Versioned bulk data exports.** Sefaria publishes its whole library on
    GitHub. *Why:* this repository already does that in part; tagged releases
    with documented schemas make it something people can depend on.
21. **A script other sites can embed to link citations.** Sefaria's Linker
    turns "Gen 1:1" on any website into a hover preview. *Why:* church
    websites, blogs and seminary pages each send readers to Logia and spread
    its reference scheme. This is the strongest growth lever on the list.
22. **Open, documented editorial rules.** Sefaria publishes how texts get in.
    *Why:* `docs/adding-a-work.md` and the rules in `CLAUDE.md` already
    exist. Publishing them on the site, with the rights basis shown for each
    version, lets anyone audit the library.

## Phase 5: community and learning

23. **Source sheets.** Users build handouts from library passages plus their
    own notes; this is arguably Sefaria's most used feature. *Why:* teachers,
    preachers and Bible-study leaders would use it every week. User notes are
    kept clearly apart from the library, marked as the user's own and never
    shown as commentary.
24. **Daily readings from the lectionaries.** Sefaria's Daf Yomi and weekly
    Torah portion bring people back every day. Logia's version is the Revised
    Common Lectionary, the Roman lectionary, the Book of Common Prayer daily
    office and the Orthodox lectionary. *Why:* repeat visits come from
    schedules, and offering all four calendars keeps Logia neutral.
25. **A volunteer pipeline for review and translation.** Sefaria uses
    volunteers and community translations. *Why:* nothing leaves `ai_draft`
    without a named human reviewer, so recruiting reviewers is the
    bottleneck. Logia needs a review queue, credit for reviewers, and
    native-speaker review for each language.
26. **Parallel interface languages.** Sefaria is bilingual throughout. *Why:*
    "English first, then many languages" needs translatable interface text
    from the start, not added later.
27. **Accounts as an option, not a requirement.** Sefaria offers saved texts,
    history and notes. *Why:* it helps returning readers. Everything stays
    readable without logging in.
28. **Mobile and offline use.** Sefaria's apps work offline. *Why:* a static
    site can become an installable web app cheaply, which matters for readers
    with poor connections.
29. **Materials for educators.** Sefaria runs an educators programme. *Why:*
    seminaries and church schools need ready-made, citable sources, and they
    are where long-term contributors come from.
30. **Nonprofit transparency.** Sefaria publishes who funds it and how it is
    governed. *Why:* Logia promises to take no side between traditions, and
    being open about who funds and governs it is what makes that promise
    believable.

## What not to copy

- **Licensed modern translations.** Sefaria includes some (JPS, Koren).
  Logia's rule of 1930 or earlier is simpler and keeps the library fully
  redistributable.
- **User content mixed into the library.** If sheets and notes appear beside
  commentary, readers can't tell them apart. The line between "copied from
  the source" and "written by a user" stays visible everywhere.

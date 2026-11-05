# Project page preview

Static, build-free English project page and research article. Open `index.html`
directly, or serve this directory:

```bash
python -m http.server 8080 --bind 127.0.0.1 --directory docs
```

Visit `http://127.0.0.1:8080/`. When using a remote machine, forward port 8080.
No JavaScript, external fonts, analytics, or remotely loaded media are required.

- `index.html`: project overview, task examples, tracks, and baseline results.
- `story.html`: draft research article with chapter navigation, a conceptual
  timing diagram, task stories, and the first-baseline results.
- `styles.css`: shared responsive styles.
- `assets/`: original SVG illustrations, not game screenshots or JoyTwin assets.
- `data/`: aggregate baseline CSV and provenance summary, not full trajectories.

The layout takes inspiration from the owner-provided JoyTwin project references;
the content, illustrations, and styling are newly authored for LiveQuestBench.
No JoyTwin scores, logos, author affiliations, or claims are reused.

## Publishing

GitHub Pages uses the `main` branch's `/docs` directory. The project URL is
https://victoryxl.github.io/LiveQuestBench/ and the article is at
https://victoryxl.github.io/LiveQuestBench/story.html.
The `.nojekyll` file keeps publishing limited to serving the static files.

Public website publication is separate from a formal benchmark release. Keep the
development-preview labels until independent installation qualification, licensing
review, and evidence packaging are complete. Review any additional gameplay media
before publication; raw episode archives and local preview tooling do not belong
in this directory.
